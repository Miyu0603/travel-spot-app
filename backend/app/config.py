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

    model_config = {"env_file": ".env"}


settings = Settings()
