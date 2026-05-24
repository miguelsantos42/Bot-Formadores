from typing import Any

import csv
import json
from io import StringIO

import streamlit as st
from pydantic import ValidationError

from bot.config import Settings, get_settings
from bot.db import list_search_runs, save_search_run
from bot.messages import generate_outreach_messages
from bot.models import CandidateResult, SearchRun, TrainingFormat, TrainingRequest
from bot.scoring import score_candidates
from bot.search import generate_search_queries, get_search_provider


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


PROFILE_TYPE_LABELS = {
    "linkedin_profile": "Perfil LinkedIn",
    "personal_site": "Site pessoal",
    "company_page": "Página de empresa",
    "job_board": "Portal de emprego",
    "article_or_post": "Artigo/post",
    "unknown": "Desconhecido",
}


EXPORT_COLUMNS = [
    "nome",
    "empresa",
    "localizacao",
    "links",
    "email_publico",
    "canal_recomendado",
    "score_total",
    "motivo_fit",
    "assunto_email",
    "email_inicial",
    "mensagem_linkedin",
    "source_domain",
    "profile_type",
    "matched_query",
]


def build_search_run(request: TrainingRequest, settings: Settings | None = None) -> SearchRun:
    settings = settings or get_settings()
    provider = get_search_provider(settings)
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


def get_provider_label(settings: Settings) -> str:
    if settings.search_provider == "mock":
        return "Mock"

    if settings.search_provider == "public_web":
        return "Pesquisa pública"

    return settings.search_provider


def format_optional(value: Any, fallback: str = "Não identificado") -> str:
    if value is None:
        return fallback

    if isinstance(value, str) and not value.strip():
        return fallback

    return str(value)


def build_score_components(result: CandidateResult) -> dict[str, int]:
    score = result.candidato_classificado.score
    return {
        "Fit temático": score.fit_tematico,
        "Fit funcional": score.fit_funcional,
        "Experiência em formação": score.experiencia_formacao,
        "Localização": score.localizacao_score,
        "Contactabilidade": score.contactabilidade,
        "Credibilidade pública": score.credibilidade_publica,
    }


def build_export_rows(search_run: SearchRun) -> list[dict[str, Any]]:
    return [
        build_export_row(result)
        for result in search_run.resultados
    ]


def build_export_row(result: CandidateResult) -> dict[str, Any]:
    scored_candidate = result.candidato_classificado
    candidate = scored_candidate.candidato
    score = scored_candidate.score

    return {
        "nome": candidate.nome,
        "empresa": candidate.empresa,
        "localizacao": candidate.localizacao,
        "links": "; ".join(str(link.url) for link in candidate.links),
        "email_publico": candidate.email_publico,
        "canal_recomendado": scored_candidate.canal_recomendado.value,
        "score_total": score.score_total,
        "motivo_fit": score.motivo,
        "assunto_email": extract_email_subject(result.mensagens.email_inicial),
        "email_inicial": result.mensagens.email_inicial,
        "mensagem_linkedin": result.mensagens.mensagem_linkedin,
        "source_domain": candidate.source_domain,
        "profile_type": candidate.profile_type.value,
        "matched_query": candidate.matched_query,
    }


def export_rows_to_csv(rows: list[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def export_rows_to_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)


def extract_email_subject(email_text: str) -> str:
    first_line = email_text.splitlines()[0] if email_text else ""
    prefix = "Assunto:"

    if first_line.startswith(prefix):
        return first_line.removeprefix(prefix).strip()

    return first_line.strip()


def build_export_filename(search_run: SearchRun, extension: str) -> str:
    topic = slugify(search_run.pedido.tema_formacao)
    return f"bot-formadores-{topic}.{extension}"


def slugify(value: str) -> str:
    slug = "".join(
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    )
    parts = [part for part in slug.split("-") if part]
    return "-".join(parts) or "export"


def render_sidebar(settings: Settings) -> bool:
    with st.sidebar:
        st.header("Estado")
        st.write(f"Provider ativo: **{get_provider_label(settings)}**")
        st.write(f"Base de dados: `{settings.database_path}`")

        runs = list_search_runs(settings.database_path)
        st.write(f"Pesquisas guardadas: **{len(runs)}**")

        return st.checkbox("Mostrar debug", value=False)


def render_request_form() -> tuple[bool, dict[str, Any]]:
    with st.form("training_request_form"):
        st.subheader("Pedido de formação")

        tema_formacao = st.text_input("Tema da formação")
        area_interna = st.text_input("Área interna")
        descricao_contexto = st.text_area("Descrição do contexto", height=120)

        col1, col2 = st.columns(2)
        with col1:
            localizacao = st.text_input("Localização")
            duracao = st.text_input("Duração")

        with col2:
            formato = st.selectbox(
                "Formato",
                options=list(TrainingFormat),
                index=3,
                format_func=lambda format_item: FORMAT_LABELS[format_item],
            )
            numero_participantes = st.number_input(
                "Número de participantes",
                min_value=0,
                step=1,
                value=0,
            )

        submitted = st.form_submit_button("Procurar formadores", type="primary")

    return submitted, {
        "tema_formacao": tema_formacao,
        "area_interna": area_interna,
        "descricao_contexto": descricao_contexto,
        "localizacao": localizacao,
        "formato": formato,
        "duracao": duracao,
        "numero_participantes": numero_participantes,
    }


def build_training_request(form_data: dict[str, Any]) -> TrainingRequest:
    return TrainingRequest(
        tema_formacao=form_data["tema_formacao"],
        area_interna=form_data["area_interna"],
        descricao_contexto=form_data["descricao_contexto"],
        localizacao=form_data["localizacao"] or None,
        formato=form_data["formato"],
        duracao=form_data["duracao"] or None,
        numero_participantes=form_data["numero_participantes"] or None,
    )


def render_search_summary(search_run: SearchRun, run_id: str) -> None:
    st.success(f"Pesquisa guardada com ID: {run_id}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Queries", len(search_run.queries))
    col2.metric("Candidatos", len(search_run.resultados))
    col3.metric(
        "Melhor score",
        search_run.resultados[0].candidato_classificado.score.score_total
        if search_run.resultados
        else 0,
    )


def render_export_actions(search_run: SearchRun) -> None:
    if not search_run.resultados:
        return

    rows = build_export_rows(search_run)
    csv_data = export_rows_to_csv(rows)
    json_data = export_rows_to_json(rows)

    st.subheader("Exportação")
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "Descarregar CSV",
            data=csv_data,
            file_name=build_export_filename(search_run, "csv"),
            mime="text/csv",
        )

    with col2:
        st.download_button(
            "Descarregar JSON",
            data=json_data,
            file_name=build_export_filename(search_run, "json"),
            mime="application/json",
        )


