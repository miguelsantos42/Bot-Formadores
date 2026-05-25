from typing import Any

import csv
import hashlib
import json
from io import StringIO

import streamlit as st
from pydantic import ValidationError

from bot.config import Settings, get_settings
from bot.db import list_search_runs, save_search_run
from bot.messages import generate_outreach_messages
from bot.models import (
    Candidate,
    CandidateResult,
    SearchDiagnostics,
    SearchRun,
    TrainingFormat,
    TrainingRequest,
)
from bot.scoring import score_candidates
from bot.search import (
    MockSearchProvider,
    SearchConfigurationError,
    generate_search_queries,
    get_search_provider,
)


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


CURATION_STATE_KEY = "candidate_curation"
ACTIVE_SEARCH_RUN_KEY = "active_search_run"
ACTIVE_RUN_ID_KEY = "active_run_id"
CURATION_STATUS_DEFAULT = "por_decidir"
CURATION_STATUS_OPTIONS = [
    "por_decidir",
    "aprovado",
    "talvez",
    "rejeitado",
    "contactado",
]
CURATION_STATUS_LABELS = {
    "por_decidir": "Por decidir",
    "aprovado": "Aprovado para contacto",
    "talvez": "Talvez",
    "rejeitado": "Rejeitado",
    "contactado": "Já contactado",
}
CURATION_STATUS_SORT_ORDER = {
    "aprovado": 0,
    "talvez": 1,
    "por_decidir": 2,
    "contactado": 3,
    "rejeitado": 4,
}
FILTER_STATUS_OPTIONS = ["todos", *CURATION_STATUS_OPTIONS]
FILTER_STATUS_LABELS = {
    "todos": "Todos",
    **CURATION_STATUS_LABELS,
}
SORT_OPTIONS = ["score_total", "estado", "nome", "empresa"]
SORT_LABELS = {
    "score_total": "Score",
    "estado": "Estado",
    "nome": "Nome",
    "empresa": "Empresa",
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
    "estado_curadoria",
    "nota_curadoria",
]


def build_search_run(request: TrainingRequest, settings: Settings | None = None) -> SearchRun:
    settings = settings or get_settings()
    provider = get_search_provider(settings)
    candidates = provider.search(request)
    provider_diagnostics = getattr(provider, "last_diagnostics", {})
    diagnostics = SearchDiagnostics(
        provider=settings.search_provider,
        public_candidate_count=(
            len(candidates) if is_public_search_provider(settings.search_provider) else 0
        ),
        query_count=int(provider_diagnostics.get("query_count", 0) or 0),
        raw_result_count=int(provider_diagnostics.get("raw_result_count", 0) or 0),
        eligible_result_count=int(
            provider_diagnostics.get("eligible_result_count", 0) or 0
        ),
        blocked_query_count=int(
            provider_diagnostics.get("blocked_query_count", 0) or 0
        ),
        block_reason=provider_diagnostics.get("block_reason") or None,
    )

    if should_use_mock_fallback(settings, candidates):
        diagnostics = diagnostics.model_copy(
            update={
                "fallback_used": True,
                "fallback_provider": "mock",
                "fallback_reason": (
                    "A pesquisa pública não devolveu candidatos públicos "
                    "aproveitáveis."
                ),
            }
        )
        candidates = MockSearchProvider().search(request)

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
        diagnostics=diagnostics,
    )


def should_use_mock_fallback(settings: Settings, candidates: list[Candidate]) -> bool:
    return (
        is_public_search_provider(settings.search_provider)
        and settings.public_search_fallback_to_mock
        and not candidates
    )


def is_public_search_provider(provider_name: str) -> bool:
    return provider_name in {"public_web", "brave", "brave_search"}


def get_provider_label(settings: Settings) -> str:
    if settings.search_provider == "mock":
        return "Mock"

    if settings.search_provider in {"brave", "brave_search"}:
        return "Brave Search API"

    if settings.search_provider == "public_web":
        return "Pesquisa pública HTML"

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


