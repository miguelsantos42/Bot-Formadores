from app import build_search_run
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
