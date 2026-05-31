from typing import Any
import httpx
from app.config import settings
from app.ollama import create_embedding
from app.schemas import RetrievedChunk
from app.chroma_db import get_chroma_collection
from app.db import pool

def generate_hyde_text(question: str) -> str:
    """Generate a lightning-fast hypothetical document paragraph with thinking disabled."""
    prompt = f"Write a single brief phrase describing the following concept:\nConcept: {question}\nDefinition:"
    
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_chat_model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {
                    "num_predict": settings.hyde_max_tokens,
                    "temperature": settings.hyde_temperature,
                    "think": False,
                    "num_ctx": 512,  # Reduce memory/parsing context window for speed
                },
            },
            timeout=25.0,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        return answer if answer else question
    except Exception as err:
        print(f"[HyDE Speed Warning] Failed, falling back to original query: {err}")
        return question

def retrieve_lexical_chunks(question: str, user_id: str, limit: int = 50) -> list[dict]:
    """Retrieve top text chunks from PostgreSQL using Full-Text Search (FTS)."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content, metadata 
                FROM documents, websearch_to_tsquery('english', %s) query
                WHERE user_id = %s::uuid 
                  AND to_tsvector('english', content) @@ query
                LIMIT %s;
                """,
                (question, user_id, limit)
            )
            rows = cur.fetchall()
            
    results = []
    for row in rows:
        results.append({
            "content": row[0],
            "metadata": row[1] or {}
        })
    return results

def reciprocal_rank_fusion(semantic_list: list[RetrievedChunk], lexical_list: list[dict], k: int = 60) -> list[RetrievedChunk]:
    """Fuse Semantic and Lexical results using Reciprocal Rank Fusion (RRF)."""
    rrf_scores = {}
    chunk_map = {}

    def get_chunk_key(text: str) -> int:
        return hash(text.strip())

    # 1. Score Semantic Chunks
    for rank, chunk in enumerate(semantic_list, start=1):
        key = get_chunk_key(chunk.content)
        chunk_map[key] = chunk
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k + rank))

    # 2. Score Lexical Chunks
    for rank, doc in enumerate(lexical_list, start=1):
        content = doc["content"]
        key = get_chunk_key(content)
        if key not in chunk_map:
            # Reconstruct RetrievedChunk shell
            int_id = abs(hash(content)) % 1000000000
            chunk_map[key] = RetrievedChunk(
                id=int_id,
                content=content,
                metadata=doc["metadata"],
                similarity=0.0
            )
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k + rank))

    # Sort chunks by fused RRF score
    sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    fused_chunks = []
    max_score = 2.0 / (k + 1)  # Max score if item is Rank 1 in both lists
    
    for key in sorted_keys:
        chunk = chunk_map[key]
        raw_score = rrf_scores[key]
        normalized_score = raw_score / max_score
        chunk.similarity = normalized_score
        fused_chunks.append(chunk)
        
    return fused_chunks

def retrieve_relevant_chunks(
    question: str, 
    sessionId: str | None = None, 
    limit: int | None = None, 
    user_id: str | None = None, 
    hyde: bool = False, 
    hybrid: bool = True,
    priority_docs: list[str] = None
) -> list[RetrievedChunk]:
    if priority_docs is None:
        priority_docs = []
        
    hyde_text = None
    if hyde:
        hyde_text = generate_hyde_text(question)
        search_text = f"Query: {question}\nTarget Context: {hyde_text}"
    else:
        search_text = question
        
    # Always fetch 50 semantic candidates for RRF fusion
    query_limit = limit if limit is not None else settings.retrieval_limit
    embedding = create_embedding(search_text)
    collection = get_chroma_collection()

    where_filter = None
    if user_id:
        where_filter = {"user_id": str(user_id)}

    try:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=50,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        print(f"ChromaDB Query Error: {e}")
        results = None

    semantic_chunks = []
    if results and results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            chunk_id = results["ids"][0][i]
            content = results["documents"][0][i]
            metadata = dict(results["metadatas"][0][i]) if results["metadatas"][0][i] is not None else {}
            if hyde:
                metadata["hyde_query"] = search_text
            distance = results["distances"][0][i]
            base_similarity = 1.0 - distance

            chunk_session_id = metadata.get("sessionId")
            # Skip chunks explicitly belonging to OTHER sessions
            if chunk_session_id and chunk_session_id != "null" and chunk_session_id != sessionId:
                continue

            int_id = abs(hash(chunk_id)) % 1000000000
            semantic_chunks.append(
                RetrievedChunk(
                    id=int_id,
                    content=content,
                    metadata=metadata,
                    similarity=base_similarity
                )
            )

    # 2. Get Lexical Chunks if Hybrid is Enabled
    if hybrid and user_id:
        try:
            lexical_raw = retrieve_lexical_chunks(question, str(user_id), limit=50)
            lexical_chunks = []
            for doc in lexical_raw:
                metadata = doc["metadata"] or {}
                chunk_session_id = metadata.get("sessionId")
                if chunk_session_id and chunk_session_id != "null" and chunk_session_id != sessionId:
                    continue
                lexical_chunks.append(doc)
            
            # Fuse semantic and lexical lists using RRF
            chunks = reciprocal_rank_fusion(semantic_chunks, lexical_chunks)
        except Exception as err:
            print(f"[Hybrid Fallback] Lexical search failed: {err}")
            chunks = semantic_chunks
    else:
        chunks = semantic_chunks

    # 3. Apply custom similarity boosting on final fused list
    for chunk in chunks:
        chunk_session_id = chunk.metadata.get("sessionId")
        
        # Session Isolation Boost (+0.03)
        if chunk_session_id == sessionId:
            chunk.similarity += 0.03

        # Source/Filename Match Boost (+0.12)
        source = chunk.metadata.get("source", "")
        if source:
            if source in priority_docs:
                if chunk_session_id == sessionId:
                    chunk.similarity += 0.20
                else:
                    chunk.similarity += 0.30
                
            source_lower = source.lower()
            q_lower = question.lower()
            clean_source_name = source_lower.replace(".pdf", "").replace(".txt", "").replace(".docx", "")

            if clean_source_name in q_lower or source_lower in q_lower:
                chunk.similarity += 0.12

    # Sort chunks by final boosted similarity
    chunks.sort(key=lambda x: x.similarity, reverse=True)

    return chunks[:query_limit]
