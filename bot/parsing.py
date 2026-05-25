from dataclasses import dataclass
import base64
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from bot.models import Candidate, PublicLink


@dataclass(frozen=True)
class PublicSearchResult:
    title: str
    url: str
    snippet: str
    matched_query: str
    source_domain: str


def parse_search_results_html(html: str, matched_query: str) -> list[PublicSearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[PublicSearchResult] = []

    for result_node in soup.select(".result, .web-result, li.b_algo"):
        link_node = result_node.select_one("h2 a")
        if link_node is None:
            link_node = result_node.select_one("a.result__a, a")
        if link_node is None:
            continue

        raw_url = link_node.get("href")
        if not raw_url:
            continue

        title = clean_text(link_node.get_text(" "))
        url = normalize_result_url(raw_url)
        domain = extract_source_domain(url)
        snippet = extract_snippet(result_node)

        if not title or not domain:
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


def parse_public_result_to_candidate(
    result: PublicSearchResult,
    fonte: str = "public_web",
) -> Candidate:
    is_linkedin = "linkedin.com" in result.source_domain
    name = infer_candidate_name(result.title)

    return Candidate(
        nome=name,
        cargo=infer_candidate_role(result.title, result.snippet),
        empresa=None,
        localizacao=None,
        links=[
            PublicLink(
                label="LinkedIn" if is_linkedin else "Fonte pública",
                url=result.url,
            )
        ],
        email_publico=None,
        fonte=fonte,
        excerto=result.snippet or result.title,
        matched_query=result.matched_query,
        source_domain=result.source_domain,
    )


def extract_source_domain(url: str) -> str:
    parsed_url = urlparse(url)
    return parsed_url.netloc.removeprefix("www.").lower()


def normalize_result_url(raw_url: str) -> str:
    parsed_url = urlparse(raw_url)

    if parsed_url.netloc.endswith("bing.com") and parsed_url.path.startswith("/ck/"):
        query_params = parse_qs(parsed_url.query)
        if "u" in query_params:
            decoded_url = decode_bing_url(query_params["u"][0])
            if decoded_url:
                return decoded_url

    if parsed_url.netloc and parsed_url.scheme:
        return raw_url

    query_params = parse_qs(parsed_url.query)
    if "uddg" in query_params:
        return unquote(query_params["uddg"][0])

    return raw_url


def decode_bing_url(value: str) -> str | None:
    if not value.startswith("a1"):
        return None

    encoded_url = value[2:]
    padding = "=" * (-len(encoded_url) % 4)

    try:
        return base64.urlsafe_b64decode(encoded_url + padding).decode("utf-8")
    except ValueError:
        return None


def extract_snippet(result_node) -> str:
    snippet_node = result_node.select_one(
        ".result__snippet, .result__body, .b_caption p, .snippet"
    )
    if snippet_node is None:
        return ""

    return clean_text(snippet_node.get_text(" "))


def infer_candidate_name(title: str) -> str:
    separators = [" | ", " - ", " – ", " — ", " LinkedIn"]
    name = title

    for separator in separators:
        if separator in name:
            name = name.split(separator, 1)[0]

    name = clean_text(name)
    return name if len(name) >= 2 else "Candidato público"


def infer_candidate_role(title: str, snippet: str) -> str | None:
    text = clean_text(" ".join([title, snippet]))
    lowered = text.lower()

    role_keywords = [
        "freelance",
        "freelancer",
        "formador",
        "formadora",
        "trainer",
        "consultor",
        "consultora",
        "speaker",
    ]

    if any(keyword in lowered for keyword in role_keywords):
        return text[:120]

    return None


def clean_text(value: str) -> str:
    return " ".join(value.split())
