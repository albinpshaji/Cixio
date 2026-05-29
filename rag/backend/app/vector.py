def to_pg_vector(embedding: list[float]) -> str:
    return f"[{','.join(str(value) for value in embedding)}]"
