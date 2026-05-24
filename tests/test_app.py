import csv
import json
from io import StringIO

from app import (
    EXPORT_COLUMNS,
    build_export_filename,
    build_export_rows,
    build_score_components,
    build_search_run,
    export_rows_to_csv,
    export_rows_to_json,
    extract_email_subject,
    format_optional,
    get_provider_label,
    slugify,
)
from bot.config import Settings
from bot.models import TrainingRequest


def make_settings() -> Settings:
    return Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="mock",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
    )


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
