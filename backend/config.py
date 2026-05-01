from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
    )

    ollama_model: str = "llama3.2"
    ollama_host: str = "http://localhost:11434"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./jobhunter.db"


settings = Settings()
