# AGENTS.md

<details open>
<summary>Português</summary>

## Objetivo do projeto
Este projeto é um MVP em Python para descobrir potenciais formadores para sessões internas da JuniFEUP, ordená-los por fit e gerar emails iniciais em PT-PT.

## Âmbito do MVP
O sistema deve:
1. receber um pedido de formação;
2. gerar queries de pesquisa pública;
3. encontrar candidatos em fontes públicas;
4. enriquecer dados básicos do perfil;
5. calcular um score de fit;
6. recomendar o canal de contacto;
7. gerar email inicial e mensagem LinkedIn.

## Fora de âmbito nesta fase
- envio automático de emails;
- automação de LinkedIn;
- scraping agressivo;
- integração com Gmail ou Calendar;
- autenticação do utilizador no LinkedIn.

## Stack preferida
- Python 3.11+
- Streamlit para UI
- SQLite para persistência
- Pydantic para modelos
- requests + BeautifulSoup para parsing simples
- pytest para testes
- python-dotenv para config local

## Regras de implementação
- escrever código simples, modular e legível;
- explicar cada passo antes de alterar ficheiros;
- criar o projeto por fases pequenas;
- mostrar sempre os ficheiros criados/alterados;
- usar typing;
- acrescentar comentários úteis, sem exagero;
- evitar dependências desnecessárias;
- manter tudo em PT-PT apenas nas mensagens geradas ao utilizador final;
- manter nomes de código em inglês.

## Regras de interação
- antes de implementar, propor um plano curto;
- depois, executar fase a fase;
- no fim de cada fase, resumir:
  1. o que foi feito
  2. que ficheiros mudaram
  3. que comando devo correr
  4. como validar manualmente

## Objetivo de UX
O utilizador deve conseguir:
- inserir tema, área, localização, formato e nº de participantes;
- ver shortlist de candidatos;
- ver score e motivo do fit;
- copiar email e mensagem LinkedIn.

</details>

<details>
<summary>English</summary>

## Project Goal
This project is a Python MVP to discover potential trainers for JuniFEUP internal sessions, rank them by fit, and generate initial outreach emails in PT-PT.

## MVP Scope
The system should:
1. receive a training request;
2. generate public search queries;
3. find candidates from public sources;
4. enrich basic profile data;
5. calculate a fit score;
6. recommend the contact channel;
7. generate the initial email and LinkedIn message.

## Out of Scope at This Stage
- automatic email sending;
- LinkedIn automation;
- aggressive scraping;
- Gmail or Calendar integration;
- user authentication on LinkedIn.

## Preferred Stack
- Python 3.11+
- Streamlit for the UI
- SQLite for persistence
- Pydantic for models
- requests + BeautifulSoup for simple parsing
- pytest for tests
- python-dotenv for local config

## Implementation Rules
- write simple, modular, and readable code;
- explain each step before changing files;
- create the project in small phases;
- always show the files created/changed;
- use typing;
- add useful comments, without overdoing it;
- avoid unnecessary dependencies;
- keep everything in PT-PT only in messages generated for the end user;
- keep code names in English.

## Interaction Rules
- before implementing, propose a short plan;
- then execute phase by phase;
- at the end of each phase, summarize:
  1. what was done
  2. which files changed
  3. which command I should run
  4. how to validate manually

## UX Goal
The user should be able to:
- enter topic, area, location, format, and number of participants;
- see a candidate shortlist;
- see the score and fit rationale;
- copy the email and LinkedIn message.

</details>