def get_curation_state() -> dict[str, dict[str, str]]:
    if CURATION_STATE_KEY not in st.session_state:
        st.session_state[CURATION_STATE_KEY] = {}

    return st.session_state[CURATION_STATE_KEY]


def candidate_key(result: CandidateResult) -> str:
    candidate = result.candidato_classificado.candidato
    primary_url = str(candidate.links[0].url) if candidate.links else ""
    key_parts = [
        candidate.nome.strip().lower(),
        (candidate.empresa or "").strip().lower(),
        (candidate.source_domain or "").strip().lower(),
        primary_url.strip().lower(),
        (candidate.matched_query or "").strip().lower(),
    ]

    return "|".join(key_parts)


def candidate_widget_key(result: CandidateResult) -> str:
    key = candidate_key(result).encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:12]


def normalize_curation_record(record: dict[str, str] | None) -> dict[str, str]:
    record = record or {}
    status = record.get("status", CURATION_STATUS_DEFAULT)
    note = record.get("note", "")

    if status not in CURATION_STATUS_OPTIONS:
        status = CURATION_STATUS_DEFAULT

    return {
        "status": status,
        "note": (note or "").strip(),
    }


def get_candidate_curation(
    result: CandidateResult,
    curation_state: dict[str, dict[str, str]],
) -> dict[str, str]:
    return normalize_curation_record(curation_state.get(candidate_key(result)))


def update_candidate_curation(
    result: CandidateResult,
    curation_state: dict[str, dict[str, str]],
    status: str,
    note: str,
) -> None:
    curation_state[candidate_key(result)] = normalize_curation_record(
        {
            "status": status,
            "note": note,
        }
    )


def filter_results_by_status(
    results: list[CandidateResult],
    curation_state: dict[str, dict[str, str]],
    selected_status: str,
) -> list[CandidateResult]:
    if selected_status == "todos" or selected_status not in FILTER_STATUS_OPTIONS:
        return list(results)

    return [
        result
        for result in results
        if get_candidate_curation(result, curation_state)["status"] == selected_status
    ]


def sort_results(
    results: list[CandidateResult],
    curation_state: dict[str, dict[str, str]],
    sort_by: str,
) -> list[CandidateResult]:
    if sort_by == "estado":
        return sorted(
            results,
            key=lambda result: (
                CURATION_STATUS_SORT_ORDER[
                    get_candidate_curation(result, curation_state)["status"]
                ],
                -result.candidato_classificado.score.score_total,
                result.candidato_classificado.candidato.nome.lower(),
            ),
        )

    if sort_by == "nome":
        return sorted(
            results,
            key=lambda result: result.candidato_classificado.candidato.nome.lower(),
        )

    if sort_by == "empresa":
        return sorted(
            results,
            key=lambda result: (
                (result.candidato_classificado.candidato.empresa or "").lower(),
                result.candidato_classificado.candidato.nome.lower(),
            ),
        )

    return sorted(
        results,
        key=lambda result: result.candidato_classificado.score.score_total,
        reverse=True,
    )


def count_approved_results(
    results: list[CandidateResult],
    curation_state: dict[str, dict[str, str]],
) -> int:
    return len(filter_results_by_status(results, curation_state, "aprovado"))


def build_export_rows(
    search_run: SearchRun,
    curation_state: dict[str, dict[str, str]] | None = None,
    results: list[CandidateResult] | None = None,
    only_approved: bool = False,
) -> list[dict[str, Any]]:
    curation_state = curation_state or {}
    selected_results = results if results is not None else search_run.resultados
    rows: list[dict[str, Any]] = []

    for result in selected_results:
        curation = get_candidate_curation(result, curation_state)
        if only_approved and curation["status"] != "aprovado":
            continue

        rows.append(build_export_row(result, curation))

    return rows


