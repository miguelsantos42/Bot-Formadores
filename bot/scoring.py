from bot.models import (
    Candidate,
    CandidateScore,
    ContactChannel,
    ScoredCandidate,
    TrainingRequest,
)


TRAINING_KEYWORDS = [
    "formador",
    "formadora",
    "trainer",
    "speaker",
    "workshop",
    "palestra",
    "consultor",
    "consultora",
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

    score_total = round(
        fit_tematico * 0.30
        + fit_funcional * 0.20
        + experiencia_formacao * 0.15
        + localizacao_score * 0.10
        + contactabilidade * 0.15
        + credibilidade_publica * 0.10
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
    haystack = normalize_text(
        " ".join(
            [
                candidate.cargo or "",
                candidate.empresa or "",
                candidate.excerto or "",
            ]
        )
    )
    topic = normalize_text(request.tema_formacao)

    if topic in haystack:
        return 95

    topic_terms = topic.split()
    matched_terms = [term for term in topic_terms if term in haystack]

    if matched_terms:
        return 75

    return 45


def calculate_functional_fit(
    request: TrainingRequest,
    candidate: Candidate,
) -> int:
    haystack = normalize_text(
        " ".join(
            [
                candidate.cargo or "",
                candidate.empresa or "",
                candidate.excerto or "",
            ]
        )
    )
    area = normalize_text(request.area_interna)

    if area in haystack:
        return 85

    if any(keyword in haystack for keyword in TRAINING_KEYWORDS):
        return 70

    return 50


def calculate_training_experience(candidate: Candidate) -> int:
    haystack = normalize_text(
        " ".join(
            [
                candidate.cargo or "",
                candidate.excerto or "",
            ]
        )
    )

    if "formador" in haystack or "formadora" in haystack or "trainer" in haystack:
        return 90

    if "workshop" in haystack or "speaker" in haystack or "palestra" in haystack:
        return 80

    if "consultor" in haystack or "consultora" in haystack:
        return 65

    return 40


def calculate_location_score(
    request: TrainingRequest,
    candidate: Candidate,
) -> int:
    if not request.localizacao:
        return 70

    if not candidate.localizacao:
        return 50

    requested_location = normalize_text(request.localizacao)
    candidate_location = normalize_text(candidate.localizacao)

    if requested_location == candidate_location:
        return 100

    if requested_location in candidate_location or candidate_location in requested_location:
        return 85

    if request.formato.value in {"remoto", "hibrido", "indiferente"}:
        return 70

    return 35


def calculate_contactability(candidate: Candidate) -> int:
    if candidate.email_publico:
        return 100

    if has_linkedin(candidate):
        return 75

    if candidate.links:
        return 55

    return 25


def calculate_public_credibility(candidate: Candidate) -> int:
    score = 40

    if candidate.links:
        score += 20

    if has_linkedin(candidate):
        score += 20

    if candidate.empresa:
        score += 10

    if candidate.excerto:
        score += 10

    return min(score, 100)


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


def build_score_reason(
    fit_tematico: int,
    experiencia_formacao: int,
    contactabilidade: int,
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

    return "; ".join(reasons) + "."


def normalize_text(value: str) -> str:
    return value.strip().lower()
