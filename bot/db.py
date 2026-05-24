import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bot.models import SearchRun


def init_db(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )


def save_search_run(database_path: Path, search_run: SearchRun) -> str:
    init_db(database_path)

    run_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    payload_json = search_run.model_dump_json()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO search_runs (id, created_at, payload_json)
            VALUES (?, ?, ?)
            """,
            (run_id, created_at, payload_json),
        )

    return run_id


def list_search_runs(database_path: Path) -> list[dict]:
    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, payload_json
            FROM search_runs
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "created_at": row[1],
            "payload": json.loads(row[2]),
        }
        for row in rows
    ]


def get_search_run(database_path: Path, run_id: str) -> dict | None:
    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, created_at, payload_json
            FROM search_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "created_at": row[1],
        "payload": json.loads(row[2]),
    }
