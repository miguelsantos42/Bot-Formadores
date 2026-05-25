from bot.models import (
    Candidate,
    ContactChannel,
    ProfileType,
    PublicLink,
    TrainingFormat,
    TrainingRequest,
)
from bot.scoring import (
    calculate_contactability,
    calculate_public_credibility,
    calculate_thematic_fit,
    calculate_training_experience,
    linkedin_profile_quality_score,
    linkedin_slug_confidence_score,
    calculate_location_score,
    multi_query_evidence_score,
    recommend_contact_channel,
    semantic_topic_match_score,
    score_candidates,
    score_candidate,
    trainer_signal_score,
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


def test_linkedin_profile_scores_higher_than_company_page() -> None:
    request = make_request()
    profile_candidate = Candidate(
        nome="Ana Silva",
        cargo="Freelance Python Trainer",
        localizacao="Porto",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/ana-silva",
            )
        ],
        fonte="public_web",
        result_title_raw="Ana Silva - Freelance Python Trainer | LinkedIn",
        snippet_raw="Trainer, speaker and workshop facilitator in Python.",
        source_domain="linkedin.com",
        search_rank=1,
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
    )
    company_candidate = Candidate(
        nome="Tech Learning Studio",
        cargo="Python training company",
        localizacao="Porto",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/company/tech-learning-studio",
            )
        ],
        fonte="public_web",
        result_title_raw="Tech Learning Studio | LinkedIn",
        snippet_raw="Company page for Python training services.",
        source_domain="linkedin.com",
        search_rank=1,
        profile_type=ProfileType.company_page,
    )

    profile_score = score_candidate(request, profile_candidate).score.score_total
    company_score = score_candidate(request, company_candidate).score.score_total

    assert profile_score > company_score
    assert linkedin_profile_quality_score(profile_candidate) > linkedin_profile_quality_score(
        company_candidate
    )


def test_job_board_profile_type_is_penalized() -> None:
    request = make_request()
    linkedin_candidate = Candidate(
        nome="Ana Silva",
        cargo="Python Trainer",
        localizacao="Porto",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/ana-silva",
            )
        ],
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer | LinkedIn",
        snippet_raw="Freelance trainer for Python workshops.",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
    )
    job_board_candidate = Candidate(
        nome="Oferta Formador Python",
        cargo="Formador Python",
        localizacao="Porto",
        links=[
            PublicLink(
                label="Oferta",
                url="https://www.net-empregos.com/formador-python",
            )
        ],
        fonte="public_web",
        result_title_raw="Oferta de emprego para Formador Python",
        snippet_raw="Vaga para formador Python.",
        profile_type=ProfileType.job_board,
    )

    linkedin_score = score_candidate(request, linkedin_candidate).score.score_total
    job_board_score = score_candidate(request, job_board_candidate).score.score_total

    assert job_board_score < linkedin_score


def test_article_or_post_profile_type_is_penalized_against_linkedin_profile() -> None:
    request = make_request()
    profile_candidate = Candidate(
        nome="Ana Silva",
        cargo="Python Trainer",
        localizacao="Porto",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/ana-silva",
            )
        ],
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer | LinkedIn",
        snippet_raw="Trainer and workshop facilitator.",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
    )
    article_candidate = Candidate(
        nome="Artigo sobre Python",
        cargo="Python Trainer",
        localizacao="Porto",
        links=[
            PublicLink(
                label="Artigo",
                url="https://example.com/blog/python-training",
            )
        ],
        fonte="public_web",
        result_title_raw="Artigo sobre Python Trainer",
        snippet_raw="Trainer and workshop facilitator.",
        profile_type=ProfileType.article_or_post,
    )

    profile_score = score_candidate(request, profile_candidate).score.score_total
    article_score = score_candidate(request, article_candidate).score.score_total

    assert article_score < profile_score


def test_headline_raw_with_training_signals_increases_thematic_fit() -> None:
    request = make_request()
    candidate_without_headline = Candidate(
        nome="Ana Silva",
        fonte="public_web",
        profile_type=ProfileType.linkedin_profile,
    )
    candidate_with_headline = Candidate(
        nome="Ana Silva",
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer and Speaker | LinkedIn",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
    )

    assert calculate_thematic_fit(request, candidate_with_headline) > calculate_thematic_fit(
        request, candidate_without_headline
    )


