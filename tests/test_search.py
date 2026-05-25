import requests

from bot.config import Settings
from bot.models import ProfileType, TrainingFormat, TrainingRequest
from bot.search import (
    MAX_CONSECUTIVE_PUBLIC_SEARCH_ERRORS,
    MockSearchProvider,
    PublicWebSearchProvider,
    build_topic_terms,
    detect_profile_type,
    dedupe_preserve_order,
    enrich_public_candidate_metadata,
    generate_search_queries,
    get_search_provider,
    has_freelance_signal,
    has_topic_experience_signal,
    has_training_experience_signal,
    is_job_board_result,
    is_probably_linkedin_profile,
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
    assert "freelancer" in queries[0]
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

    assert all(query.startswith("site:linkedin.com/in") for query in queries)
    assert all("site:linkedin.com/company" not in query for query in queries)
    assert all(
        any(
            term in query
            for term in [
                "freelance",
                "freelancer",
                "independente",
                "independent",
                "self employed",
            ]
        )
        for query in queries
    )


def test_generate_search_queries_respect_group_quotas() -> None:
    queries = generate_search_queries(make_request())

    assert sum(query.startswith("site:linkedin.com/in") for query in queries) == 20
    assert len(queries) == 20


def test_generate_search_queries_use_linkedin_profile_exclusions() -> None:
    request = make_request()

    queries = generate_search_queries(request)

    assert "-jobs" in queries[0]
    assert "-company" in queries[0]
    assert "-companies" in queries[0]
    assert "-pulse" in queries[0]
    assert "-school" in queries[0]


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


def test_generate_search_queries_include_pt_and_en_training_terms() -> None:
    queries = generate_search_queries(make_request())
    query_text = " ".join(queries)

    assert "formador" in query_text
    assert "formadora" in query_text
    assert "trainer" in query_text
    assert "speaker" in query_text
    assert "training" in query_text


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
    assert all(candidate.source_domain == "linkedin.com" for candidate in candidates)
    assert all(candidate.is_probably_linkedin_profile for candidate in candidates)
    assert all(candidate.empresa == "Freelancer" for candidate in candidates)


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

    assert "Python" in candidates[0].cargo
    assert "Freelance" in candidates[0].cargo


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
    assert candidates[0].search_rank == 1
    assert candidates[0].result_title_raw == "Ana Silva - Freelance Python Trainer | LinkedIn"
    assert candidates[0].snippet_raw == "Freelance trainer and speaker for Python workshops."
    assert candidates[0].profile_type == ProfileType.linkedin_profile
    assert candidates[0].is_probably_linkedin_profile is True


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


def test_public_web_search_provider_deduplicates_by_url(monkeypatch) -> None:
    html = """
    <div class="result">
      <a class="result__a" href="https://www.linkedin.com/in/ana-silva">
        Ana Silva - Freelance Python Trainer | LinkedIn
      </a>
      <a class="result__snippet">Freelance Python trainer and speaker.</a>
    </div>
    <div class="result">
      <a class="result__a" href="https://www.linkedin.com/in/ana-silva">
        Ana Silva - Freelance Python Trainer | LinkedIn
      </a>
      <a class="result__snippet">Duplicate result.</a>
    </div>
    """

    class FakeResponse:
        text = html

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("bot.search.requests.get", fake_get)

    provider = PublicWebSearchProvider(max_results=5)
    candidates = provider.search(make_request())

    assert len(candidates) == 1
    assert candidates[0].nome == "Ana Silva"


def test_public_web_search_provider_continues_after_request_error(monkeypatch) -> None:
    html = """
    <div class="result">
      <a class="result__a" href="https://www.linkedin.com/in/ana-silva">
        Ana Silva - Freelance Python Trainer | LinkedIn
      </a>
      <a class="result__snippet">Freelance Python trainer and speaker.</a>
    </div>
    """
    calls = {"count": 0}

    class FakeResponse:
        text = html

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.RequestException("temporary network error")
        return FakeResponse()

    monkeypatch.setattr("bot.search.requests.get", fake_get)

    provider = PublicWebSearchProvider(max_results=1)

    candidates = provider.search(make_request())

    assert len(candidates) == 1
    assert candidates[0].nome == "Ana Silva"


def test_public_web_search_provider_stops_after_repeated_request_errors(
    monkeypatch,
) -> None:
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        raise requests.RequestException("search unavailable")

    monkeypatch.setattr("bot.search.requests.get", fake_get)

    provider = PublicWebSearchProvider(max_results=1)

    candidates = provider.search(make_request())

    assert candidates == []
    assert calls["count"] == MAX_CONSECUTIVE_PUBLIC_SEARCH_ERRORS


def test_public_web_search_provider_uses_bing_safesearch_params(monkeypatch) -> None:
    captured_params = {}

    class FakeResponse:
        text = ""

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs):
        captured_params.update(kwargs["params"])
        return FakeResponse()

    monkeypatch.setattr("bot.search.requests.get", fake_get)

    provider = PublicWebSearchProvider(
        search_url="https://www.bing.com/search",
        timeout_seconds=1,
        max_results=1,
    )
    provider._fetch_results("Python trainer")

    assert captured_params["q"] == "Python trainer"
    assert captured_params["adlt"] == "strict"
    assert captured_params["setlang"] == "pt-PT"
    assert captured_params["cc"] == "pt"


