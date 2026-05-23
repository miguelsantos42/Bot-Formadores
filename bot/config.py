from dataclasses import dataclass
from pathlib import Path

import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_path: Path


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        database_path=Path(os.getenv("DATABASE_PATH", "formadores_bot.sqlite3")),
    )