def test_snippet_raw_with_workshop_signals_increases_training_experience() -> None:
    weak_candidate = Candidate(
        nome="Ana Silva",
        fonte="public_web",
        result_title_raw="Ana Silva | LinkedIn",
    )
    strong_candidate = Candidate(
        nome="Ana Silva",
        fonte="public_web",
        result_title_raw="Ana Silva | LinkedIn",
        snippet_raw="Facilitator and mentor for Python workshops and training programs.",
    )

    assert calculate_training_experience(strong_candidate) > calculate_training_experience(
        weak_candidate
    )


def test_porto_location_scores_higher_than_generic_portugal_for_porto_request() -> None:
    request = make_request()
    porto_candidate = Candidate(
        nome="Ana Silva",
        localizacao="Porto",
        fonte="public_web",
    )
    portugal_candidate = Candidate(
        nome="Joao Pereira",
        localizacao="Portugal",
        fonte="public_web",
    )

    assert calculate_location_score(request, porto_candidate) > calculate_location_score(
        request, portugal_candidate
    )


def test_public_credibility_uses_linkedin_profile_metadata() -> None:
    profile_candidate = Candidate(
        nome="Ana Silva",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/ana-silva",
            )
        ],
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer | LinkedIn",
        snippet_raw="Freelance trainer and workshop speaker.",
        source_domain="linkedin.com",
        search_rank=1,
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
    )
    article_candidate = Candidate(
        nome="Artigo sobre Python",
        links=[
            PublicLink(
                label="Artigo",
                url="https://example.com/python-workshop",
            )
        ],
        fonte="public_web",
        result_title_raw="Artigo sobre Python workshops",
        snippet_raw="Post sobre workshops.",
        profile_type=ProfileType.article_or_post,
    )

    assert calculate_public_credibility(profile_candidate) > calculate_public_credibility(
        article_candidate
    )


def test_score_total_stays_in_scale_and_orders_candidates_sensibly() -> None:
    request = make_request()
    strong_candidate = Candidate(
        nome="Ana Silva",
        cargo="Freelance Python Trainer",
        localizacao="Porto",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/ana-silva",
            )
        ],
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer and Speaker | LinkedIn",
        snippet_raw="Freelance mentor and workshop facilitator based in Porto.",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
        search_rank=1,
    )
    weak_candidate = Candidate(
        nome="Empresa X",
        cargo="Página institucional",
        localizacao="Portugal",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/company/empresa-x",
            )
        ],
        fonte="public_web",
        result_title_raw="Empresa X | LinkedIn",
        snippet_raw="Página de empresa.",
        profile_type=ProfileType.company_page,
        search_rank=8,
    )

    scored = score_candidates(request, [weak_candidate, strong_candidate])

    assert scored[0].candidato.nome == "Ana Silva"
    assert all(0 <= item.score.score_total <= 100 for item in scored)


def test_strong_public_linkedin_profile_without_email_remains_competitive() -> None:
    request = make_request()
    strong_profile_without_email = Candidate(
        nome="Ana Silva",
        cargo="Freelance Python Trainer",
        localizacao="Porto",
        links=[
            PublicLink(
                label="LinkedIn",
                url="https://www.linkedin.com/in/ana-silva",
            )
        ],
        email_publico=None,
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer and Speaker | LinkedIn",
        snippet_raw="Freelance mentor and workshop facilitator based in Porto.",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
        search_rank=1,
    )
    weak_candidate_with_email = Candidate(
        nome="Carlos Lima",
        cargo="Gestor de projeto",
        localizacao="Lisboa",
        links=[],
        email_publico="carlos@example.com",
        fonte="public_web",
        result_title_raw="Carlos Lima",
        snippet_raw="Perfil público generalista.",
        profile_type=ProfileType.unknown,
    )

    scored = score_candidates(request, [weak_candidate_with_email, strong_profile_without_email])

    assert scored[0].candidato.nome == "Ana Silva"
    assert scored[0].canal_recomendado == ContactChannel.linkedin


