from app.schemas import RetrievedChunk


def build_rag_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context_parts: list[str] = []

    for index, chunk in enumerate(chunks):
        metadata = chunk.metadata or {}
        source = metadata.get("source", "pasted text")
        chunk_index = metadata.get("chunkIndex", chunk.id)
        page = metadata.get("page")
        location = f"page {page}, chunk {chunk_index}" if page else f"chunk {chunk_index}"
        context_parts.append(
            f"Source {index + 1} ({source}, {location}, "
            f"similarity {chunk.similarity:.3f}):\n{chunk.content}"
        )

    context = "\n\n---\n\n".join(context_parts)

    return f"""You are a careful document question-answering assistant.

Use only the provided context to answer the user's question.
If the context does not contain enough information, say that the document context does not provide enough information.
Be concise, specific, and cite the source numbers you used.

Context:
{context}

Question:
{question}

Answer:"""
