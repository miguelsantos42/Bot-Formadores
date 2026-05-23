from bot.models import TrainingFormat, TrainingRequest
from bot.search import MockSearchProvider, generate_search_queries


def make_request() -> TrainingRequest:
    return TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Porto",
        formato=TrainingFormat.presencial,
        duracao="2 horas",
        numero_participantes=20,
    )


def test_generate_search_queries_uses_request_fields() -> None:
    request = make_request()

    queries = generate_search_queries(request)

    assert len(queries) == 5
    assert "Python" in queries[0]
    assert "Tecnologia" in queries[0]
    assert "Porto" in queries[0]


def test_generate_search_queries_without_location() -> None:
    request = TrainingRequest(
        tema_formacao="Data Science",
        area_interna="Analytics",
        descricao_contexto="Sessao para explorar fundamentos de ciencia de dados.",
    )

    queries = generate_search_queries(request)

    assert len(queries) == 5
    assert "Data Science" in queries[0]
    assert "Analytics" in queries[0]


def test_mock_search_provider_returns_candidates() -> None:
    request = make_request()
    provider = MockSearchProvider()

    candidates = provider.search(request)

    assert len(candidates) == 3
    assert candidates[0].nome == "Ana Silva"
    assert candidates[0].fonte == "mock"


def test_mock_search_provider_returns_candidates_with_links() -> None:
    request = make_request()
    provider = MockSearchProvider()

    candidates = provider.search(request)

    assert candidates[0].links
    assert candidates[0].links[0].label == "LinkedIn"


def test_mock_search_provider_uses_request_topic_in_candidate_role() -> None:
    request = make_request()
    provider = MockSearchProvider()

    candidates = provider.search(request)

    assert candidates[0].cargo == "Especialista em Python"