def test_multi_query_evidence_increases_score() -> None:
    request = make_request()
    single_query_candidate = Candidate(
        nome="Ana Silva",
        cargo="Python Trainer",
        links=[PublicLink(label="LinkedIn", url="https://www.linkedin.com/in/ana-silva")],
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer | LinkedIn",
        snippet_raw="Trainer for Python workshops.",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
        linkedin_profile_slug="ana-silva",
        linkedin_profile_url="https://www.linkedin.com/in/ana-silva",
        search_rank=4,
        evidence_query_count=1,
        matched_queries=["site:linkedin.com/in Python trainer"],
        training_signals=["trainer"],
        topic_signals=["python"],
    )
    multi_query_candidate = single_query_candidate.model_copy(
        update={
            "nome": "Joao Pereira",
            "linkedin_profile_slug": "joao-pereira",
            "linkedin_profile_url": "https://www.linkedin.com/in/joao-pereira",
            "evidence_query_count": 4,
            "search_rank": 1,
            "matched_queries": [
                "site:linkedin.com/in Python trainer",
                "site:linkedin.com/in Python speaker",
                "site:linkedin.com/in Python workshop",
                "site:linkedin.com/in Python mentor",
            ],
            "training_signals": ["trainer", "speaker", "workshop", "mentor"],
        }
    )

    assert multi_query_evidence_score(multi_query_candidate) > multi_query_evidence_score(
        single_query_candidate
    )
    assert (
        score_candidate(request, multi_query_candidate).score.score_total
        > score_candidate(request, single_query_candidate).score.score_total
    )


def test_trainer_and_topic_signals_drive_linkedin_first_components() -> None:
    request = make_request()
    candidate = Candidate(
        nome="Ana Silva",
        cargo="Python Trainer",
        links=[PublicLink(label="LinkedIn", url="https://www.linkedin.com/in/ana-silva")],
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer and Speaker | LinkedIn",
        snippet_raw="Workshop mentor and facilitator for Python teams.",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
        linkedin_profile_slug="ana-silva",
        linkedin_profile_url="https://www.linkedin.com/in/ana-silva",
        training_signals=["trainer", "speaker", "workshop", "mentor"],
        topic_signals=["python"],
        evidence_query_count=3,
        search_rank=2,
    )

    score = score_candidate(request, candidate).score

    assert semantic_topic_match_score(request, candidate) >= 84
    assert trainer_signal_score(candidate) >= 92
    assert linkedin_profile_quality_score(candidate) >= 90
    assert linkedin_slug_confidence_score(candidate) >= 90
    assert score.semantic_topic_match_score == score.fit_tematico
    assert score.trainer_signal_score == score.experiencia_formacao
    assert score.multi_query_evidence_score >= 80


def test_generic_linkedin_profile_descends_against_aligned_trainer() -> None:
    request = make_request()
    generic_profile = Candidate(
        nome="Carlos Lima",
        cargo="Technology Manager",
        links=[PublicLink(label="LinkedIn", url="https://www.linkedin.com/in/carlos-lima")],
        fonte="public_web",
        result_title_raw="Carlos Lima - Technology Manager | LinkedIn",
        snippet_raw="Manager with broad technology experience.",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
        linkedin_profile_slug="carlos-lima",
        linkedin_profile_url="https://www.linkedin.com/in/carlos-lima",
        evidence_query_count=1,
        search_rank=2,
    )
    aligned_trainer = Candidate(
        nome="Ana Silva",
        cargo="Python Trainer",
        links=[PublicLink(label="LinkedIn", url="https://www.linkedin.com/in/ana-silva")],
        fonte="public_web",
        result_title_raw="Ana Silva - Python Trainer | LinkedIn",
        snippet_raw="Speaker, mentor and workshop facilitator for Python.",
        profile_type=ProfileType.linkedin_profile,
        is_probably_linkedin_profile=True,
        linkedin_profile_slug="ana-silva",
        linkedin_profile_url="https://www.linkedin.com/in/ana-silva",
        training_signals=["trainer", "speaker", "mentor", "workshop"],
        topic_signals=["python"],
        evidence_query_count=2,
        search_rank=3,
    )

    scored = score_candidates(request, [generic_profile, aligned_trainer])

    assert scored[0].candidato.nome == "Ana Silva"
