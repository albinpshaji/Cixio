from typing import Any
from app.config import settings
from app.ollama import create_embedding
from app.schemas import RetrievedChunk
from app.chroma_db import get_chroma_collection

def retrieve_relevant_chunks(question: str, sessionId: str | None = None, limit: int | None = None, user_id: str | None = None) -> list[RetrievedChunk]:
    embedding = create_embedding(question)
    query_limit = limit if limit is not None else settings.retrieval_limit

    collection = get_chroma_collection()

    where_filter = {}
    if user_id:
        where_filter["user_id"] = str(user_id)

    # Query ChromaDB for top 50 matches for the user
    # We fetch more than the limit so we can apply python-side boosting and sorting
    try:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=50,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        print(f"ChromaDB Query Error: {e}")
        return []

    if not results or not results["ids"] or not results["ids"][0]:
        return []

    chunks = []
    for i in range(len(results["ids"][0])):
        chunk_id = results["ids"][0][i]
        content = results["documents"][0][i]
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        # ChromaDB with cosine space returns distance = 1 - cosine_similarity
        # So base_similarity = 1 - distance
        base_similarity = 1.0 - distance

        chunk_session_id = metadata.get("sessionId")

        # Skip chunks explicitly belonging to OTHER sessions
        if chunk_session_id and chunk_session_id != "null" and chunk_session_id != sessionId:
            continue

        similarity = base_similarity

        # Session Isolation Boost (+0.03)
        if chunk_session_id == sessionId:
            similarity += 0.03

        # Source/Filename Match Boost (+0.12)
        source = metadata.get("source", "")
        if source:
            source_lower = source.lower()
            q_lower = question.lower()
            clean_source = source_lower.replace(".pdf", "").replace(".txt", "").replace(".docx", "")

            if clean_source in q_lower or source_lower in q_lower:
                similarity += 0.12

        # Convert chunk_id (UUID string) to int if needed by schema, but we can pass hash or change schema.
        # We will use hash(chunk_id) mod 1e9 to fit into an integer.
        int_id = abs(hash(chunk_id)) % 1000000000

        chunks.append(
            RetrievedChunk(
                id=int_id,
                content=content,
                metadata=metadata,
                similarity=similarity,
            )
        )

    # Sort chunks by boosted similarity
    chunks.sort(key=lambda x: x.similarity, reverse=True)

    return chunks[:query_limit]
