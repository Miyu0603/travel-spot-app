from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./travel_spots.db"

    # Apify
    apify_api_token: str = ""

    # OpenAI (for LLM extraction & Whisper)
    openai_api_key: str = ""

    # Google Maps / Places
    google_maps_api_key: str = ""

    # Shared password for the API. Empty means auth is disabled (local dev).
    api_secret: str = ""

    # Comma-separated list of origins allowed to call the API
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Caps on the AI extraction endpoints, which cost money per call.
    # Set either to 0 to disable that limit.
    rate_limit_per_ip_hourly: int = 10
    rate_limit_global_daily: int = 50

    # Every key present in .env must be declared above: pydantic-settings rejects
    # unknown keys, and the resulting error prints the offending value in plain text.
    model_config = {"env_file": ".env"}


settings = Settings()
