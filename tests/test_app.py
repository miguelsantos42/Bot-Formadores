from app import (
    build_score_components,
    build_search_run,
    format_optional,
    get_provider_label,
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
