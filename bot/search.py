from abc import ABC, abstractmethod
import re

import requests

from bot.config import Settings
from bot.models import Candidate, ProfileType, PublicLink, TrainingRequest
from bot.parsing import (
    PublicSearchResult,
    parse_public_result_to_candidate,
    parse_search_results_html,
)

MAX_SEARCH_QUERIES = 20
LINKEDIN_PEOPLE_QUERY_LIMIT = 20
MAX_CONSECUTIVE_PUBLIC_SEARCH_ERRORS = 3

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

FREELANCE_LINKEDIN_TERMS = [
    "freelancer",
    "freelance",
    "consultor independente",
    "consultora independente",
    "independent consultant",
    "self employed",
]

LINKEDIN_PEOPLE_EXCLUSIONS = [
    "-jobs",
    "-job",
    "-careers",
    "-company",
    "-companies",
    "-pulse",
    "-posts",
    "-school",
]

FREELANCE_SIGNAL_TERMS = [
    "freelance",
    "freelancer",
    "independent",
    "independente",
    "self-employed",
    "self employed",
    "consultor independente",
    "consultora independente",
]

TRAINING_EXPERIENCE_SIGNAL_TERMS = PEOPLE_LINKEDIN_TERMS + ["workshop", "workshops"]

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
    query_patterns = [
        ("freelancer", "formador"),
        ("freelance", "trainer"),
        ("freelancer", "formadora"),
        ("freelance", "speaker"),
        ("consultor independente", "workshop"),
        ("independent consultant", "training"),
        ("self employed", "mentor"),
        ("freelancer", "consultant"),
    ]

    for freelance_term, people_term in query_patterns:
        quoted_freelance_term = quote_term(freelance_term)

        for term in topic_terms[:8]:
            quoted_term = quote_term(term)
            queries.append(
                build_query(
                    (
                        "site:linkedin.com/in "
                        f"{quoted_term} {quoted_freelance_term} "
                        f"{people_term}{location_part}"
                    ),
                    LINKEDIN_PEOPLE_EXCLUSIONS,
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
                cargo=f"Freelance {request.tema_formacao} trainer",
                empresa="Freelancer",
                localizacao=request.localizacao or "Portugal",
                links=[
                    PublicLink(
                        label="LinkedIn",
                        url="https://www.linkedin.com/in/ana-silva",
                    ),
                ],
                email_publico="ana.silva@example.com",
                fonte="mock",
                excerto=(
                    f"Perfil encontrado para a query '{queries[0]}'. "
                    f"Freelancer com experiência em workshops de {request.tema_formacao}."
                ),
                matched_query=queries[0],
                source_domain="linkedin.com",
                profile_type=ProfileType.linkedin_profile,
                is_probably_linkedin_profile=True,
            ),
            Candidate(
                nome="Joao Pereira",
                cargo=f"Consultor independente e formador em {request.tema_formacao}",
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
                    f"Conteúdos públicos indicam experiência como freelancer "
                    f"e speaker em {request.tema_formacao}."
                ),
                matched_query=queries[1],
                source_domain="linkedin.com",
                profile_type=ProfileType.linkedin_profile,
                is_probably_linkedin_profile=True,
            ),
            Candidate(
                nome="Mariana Costa",
                cargo=f"Freelance workshop facilitator em {request.tema_formacao}",
                empresa="Freelancer",
                localizacao="Lisboa",
                links=[
                    PublicLink(
                        label="LinkedIn",
                        url="https://www.linkedin.com/in/mariana-costa",
                    )
                ],
                email_publico="formacao@example.com",
                fonte="mock",
                excerto=(
                    f"Perfil encontrado para a query '{queries[2]}'. "
                    f"Perfil freelancer com experiência prática em {request.tema_formacao}."
                ),
                matched_query=queries[2],
                source_domain="linkedin.com",
                profile_type=ProfileType.linkedin_profile,
                is_probably_linkedin_profile=True,
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
        consecutive_errors = 0

        for query in generate_search_queries(request):
            try:
                fetched_results = self._fetch_results(query)
            except requests.RequestException:
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_PUBLIC_SEARCH_ERRORS:
                    break
                continue

            consecutive_errors = 0

            for search_rank, result in enumerate(fetched_results, start=1):
                if not is_relevant_public_result(result, request):
                    continue

                if result.url in seen_urls:
                    continue

                seen_urls.add(result.url)
                candidates.append(
                    enrich_public_candidate_metadata(
                        candidate=parse_public_result_to_candidate(result),
                        result=result,
                        search_rank=search_rank,
                    )
                )

                if len(candidates) >= self.max_results:
                    return candidates

        return candidates

    def _fetch_results(self, query: str) -> list[PublicSearchResult]:
        params = {"q": query}
        if "bing.com" in self.search_url:
            params.update(
                {
                    "adlt": "strict",
                    "setlang": "pt-PT",
                    "cc": "pt",
                }
            )

        response = requests.get(
            self.search_url,
            params=params,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0 Safari/537.36"
                )
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        return parse_search_results_html(response.text, matched_query=query)


def is_relevant_public_result(
    result: PublicSearchResult,
    request: TrainingRequest,
) -> bool:
    if is_job_board_result(result):
        return False

    return (
        is_probably_linkedin_profile(result)
        and has_freelance_signal(result)
        and has_training_experience_signal(result)
        and has_topic_experience_signal(result, request)
    )


def has_freelance_signal(result: PublicSearchResult) -> bool:
    text = searchable_result_text(result)
    return any(term in text for term in FREELANCE_SIGNAL_TERMS)


def has_training_experience_signal(result: PublicSearchResult) -> bool:
    text = searchable_result_text(result)
    return any(term in text for term in TRAINING_EXPERIENCE_SIGNAL_TERMS)


def has_topic_experience_signal(
    result: PublicSearchResult,
    request: TrainingRequest,
) -> bool:
    text = searchable_result_text(result)
    topic = normalize_query_text(request.tema_formacao)

    if topic and topic in text:
        return True

    topic_tokens = [
        token
        for token in re.findall(r"[\w+#.-]+", topic)
        if len(token) >= 2
    ]
    if not topic_tokens:
        return False

    return all(token in text for token in topic_tokens)


def searchable_result_text(result: PublicSearchResult) -> str:
    return normalize_query_text(" ".join([result.title, result.snippet]))


def enrich_public_candidate_metadata(
    candidate: Candidate,
    result: PublicSearchResult,
    search_rank: int,
) -> Candidate:
    return candidate.model_copy(
        update={
            "search_rank": search_rank,
            "snippet_raw": result.snippet or None,
            "result_title_raw": result.title,
            "profile_type": detect_profile_type(result),
            "is_probably_linkedin_profile": is_probably_linkedin_profile(result),
        }
    )


def detect_profile_type(result: PublicSearchResult) -> ProfileType:
    url = result.url.lower()
    domain = result.source_domain.lower()
    text = " ".join([result.title, result.snippet]).lower()

    if "linkedin.com" in domain and "/in/" in url:
        return ProfileType.linkedin_profile

    if "linkedin.com" in domain and "/company/" in url:
        return ProfileType.company_page

    if is_job_board_result(result):
        return ProfileType.job_board

    if any(term in url for term in ["/blog", "/post", "/article", "/news"]):
        return ProfileType.article_or_post

    if any(term in text for term in ["blog", "artigo", "article", "post"]):
        return ProfileType.article_or_post

    if any(term in text for term in ["portfolio", "freelance", "consultor", "trainer"]):
        return ProfileType.personal_site

    return ProfileType.unknown


def is_probably_linkedin_profile(result: PublicSearchResult) -> bool:
    return (
        "linkedin.com" in result.source_domain.lower()
        and "/in/" in result.url.lower()
    )


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
