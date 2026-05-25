import pytest
from pydantic import ValidationError

from bot.models import (
    Candidate,
    CandidateScore,
    ContactChannel,
    ProfileType,
    PublicLink,
    ScoredCandidate,
    TrainingFormat,
    TrainingRequest,
)


def test_training_request_accepts_required_fields() -> None:
    request = TrainingRequest(
        tema_formacao="Python para automacao",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Porto",
        formato=TrainingFormat.presencial,
        numero_participantes=25,
    )

    assert request.tema_formacao == "Python para automacao"
    assert request.area_interna == "Tecnologia"
    assert request.formato == TrainingFormat.presencial
    assert request.numero_participantes == 25


def test_training_request_accepts_short_acronym_topic() -> None:
    request = TrainingRequest(
        tema_formacao="AI",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )

    assert request.tema_formacao == "AI"


def test_training_request_only_requires_topic() -> None:
    request = TrainingRequest(tema_formacao="Power BI")

    assert request.tema_formacao == "Power BI"
    assert request.area_interna == ""
    assert request.descricao_contexto == ""
    assert request.localizacao is None


def test_training_request_rejects_invalid_participant_count() -> None:
    with pytest.raises(ValidationError):
        TrainingRequest(
            tema_formacao="Python",
            area_interna="TI",
            descricao_contexto="Sessao interna para membros da JuniFEUP.",
            numero_participantes=0,
        )


def test_candidate_accepts_public_links() -> None:
    candidate = Candidate(
        nome="Ana Silva",
        cargo="Data Scientist",
        empresa="Tech Company",
        localizacao="Porto",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/ana-silva",
            )
        ],
        email_publico="ana@example.com",
        fonte="mock",
        matched_query="Python Tecnologia freelancer",
        source_domain="linkedin.com",
        search_rank=1,
        snippet_raw="Ana Silva is a freelance trainer.",
        result_title_raw="Ana Silva - Freelance Python Trainer | LinkedIn",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
    )

    assert candidate.nome == "Ana Silva"
    assert candidate.cargo == "Data Scientist"
    assert len(candidate.links) == 1
    assert candidate.links[0].label == "LinkedIn"
    assert candidate.matched_query == "Python Tecnologia freelancer"
    assert candidate.source_domain == "linkedin.com"
    assert candidate.search_rank == 1
    assert candidate.snippet_raw == "Ana Silva is a freelance trainer."
    assert candidate.result_title_raw == "Ana Silva - Freelance Python Trainer | LinkedIn"
    assert candidate.profile_type == ProfileType.linkedin_profile
    assert candidate.is_probably_linkedin_profile is True


def test_candidate_defaults_public_profile_metadata() -> None:
    candidate = Candidate(
        nome="Ana Silva",
        fonte="manual",
    )

    assert candidate.search_rank is None
    assert candidate.search_ranks == []
    assert candidate.matched_queries == []
    assert candidate.evidence_query_count == 0
    assert candidate.training_signals == []
    assert candidate.topic_signals == []
    assert candidate.snippet_raw is None
    assert candidate.result_title_raw is None
    assert candidate.profile_type == ProfileType.unknown
    assert candidate.is_probably_linkedin_profile is False


def test_candidate_accepts_none_for_optional_public_metadata() -> None:
    candidate = Candidate(
        nome="Ana Silva",
        fonte="public_web",
        matched_query=None,
        source_domain=None,
        search_rank=None,
        snippet_raw=None,
        result_title_raw=None,
    )

    assert candidate.matched_query is None
    assert candidate.source_domain is None
    assert candidate.search_rank is None
    assert candidate.snippet_raw is None
    assert candidate.result_title_raw is None


def test_candidate_rejects_invalid_search_rank() -> None:
    with pytest.raises(ValidationError):
        Candidate(
            nome="Ana Silva",
            fonte="public_web",
            search_rank=0,
        )


def test_candidate_rejects_invalid_profile_type() -> None:
    with pytest.raises(ValidationError):
        Candidate(
            nome="Ana Silva",
            fonte="public_web",
            profile_type="linkedin_person",
        )


def test_profile_type_enum_values_are_stable() -> None:
    assert ProfileType.linkedin_profile.value == "linkedin_profile"
    assert ProfileType.company_page.value == "company_page"
    assert ProfileType.job_board.value == "job_board"
    assert ProfileType.article_or_post.value == "article_or_post"
    assert ProfileType.unknown.value == "unknown"


def test_score_rejects_values_above_100() -> None:
    with pytest.raises(ValidationError):
        CandidateScore(
            fit_tematico=120,
            fit_funcional=80,
            experiencia_formacao=70,
            localizacao_score=90,
            contactabilidade=60,
            credibilidade_publica=75,
            score_total=82,
            motivo="Score invalido porque um subscore passa de 100.",
        )


def test_score_rejects_values_below_0() -> None:
    with pytest.raises(ValidationError):
        CandidateScore(
            fit_tematico=90,
            fit_funcional=-1,
            experiencia_formacao=70,
            localizacao_score=90,
            contactabilidade=60,
            credibilidade_publica=75,
            score_total=82,
            motivo="Score invalido porque um subscore esta abaixo de 0.",
        )


def test_scored_candidate_has_recommended_channel() -> None:
    candidate = Candidate(
        nome="Joao Pereira",
        cargo="Formador Python",
        empresa="Freelancer",
        fonte="mock",
    )

    score = CandidateScore(
        fit_tematico=90,
        fit_funcional=80,
        experiencia_formacao=85,
        localizacao_score=70,
        contactabilidade=95,
        credibilidade_publica=75,
        score_total=83,
        motivo="Bom alinhamento com o tema e contacto direto disponivel.",
    )

    scored_candidate = ScoredCandidate(
        candidato=candidate,
        score=score,
        canal_recomendado=ContactChannel.email,
    )

    assert scored_candidate.candidato.nome == "Joao Pereira"
    assert scored_candidate.score.score_total == 83
    assert scored_candidate.canal_recomendado == ContactChannel.email
