from bot.models import (
    Candidate,
    ContactChannel,
    PublicLink,
    TrainingFormat,
    TrainingRequest,
)
from bot.scoring import (
    calculate_contactability,
    calculate_location_score,
    recommend_contact_channel,
    score_candidates,
)


def make_request() -> TrainingRequest:
    return TrainingRequest(
        tema_formacao="Python",
        area_interna="Tecnologia",
        descricao_contexto="Sessao interna para membros da JuniFEUP.",
        localizacao="Porto",
        formato=TrainingFormat.presencial,
        numero_participantes=20,
    )


def test_score_candidates_orders_by_total_score() -> None:
    request = make_request()

    strong_candidate = Candidate(
        nome="Ana Silva",
        cargo="Formadora Python",
        empresa="Tech Learning Studio",
        localizacao="Porto",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/ana-silva",
            )
        ],
        email_publico="ana@example.com",
        fonte="test",
        excerto="Experiencia em workshops de Python para equipas tecnicas.",
    )

    weak_candidate = Candidate(
        nome="Carlos Lima",
        cargo="Gestor de projeto",
        empresa="Empresa X",
        localizacao="Lisboa",
        links=[],
        email_publico=None,
        fonte="test",
        excerto="Perfil publico generalista.",
    )

    scored = score_candidates(request, [weak_candidate, strong_candidate])

    assert scored[0].candidato.nome == "Ana Silva"
    assert scored[0].score.score_total > scored[1].score.score_total


def test_email_is_recommended_when_public_email_exists() -> None:
    candidate = Candidate(
        nome="Ana Silva",
        email_publico="ana@example.com",
        fonte="test",
    )

    channel = recommend_contact_channel(candidate)

    assert channel == ContactChannel.email


def test_linkedin_is_recommended_when_no_email_but_linkedin_exists() -> None:
    candidate = Candidate(
        nome="Joao Pereira",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/joao-pereira",
            )
        ],
        fonte="test",
    )

    channel = recommend_contact_channel(candidate)

    assert channel == ContactChannel.linkedin


def test_form_is_recommended_without_email_or_linkedin() -> None:
    candidate = Candidate(
        nome="Mariana Costa",
        links=[
            PublicLink(
                label="Website",
                url="https://example.com/mariana-costa",
            )
        ],
        fonte="test",
    )

    channel = recommend_contact_channel(candidate)

    assert channel == ContactChannel.formulario


def test_contactability_is_high_with_public_email() -> None:
    candidate = Candidate(
        nome="Ana Silva",
        email_publico="ana@example.com",
        fonte="test",
    )

    assert calculate_contactability(candidate) == 100


def test_location_score_is_high_when_locations_match() -> None:
    request = make_request()
    candidate = Candidate(
        nome="Ana Silva",
        localizacao="Porto",
        fonte="test",
    )

    assert calculate_location_score(request, candidate) == 100


def test_location_score_is_lower_for_different_presential_location() -> None:
    request = make_request()
    candidate = Candidate(
        nome="Ana Silva",
        localizacao="Lisboa",
        fonte="test",
    )

    assert calculate_location_score(request, candidate) == 35