def render_candidate_result(
    result: CandidateResult,
    index: int,
    show_debug: bool,
) -> None:
    scored_candidate = result.candidato_classificado
    candidate = scored_candidate.candidato
    score = scored_candidate.score
    channel = CHANNEL_LABELS[scored_candidate.canal_recomendado.value]
    profile_type = PROFILE_TYPE_LABELS[candidate.profile_type.value]

    with st.container(border=True):
        header_left, header_right = st.columns([4, 1])

        with header_left:
            st.subheader(f"{index + 1}. {candidate.nome}")
            st.write(format_optional(candidate.cargo, "Cargo não identificado"))
            st.caption(
                " | ".join(
                    [
                        f"Empresa: {format_optional(candidate.empresa)}",
                        f"Localização: {format_optional(candidate.localizacao)}",
                        f"Fonte: {format_optional(candidate.source_domain)}",
                        f"Tipo: {profile_type}",
                    ]
                )
            )

        with header_right:
            st.metric("Score", score.score_total)
            st.write(f"Canal: **{channel}**")

        st.write(score.motivo)

        render_generated_messages(result, index)
        render_candidate_details(result, index, show_debug)


def render_generated_messages(result: CandidateResult, index: int) -> None:
    email_tab, linkedin_tab = st.tabs(["Email inicial", "Mensagem LinkedIn"])

    with email_tab:
        st.text_area(
            "Email gerado",
            result.mensagens.email_inicial,
            height=260,
            key=f"email_{index}",
        )

    with linkedin_tab:
        st.text_area(
            "Mensagem gerada",
            result.mensagens.mensagem_linkedin,
            height=140,
            key=f"linkedin_{index}",
        )


def render_candidate_details(
    result: CandidateResult,
    index: int,
    show_debug: bool,
) -> None:
    scored_candidate = result.candidato_classificado
    candidate = scored_candidate.candidato

    with st.expander("Detalhes do candidato", expanded=show_debug):
        st.write(f"Query: `{format_optional(candidate.matched_query)}`")
        st.write(f"Título bruto: {format_optional(candidate.result_title_raw)}")
        st.write(f"Snippet bruto: {format_optional(candidate.snippet_raw)}")

        st.write("Score por componente")
        st.dataframe(
            [
                {"Componente": component, "Score": value}
                for component, value in build_score_components(result).items()
            ],
            hide_index=True,
            use_container_width=True,
        )

        if candidate.links:
            st.write("Links disponíveis")
            for link in candidate.links:
                st.link_button(link.label, str(link.url))
        else:
            st.info("Este candidato não tem links públicos associados.")

        if show_debug:
            st.json(
                {
                    "candidate": candidate.model_dump(mode="json"),
                    "score": scored_candidate.score.model_dump(mode="json"),
                    "canal_recomendado": scored_candidate.canal_recomendado.value,
                }
            )


def render_debug_queries(search_run: SearchRun, show_debug: bool) -> None:
    if not show_debug:
        return

    with st.expander("Debug da pesquisa", expanded=False):
        st.write("Queries geradas")
        st.code("\n".join(search_run.queries))


def main() -> None:
    settings = get_settings()

    st.set_page_config(page_title="Bot-Formadores", layout="wide")
    st.title("Bot-Formadores")

    show_debug = render_sidebar(settings)
    submitted, form_data = render_request_form()

    if not submitted:
        return

    try:
        request = build_training_request(form_data)
    except ValidationError as error:
        st.error("Revê os campos do pedido antes de continuar.")
        if show_debug:
            st.exception(error)
        return

    with st.spinner("A procurar candidatos públicos..."):
        try:
            search_run = build_search_run(request, settings=settings)
        except Exception as error:
            st.error("O provider de pesquisa falhou. Tenta novamente ou muda o provider.")
            if show_debug:
                st.exception(error)
            return

    try:
        run_id = save_search_run(settings.database_path, search_run)
    except Exception as error:
        st.error("A pesquisa correu, mas não foi possível guardar os resultados.")
        if show_debug:
            st.exception(error)
        return

    render_search_summary(search_run, run_id)
    render_debug_queries(search_run, show_debug)

    st.subheader("Candidatos recomendados")
    if not search_run.resultados:
        st.warning(
            "Não foram encontrados candidatos públicos para este pedido. "
            "Experimenta alargar o tema, remover a localização ou voltar a usar o provider mock."
        )
        return

    render_export_actions(search_run)

    for index, result in enumerate(search_run.resultados):
        render_candidate_result(result, index, show_debug)


if __name__ == "__main__":
    main()
