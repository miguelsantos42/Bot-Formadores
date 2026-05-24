from bot.messages import generate_outreach_messages
from bot.models import (
    Candidate,
    CandidateScore,
    ContactChannel,
    ScoredCandidate,
    TrainingRequest,
)


def make_request() -> TrainingRequest:
    return TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
    )


def make_scored_candidate() -> ScoredCandidate:
    candidate = Candidate(
        nome="Ana Silva",
        cargo="Formadora Python",
        empresa="Tech Learning Studio",
        email_publico="ana@example.com",
        fonte="test",
    )

    score = CandidateScore(
        fit_tematico=95,
        fit_funcional=80,
        experiencia_formacao=90,
        localizacao_score=70,
        contactabilidade=100,
        credibilidade_publica=80,
        score_total=88,
        motivo="forte alinhamento com o tema; contacto direto disponivel.",
    )

    return ScoredCandidate(
        candidato=candidate,
        score=score,
        canal_recomendado=ContactChannel.email,
    )


def test_generate_outreach_messages_returns_email_and_linkedin_message() -> None:
    messages = generate_outreach_messages(
        request=make_request(),
        scored_candidate=make_scored_candidate(),
    )

    assert messages.email_inicial
    assert messages.mensagem_linkedin


def test_email_mentions_candidate_name_and_training_topic() -> None:
    messages = generate_outreach_messages(
        request=make_request(),
        scored_candidate=make_scored_candidate(),
    )

    assert "Ola Ana" in messages.email_inicial
    assert "Python" in messages.email_inicial
    assert "JuniFEUP" in messages.email_inicial


def test_linkedin_message_is_short() -> None:
    messages = generate_outreach_messages(
        request=make_request(),
        scored_candidate=make_scored_candidate(),
    )

    assert len(messages.mensagem_linkedin) <= 500


def test_linkedin_message_mentions_training_topic() -> None:
    messages = generate_outreach_messages(
        request=make_request(),
        scored_candidate=make_scored_candidate(),
    )

    assert "Python" in messages.mensagem_linkedin
