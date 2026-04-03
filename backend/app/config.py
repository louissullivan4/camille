from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://camille:localdev@localhost:5432/camille"
    ANTHROPIC_API_KEY: str = ""
    API_KEY_SECRET: str = "change-me-in-production"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    LLM_EXTRACTION_MODEL: str = "claude-sonnet-4-6"
    LLM_CLASSIFICATION_MODEL: str = "claude-opus-4-6"
    LLM_REPORT_MODEL: str = "claude-opus-4-6"

settings = Settings()
