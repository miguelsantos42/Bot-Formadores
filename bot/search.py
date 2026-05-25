from abc import ABC, abstractmethod
import re
from urllib.parse import urlparse

import requests

from bot.config import Settings
from bot.models import Candidate, ProfileType, PublicLink, TrainingRequest
from bot.parsing import (
    PublicSearchResult,
    clean_text,
    extract_source_domain,
    parse_public_result_to_candidate,
    parse_search_results_html,
)

MAX_SEARCH_QUERIES = 48
MAX_CONSECUTIVE_PUBLIC_SEARCH_ERRORS = 3

QUERY_BUCKET_QUOTAS = {
    "topic_training": 10,
    "topic_role_domain": 10,
    "topic_pt_en": 8,
    "topic_training_signals": 8,
    "topic_location": 6,
    "exploratory": 6,
}

PEOPLE_LINKEDIN_TERMS = [
    "formador",
    "formadora",
    "trainer",
    "instructor",
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

ROLE_DOMAIN_TERMS = [
    "specialist",
    "especialista",
    "consultant",
    "consultor",
    "advisor",
    "lead",
    "manager",
    "head",
    "director",
]

TRAINING_SIGNAL_TERMS = [
    "training",
    "formação",
    "workshop",
    "workshops",
    "speaker",
    "mentor",
    "coach",
    "facilitator",
    "instructor",
]

EXPLORATORY_TERMS = [
    "people development",
    "career development",
    "talent development",
    "leadership",
    "productivity",
    "quality",
    "marketing strategy",
    "consultant",
    "speaker",
    "workshop",
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

LINKEDIN_NON_PROFILE_PATH_PARTS = {
    "company",
    "jobs",
    "feed",
    "posts",
    "pulse",
    "school",
    "learning",
    "groups",
}

SEARCH_CHALLENGE_MARKERS = [
    "captcha",
    "turnstile",
    "cfconfig",
    "challenge/verify",
    "verificationcomplete",
    "verificationfailed",
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


class SearchConfigurationError(ValueError):
    """Raised when the selected search provider is not configured correctly."""


def generate_search_queries(request: TrainingRequest) -> list[str]:
    topic = request.tema_formacao.strip()
    area = request.area_interna.strip()
    location_part = build_location_part(request.localizacao)
    topic_terms = build_topic_terms(topic, area)
    role_domain_terms = build_role_domain_terms(topic, area)

    queries: list[str] = []
    queries.extend(take_bucket(build_topic_training_queries(topic_terms), "topic_training"))
    queries.extend(
        take_bucket(
            build_topic_role_domain_queries(topic_terms, role_domain_terms),
            "topic_role_domain",
        )
    )
    queries.extend(take_bucket(build_topic_pt_en_queries(topic_terms), "topic_pt_en"))
    queries.extend(
        take_bucket(
            build_topic_training_signal_queries(topic_terms),
            "topic_training_signals",
        )
    )
    queries.extend(
        take_bucket(
            build_topic_location_queries(topic_terms, location_part),
            "topic_location",
        )
    )
    queries.extend(
        take_bucket(
            build_exploratory_linkedin_queries(topic_terms, role_domain_terms),
            "exploratory",
        )
    )

    return dedupe_preserve_order(queries, limit=MAX_SEARCH_QUERIES)


def take_bucket(queries: list[str], bucket_name: str) -> list[str]:
    return queries[: QUERY_BUCKET_QUOTAS[bucket_name]]


def build_topic_terms(topic: str, area: str) -> list[str]:
    clean_topic = topic.strip()
    clean_area = area.strip()
    base_terms = [clean_topic]
    if clean_area:
        base_terms.extend([clean_area, f"{clean_topic} {clean_area}"])

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


def build_role_domain_terms(topic: str, area: str) -> list[str]:
    text = normalize_query_text(f"{topic} {area}")
    terms = [area.strip()] if area.strip() else []

    if has_any(text, ["rh", "recursos humanos", "human resources"]):
        terms.extend(["hr", "people", "people development", "talent development"])

    if has_any(text, ["marketing"]):
        terms.extend(["marketing", "growth", "brand", "marketing strategy"])

    if has_any(text, ["qualidade", "quality"]):
        terms.extend(["quality", "quality management", "continuous improvement"])

    if has_any(text, ["liderança", "lideranca", "leadership"]):
        terms.extend(["leadership", "team leadership", "people management"])

    if has_any(text, ["produtividade", "productivity"]):
        terms.extend(["productivity", "time management", "performance"])

    terms.extend(ROLE_DOMAIN_TERMS)
    return dedupe_preserve_order(terms, limit=12)


def build_topic_training_queries(topic_terms: list[str]) -> list[str]:
    queries: list[str] = []
    for training_term in ["formador", "formadora", "trainer", "speaker", "instructor"]:
        for term in topic_terms:
            quoted_term = quote_term(term)
            queries.append(
                build_query(
                    f"site:linkedin.com/in {quoted_term} {training_term}",
                    LINKEDIN_PEOPLE_EXCLUSIONS,
                )
            )

    return queries


def build_topic_role_domain_queries(
    topic_terms: list[str],
    role_domain_terms: list[str],
) -> list[str]:
    queries: list[str] = []
    for role_term in role_domain_terms[:8]:
        for term in topic_terms[:6]:
            if normalize_query_text(role_term) == normalize_query_text(term):
                continue

            quoted_term = quote_term(term)
            queries.append(
                build_query(
                    f"site:linkedin.com/in {quoted_term} {quote_term(role_term)}",
                    LINKEDIN_PEOPLE_EXCLUSIONS,
                )
            )

    return queries


def build_topic_pt_en_queries(topic_terms: list[str]) -> list[str]:
    queries: list[str] = []
    language_signals = ["formação", "training", "consultoria", "consulting"]
    for language_signal in language_signals:
        for term in topic_terms:
            quoted_term = quote_term(term)
            queries.append(
                build_query(
                    f"site:linkedin.com/in {quoted_term} {language_signal}",
                    LINKEDIN_PEOPLE_EXCLUSIONS,
                )
            )

    return queries


def build_topic_training_signal_queries(topic_terms: list[str]) -> list[str]:
    queries: list[str] = []
    for signal in TRAINING_SIGNAL_TERMS:
        for term in topic_terms[:6]:
            quoted_term = quote_term(term)
            queries.append(
                build_query(
                    f"site:linkedin.com/in {quoted_term} {signal}",
                    LINKEDIN_PEOPLE_EXCLUSIONS,
                )
            )

    return queries


def build_topic_location_queries(
    topic_terms: list[str],
    location_part: str,
) -> list[str]:
    if not location_part:
        return []

    queries: list[str] = []
    for signal in ["trainer", "formador", "speaker", "consultant"]:
        for term in topic_terms:
            quoted_term = quote_term(term)
            queries.append(
                build_query(
                    f"site:linkedin.com/in {quoted_term} {signal}{location_part}",
                    LINKEDIN_PEOPLE_EXCLUSIONS,
                )
            )

    return queries


def build_exploratory_linkedin_queries(
    topic_terms: list[str],
    role_domain_terms: list[str],
) -> list[str]:
    queries: list[str] = []
    exploratory_terms = dedupe_preserve_order(
        [*role_domain_terms, *EXPLORATORY_TERMS],
        limit=16,
    )

    for term in topic_terms[:4]:
        for exploratory_term in exploratory_terms:
            quoted_term = quote_term(term)
            queries.append(
                build_query(
                    f"site:linkedin.com/in {quoted_term} {quote_term(exploratory_term)}",
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

    if settings.search_provider in {"brave", "brave_search"}:
        if not settings.brave_search_api_key:
            raise SearchConfigurationError(
                "BRAVE_SEARCH_API_KEY is required when SEARCH_PROVIDER=brave_search. "
                "Set it in .env or use SEARCH_PROVIDER=mock/public_web for local development."
            )

        return BraveSearchProvider(
            api_key=settings.brave_search_api_key,
            search_url=settings.brave_search_url,
            timeout_seconds=settings.public_search_timeout_seconds,
            max_results=settings.public_search_max_results,
        )

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

        candidates = [
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

        return [
            enrich_public_candidate_metadata(
                candidate=candidate,
                result=PublicSearchResult(
                    title=candidate.cargo or candidate.nome,
                    url=str(candidate.links[0].url),
                    snippet=candidate.excerto or "",
                    matched_query=candidate.matched_query or queries[index],
                    source_domain="linkedin.com",
                ),
                search_rank=index + 1,
                request=request,
            )
            for index, candidate in enumerate(candidates)
        ]


class BraveSearchProvider(SearchProvider):
    def __init__(
        self,
        api_key: str,
        search_url: str = "https://api.search.brave.com/res/v1/web/search",
        timeout_seconds: int = 10,
        max_results: int = 10,
    ) -> None:
        self.api_key = api_key
        self.search_url = search_url
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self.last_diagnostics: dict[str, int | str | None] = {}

    def search(self, request: TrainingRequest) -> list[Candidate]:
        self.reset_diagnostics()
        candidates_by_key: dict[str, Candidate] = {}
        candidate_order: list[str] = []
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

                self.increment_diagnostic("eligible_result_count")
                profile_key = build_linkedin_profile_key(result.url)
                if profile_key is None:
                    continue

                candidate = enrich_public_candidate_metadata(
                    candidate=parse_public_result_to_candidate(
                        result,
                        fonte="brave_search",
                    ),
                    result=result,
                    search_rank=search_rank,
                    request=request,
                )
                if profile_key in candidates_by_key:
                    candidates_by_key[profile_key] = merge_candidate_evidence(
                        candidates_by_key[profile_key],
                        candidate,
                    )
                else:
                    candidates_by_key[profile_key] = candidate
                    candidate_order.append(profile_key)

        return [
            candidates_by_key[key]
            for key in candidate_order[: self.max_results]
        ]

    def reset_diagnostics(self) -> None:
        self.last_diagnostics = {
            "query_count": 0,
            "raw_result_count": 0,
            "eligible_result_count": 0,
            "blocked_query_count": 0,
            "block_reason": None,
        }

    def ensure_diagnostics(self) -> None:
        if not self.last_diagnostics:
            self.reset_diagnostics()

    def increment_diagnostic(self, key: str, amount: int = 1) -> None:
        self.ensure_diagnostics()
        current_value = self.last_diagnostics.get(key)
        if isinstance(current_value, int):
            self.last_diagnostics[key] = current_value + amount

    def _fetch_results(self, query: str) -> list[PublicSearchResult]:
        self.increment_diagnostic("query_count")
        response = requests.get(
            self.search_url,
            params={
                "q": query,
                "count": min(max(self.max_results, 1), 20),
                "country": "PT",
                "search_lang": "pt",
                "ui_lang": "pt-PT",
                "safesearch": "strict",
                "extra_snippets": "true",
            },
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.api_key,
            },
            timeout=self.timeout_seconds,
        )

        status_code = getattr(response, "status_code", None)
        if status_code in {401, 403}:
            raise SearchConfigurationError(
                "Brave Search API rejected the request. Check BRAVE_SEARCH_API_KEY."
            )

        response.raise_for_status()
        results = parse_brave_search_results(response.json(), matched_query=query)
        self.increment_diagnostic("raw_result_count", len(results))
        return results


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
        self.last_diagnostics: dict[str, int | str | None] = {}

    def search(self, request: TrainingRequest) -> list[Candidate]:
        self.reset_diagnostics()
        candidates_by_key: dict[str, Candidate] = {}
        candidate_order: list[str] = []
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

                self.increment_diagnostic("eligible_result_count")
                profile_key = build_linkedin_profile_key(result.url)
                if profile_key is None:
                    continue

                candidate = enrich_public_candidate_metadata(
                    candidate=parse_public_result_to_candidate(result),
                    result=result,
                    search_rank=search_rank,
                    request=request,
                )
                if profile_key in candidates_by_key:
                    candidates_by_key[profile_key] = merge_candidate_evidence(
                        candidates_by_key[profile_key],
                        candidate,
                    )
                else:
                    candidates_by_key[profile_key] = candidate
                    candidate_order.append(profile_key)

        return [
            candidates_by_key[key]
            for key in candidate_order[: self.max_results]
        ]

    def reset_diagnostics(self) -> None:
        self.last_diagnostics = {
            "query_count": 0,
            "raw_result_count": 0,
            "eligible_result_count": 0,
            "blocked_query_count": 0,
            "block_reason": None,
        }

    def ensure_diagnostics(self) -> None:
        if not self.last_diagnostics:
            self.reset_diagnostics()

    def increment_diagnostic(self, key: str, amount: int = 1) -> None:
        self.ensure_diagnostics()
        current_value = self.last_diagnostics.get(key)
        if isinstance(current_value, int):
            self.last_diagnostics[key] = current_value + amount

    def _fetch_results(self, query: str) -> list[PublicSearchResult]:
        self.increment_diagnostic("query_count")
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
        status_code = getattr(response, "status_code", None)

        if is_search_challenge_html(response.text, status_code=status_code):
            self.increment_diagnostic("blocked_query_count")
            self.last_diagnostics["block_reason"] = "captcha_or_search_challenge"
            return []

        results = parse_search_results_html(response.text, matched_query=query)
        self.increment_diagnostic("raw_result_count", len(results))
        return results


def parse_brave_search_results(
    payload: dict,
    matched_query: str,
) -> list[PublicSearchResult]:
    raw_results = payload.get("web", {}).get("results", [])
    if not isinstance(raw_results, list):
        return []

    results: list[PublicSearchResult] = []
    for raw_result in raw_results:
        if not isinstance(raw_result, dict):
            continue

        title = clean_text(str(raw_result.get("title") or ""))
        url = str(raw_result.get("url") or "").strip()
        snippet_parts = [str(raw_result.get("description") or "")]
        extra_snippets = raw_result.get("extra_snippets", [])
        if isinstance(extra_snippets, list):
            snippet_parts.extend(str(snippet) for snippet in extra_snippets)

        snippet = clean_text(" ".join(snippet_parts))
        domain = extract_source_domain(url)

        if not title or not url or not domain:
            continue

        results.append(
            PublicSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                matched_query=matched_query,
                source_domain=domain,
            )
        )

    return results


def is_search_challenge_html(
    html: str,
    status_code: int | None = None,
) -> bool:
    if status_code == 202:
        return True

    lowered_html = html.lower()
    return any(marker in lowered_html for marker in SEARCH_CHALLENGE_MARKERS)


def is_relevant_public_result(
    result: PublicSearchResult,
    request: TrainingRequest,
) -> bool:
    if is_job_board_result(result):
        return False

    return is_eligible_linkedin_profile_result(result)


def is_eligible_linkedin_profile_result(result: PublicSearchResult) -> bool:
    return (
        is_probably_linkedin_profile(result)
        and extract_linkedin_profile_slug(result.url) is not None
        and not is_irrelevant_linkedin_result(result)
    )


def is_irrelevant_linkedin_result(result: PublicSearchResult) -> bool:
    url = result.url.lower()
    text = searchable_result_text(result)
    blocked_terms = [
        "linkedin job",
        "jobs on linkedin",
        "vagas",
        "ofertas de emprego",
        "company page",
        "school page",
        "pulse",
        "feed",
    ]

    if any(f"/{part}/" in url for part in LINKEDIN_NON_PROFILE_PATH_PARTS):
        return True

    return any(term in text for term in blocked_terms)


def build_linkedin_profile_key(raw_url: str) -> str | None:
    slug = extract_linkedin_profile_slug(raw_url)
    if slug:
        return f"linkedin:{slug}"

    return normalize_linkedin_profile_url(raw_url)


def normalize_linkedin_profile_url(raw_url: str) -> str | None:
    slug = extract_linkedin_profile_slug(raw_url)
    if not slug:
        return None

    return f"https://www.linkedin.com/in/{slug}"


def extract_linkedin_profile_slug(raw_url: str) -> str | None:
    parsed_url = urlparse(raw_url)
    domain = parsed_url.netloc.lower().removeprefix("www.")
    if domain not in {"linkedin.com", "linkedin.pt"}:
        return None

    path_parts = [
        part
        for part in parsed_url.path.split("/")
        if part
    ]
    if len(path_parts) < 2:
        return None

    if path_parts[0].lower() != "in":
        return None

    slug = path_parts[1].strip().lower()
    if not slug or slug in LINKEDIN_NON_PROFILE_PATH_PARTS:
        return None

    return slug


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
    request: TrainingRequest,
) -> Candidate:
    normalized_profile_url = normalize_linkedin_profile_url(result.url)
    profile_slug = extract_linkedin_profile_slug(result.url)
    links = candidate.links
    if normalized_profile_url:
        links = [
            PublicLink(
                label="LinkedIn",
                url=normalized_profile_url,
            )
        ]

    return candidate.model_copy(
        update={
            "links": links,
            "search_rank": search_rank,
            "search_ranks": [search_rank],
            "matched_queries": [result.matched_query],
            "evidence_titles": [result.title],
            "evidence_snippets": [result.snippet] if result.snippet else [],
            "training_signals": collect_training_signals(result),
            "topic_signals": collect_topic_signals(result, request),
            "functional_signals": collect_functional_signals(result, request),
            "evidence_query_count": 1,
            "snippet_raw": result.snippet or None,
            "result_title_raw": result.title,
            "profile_type": detect_profile_type(result),
            "is_probably_linkedin_profile": is_probably_linkedin_profile(result),
            "linkedin_profile_url": normalized_profile_url,
            "linkedin_profile_slug": profile_slug,
        }
    )


def merge_candidate_evidence(existing: Candidate, incoming: Candidate) -> Candidate:
    best_candidate = existing
    if is_better_rank(incoming.search_rank, existing.search_rank):
        best_candidate = incoming

    merged_queries = merge_unique(existing.matched_queries, incoming.matched_queries)
    merged_ranks = sorted(set([*existing.search_ranks, *incoming.search_ranks]))
    merged_titles = merge_unique(existing.evidence_titles, incoming.evidence_titles)
    merged_snippets = merge_unique(existing.evidence_snippets, incoming.evidence_snippets)

    return existing.model_copy(
        update={
            "cargo": best_candidate.cargo or existing.cargo,
            "empresa": best_candidate.empresa or existing.empresa,
            "localizacao": best_candidate.localizacao or existing.localizacao,
            "excerto": best_candidate.excerto or existing.excerto,
            "matched_query": best_candidate.matched_query or existing.matched_query,
            "search_rank": best_candidate.search_rank or existing.search_rank,
            "search_ranks": merged_ranks,
            "matched_queries": merged_queries,
            "evidence_titles": merged_titles,
            "evidence_snippets": merged_snippets,
            "training_signals": merge_unique(
                existing.training_signals,
                incoming.training_signals,
            ),
            "topic_signals": merge_unique(
                existing.topic_signals,
                incoming.topic_signals,
            ),
            "functional_signals": merge_unique(
                existing.functional_signals,
                incoming.functional_signals,
            ),
            "evidence_query_count": len(merged_queries),
            "snippet_raw": best_candidate.snippet_raw or existing.snippet_raw,
            "result_title_raw": best_candidate.result_title_raw
            or existing.result_title_raw,
        }
    )


def is_better_rank(new_rank: int | None, existing_rank: int | None) -> bool:
    if new_rank is None:
        return False

    if existing_rank is None:
        return True

    return new_rank < existing_rank


def merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged: list[str] = []
    for value in [*first, *second]:
        clean_value = value.strip() if isinstance(value, str) else value
        if clean_value and clean_value not in merged:
            merged.append(clean_value)

    return merged


def collect_training_signals(result: PublicSearchResult) -> list[str]:
    text = searchable_result_text(result)
    return [
        signal
        for signal in TRAINING_EXPERIENCE_SIGNAL_TERMS
        if signal in text
    ]


def collect_topic_signals(
    result: PublicSearchResult,
    request: TrainingRequest,
) -> list[str]:
    text = searchable_result_text(result)
    topic = normalize_query_text(request.tema_formacao)
    topic_tokens = [
        token
        for token in re.findall(r"[\w+#.-]+", topic)
        if len(token) >= 2
    ]
    signals = [topic] if topic and topic in text else []
    signals.extend(token for token in topic_tokens if token in text)
    return dedupe_preserve_order(signals, limit=12)


def collect_functional_signals(
    result: PublicSearchResult,
    request: TrainingRequest,
) -> list[str]:
    text = searchable_result_text(result)
    area = normalize_query_text(request.area_interna)
    if not area:
        return []

    area_tokens = [
        token
        for token in re.findall(r"[\w+#.-]+", area)
        if len(token) >= 2
    ]
    signals = [area] if area in text else []
    signals.extend(token for token in area_tokens if token in text)
    return dedupe_preserve_order(signals, limit=12)


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
    return extract_linkedin_profile_slug(result.url) is not None


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
