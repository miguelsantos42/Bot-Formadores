from bot.models import (
    Candidate,
    CandidateScore,
    ContactChannel,
    ProfileType,
    ScoredCandidate,
    TrainingRequest,
)


PRIMARY_TRAINING_SIGNALS = [
    "formador",
    "formadora",
    "trainer",
    "speaker",
    "mentor",
    "workshop",
    "facilitator",
    "coach",
]

SECONDARY_TRAINING_SIGNALS = [
    "consultant",
    "consultor",
    "consultora",
    "training",
    "formação",
    "formacao",
    "palestra",
    "facilitação",
    "facilitacao",
]

PORTO_LOCATION_TERMS = [
    "porto",
    "grande porto",
    "maia",
    "matosinhos",
    "vila nova de gaia",
    "gaia",
]

NORTH_LOCATION_TERMS = [
    "norte",
    "north",
    "porto",
    "braga",
    "guimarães",
    "guimaraes",
    "viana do castelo",
    "vila real",
    "bragança",
    "braganca",
]

PORTUGAL_LOCATION_TERMS = [
    "portugal",
    "português",
    "portugues",
    "portuguese",
]


def score_candidates(
    request: TrainingRequest,
    candidates: list[Candidate],
) -> list[ScoredCandidate]:
    scored_candidates = [
        score_candidate(request=request, candidate=candidate)
        for candidate in candidates
    ]

    return sorted(
        scored_candidates,
        key=lambda scored_candidate: scored_candidate.score.score_total,
        reverse=True,
    )


def score_candidate(
    request: TrainingRequest,
    candidate: Candidate,
) -> ScoredCandidate:
    fit_tematico = calculate_thematic_fit(request, candidate)
    fit_funcional = calculate_functional_fit(request, candidate)
    experiencia_formacao = calculate_training_experience(candidate)
    localizacao_score = calculate_location_score(request, candidate)
    contactabilidade = calculate_contactability(candidate)
    credibilidade_publica = calculate_public_credibility(candidate)

    base_score_total = round(
        fit_tematico * 0.30
        + fit_funcional * 0.20
        + experiencia_formacao * 0.15
        + localizacao_score * 0.10
        + contactabilidade * 0.15
        + credibilidade_publica * 0.10
    )
    score_total = clamp_score(
        base_score_total + profile_type_adjustment(candidate)
    )

    score = CandidateScore(
        fit_tematico=fit_tematico,
        fit_funcional=fit_funcional,
        experiencia_formacao=experiencia_formacao,
        localizacao_score=localizacao_score,
        contactabilidade=contactabilidade,
        credibilidade_publica=credibilidade_publica,
        score_total=score_total,
        motivo=build_score_reason(
            fit_tematico=fit_tematico,
            experiencia_formacao=experiencia_formacao,
            contactabilidade=contactabilidade,
            credibilidade_publica=credibilidade_publica,
        ),
    )

    return ScoredCandidate(
        candidato=candidate,
        score=score,
        canal_recomendado=recommend_contact_channel(candidate),
    )


def calculate_thematic_fit(
    request: TrainingRequest,
    candidate: Candidate,
) -> int:
    text = candidate_public_text(candidate)
    topic = normalize_text(request.tema_formacao)
    topic_terms = topic.split()

    if topic in text:
        base_score = 90
    elif any(term in text for term in topic_terms):
        base_score = 70
    else:
        base_score = 45

    return max(base_score, headline_match_score(request, candidate))


def headline_match_score(
    request: TrainingRequest,
    candidate: Candidate,
) -> int:
    headline_text = normalize_text(
        " ".join(
            [
                candidate.result_title_raw or "",
                candidate.snippet_raw or "",
            ]
        )
    )
    if not headline_text:
        return 0

    topic = normalize_text(request.tema_formacao)
    area = normalize_text(request.area_interna)
    score = 45

    if topic in headline_text:
        score += 30
    elif any(term in headline_text for term in topic.split()):
        score += 15

    if area in headline_text:
        score += 10

    if trainer_signal_score(candidate) >= 80:
        score += 10

    return clamp_score(score)


def calculate_functional_fit(
    request: TrainingRequest,
    candidate: Candidate,
) -> int:
    text = candidate_public_text(candidate)
    area = normalize_text(request.area_interna)
    training_signal = trainer_signal_score(candidate)

    if area in text and training_signal >= 80:
        return 90

    if area in text:
        return 80

    if training_signal >= 85:
        return 75

    if training_signal >= 65:
        return 65

    return 45


def calculate_training_experience(candidate: Candidate) -> int:
    return trainer_signal_score(candidate)


def trainer_signal_score(candidate: Candidate) -> int:
    text = candidate_public_text(candidate)
    primary_matches = count_matches(text, PRIMARY_TRAINING_SIGNALS)
    secondary_matches = count_matches(text, SECONDARY_TRAINING_SIGNALS)

    if primary_matches >= 2:
        return 95

    if primary_matches == 1 and secondary_matches >= 1:
        return 90

    if primary_matches == 1:
        return 82

    if secondary_matches >= 2:
        return 72

    if secondary_matches == 1:
        return 62

    return 30


