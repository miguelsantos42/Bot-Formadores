from pathlib import Path
import sqlite3

from bot.db import (
    get_search_run,
    get_search_run_debug,
    init_db,
    list_search_run_candidates,
    list_search_run_queries,
    list_search_runs,
    save_search_run,
)
from bot.messages import generate_outreach_messages
from bot.models import SearchRun, TrainingRequest
from bot.scoring import score_candidates
from bot.search import MockSearchProvider, generate_search_queries


def make_search_run() -> SearchRun:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Porto",
    )

    provider = MockSearchProvider()
    candidates = provider.search(request)
    scored_candidates = score_candidates(request, candidates)

    results = [
        {
            "candidato_classificado": scored_candidate,
            "mensagens": generate_outreach_messages(request, scored_candidate),
        }
        for scored_candidate in scored_candidates
    ]

    return SearchRun(
        pedido=request,
        queries=generate_search_queries(request),
        resultados=results,
    )


def test_init_db_creates_database_file(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"

    init_db(database_path)

    assert database_path.exists()


def test_init_db_creates_observability_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"

    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

    table_names = {row[0] for row in rows}
    assert "search_runs" in table_names
    assert "search_queries" in table_names
    assert "search_candidates" in table_names


def test_save_search_run_returns_id(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    assert run_id


def test_list_search_runs_returns_saved_run(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    save_search_run(database_path, search_run)

    runs = list_search_runs(database_path)

    assert len(runs) == 1
    assert runs[0]["payload"]["pedido"]["tema_formacao"] == "Python"


def test_list_search_run_queries_returns_query_order(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    queries = list_search_run_queries(database_path, run_id)

    assert len(queries) == len(search_run.queries)
    assert queries[0]["query_order"] == 1
    assert queries[0]["query_text"] == search_run.queries[0]


def test_list_search_run_candidates_returns_debug_payload(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    candidates = list_search_run_candidates(database_path, run_id)
    first_candidate = candidates[0]

    assert len(candidates) == len(search_run.resultados)
    assert first_candidate["candidate_name"]
    assert first_candidate["matched_query"]
    assert first_candidate["source_domain"]
    assert first_candidate["recommended_channel"] in {"email", "linkedin", "formulario"}
    assert first_candidate["score_total"] == first_candidate["score"]["score_total"]
    assert "fit_tematico" in first_candidate["score"]
    assert "contactabilidade" in first_candidate["score"]
    assert first_candidate["candidate"]["nome"] == first_candidate["candidate_name"]
    assert first_candidate["raw_result"]["matched_query"] == first_candidate["matched_query"]
    assert first_candidate["created_at"]


def test_search_candidate_debug_keeps_all_score_components(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    first_candidate = list_search_run_candidates(database_path, run_id)[0]

    assert set(first_candidate["score"]) >= {
        "fit_tematico",
        "fit_funcional",
        "experiencia_formacao",
        "localizacao_score",
        "contactabilidade",
        "credibilidade_publica",
        "score_total",
        "motivo",
    }


def test_candidate_debug_payload_links_to_matching_query(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    queries = list_search_run_queries(database_path, run_id)
    candidates = list_search_run_candidates(database_path, run_id)
    query_ids = {query["id"] for query in queries}

    assert candidates[0]["query_id"] in query_ids


def test_candidate_debug_payload_query_text_matches_stored_query(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    queries = list_search_run_queries(database_path, run_id)
    candidates = list_search_run_candidates(database_path, run_id)
    queries_by_id = {query["id"]: query for query in queries}

    for candidate in candidates:
        assert candidate["query_id"] is not None
        stored_query = queries_by_id[candidate["query_id"]]
        assert stored_query["query_text"] == candidate["matched_query"]


def test_get_search_run_returns_saved_run(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    saved_run = get_search_run(database_path, run_id)

    assert saved_run is not None
    assert saved_run["id"] == run_id
    assert saved_run["payload"]["pedido"]["area_interna"] == "Tecnologia"


def test_get_search_run_debug_returns_run_queries_and_candidates(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    debug_run = get_search_run_debug(database_path, run_id)

    assert debug_run is not None
    assert debug_run["id"] == run_id
    assert debug_run["payload"]["pedido"]["tema_formacao"] == "Python"
    assert debug_run["queries"]
    assert debug_run["candidates"]
    assert debug_run["candidates"][0]["score_total"] >= 0


def test_get_search_run_returns_none_for_unknown_id(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"

    saved_run = get_search_run(database_path, "unknown-id")

    assert saved_run is None


def test_get_search_run_debug_returns_none_for_unknown_id(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"

    debug_run = get_search_run_debug(database_path, "unknown-id")

    assert debug_run is None