def build_export_row(
    result: CandidateResult,
    curation: dict[str, str] | None = None,
) -> dict[str, Any]:
    scored_candidate = result.candidato_classificado
    candidate = scored_candidate.candidato
    score = scored_candidate.score
    curation = normalize_curation_record(curation)

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
        "estado_curadoria": CURATION_STATUS_LABELS[curation["status"]],
        "nota_curadoria": curation["note"],
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


def build_export_filename(
    search_run: SearchRun,
    extension: str,
    suffix: str | None = None,
) -> str:
    topic = slugify(search_run.pedido.tema_formacao)
    suffix_part = f"-{slugify(suffix)}" if suffix else ""
    return f"bot-formadores-{topic}{suffix_part}.{extension}"


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
        if is_public_search_provider(settings.search_provider):
            st.write("Critério: **LinkedIn pessoal + recall/rerank**")
            fallback_label = (
                "ativo" if settings.public_search_fallback_to_mock else "inativo"
            )
            st.write(f"Fallback mock: **{fallback_label}**")

        runs = list_search_runs(settings.database_path)
        st.write(f"Pesquisas guardadas: **{len(runs)}**")

        return st.checkbox("Mostrar debug", value=False)


def render_request_form() -> tuple[bool, dict[str, Any]]:
    with st.form("training_request_form"):
        st.subheader("Pedido de formação")

        tema_formacao = st.text_input("Tema da formação")
        area_interna = st.text_input("Área interna (opcional)")
        descricao_contexto = st.text_area("Descrição do contexto (opcional)", height=120)

        col1, col2 = st.columns(2)
        with col1:
            localizacao = st.text_input("Localização (opcional)")
            duracao = st.text_input("Duração (opcional)")

        with col2:
            formato = st.selectbox(
                "Formato",
                options=list(TrainingFormat),
                index=3,
                format_func=lambda format_item: FORMAT_LABELS[format_item],
            )
            numero_participantes = st.number_input(
                "Número de participantes (opcional)",
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
        area_interna=form_data["area_interna"] or "",
        descricao_contexto=form_data["descricao_contexto"] or "",
        localizacao=form_data["localizacao"] or None,
        formato=form_data["formato"],
        duracao=form_data["duracao"] or None,
        numero_participantes=form_data["numero_participantes"] or None,
    )


def render_search_summary(search_run: SearchRun, run_id: str) -> None:
    st.success(f"Pesquisa guardada com ID: {run_id}")
    render_search_diagnostics(search_run)

    col1, col2, col3 = st.columns(3)
    col1.metric("Queries", len(search_run.queries))
    col2.metric("Candidatos", len(search_run.resultados))
    col3.metric(
        "Melhor score",
        search_run.resultados[0].candidato_classificado.score.score_total
        if search_run.resultados
        else 0,
    )


def render_search_diagnostics(search_run: SearchRun) -> None:
    diagnostics = search_run.diagnostics
    if diagnostics is None:
        return

    if diagnostics.fallback_used:
        if diagnostics.block_reason:
            st.warning(
                "O motor de busca bloqueou a pesquisa automática com captcha/desafio. "
                "Para conseguires testar o fluxo completo, estou a mostrar candidatos "
                "de demonstração."
            )
            return

        st.warning(
            "A pesquisa pública não encontrou candidatos aproveitáveis. "
            "Para conseguires testar o fluxo completo, estou a mostrar candidatos "
            "de demonstração."
        )
        return

    if diagnostics.provider == "public_web" and diagnostics.block_reason:
        st.warning(
            "O motor de busca bloqueou a pesquisa automática com captcha/desafio. "
            "A app não recebeu resultados públicos para analisar. Usa o mock para "
            "testar o fluxo ou configura uma Search API para pesquisa real estável."
        )
        return

    if diagnostics.provider == "public_web" and diagnostics.public_candidate_count == 0:
        st.warning(
            "A pesquisa pública correu, mas não encontrou candidatos aproveitáveis."
        )


