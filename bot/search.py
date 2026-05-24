from abc import ABC, abstractmethod

from bot.models import Candidate, PublicLink, TrainingRequest


class SearchProvider(ABC):
    @abstractmethod
    def search(self, request: TrainingRequest) -> list[Candidate]:
        """Return candidates for a training request."""


def generate_search_queries(request: TrainingRequest) -> list[str]:
    base_terms = [
        request.tema_formacao,
        request.area_interna,
    ]

    if request.localizacao:
        base_terms.append(request.localizacao)

    main_query = " ".join(base_terms)

    return [
        f"{main_query} formador",
        f"{main_query} speaker",
        f"{main_query} workshop",
        f"{main_query} palestra",
        f'{request.tema_formacao} "{request.area_interna}" LinkedIn',
    ]


class MockSearchProvider(SearchProvider):
    def search(self, request: TrainingRequest) -> list[Candidate]:
        queries = generate_search_queries(request)

        return [
            Candidate(
                nome="Ana Silva",
                cargo=f"Especialista em {request.tema_formacao}",
                empresa="Tech Learning Studio",
                localizacao=request.localizacao or "Portugal",
                links=[
                    PublicLink(
                        label="LinkedIn",
                        url="https://www.linkedin.com/in/ana-silva",
                    ),
                    PublicLink(
                        label="Website",
                        url="https://example.com/ana-silva",
                    ),
                ],
                email_publico="ana.silva@example.com",
                fonte="mock",
                excerto=(
                    f"Perfil encontrado para a query '{queries[0]}'. "
                    "Experiência em workshops e sessões práticas."
                ),
            ),
            Candidate(
                nome="Joao Pereira",
                cargo="Consultor e formador",
                empresa="Freelancer",
                localizacao="Porto",
                links=[
                    PublicLink(
                        label="LinkedIn",
                        url="https://www.linkedin.com/in/joao-pereira",
                    )
                ],
                email_publico=None,
                fonte="mock",
                excerto=(
                    f"Perfil encontrado para a query '{queries[1]}'. "
                    "Conteúdos públicos indicam experiência como speaker."
                ),
            ),
            Candidate(
                nome="Mariana Costa",
                cargo="Head of People Development",
                empresa="Empresa Exemplo",
                localizacao="Lisboa",
                links=[
                    PublicLink(
                        label="Perfil publico",
                        url="https://example.com/mariana-costa",
                    )
                ],
                email_publico="formacao@example.com",
                fonte="mock",
                excerto=(
                    f"Perfil encontrado para a query '{queries[2]}'. "
                    "Ligação forte a aprendizagem interna e desenvolvimento de equipas."
                ),
            ),
        ]
