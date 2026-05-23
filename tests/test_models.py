import pytest
from pydantic import ValidationError

from bot.models import (
    Candidate,
    CandidateScore,
    ContactChannel,
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
    )

    assert candidate.nome == "Ana Silva"
    assert candidate.cargo == "Data Scientist"
    assert len(candidate.links) == 1
    assert candidate.links[0].label == "LinkedIn"


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
