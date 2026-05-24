from bot.parsing import (
    decode_bing_url,
    extract_source_domain,
    normalize_result_url,
    parse_public_result_to_candidate,
    parse_search_results_html,
)


def test_extract_source_domain_removes_www() -> None:
    domain = extract_source_domain("https://www.linkedin.com/in/ana-silva")

    assert domain == "linkedin.com"


def test_parse_search_results_html_extracts_public_results() -> None:
    html = """
    <html>
      <body>
        <div class="result">
          <a class="result__a" href="https://www.linkedin.com/in/ana-silva">
            Ana Silva - Freelance Python Trainer | LinkedIn
          </a>
          <a class="result__snippet">
            Freelance trainer and workshop facilitator.
          </a>
        </div>
      </body>
    </html>
    """

    results = parse_search_results_html(
        html,
        matched_query="site:linkedin.com/in Python freelancer",
    )

    assert len(results) == 1
    assert results[0].title == "Ana Silva - Freelance Python Trainer | LinkedIn"
    assert results[0].source_domain == "linkedin.com"
    assert results[0].matched_query == "site:linkedin.com/in Python freelancer"


def test_parse_public_result_to_candidate_keeps_metadata() -> None:
    html = """
    <div class="result">
      <a class="result__a" href="https://joaopereira.example.com">
        João Pereira - Consultor Freelance
      </a>
      <a class="result__snippet">
        Consultor freelance e formador em Python.
      </a>
    </div>
    """

    result = parse_search_results_html(html, matched_query="Python freelancer")[0]
    candidate = parse_public_result_to_candidate(result)

    assert candidate.nome == "João Pereira"
    assert candidate.fonte == "public_web"
    assert candidate.matched_query == "Python freelancer"
    assert candidate.source_domain == "joaopereira.example.com"
    assert candidate.links[0].label == "Fonte pública"


def test_normalize_result_url_decodes_bing_redirect() -> None:
    raw_url = (
        "https://www.bing.com/ck/a?"
        "u=a1aHR0cHM6Ly93d3cubGlua2VkaW4uY29tL2luL2FuYS1zaWx2YQ"
    )

    normalized_url = normalize_result_url(raw_url)

    assert normalized_url == "https://www.linkedin.com/in/ana-silva"


def test_decode_bing_url_returns_none_for_unexpected_value() -> None:
    assert decode_bing_url("https://example.com") is None
