from abc import ABC, abstractmethod
from collections.abc import Iterable

import requests

from bot.config import Settings
from bot.models import Candidate, PublicLink, TrainingRequest
from bot.parsing import (
    PublicSearchResult,
    parse_public_result_to_candidate,
    parse_search_results_html,
)


class SearchProvider(ABC):
    @abstractmethod
    def search(self, request: TrainingRequest) -> list[Candidate]:
        """Return candidates for a training request."""


def generate_search_queries(request: TrainingRequest) -> list[str]:
    base_terms = [
        request.tema_formacao,
        request.area_interna,
    ]

    if request.localizacao:
        base_terms.append(request.localizacao)

    main_query = " ".join(base_terms)

    return [
        f"site:linkedin.com/in {main_query} freelancer formador",
        f"site:linkedin.com/in {main_query} freelance trainer",
        f"{main_query} freelancer workshop portfolio",
        f"{main_query} formador freelancer site pessoal",
        f'{request.tema_formacao} "{request.area_interna}" LinkedIn freelancer',
    ]


def get_search_provider(settings: Settings) -> SearchProvider:
    if settings.search_provider == "mock":
        return MockSearchProvider()

    if settings.search_provider == "public_web":
        return PublicWebSearchProvider(
            search_url=settings.public_search_url,
            timeout_seconds=settings.public_search_timeout_seconds,
            max_results=settings.public_search_max_results,
        )

    raise ValueError(f"Unknown search provider: {settings.search_provider}")


class MockSearchProvider(SearchProvider):
    def search(self, request: TrainingRequest) -> list[Candidate]:
        queries = generate_search_queries(request)

        return [
            Candidate(
                nome="Ana Silva",
                cargo=f"Especialista em {request.tema_formacao}",
                empresa="Tech Learning Studio",
                localizacao=request.localizacao or "Portugal",
                links=[
                    PublicLink(
                        label="LinkedIn",
                        url="https://www.linkedin.com/in/ana-silva",
                    ),
                    PublicLink(
                        label="Website",
                        url="https://example.com/ana-silva",
                    ),
                ],
                email_publico="ana.silva@example.com",
                fonte="mock",
                excerto=(
                    f"Perfil encontrado para a query '{queries[0]}'. "
                    "Experiência em workshops e sessões práticas."
                ),
                matched_query=queries[0],
                source_domain="linkedin.com",
            ),
            Candidate(
                nome="Joao Pereira",
                cargo="Consultor e formador",
                empresa="Freelancer",
                localizacao="Porto",
                links=[
                    PublicLink(
                        label="LinkedIn",
                        url="https://www.linkedin.com/in/joao-pereira",
                    )
                ],
                email_publico=None,
                fonte="mock",
                excerto=(
                    f"Perfil encontrado para a query '{queries[1]}'. "
                    "Conteúdos públicos indicam experiência como speaker."
                ),
                matched_query=queries[1],
                source_domain="linkedin.com",
            ),
            Candidate(
                nome="Mariana Costa",
                cargo="Head of People Development",
                empresa="Empresa Exemplo",
                localizacao="Lisboa",
                links=[
                    PublicLink(
                        label="Perfil publico",
                        url="https://example.com/mariana-costa",
                    )
                ],
                email_publico="formacao@example.com",
                fonte="mock",
                excerto=(
                    f"Perfil encontrado para a query '{queries[2]}'. "
                    "Ligação forte a aprendizagem interna e desenvolvimento de equipas."
                ),
                matched_query=queries[2],
                source_domain="example.com",
            ),
        ]


class PublicWebSearchProvider(SearchProvider):
    def __init__(
        self,
        search_url: str = "https://www.bing.com/search",
        timeout_seconds: int = 10,
        max_results: int = 10,
    ) -> None:
        self.search_url = search_url
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results

    def search(self, request: TrainingRequest) -> list[Candidate]:
        candidates: list[Candidate] = []
        seen_urls: set[str] = set()

        for query in generate_search_queries(request):
            for result in self._safe_fetch_results(query):
                if not is_relevant_public_result(result):
                    continue

                if result.url in seen_urls:
                    continue

                seen_urls.add(result.url)
                candidates.append(parse_public_result_to_candidate(result))

                if len(candidates) >= self.max_results:
                    return candidates

        return candidates

    def _safe_fetch_results(self, query: str) -> Iterable[PublicSearchResult]:
        try:
            return self._fetch_results(query)
        except requests.RequestException:
            return []

    def _fetch_results(self, query: str) -> list[PublicSearchResult]:
        response = requests.get(
            self.search_url,
            params={"q": query},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 compatible; Bot-Formadores/1.0; "
                    "public web search"
                )
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        return parse_search_results_html(response.text, matched_query=query)


def is_relevant_public_result(result: PublicSearchResult) -> bool:
    if "linkedin.com" in result.source_domain and "/in/" in result.url:
        return True

    if is_job_board_result(result):
        return False

    text = " ".join([result.title, result.snippet]).lower()
    keywords = [
        "freelance",
        "freelancer",
        "formador",
        "formadora",
        "trainer",
        "consultor",
        "consultora",
        "speaker",
        "workshop",
        "portfolio",
    ]

    return any(keyword in text for keyword in keywords)


def is_job_board_result(result: PublicSearchResult) -> bool:
    domain = result.source_domain
    text = " ".join([result.title, result.snippet]).lower()

    excluded_domains = [
        "net-empregos.com",
        "emprego.sapo.pt",
        "indeed.com",
        "linkedin.com/jobs",
        "netforce.iefp.pt",
        "glassdoor.com",
    ]
    excluded_terms = [
        "vagas",
        "ofertas de emprego",
        "emprego formador",
        "job alert",
        "candidate-se",
        "recrutamento",
    ]

    return any(excluded_domain in domain for excluded_domain in excluded_domains) or any(
        term in text for term in excluded_terms
    )
