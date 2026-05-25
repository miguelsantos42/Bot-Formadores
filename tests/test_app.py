import csv
import json
from io import StringIO

from app import (
    CURATION_STATUS_DEFAULT,
    EXPORT_COLUMNS,
    build_export_filename,
    build_export_rows,
    build_score_components,
    build_search_run,
    candidate_key,
    count_approved_results,
    export_rows_to_csv,
    export_rows_to_json,
    extract_email_subject,
    filter_results_by_status,
    format_optional,
    get_candidate_curation,
    get_provider_label,
    should_use_mock_fallback,
    slugify,
    sort_results,
)
from bot.config import Settings
from bot.models import Candidate, SearchRun, TrainingRequest


def make_settings() -> Settings:
    return Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="mock",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
    )


def make_search_run() -> SearchRun:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Porto",
    )

    return build_search_run(request, settings=make_settings())


def test_build_search_run_returns_queries_and_results() -> None:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Porto",
    )

    search_run = build_search_run(request, settings=make_settings())

    assert search_run.queries
    assert search_run.resultados
    assert search_run.diagnostics is not None


def test_build_search_run_returns_messages_for_each_result() -> None:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )

    search_run = build_search_run(request, settings=make_settings())
    first_result = search_run.resultados[0]

    assert first_result.mensagens.email_inicial
    assert first_result.mensagens.mensagem_linkedin


def test_build_search_run_falls_back_to_mock_when_public_search_is_empty(
    monkeypatch,
) -> None:
    class EmptyProvider:
        def search(self, request: TrainingRequest) -> list[Candidate]:
            return []

    monkeypatch.setattr("app.get_search_provider", lambda settings: EmptyProvider())

    settings = Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="public_web",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
        public_search_fallback_to_mock=True,
    )
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )

    search_run = build_search_run(request, settings=settings)

    assert search_run.resultados
    assert search_run.diagnostics is not None
    assert search_run.diagnostics.fallback_used is True
    assert search_run.diagnostics.fallback_provider == "mock"
    assert search_run.diagnostics.public_candidate_count == 0
    assert all(
        result.candidato_classificado.candidato.fonte == "mock"
        for result in search_run.resultados
    )


def test_build_search_run_can_disable_mock_fallback(monkeypatch) -> None:
    class EmptyProvider:
        def search(self, request: TrainingRequest) -> list[Candidate]:
            return []

    monkeypatch.setattr("app.get_search_provider", lambda settings: EmptyProvider())

    settings = Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="public_web",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
        public_search_fallback_to_mock=False,
    )
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )

    search_run = build_search_run(request, settings=settings)

    assert search_run.resultados == []
    assert search_run.diagnostics is not None
    assert search_run.diagnostics.fallback_used is False


def test_should_use_mock_fallback_requires_public_provider_and_empty_results() -> None:
    public_settings = Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="public_web",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
        public_search_fallback_to_mock=True,
    )
    mock_settings = Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="mock",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
    )

    assert should_use_mock_fallback(public_settings, [])
    assert not should_use_mock_fallback(mock_settings, [])


def test_get_provider_label_formats_known_providers() -> None:
    settings = make_settings()

    assert get_provider_label(settings) == "Mock"

    public_settings = Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="public_web",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
    )

    assert get_provider_label(public_settings) == "Pesquisa pública"


def test_format_optional_handles_missing_values() -> None:
    assert format_optional(None) == "Não identificado"
    assert format_optional("") == "Não identificado"
    assert format_optional("Porto") == "Porto"


def test_build_score_components_returns_readable_component_names() -> None:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )
    search_run = build_search_run(request, settings=make_settings())

    components = build_score_components(search_run.resultados[0])

    assert set(components) == {
        "Fit temático",
        "Fit funcional",
        "Experiência em formação",
        "Localização",
        "Contactabilidade",
        "Credibilidade pública",
    }
    assert all(isinstance(value, int) for value in components.values())


def test_build_export_rows_contains_shortlist_fields() -> None:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )
    search_run = build_search_run(request, settings=make_settings())

    rows = build_export_rows(search_run)
    first_row = rows[0]

    assert rows
    assert set(EXPORT_COLUMNS).issubset(first_row)
    assert first_row["nome"]
    assert first_row["canal_recomendado"] in {"email", "linkedin", "formulario"}
    assert isinstance(first_row["score_total"], int)
    assert first_row["email_inicial"]
    assert first_row["mensagem_linkedin"]


def test_export_rows_to_csv_uses_consistent_columns() -> None:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )
    search_run = build_search_run(request, settings=make_settings())
    rows = build_export_rows(search_run)

    csv_data = export_rows_to_csv(rows)
    parsed_rows = list(csv.DictReader(StringIO(csv_data)))

    assert parsed_rows
    assert parsed_rows[0].keys() == set(EXPORT_COLUMNS)
    assert parsed_rows[0]["nome"] == rows[0]["nome"]


