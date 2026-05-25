from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class TrainingFormat(str, Enum):
    presencial = "presencial"
    remoto = "remoto"
    hibrido = "hibrido"
    indiferente = "indiferente"


class ContactChannel(str, Enum):
    email = "email"
    linkedin = "linkedin"
    formulario = "formulario"


class ProfileType(str, Enum):
    linkedin_profile = "linkedin_profile"
    personal_site = "personal_site"
    company_page = "company_page"
    job_board = "job_board"
    article_or_post = "article_or_post"
    unknown = "unknown"


class TrainingRequest(BaseModel):
    tema_formacao: str = Field(min_length=2)
    area_interna: str = ""
    descricao_contexto: str = ""

    localizacao: str | None = None
    formato: TrainingFormat = TrainingFormat.indiferente
    duracao: str | None = None
    numero_participantes: int | None = Field(default=None, ge=1)


class PublicLink(BaseModel):
    label: str
    url: HttpUrl


class Candidate(BaseModel):
    nome: str = Field(min_length=2)
    cargo: str | None = None
    empresa: str | None = None
    localizacao: str | None = None

    links: list[PublicLink] = Field(default_factory=list)
    email_publico: str | None = None

    fonte: str
    excerto: str | None = None
    matched_query: str | None = None
    source_domain: str | None = None
    linkedin_profile_url: str | None = None
    linkedin_profile_slug: str | None = None
    profile_slug: str | None = None
    search_rank: int | None = Field(default=None, ge=1)
    best_search_rank: int | None = Field(default=None, ge=1)
    search_ranks: list[int] = Field(default_factory=list)
    matched_queries: list[str] = Field(default_factory=list)
    queries_found_count: int = Field(default=0, ge=0)
    evidence_titles: list[str] = Field(default_factory=list)
    evidence_snippets: list[str] = Field(default_factory=list)
    training_signals: list[str] = Field(default_factory=list)
    topic_signals: list[str] = Field(default_factory=list)
    functional_signals: list[str] = Field(default_factory=list)
    evidence_query_count: int = Field(default=0, ge=0)
    snippet_raw: str | None = None
    result_title_raw: str | None = None
    profile_type: ProfileType = ProfileType.unknown
    is_probably_linkedin_profile: bool = False


class CandidateScore(BaseModel):
    fit_tematico: int = Field(ge=0, le=100)
    fit_funcional: int = Field(ge=0, le=100)
    experiencia_formacao: int = Field(ge=0, le=100)
    localizacao_score: int = Field(ge=0, le=100)
    contactabilidade: int = Field(ge=0, le=100)
    credibilidade_publica: int = Field(ge=0, le=100)
    linkedin_profile_quality_score: int = Field(default=0, ge=0, le=100)
    semantic_topic_match_score: int = Field(default=0, ge=0, le=100)
    trainer_signal_score: int = Field(default=0, ge=0, le=100)
    multi_query_evidence_score: int = Field(default=0, ge=0, le=100)
    linkedin_slug_confidence_score: int = Field(default=0, ge=0, le=100)
    improved_location_score: int = Field(default=0, ge=0, le=100)

    score_total: int = Field(ge=0, le=100)
    motivo: str


class ScoredCandidate(BaseModel):
    candidato: Candidate
    score: CandidateScore
    canal_recomendado: ContactChannel


class OutreachMessages(BaseModel):
    email_inicial: str
    mensagem_linkedin: str


class SearchDiagnostics(BaseModel):
    provider: str
    public_candidate_count: int = 0
    query_count: int = 0
    raw_result_count: int = 0
    eligible_result_count: int = 0
    blocked_query_count: int = 0
    block_reason: str | None = None
    fallback_used: bool = False
    fallback_provider: str | None = None
    fallback_reason: str | None = None


class CandidateResult(BaseModel):
    candidato_classificado: ScoredCandidate
    mensagens: OutreachMessages


class SearchRun(BaseModel):
    pedido: TrainingRequest
    queries: list[str]
    resultados: list[CandidateResult]
    diagnostics: SearchDiagnostics | None = None
