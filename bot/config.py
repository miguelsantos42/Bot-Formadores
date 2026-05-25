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
    public_search_fallback_to_mock: bool = True


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        database_path=Path(os.getenv("DATABASE_PATH", "formadores_bot.sqlite3")),
        search_provider=os.getenv("SEARCH_PROVIDER", "public_web"),
        public_search_url=os.getenv(
            "PUBLIC_SEARCH_URL",
            "https://www.bing.com/search",
        ),
        public_search_timeout_seconds=int(os.getenv("PUBLIC_SEARCH_TIMEOUT_SECONDS", "10")),
        public_search_max_results=int(os.getenv("PUBLIC_SEARCH_MAX_RESULTS", "10")),
        public_search_fallback_to_mock=parse_bool(
            os.getenv("PUBLIC_SEARCH_FALLBACK_TO_MOCK", "true")
        ),
    )


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
