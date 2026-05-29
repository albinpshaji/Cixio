import httpx

from app.config import settings


def create_embedding(input_text: str) -> list[float]:
    response = httpx.post(
        f"{settings.ollama_base_url}/api/embeddings",
        json={
            "model": settings.ollama_embed_model,
            "prompt": input_text,
        },
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    embedding = data.get("embedding")

    if embedding is None:
        embeddings = data.get("embeddings")
        if embeddings:
            embedding = embeddings[0]

    if not embedding or len(embedding) != settings.embedding_dimensions:
        received = len(embedding) if embedding else 0
        raise ValueError(
            f"Expected a {settings.embedding_dimensions}-dimensional embedding, "
            f"received {received}"
        )

    return embedding


def generate_answer(prompt: str) -> str:
    timeout_seconds = settings.generation_timeout_ms / 1000
    response = httpx.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.ollama_chat_model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "num_predict": settings.generation_max_tokens,
                "temperature": 0.2,
            },
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    answer = response.json().get("response", "").strip()

    if not answer:
        raise ValueError("Ollama returned an empty answer.")

    return answer
