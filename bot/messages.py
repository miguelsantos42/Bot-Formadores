from bot.models import OutreachMessages, ScoredCandidate, TrainingRequest


def generate_outreach_messages(
    request: TrainingRequest,
    scored_candidate: ScoredCandidate,
) -> OutreachMessages:
    return OutreachMessages(
        email_inicial=build_initial_email(request, scored_candidate),
        mensagem_linkedin=build_linkedin_message(request, scored_candidate),
    )


def build_initial_email(
    request: TrainingRequest,
    scored_candidate: ScoredCandidate,
) -> str:
    candidate = scored_candidate.candidato
    first_name = get_first_name(candidate.nome)
    candidate_context = build_candidate_context(scored_candidate)

    return (
        f"Assunto: Convite para sessao sobre {request.tema_formacao}\n\n"
        f"Ola {first_name},\n\n"
        "O meu nome e Miguel e faco parte da JuniFEUP. "
        f"Estamos a preparar uma sessao interna sobre {request.tema_formacao} "
        f"para a area de {request.area_interna}.\n\n"
        f"Encontramos o teu perfil e pareceu-nos relevante porque {candidate_context}.\n\n"
        f"Contexto da sessao: {request.descricao_contexto}\n\n"
        "Gostariamos de perceber se terias disponibilidade para uma primeira conversa "
        "exploratoria sobre uma possivel colaboracao.\n\n"
        "Obrigado,\n"
        "Miguel"
    )


def build_linkedin_message(
    request: TrainingRequest,
    scored_candidate: ScoredCandidate,
) -> str:
    candidate = scored_candidate.candidato
    first_name = get_first_name(candidate.nome)

    message = (
        f"Ola {first_name}, encontrei o teu perfil no contexto de uma sessao interna "
        f"da JuniFEUP sobre {request.tema_formacao}. "
        "Pareceu-me que podia haver bom alinhamento com a tua experiencia. "
        "Teria interesse em falar brevemente sobre uma possivel colaboracao?"
    )

    return truncate_text(message, max_length=500)


def build_candidate_context(scored_candidate: ScoredCandidate) -> str:
    candidate = scored_candidate.candidato
    pieces: list[str] = []

    if candidate.cargo:
        pieces.append(f"o teu cargo atual e '{candidate.cargo}'")

    if candidate.empresa:
        pieces.append(f"a tua experiencia esta ligada a {candidate.empresa}")

    if scored_candidate.score.motivo:
        pieces.append(scored_candidate.score.motivo)

    return "; ".join(pieces) if pieces else "o teu perfil publico parece alinhado"


def get_first_name(full_name: str) -> str:
    return full_name.strip().split()[0]


def truncate_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value

    return value[: max_length - 3].rstrip() + "..."