def test_export_rows_to_json_is_readable_and_structured() -> None:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )
    search_run = build_search_run(request, settings=make_settings())
    rows = build_export_rows(search_run)

    json_data = export_rows_to_json(rows)
    parsed_rows = json.loads(json_data)

    assert parsed_rows[0]["nome"] == rows[0]["nome"]
    assert parsed_rows[0]["score_total"] == rows[0]["score_total"]


def test_extract_email_subject_returns_subject_line() -> None:
    subject = extract_email_subject(
        "Assunto: Convite para sessão sobre Python\n\nOlá Ana,"
    )

    assert subject == "Convite para sessão sobre Python"


def test_build_export_filename_uses_topic_slug() -> None:
    request = TrainingRequest(
        tema_formacao="Python para automação",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )
    search_run = build_search_run(request, settings=make_settings())

    assert build_export_filename(search_run, "csv") == "bot-formadores-python-para-automação.csv"


def test_slugify_has_safe_fallback() -> None:
    assert slugify("   ") == "export"


def test_candidate_key_is_stable_and_specific() -> None:
    search_run = make_search_run()
    first_result = search_run.resultados[0]
    second_result = search_run.resultados[1]

    assert candidate_key(first_result) == candidate_key(first_result)
    assert candidate_key(first_result) != candidate_key(second_result)
    assert first_result.candidato_classificado.candidato.nome.lower() in candidate_key(
        first_result
    )


def test_get_candidate_curation_uses_safe_defaults() -> None:
    search_run = make_search_run()

    curation = get_candidate_curation(search_run.resultados[0], {})

    assert curation["status"] == CURATION_STATUS_DEFAULT
    assert curation["note"] == ""


def test_build_export_rows_includes_curation_fields() -> None:
    search_run = make_search_run()
    first_result = search_run.resultados[0]
    curation_state = {
        candidate_key(first_result): {
            "status": "aprovado",
            "note": "Boa opção para workshop prático.",
        }
    }

    rows = build_export_rows(search_run, curation_state=curation_state)

    assert rows[0]["estado_curadoria"] == "Aprovado para contacto"
    assert rows[0]["nota_curadoria"] == "Boa opção para workshop prático."


def test_build_export_rows_can_export_only_approved_candidates() -> None:
    search_run = make_search_run()
    approved_result = search_run.resultados[1]
    curation_state = {
        candidate_key(approved_result): {
            "status": "aprovado",
            "note": "Perfil forte sem email público.",
        }
    }

    rows = build_export_rows(
        search_run,
        curation_state=curation_state,
        only_approved=True,
    )

    assert len(rows) == 1
    assert rows[0]["nome"] == approved_result.candidato_classificado.candidato.nome
    assert rows[0]["estado_curadoria"] == "Aprovado para contacto"


def test_filter_results_by_status_handles_marked_and_unmarked_candidates() -> None:
    search_run = make_search_run()
    approved_result = search_run.resultados[0]
    curation_state = {
        candidate_key(approved_result): {
            "status": "aprovado",
            "note": "",
        }
    }

    approved_results = filter_results_by_status(
        search_run.resultados,
        curation_state,
        "aprovado",
    )
    pending_results = filter_results_by_status(
        search_run.resultados,
        curation_state,
        "por_decidir",
    )

    assert approved_results == [approved_result]
    assert approved_result not in pending_results
    assert len(pending_results) == len(search_run.resultados) - 1


def test_sort_results_orders_by_score_name_company_and_status() -> None:
    search_run = make_search_run()
    curation_state = {
        candidate_key(search_run.resultados[0]): {
            "status": "rejeitado",
            "note": "",
        },
        candidate_key(search_run.resultados[1]): {
            "status": "aprovado",
            "note": "",
        },
    }

    by_score = sort_results(search_run.resultados, curation_state, "score_total")
    by_name = sort_results(search_run.resultados, curation_state, "nome")
    by_company = sort_results(search_run.resultados, curation_state, "empresa")
    by_status = sort_results(search_run.resultados, curation_state, "estado")

    score_values = [
        result.candidato_classificado.score.score_total
        for result in by_score
    ]
    names = [
        result.candidato_classificado.candidato.nome
        for result in by_name
    ]
    companies = [
        result.candidato_classificado.candidato.empresa or ""
        for result in by_company
    ]

    assert score_values == sorted(score_values, reverse=True)
    assert names == sorted(names)
    assert companies == sorted(companies)
    assert by_status[0] == search_run.resultados[1]


def test_count_approved_results_counts_only_approved_candidates() -> None:
    search_run = make_search_run()
    curation_state = {
        candidate_key(search_run.resultados[0]): {
            "status": "aprovado",
            "note": "",
        },
        candidate_key(search_run.resultados[1]): {
            "status": "talvez",
            "note": "",
        },
    }

    assert count_approved_results(search_run.resultados, curation_state) == 1


def test_build_export_filename_accepts_suffix() -> None:
    search_run = make_search_run()

    assert (
        build_export_filename(search_run, "csv", "shortlist aprovada")
        == "bot-formadores-python-shortlist-aprovada.csv"
    )
