import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bot.models import Candidate, CandidateResult, SearchRun


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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_queries (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                query_order INTEGER NOT NULL,
                query_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES search_runs (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_candidates (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                query_id TEXT,
                candidate_order INTEGER NOT NULL,
                candidate_name TEXT NOT NULL,
                matched_query TEXT,
                source_domain TEXT,
                profile_type TEXT,
                recommended_channel TEXT NOT NULL,
                score_total INTEGER NOT NULL,
                score_json TEXT NOT NULL,
                candidate_json TEXT NOT NULL,
                raw_result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES search_runs (id),
                FOREIGN KEY (query_id) REFERENCES search_queries (id)
            )
            """
        )


def save_search_run(database_path: Path, search_run: SearchRun) -> str:
    init_db(database_path)

    run_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    payload_json = search_run.model_dump_json()
    query_ids_by_text = {
        query: str(uuid4())
        for query in search_run.queries
    }

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO search_runs (id, created_at, payload_json)
            VALUES (?, ?, ?)
            """,
            (run_id, created_at, payload_json),
        )
        connection.executemany(
            """
            INSERT INTO search_queries (id, run_id, query_order, query_text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    query_ids_by_text[query],
                    run_id,
                    index,
                    query,
                    created_at,
                )
                for index, query in enumerate(search_run.queries, start=1)
            ],
        )
        connection.executemany(
            """
            INSERT INTO search_candidates (
                id,
                run_id,
                query_id,
                candidate_order,
                candidate_name,
                matched_query,
                source_domain,
                profile_type,
                recommended_channel,
                score_total,
                score_json,
                candidate_json,
                raw_result_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                build_candidate_observability_row(
                    run_id=run_id,
                    query_ids_by_text=query_ids_by_text,
                    candidate_order=index,
                    created_at=created_at,
                    result=result,
                )
                for index, result in enumerate(search_run.resultados, start=1)
            ],
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


def get_search_run_debug(database_path: Path, run_id: str) -> dict | None:
    run = get_search_run(database_path, run_id)
    if run is None:
        return None

    return {
        **run,
        "queries": list_search_run_queries(database_path, run_id),
        "candidates": list_search_run_candidates(database_path, run_id),
    }


def list_search_run_queries(database_path: Path, run_id: str) -> list[dict]:
    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, query_order, query_text, created_at
            FROM search_queries
            WHERE run_id = ?
            ORDER BY query_order ASC
            """,
            (run_id,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "query_order": row[1],
            "query_text": row[2],
            "created_at": row[3],
        }
        for row in rows
    ]


def list_search_run_candidates(database_path: Path, run_id: str) -> list[dict]:
    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                query_id,
                candidate_order,
                candidate_name,
                matched_query,
                source_domain,
                profile_type,
                recommended_channel,
                score_total,
                score_json,
                candidate_json,
                raw_result_json,
                created_at
            FROM search_candidates
            WHERE run_id = ?
            ORDER BY candidate_order ASC
            """,
            (run_id,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "query_id": row[1],
            "candidate_order": row[2],
            "candidate_name": row[3],
            "matched_query": row[4],
            "source_domain": row[5],
            "profile_type": row[6],
            "recommended_channel": row[7],
            "score_total": row[8],
            "score": json.loads(row[9]),
            "candidate": json.loads(row[10]),
            "raw_result": json.loads(row[11]),
            "created_at": row[12],
        }
        for row in rows
    ]


def build_candidate_observability_row(
    run_id: str,
    query_ids_by_text: dict[str, str],
    candidate_order: int,
    created_at: str,
    result: CandidateResult,
) -> tuple:
    scored_candidate = result.candidato_classificado
    candidate = scored_candidate.candidato
    score = scored_candidate.score
    matched_query = candidate.matched_query

    return (
        str(uuid4()),
        run_id,
        query_ids_by_text.get(matched_query) if matched_query else None,
        candidate_order,
        candidate.nome,
        matched_query,
        candidate.source_domain,
        candidate.profile_type.value,
        scored_candidate.canal_recomendado.value,
        score.score_total,
        score.model_dump_json(),
        candidate.model_dump_json(),
        json.dumps(build_raw_result_payload(candidate), ensure_ascii=False),
        created_at,
    )


def build_raw_result_payload(candidate: Candidate) -> dict:
    return {
        "matched_query": candidate.matched_query,
        "search_rank": candidate.search_rank,
        "source_domain": candidate.source_domain,
        "result_title_raw": candidate.result_title_raw,
        "snippet_raw": candidate.snippet_raw,
        "excerto": candidate.excerto,
        "links": [
            {
                "label": link.label,
                "url": str(link.url),
            }
            for link in candidate.links
        ],
    }