def render_workflow_controls(
    search_run: SearchRun,
    curation_state: dict[str, dict[str, str]],
) -> tuple[str, str]:
    st.subheader("Curadoria")

    col1, col2, col3 = st.columns(3)
    col1.metric("Candidatos", len(search_run.resultados))
    col2.metric("Aprovados", count_approved_results(search_run.resultados, curation_state))
    col3.caption("Estados e notas ficam guardados nesta sessão da app.")

    control_left, control_right = st.columns(2)
    with control_left:
        selected_status = st.selectbox(
            "Filtrar por estado",
            options=FILTER_STATUS_OPTIONS,
            format_func=lambda status: FILTER_STATUS_LABELS[status],
        )

    with control_right:
        sort_by = st.selectbox(
            "Ordenar por",
            options=SORT_OPTIONS,
            format_func=lambda value: SORT_LABELS[value],
        )

    return selected_status, sort_by


def render_export_actions(
    search_run: SearchRun,
    curation_state: dict[str, dict[str, str]],
    filtered_results: list[CandidateResult],
) -> None:
    if not search_run.resultados:
        return

    all_rows = build_export_rows(search_run, curation_state=curation_state)
    filtered_rows = build_export_rows(
        search_run,
        curation_state=curation_state,
        results=filtered_results,
    )
    approved_rows = build_export_rows(
        search_run,
        curation_state=curation_state,
        only_approved=True,
    )

    st.subheader("Exportação")
    all_col, filtered_col, approved_col = st.columns(3)

    with all_col:
        st.caption("Todos os candidatos")
        st.download_button(
            "CSV completo",
            data=export_rows_to_csv(all_rows),
            file_name=build_export_filename(search_run, "csv"),
            mime="text/csv",
        )
        st.download_button(
            "JSON completo",
            data=export_rows_to_json(all_rows),
            file_name=build_export_filename(search_run, "json"),
            mime="application/json",
        )

    with filtered_col:
        st.caption("Resultados filtrados")
        if filtered_rows:
            st.download_button(
                "CSV filtrado",
                data=export_rows_to_csv(filtered_rows),
                file_name=build_export_filename(search_run, "csv", "filtrado"),
                mime="text/csv",
            )
            st.download_button(
                "JSON filtrado",
                data=export_rows_to_json(filtered_rows),
                file_name=build_export_filename(search_run, "json", "filtrado"),
                mime="application/json",
            )
        else:
            st.info("O filtro atual não tem candidatos para exportar.")

    with approved_col:
        st.caption("Shortlist aprovada")
        if approved_rows:
            st.download_button(
                "CSV shortlist",
                data=export_rows_to_csv(approved_rows),
                file_name=build_export_filename(
                    search_run,
                    "csv",
                    "shortlist-aprovada",
                ),
                mime="text/csv",
            )
            st.download_button(
                "JSON shortlist",
                data=export_rows_to_json(approved_rows),
                file_name=build_export_filename(
                    search_run,
                    "json",
                    "shortlist-aprovada",
                ),
                mime="application/json",
            )
        else:
            st.info("Marca candidatos como aprovados para gerar a shortlist.")


def render_approved_shortlist(
    search_run: SearchRun,
    curation_state: dict[str, dict[str, str]],
) -> None:
    approved_results = sort_results(
        filter_results_by_status(search_run.resultados, curation_state, "aprovado"),
        curation_state,
        "score_total",
    )

    with st.expander(f"Shortlist aprovada ({len(approved_results)})", expanded=False):
        if not approved_results:
            st.info("Ainda não há candidatos aprovados para contacto.")
            return

        st.dataframe(
            [
                {
                    "Nome": result.candidato_classificado.candidato.nome,
                    "Empresa": format_optional(
                        result.candidato_classificado.candidato.empresa
                    ),
                    "Localização": format_optional(
                        result.candidato_classificado.candidato.localizacao
                    ),
                    "Score": result.candidato_classificado.score.score_total,
                    "Canal": CHANNEL_LABELS[
                        result.candidato_classificado.canal_recomendado.value
                    ],
                    "Nota": get_candidate_curation(result, curation_state)["note"],
                }
                for result in approved_results
            ],
            hide_index=True,
            use_container_width=True,
        )