def test_linkedin_profile_result_is_relevant() -> None:
    result = PublicSearchResult(
        title="Ana Silva - Freelance Python Trainer",
        url="https://www.linkedin.com/in/ana-silva",
        snippet="Freelance trainer.",
        matched_query="Python freelancer",
        source_domain="linkedin.com",
    )

    assert is_relevant_public_result(result, make_request())
    assert detect_profile_type(result) == ProfileType.linkedin_profile
    assert is_probably_linkedin_profile(result) is True
    assert has_freelance_signal(result)
    assert has_training_experience_signal(result)
    assert has_topic_experience_signal(result, make_request())


def test_linkedin_profile_without_freelance_signal_is_not_relevant() -> None:
    result = PublicSearchResult(
        title="Ana Silva - Python Trainer",
        url="https://www.linkedin.com/in/ana-silva",
        snippet="Python trainer and speaker.",
        matched_query="site:linkedin.com/in Python trainer",
        source_domain="linkedin.com",
    )

    assert not is_relevant_public_result(result, make_request())


def test_linkedin_profile_without_topic_evidence_is_not_relevant() -> None:
    result = PublicSearchResult(
        title="Ana Silva - Freelance JavaScript Trainer",
        url="https://www.linkedin.com/in/ana-silva",
        snippet="Freelance trainer and speaker.",
        matched_query="site:linkedin.com/in Python freelancer trainer",
        source_domain="linkedin.com",
    )

    assert not is_relevant_public_result(result, make_request())


def test_company_linkedin_page_is_not_relevant_even_with_training_terms() -> None:
    result = PublicSearchResult(
        title="Empresa X | LinkedIn",
        url="https://www.linkedin.com/company/empresa-x",
        snippet="Freelance Python training and consulting company.",
        matched_query="site:linkedin.com/company Python training",
        source_domain="linkedin.com",
    )

    assert not is_relevant_public_result(result, make_request())


def test_company_page_result_is_classified_as_company_page() -> None:
    result = PublicSearchResult(
        title="Empresa X | LinkedIn",
        url="https://www.linkedin.com/company/empresa-x",
        snippet="Training and consulting company.",
        matched_query="Python training",
        source_domain="linkedin.com",
    )

    assert detect_profile_type(result) == ProfileType.company_page
    assert is_probably_linkedin_profile(result) is False


def test_article_result_is_classified_as_article_or_post() -> None:
    result = PublicSearchResult(
        title="Como preparar um workshop de Python",
        url="https://example.com/blog/python-workshop",
        snippet="Artigo sobre workshops de Python.",
        matched_query="Python workshop",
        source_domain="example.com",
    )

    assert detect_profile_type(result) == ProfileType.article_or_post


def test_job_board_result_is_not_relevant() -> None:
    result = PublicSearchResult(
        title="Emprego Formador - Maio 2026",
        url="https://www.net-empregos.com/formador-python",
        snippet="Ofertas de emprego para formador.",
        matched_query="formador python freelance",
        source_domain="net-empregos.com",
    )

    assert is_job_board_result(result)
    assert not is_relevant_public_result(result, make_request())
    assert detect_profile_type(result) == ProfileType.job_board


def test_unknown_result_is_classified_as_unknown() -> None:
    result = PublicSearchResult(
        title="Página institucional",
        url="https://example.com/about",
        snippet="Informação geral sobre a organização.",
        matched_query="Python",
        source_domain="example.com",
    )

    assert detect_profile_type(result) == ProfileType.unknown


def test_enrich_public_candidate_metadata_preserves_query_and_source() -> None:
    result = PublicSearchResult(
        title="Ana Silva - Python Trainer | LinkedIn",
        url="https://www.linkedin.com/in/ana-silva",
        snippet="Python trainer and workshop speaker.",
        matched_query="site:linkedin.com/in Python trainer",
        source_domain="linkedin.com",
    )
    candidate = MockSearchProvider().search(make_request())[0]

    enriched_candidate = enrich_public_candidate_metadata(
        candidate=candidate,
        result=result,
        search_rank=2,
    )

    assert enriched_candidate.matched_query == candidate.matched_query
    assert enriched_candidate.source_domain == "linkedin.com"
    assert enriched_candidate.search_rank == 2
    assert enriched_candidate.result_title_raw == result.title
    assert enriched_candidate.snippet_raw == result.snippet
    assert enriched_candidate.profile_type == ProfileType.linkedin_profile
