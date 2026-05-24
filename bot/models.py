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
    tema_formacao: str = Field(min_length=3)
    area_interna: str = Field(min_length=2)
    descricao_contexto: str = Field(min_length=10)

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
    search_rank: int | None = Field(default=None, ge=1)
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

    score_total: int = Field(ge=0, le=100)
    motivo: str


class ScoredCandidate(BaseModel):
    candidato: Candidate
    score: CandidateScore
    canal_recomendado: ContactChannel


class OutreachMessages(BaseModel):
    email_inicial: str
    mensagem_linkedin: str


class CandidateResult(BaseModel):
    candidato_classificado: ScoredCandidate
    mensagens: OutreachMessages


class SearchRun(BaseModel):
    pedido: TrainingRequest
    queries: list[str]
    resultados: list[CandidateResult]
