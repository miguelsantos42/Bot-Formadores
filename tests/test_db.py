from pathlib import Path

from bot.db import get_search_run, init_db, list_search_runs, save_search_run
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


def test_get_search_run_returns_saved_run(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    search_run = make_search_run()

    run_id = save_search_run(database_path, search_run)

    saved_run = get_search_run(database_path, run_id)

    assert saved_run is not None
    assert saved_run["id"] == run_id
    assert saved_run["payload"]["pedido"]["area_interna"] == "Tecnologia"


def test_get_search_run_returns_none_for_unknown_id(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"

    saved_run = get_search_run(database_path, "unknown-id")

    assert saved_run is None
