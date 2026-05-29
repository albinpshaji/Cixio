from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:albin@localhost:5433/rag_db"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3.5:4b"
    ollama_embed_model: str = "nomic-embed-text"
    retrieval_limit: int = 5
    generation_timeout_ms: int = 60000
    generation_max_tokens: int = 384
    embedding_dimensions: int = 768
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
