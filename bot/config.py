from dataclasses import dataclass
from pathlib import Path

import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_path: Path
    search_provider: str
    public_search_url: str
    public_search_timeout_seconds: int
    public_search_max_results: int
    public_search_fallback_to_mock: bool = False
    brave_search_api_key: str | None = None
    brave_search_url: str = "https://api.search.brave.com/res/v1/web/search"


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        database_path=Path(os.getenv("DATABASE_PATH", "formadores_bot.sqlite3")),
        search_provider=os.getenv("SEARCH_PROVIDER", "brave_search"),
        brave_search_api_key=empty_to_none(os.getenv("BRAVE_SEARCH_API_KEY")),
        brave_search_url=os.getenv(
            "BRAVE_SEARCH_URL",
            "https://api.search.brave.com/res/v1/web/search",
        ),
        public_search_url=os.getenv(
            "PUBLIC_SEARCH_URL",
            "https://www.bing.com/search",
        ),
        public_search_timeout_seconds=int(os.getenv("PUBLIC_SEARCH_TIMEOUT_SECONDS", "10")),
        public_search_max_results=int(os.getenv("PUBLIC_SEARCH_MAX_RESULTS", "25")),
        public_search_fallback_to_mock=parse_bool(
            os.getenv("PUBLIC_SEARCH_FALLBACK_TO_MOCK", "false")
        ),
    )


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None

    clean_value = value.strip()
    return clean_value or None
