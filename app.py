import streamlit as st
from pydantic import ValidationError

from bot.config import get_settings
from bot.db import list_search_runs, save_search_run
from bot.messages import generate_outreach_messages
from bot.models import CandidateResult, SearchRun, TrainingFormat, TrainingRequest
from bot.scoring import score_candidates
from bot.search import MockSearchProvider, generate_search_queries


FORMAT_LABELS = {
    TrainingFormat.presencial: "Presencial",
    TrainingFormat.remoto: "Remoto",
    TrainingFormat.hibrido: "Híbrido",
    TrainingFormat.indiferente: "Indiferente",
}


CHANNEL_LABELS = {
    "email": "email",
    "linkedin": "LinkedIn",
    "formulario": "formulário",
}


def build_search_run(request: TrainingRequest) -> SearchRun:
    provider = MockSearchProvider()
    candidates = provider.search(request)
    scored_candidates = score_candidates(request, candidates)

    results = [
        CandidateResult(
            candidato_classificado=scored_candidate,
            mensagens=generate_outreach_messages(request, scored_candidate),
        )
        for scored_candidate in scored_candidates
    ]

    return SearchRun(
        pedido=request,
        queries=generate_search_queries(request),
        resultados=results,
    )


def render_candidate_result(result: CandidateResult, index: int) -> None:
    scored_candidate = result.candidato_classificado
    candidate = scored_candidate.candidato
    score = scored_candidate.score

    with st.container(border=True):
        left, right = st.columns([3, 1])

        with left:
            st.subheader(candidate.nome)
            st.write(candidate.cargo or "Cargo não identificado")
            st.write(candidate.empresa or "Empresa não identificada")
            st.write(candidate.localizacao or "Localização não identificada")
            st.write(score.motivo)

        with right:
            st.metric("Score", score.score_total)
            channel = CHANNEL_LABELS[scored_candidate.canal_recomendado.value]
            st.write(f"Canal: {channel}")

        if candidate.links:
            st.write("Links públicos")
            for link in candidate.links:
                st.link_button(link.label, str(link.url))

        st.text_area(
            "Email inicial",
            result.mensagens.email_inicial,
            height=240,
            key=f"email_{index}",
        )
        st.text_area(
            "Mensagem LinkedIn",
            result.mensagens.mensagem_linkedin,
            height=120,
            key=f"linkedin_{index}",
        )


def main() -> None:
    settings = get_settings()

    st.set_page_config(page_title="Bot-Formadores", layout="wide")
    st.title("Bot-Formadores")

    with st.sidebar:
        st.header("Histórico")
        runs = list_search_runs(settings.database_path)
        st.write(f"{len(runs)} pesquisas guardadas")

    with st.form("training_request_form"):
        tema_formacao = st.text_input("Tema da formação")
        area_interna = st.text_input("Área interna")
        descricao_contexto = st.text_area("Descrição do contexto")

        localizacao = st.text_input("Localização")
        formato = st.selectbox(
            "Formato",
            options=list(TrainingFormat),
            index=3,
            format_func=lambda format_item: FORMAT_LABELS[format_item],
        )
        duracao = st.text_input("Duração")
        numero_participantes = st.number_input(
            "Número de participantes",
            min_value=0,
            step=1,
            value=0,
        )

        submitted = st.form_submit_button("Procurar formadores")

    if not submitted:
        return

    try:
        request = TrainingRequest(
            tema_formacao=tema_formacao,
            area_interna=area_interna,
            descricao_contexto=descricao_contexto,
            localizacao=localizacao or None,
            formato=formato,
            duracao=duracao or None,
            numero_participantes=numero_participantes or None,
        )
    except ValidationError as error:
        st.error("Revê os campos do pedido antes de continuar.")
        st.exception(error)
        return

    search_run = build_search_run(request)
    run_id = save_search_run(settings.database_path, search_run)

    st.success(f"Pesquisa guardada com ID: {run_id}")

    st.subheader("Queries geradas")
    st.code("\n".join(search_run.queries))

    st.subheader("Candidatos recomendados")
    for index, result in enumerate(search_run.resultados):
        render_candidate_result(result, index)


if __name__ == "__main__":
    main()
