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

MAX_SEARCH_QUERIES = 20
LINKEDIN_PEOPLE_QUERY_LIMIT = 10
LINKEDIN_COMPANY_QUERY_LIMIT = 4
PUBLIC_GENERAL_QUERY_LIMIT = 4
EXPERIMENTAL_QUERY_LIMIT = 2

PEOPLE_LINKEDIN_TERMS = [
    "formador",
    "formadora",
    "trainer",
    "speaker",
    "mentor",
    "coach",
    "consultant",
    "facilitator",
]

COMPANY_LINKEDIN_TERMS = [
    "formação",
    "training",
    "consultoria",
    "consulting",
    "workshops",
]

PUBLIC_PROFILE_TERMS = [
    "workshop",
    "trainer",
    "speaker",
    "consultant",
    "coach",
    "portfolio",
]

EXPERIMENTAL_TERMS = [
    "freelancer",
    "independent consultant",
    "facilitator",
]

LINKEDIN_PEOPLE_EXCLUSIONS = [
    "-jobs",
    "-job",
    "-careers",
    "-company",
    "-pulse",
    "-posts",
]

LINKEDIN_COMPANY_EXCLUSIONS = [
    "-jobs",
    "-job",
    "-careers",
    "-vagas",
    "-emprego",
]

PUBLIC_GENERAL_EXCLUSIONS = [
    "-wikipedia",
    "-youtube",
]

EXPERIMENTAL_EXCLUSIONS = [
    "-wikipedia",
]

DOMAIN_TOPIC_EXPANSIONS = {
    "rh": [
        "recursos humanos",
        "human resources",
        "people management",
        "career development",
        "gestão de carreira",
    ],
    "marketing": [
        "marketing estratégico",
        "strategic marketing",
        "marketing strategy",
    ],
    "qualidade": [
        "gestão da qualidade",
        "quality management",
        "continuous improvement",
    ],
    "lideranca": [
        "liderança",
        "leadership",
        "team leadership",
    ],
    "produtividade": [
        "produtividade",
        "productivity",
        "time management",
    ],
}


class SearchProvider(ABC):
    @abstractmethod
    def search(self, request: TrainingRequest) -> list[Candidate]:
        """Return candidates for a training request."""


def generate_search_queries(request: TrainingRequest) -> list[str]:
    topic = request.tema_formacao.strip()
    area = request.area_interna.strip()
    location_part = build_location_part(request.localizacao)
    topic_terms = build_topic_terms(topic, area)

    queries: list[str] = []
    queries.extend(
        build_linkedin_people_queries(topic_terms, location_part)[
            :LINKEDIN_PEOPLE_QUERY_LIMIT
        ]
    )
    queries.extend(
        build_linkedin_company_queries(topic_terms, location_part)[
            :LINKEDIN_COMPANY_QUERY_LIMIT
        ]
    )
    queries.extend(
        build_public_general_queries(topic_terms, location_part)[
            :PUBLIC_GENERAL_QUERY_LIMIT
        ]
    )
    queries.extend(
        build_experimental_queries(topic_terms, location_part)[:EXPERIMENTAL_QUERY_LIMIT]
    )

    return dedupe_preserve_order(queries, limit=MAX_SEARCH_QUERIES)


def build_topic_terms(topic: str, area: str) -> list[str]:
    base_terms = [
        topic,
        area,
        f"{topic} {area}",
    ]
    text = normalize_query_text(f"{topic} {area}")
    expanded_terms = list(base_terms)

    if has_any(text, ["rh", "recursos humanos", "human resources"]):
        expanded_terms.extend(DOMAIN_TOPIC_EXPANSIONS["rh"])

    if has_any(text, ["marketing"]):
        expanded_terms.extend(DOMAIN_TOPIC_EXPANSIONS["marketing"])

    if has_any(text, ["qualidade", "quality"]):
        expanded_terms.extend(DOMAIN_TOPIC_EXPANSIONS["qualidade"])

    if has_any(text, ["liderança", "lideranca", "leadership"]):
        expanded_terms.extend(DOMAIN_TOPIC_EXPANSIONS["lideranca"])

    if has_any(text, ["produtividade", "productivity"]):
        expanded_terms.extend(DOMAIN_TOPIC_EXPANSIONS["produtividade"])

    return dedupe_preserve_order(expanded_terms, limit=8)


def build_linkedin_people_queries(
    topic_terms: list[str],
    location_part: str,
) -> list[str]:
    queries: list[str] = []

    for term in topic_terms[:4]:
        quoted_term = quote_term(term)

        for people_term in PEOPLE_LINKEDIN_TERMS[:4]:
            queries.append(
                build_query(
                    f"site:linkedin.com/in {quoted_term} {people_term}{location_part}",
                    LINKEDIN_PEOPLE_EXCLUSIONS,
                )
            )

    return queries


def build_linkedin_company_queries(
    topic_terms: list[str],
    location_part: str,
) -> list[str]:
    queries: list[str] = []

    for term in topic_terms[:3]:
        quoted_term = quote_term(term)

        for company_term in COMPANY_LINKEDIN_TERMS[:2]:
            queries.append(
                build_query(
                    f"site:linkedin.com/company {quoted_term} {company_term}{location_part}",
                    LINKEDIN_COMPANY_EXCLUSIONS,
                )
            )

    return queries


def build_public_general_queries(
    topic_terms: list[str],
    location_part: str,
) -> list[str]:
    queries: list[str] = []
    public_patterns = [
        " ".join(PUBLIC_PROFILE_TERMS[:3]),
        " ".join(PUBLIC_PROFILE_TERMS[3:6]),
    ]

    for public_terms in public_patterns:
        for term in topic_terms[:4]:
            quoted_term = quote_term(term)
            queries.append(
                build_query(
                    f"{quoted_term} {public_terms}{location_part}",
                    PUBLIC_GENERAL_EXCLUSIONS,
                )
            )

    return queries


def build_experimental_queries(
    topic_terms: list[str],
    location_part: str,
) -> list[str]:
    queries: list[str] = []

    for term in topic_terms[:3]:
        quoted_term = quote_term(term)

        for experimental_term in EXPERIMENTAL_TERMS[:2]:
            queries.append(
                build_query(
                    f"{quoted_term} {experimental_term}{location_part}",
                    EXPERIMENTAL_EXCLUSIONS,
                )
            )

    return queries


def build_query(base_query: str, exclusions: list[str]) -> str:
    return " ".join([base_query, *exclusions]).strip()


def build_location_part(location: str | None) -> str:
    if not location:
        return ""

    return f" {location.strip()}"


def quote_term(value: str) -> str:
    clean_value = value.strip()

    if " " in clean_value:
        return f'"{clean_value}"'

    return clean_value


def has_any(text: str, values: list[str]) -> bool:
    return any(value in text for value in values)


def normalize_query_text(value: str) -> str:
    return value.strip().lower()


def dedupe_preserve_order(values: list[str], limit: int) -> list[str]:
    deduped: list[str] = []

    for value in values:
        clean_value = value.strip()
        if not clean_value:
            continue

        if clean_value not in deduped:
            deduped.append(clean_value)

        if len(deduped) >= limit:
            break

    return deduped


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
