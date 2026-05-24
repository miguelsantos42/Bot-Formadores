from app import build_search_run
from bot.models import TrainingRequest


def test_build_search_run_returns_queries_and_results() -> None:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Porto",
    )

    search_run = build_search_run(request)

    assert search_run.queries
    assert search_run.resultados


def test_build_search_run_returns_messages_for_each_result() -> None:
    request = TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )

    search_run = build_search_run(request)
    first_result = search_run.resultados[0]

    assert first_result.mensagens.email_inicial
    assert first_result.mensagens.mensagem_linkedin
