from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:albin@localhost:5433/rag_db"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3.5:4b"
    ollama_embed_model: str = "nomic-embed-text"
    retrieval_limit: int = 8
    ollama_num_ctx: int = 8192
    generation_timeout_ms: int = 300000
    generation_max_tokens: int = 4096
    embedding_dimensions: int = 768
    cors_origins: list[str] = ["http://localhost:3000"]
    jwt_secret_key: str = "smarthub-dev-secret-change-in-production-2026"
    jwt_access_expiry_minutes: int = 30
    jwt_refresh_expiry_days: int = 7
    hyde_max_tokens: int = 35
    hyde_temperature: float = 0.1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