def render_candidate_result(
    result: CandidateResult,
    index: int,
    show_debug: bool,
    curation_state: dict[str, dict[str, str]],
) -> None:
    scored_candidate = result.candidato_classificado
    candidate = scored_candidate.candidato
    score = scored_candidate.score
    channel = CHANNEL_LABELS[scored_candidate.canal_recomendado.value]
    profile_type = PROFILE_TYPE_LABELS[candidate.profile_type.value]
    curation = get_candidate_curation(result, curation_state)
    widget_key = candidate_widget_key(result)

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

        curation_left, curation_right = st.columns([1, 2])
        with curation_left:
            status = st.selectbox(
                "Estado",
                options=CURATION_STATUS_OPTIONS,
                index=CURATION_STATUS_OPTIONS.index(curation["status"]),
                format_func=lambda value: CURATION_STATUS_LABELS[value],
                key=f"curation_status_{widget_key}",
            )

        with curation_right:
            note = st.text_input(
                "Nota manual",
                value=curation["note"],
                max_chars=180,
                key=f"curation_note_{widget_key}",
            )

        update_candidate_curation(result, curation_state, status, note)

        render_generated_messages(result, widget_key)
        render_candidate_details(result, index, show_debug)


def render_generated_messages(result: CandidateResult, widget_key: str) -> None:
    email_tab, linkedin_tab = st.tabs(["Email inicial", "Mensagem LinkedIn"])

    with email_tab:
        st.text_area(
            "Email gerado",
            result.mensagens.email_inicial,
            height=260,
            key=f"email_{widget_key}",
        )

    with linkedin_tab:
        st.text_area(
            "Mensagem gerada",
            result.mensagens.mensagem_linkedin,
            height=140,
            key=f"linkedin_{widget_key}",
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
        if search_run.diagnostics is not None:
            st.write("Diagnóstico")
            st.json(search_run.diagnostics.model_dump(mode="json"))

        st.write("Queries geradas")
        st.code("\n".join(search_run.queries))


def main() -> None:
    settings = get_settings()

    st.set_page_config(page_title="Bot-Formadores", layout="wide")
    st.title("Bot-Formadores")

    show_debug = render_sidebar(settings)
    submitted, form_data = render_request_form()

    if submitted:
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
            except SearchConfigurationError as error:
                st.error(str(error))
                if show_debug:
                    st.exception(error)
                return
            except Exception as error:
                st.error(
                    "O provider de pesquisa falhou. Tenta novamente ou muda o provider."
                )
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

        st.session_state[ACTIVE_SEARCH_RUN_KEY] = search_run
        st.session_state[ACTIVE_RUN_ID_KEY] = run_id
        st.session_state[CURATION_STATE_KEY] = {}

    if ACTIVE_SEARCH_RUN_KEY not in st.session_state:
        return

    search_run = st.session_state[ACTIVE_SEARCH_RUN_KEY]
    run_id = st.session_state[ACTIVE_RUN_ID_KEY]

    render_search_summary(search_run, run_id)
    render_debug_queries(search_run, show_debug)

    st.subheader("Candidatos recomendados")
    if not search_run.resultados:
        st.warning(
            "Não foram encontrados candidatos públicos para este pedido. "
            "Experimenta alargar o tema, remover a localização ou voltar a usar o provider mock."
        )
        return

    curation_state = get_curation_state()
    selected_status, sort_by = render_workflow_controls(search_run, curation_state)
    filtered_results = filter_results_by_status(
        search_run.resultados,
        curation_state,
        selected_status,
    )
    visible_results = sort_results(filtered_results, curation_state, sort_by)

    render_export_actions(search_run, curation_state, visible_results)
    render_approved_shortlist(search_run, curation_state)

    if not visible_results:
        st.warning("Não há candidatos para o estado selecionado.")
        return

    for index, result in enumerate(visible_results):
        render_candidate_result(result, index, show_debug, curation_state)


if __name__ == "__main__":
    main()
