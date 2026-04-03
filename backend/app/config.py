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
    EXTRACTION_CONCURRENCY: int = 3  # max parallel LLM calls; lower to avoid rate limits
    # AWS / S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "camille-documents-local"
    # External signals
    NEWS_API_KEY: str = ""
    PACER_API_KEY: str = ""
    # Observability
    SENTRY_DSN: str = ""

settings = Settings()
