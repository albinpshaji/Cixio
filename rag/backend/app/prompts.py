from app.schemas import RetrievedChunk


def build_rag_prompt(question: str, chunks: list[RetrievedChunk], think_level: str = "medium") -> str:
    # Group chunks by their source document
    grouped_chunks: dict[str, list[tuple[int, RetrievedChunk]]] = {}
    for index, chunk in enumerate(chunks):
        metadata = chunk.metadata or {}
        source = metadata.get("source", "pasted text")
        if source not in grouped_chunks:
            grouped_chunks[source] = []
        grouped_chunks[source].append((index + 1, chunk))

    context_parts: list[str] = []
    for source, source_chunks in grouped_chunks.items():
        chunk_texts: list[str] = []
        for src_num, chunk in source_chunks:
            metadata = chunk.metadata or {}
            chunk_index = metadata.get("chunkIndex", chunk.id)
            page = metadata.get("page")
            location = f"page {page}, chunk {chunk_index}" if page else f"chunk {chunk_index}"
            chunk_texts.append(
                f"[Source {src_num} ({location}, similarity {chunk.similarity:.3f})]:\n{chunk.content}"
            )
        
        chunks_joined = "\n\n".join(chunk_texts)
        context_parts.append(
            f"========================================\n"
            f"📄 DOCUMENT REFERENCE: {source.upper()}\n"
            f"========================================\n"
            f"{chunks_joined}"
        )

    context = "\n\n".join(context_parts)

    reasoning_instructions = ""
    if think_level == "low":
        reasoning_instructions = "Reason about the question in one short sentence, then present a fully detailed, comprehensive answer."
    elif think_level == "medium":
        reasoning_instructions = "Provide a concise, structured step-by-step thinking process before answering."
    elif think_level == "max":
        reasoning_instructions = "Reason deeply and systematically, analyzing the context from multiple perspectives before answering."

    instructions = [
        "You are a careful document question-answering assistant.",
        "Use only the provided context to answer the user's question.",
        "Do NOT mix, combine, or cross-contaminate information between different documents.",
        "Keep each document's details strictly isolated and separate.",
        "If the context does not contain enough information, say that the document context does not provide enough information.",
        "Be concise, specific, and cite the source numbers you used.",
    ]
    if reasoning_instructions:
        instructions.append(reasoning_instructions)

    instructions_text = "\n".join(instructions)

    return f"""{instructions_text}

Context:
{context}

Question:
{question}

Answer:"""
