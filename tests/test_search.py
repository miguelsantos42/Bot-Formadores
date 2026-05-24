from bot.config import Settings
from bot.models import TrainingFormat, TrainingRequest
from bot.search import (
    MockSearchProvider,
    PublicWebSearchProvider,
    build_topic_terms,
    dedupe_preserve_order,
    generate_search_queries,
    get_search_provider,
    is_job_board_result,
    is_relevant_public_result,
)
from bot.parsing import PublicSearchResult


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

    assert len(queries) == 20
    assert "Python" in queries[0]
    assert "Porto" in queries[0]
    assert queries[0].startswith("site:linkedin.com/in")
    assert "formador" in queries[0]


def test_generate_search_queries_without_location() -> None:
    request = TrainingRequest(
        tema_formacao="Data Science",
        area_interna="Analytics",
        descricao_contexto="Sessao para explorar fundamentos de ciencia de dados.",
    )

    queries = generate_search_queries(request)

    assert len(queries) == 20
    assert "Data Science" in queries[0]
    assert all("  " not in query for query in queries)


def test_generate_search_queries_are_ordered_by_priority() -> None:
    request = make_request()

    queries = generate_search_queries(request)

    people_queries = queries[:10]
    company_queries = queries[10:14]
    public_queries = queries[14:18]
    experimental_queries = queries[18:20]

    assert all(query.startswith("site:linkedin.com/in") for query in people_queries)
    assert all(query.startswith("site:linkedin.com/company") for query in company_queries)
    assert all(not query.startswith("site:linkedin.com") for query in public_queries)
    assert all(not query.startswith("site:linkedin.com") for query in experimental_queries)


def test_generate_search_queries_use_stronger_linkedin_exclusions() -> None:
    request = make_request()

    queries = generate_search_queries(request)

    assert "-jobs" in queries[0]
    assert "-company" in queries[0]
    assert "-pulse" in queries[0]
    assert "-youtube" not in queries[0]


def test_generate_search_queries_use_lighter_public_exclusions() -> None:
    request = make_request()

    queries = generate_search_queries(request)
    public_query = queries[14]

    assert "-wikipedia" in public_query
    assert "-youtube" in public_query
    assert "-jobs" not in public_query
    assert "-company" not in public_query


def test_generate_search_queries_expand_hr_terms_with_controlled_limit() -> None:
    request = TrainingRequest(
        tema_formacao="plano de carreira",
        area_interna="RH",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Portugal",
    )

    topic_terms = build_topic_terms(request.tema_formacao, request.area_interna)
    queries = generate_search_queries(request)

    assert len(topic_terms) <= 8
    assert "recursos humanos" in topic_terms
    assert "human resources" in topic_terms
    assert "career development" in topic_terms
    assert "gestão de carreira" in topic_terms
    assert any('"recursos humanos"' in query for query in queries)
    assert len(queries) == 20
    assert len(queries) == len(set(queries))


def test_generate_search_queries_expand_marketing_terms() -> None:
    request = TrainingRequest(
        tema_formacao="marketing estratégico",
        area_interna="Marketing",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Portugal",
    )

    topic_terms = build_topic_terms(request.tema_formacao, request.area_interna)
    queries = generate_search_queries(request)

    assert "strategic marketing" in topic_terms
    assert "marketing strategy" in topic_terms
    assert any('"strategic marketing"' in query for query in queries)
    assert len(queries) == 20


def test_dedupe_preserve_order_keeps_first_values() -> None:
    values = ["alpha", "beta", "alpha", "gamma"]

    deduped = dedupe_preserve_order(values, limit=3)

    assert deduped == ["alpha", "beta", "gamma"]


def test_mock_search_provider_returns_candidates() -> None:
    request = make_request()
    provider = MockSearchProvider()

    candidates = provider.search(request)

    assert len(candidates) == 3
    assert candidates[0].nome == "Ana Silva"
    assert candidates[0].fonte == "mock"
    assert candidates[0].matched_query
    assert candidates[0].source_domain == "linkedin.com"


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


def test_get_search_provider_returns_mock_provider() -> None:
    settings = Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="mock",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
    )

    provider = get_search_provider(settings)

    assert isinstance(provider, MockSearchProvider)


def test_get_search_provider_returns_public_web_provider() -> None:
    settings = Settings(
        app_env="test",
        database_path="test.sqlite3",
        search_provider="public_web",
        public_search_url="https://example.com/search",
        public_search_timeout_seconds=1,
        public_search_max_results=5,
    )

    provider = get_search_provider(settings)

    assert isinstance(provider, PublicWebSearchProvider)


def test_public_web_search_provider_returns_candidates(monkeypatch) -> None:
    html = """
    <div class="result">
      <a class="result__a" href="https://www.linkedin.com/in/ana-silva">
        Ana Silva - Freelance Python Trainer | LinkedIn
      </a>
      <a class="result__snippet">
        Freelance trainer and speaker for Python workshops.
      </a>
    </div>
    """

    class FakeResponse:
        text = html

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("bot.search.requests.get", fake_get)

    provider = PublicWebSearchProvider(
        search_url="https://example.com/search",
        timeout_seconds=1,
        max_results=1,
    )

    candidates = provider.search(make_request())

    assert len(candidates) == 1
    assert candidates[0].nome == "Ana Silva"
    assert candidates[0].fonte == "public_web"
    assert candidates[0].source_domain == "linkedin.com"
    assert candidates[0].matched_query


def test_public_web_search_provider_filters_irrelevant_results(monkeypatch) -> None:
    html = """
    <li class="b_algo">
      <h2>
        <a href="https://www.python.org/">Welcome to Python.org</a>
      </h2>
      <div class="b_caption">
        <p>The official home of the Python programming language.</p>
      </div>
    </li>
    """

    class FakeResponse:
        text = html

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("bot.search.requests.get", fake_get)

    provider = PublicWebSearchProvider(max_results=1)

    candidates = provider.search(make_request())

    assert candidates == []


def test_linkedin_profile_result_is_relevant() -> None:
    result = PublicSearchResult(
        title="Ana Silva - Freelance Python Trainer",
        url="https://www.linkedin.com/in/ana-silva",
        snippet="Freelance trainer.",
        matched_query="Python freelancer",
        source_domain="linkedin.com",
    )

    assert is_relevant_public_result(result)


def test_job_board_result_is_not_relevant() -> None:
    result = PublicSearchResult(
        title="Emprego Formador - Maio 2026",
        url="https://www.net-empregos.com/formador-python",
        snippet="Ofertas de emprego para formador.",
        matched_query="formador python freelance",
        source_domain="net-empregos.com",
    )

    assert is_job_board_result(result)
    assert not is_relevant_public_result(result)