def calculate_location_score(
    request: TrainingRequest,
    candidate: Candidate,
) -> int:
    if not request.localizacao:
        return 70

    requested_location = normalize_text(request.localizacao)
    candidate_location_text = normalize_text(
        " ".join(
            [
                candidate.localizacao or "",
                candidate.result_title_raw or "",
                candidate.snippet_raw or "",
                candidate.excerto or "",
            ]
        )
    )

    if not candidate_location_text:
        return 50

    if requested_location in candidate_location_text:
        return 100

    if is_porto_location(requested_location):
        if has_any(candidate_location_text, PORTO_LOCATION_TERMS):
            return 95

        if has_any(candidate_location_text, NORTH_LOCATION_TERMS):
            return 85

        if has_any(candidate_location_text, PORTUGAL_LOCATION_TERMS):
            return 70

    if is_north_location(requested_location):
        if has_any(candidate_location_text, NORTH_LOCATION_TERMS):
            return 90

        if has_any(candidate_location_text, PORTUGAL_LOCATION_TERMS):
            return 75

    if is_portugal_location(requested_location):
        if has_any(
            candidate_location_text,
            PORTUGAL_LOCATION_TERMS + NORTH_LOCATION_TERMS,
        ):
            return 90

    if request.formato.value in {"remoto", "hibrido", "indiferente"}:
        return 70

    return 35


def calculate_contactability(candidate: Candidate) -> int:
    if candidate.email_publico:
        return 100

    if has_linkedin_profile(candidate):
        return 85

    if has_linkedin(candidate):
        return 75

    if candidate.links:
        return 55

    return 25


def calculate_public_credibility(candidate: Candidate) -> int:
    score = linkedin_profile_quality_score(candidate)

    if candidate.profile_type == ProfileType.personal_site:
        score = max(score, 70)

    if candidate.links:
        score += 5

    if candidate.source_domain:
        score += 5

    if candidate.result_title_raw or candidate.snippet_raw:
        score += 8

    if trainer_signal_score(candidate) >= 80:
        score += 7

    if candidate.search_rank is not None and candidate.search_rank <= 3:
        score += 5

    return clamp_score(score)


def linkedin_profile_quality_score(candidate: Candidate) -> int:
    if has_linkedin_profile(candidate):
        score = 82

        if candidate.is_probably_linkedin_profile:
            score += 8

        if candidate.profile_type == ProfileType.linkedin_profile:
            score += 6

        if candidate.search_rank == 1:
            score += 4
        elif candidate.search_rank is not None and candidate.search_rank <= 3:
            score += 2

        return clamp_score(score)

    if candidate.profile_type == ProfileType.company_page or has_linkedin_company(candidate):
        return 55

    if candidate.profile_type == ProfileType.job_board:
        return 20

    if candidate.profile_type == ProfileType.article_or_post:
        return 35

    if candidate.profile_type == ProfileType.personal_site:
        return 70

    if candidate.links:
        return 50

    return 35


def profile_type_adjustment(candidate: Candidate) -> int:
    if candidate.profile_type == ProfileType.linkedin_profile:
        return 5

    if candidate.profile_type == ProfileType.personal_site:
        return 3

    if candidate.profile_type == ProfileType.company_page:
        return -8

    if candidate.profile_type == ProfileType.article_or_post:
        return -12

    if candidate.profile_type == ProfileType.job_board:
        return -25

    return 0


def recommend_contact_channel(candidate: Candidate) -> ContactChannel:
    if candidate.email_publico:
        return ContactChannel.email

    if has_linkedin(candidate):
        return ContactChannel.linkedin

    return ContactChannel.formulario


def has_linkedin(candidate: Candidate) -> bool:
    return any(
        "linkedin.com" in str(link.url).lower()
        or "linkedin" in link.label.lower()
        for link in candidate.links
    )


def has_linkedin_profile(candidate: Candidate) -> bool:
    if candidate.profile_type == ProfileType.linkedin_profile:
        return True

    if candidate.is_probably_linkedin_profile:
        return True

    return any(
        "linkedin.com/in/" in str(link.url).lower()
        for link in candidate.links
    )


def has_linkedin_company(candidate: Candidate) -> bool:
    if candidate.profile_type == ProfileType.company_page:
        return True

    return any(
        "linkedin.com/company/" in str(link.url).lower()
        for link in candidate.links
    )


def build_score_reason(
    fit_tematico: int,
    experiencia_formacao: int,
    contactabilidade: int,
    credibilidade_publica: int,
) -> str:
    reasons: list[str] = []

    if fit_tematico >= 90:
        reasons.append("forte alinhamento com o tema")
    elif fit_tematico >= 70:
        reasons.append("alinhamento parcial com o tema")
    else:
        reasons.append("alinhamento temático limitado")

    if experiencia_formacao >= 80:
        reasons.append("sinais públicos de experiência em formação")
    elif experiencia_formacao >= 60:
        reasons.append("alguma proximidade a atividades de formação")
    else:
        reasons.append("pouca evidência pública de experiência em formação")

    if contactabilidade >= 90:
        reasons.append("contacto direto disponível")
    elif contactabilidade >= 70:
        reasons.append("contacto viável via LinkedIn")
    else:
        reasons.append("contacto menos direto")

    if credibilidade_publica >= 85:
        reasons.append("fonte pública forte")

    return "; ".join(reasons) + "."


def candidate_public_text(candidate: Candidate) -> str:
    return normalize_text(
        " ".join(
            [
                candidate.nome,
                candidate.cargo or "",
                candidate.empresa or "",
                candidate.localizacao or "",
                candidate.excerto or "",
                candidate.result_title_raw or "",
                candidate.snippet_raw or "",
                candidate.matched_query or "",
                candidate.source_domain or "",
            ]
        )
    )


def count_matches(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def is_porto_location(value: str) -> bool:
    return has_any(value, PORTO_LOCATION_TERMS)


def is_north_location(value: str) -> bool:
    return has_any(value, NORTH_LOCATION_TERMS)


def is_portugal_location(value: str) -> bool:
    return has_any(value, PORTUGAL_LOCATION_TERMS)


def clamp_score(value: int) -> int:
    return max(0, min(value, 100))


def normalize_text(value: str) -> str:
    return value.strip().lower()
