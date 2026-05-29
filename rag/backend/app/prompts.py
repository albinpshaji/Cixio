from app.schemas import RetrievedChunk


def build_rag_prompt(question: str, chunks: list[RetrievedChunk], think_level: str = "medium") -> str:
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
