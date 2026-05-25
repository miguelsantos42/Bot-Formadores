# Bot-Formadores

MVP local em Python para apoiar a descoberta de potenciais formadores para sessões internas da JuniFEUP.

## Objetivo

O sistema recebe um pedido de formação, gera pesquisas públicas, recolhe candidatos, calcula um score de fit, recomenda um canal de contacto e gera mensagens iniciais.

## Fora de âmbito

- Envio automático de emails
- Automação de LinkedIn
- Acesso à conta LinkedIn

## Correr localmente

Este projeto é uma app Streamlit. Não deve ser arrancado com `python app.py`.

```bash
cd /Users/miguel/Desktop/JuniFEUP/Bot-Formadores
source .venv/bin/activate
streamlit run app.py
```

Depois abre:

```text
http://localhost:8501
```

Se a porta 8501 já estiver ocupada, usa outra:

```bash
streamlit run app.py --server.port 8502
```

## Pesquisa pública e fallback

Só o campo `Tema da formação` é obrigatório. Os restantes campos servem apenas
para afinar a pesquisa quando fizer sentido.

Por defeito, a app tenta usar a Brave Search API com estratégia
LinkedIn-only recall-then-rerank:

- só perfis pessoais de LinkedIn (`linkedin.com/in`);
- não pesquisa empresas, jobs, posts, feed, pulse, school, blogs ou sites externos;
- gera queries por buckets com PT + EN, sinais de formação, função/domínio,
  localização e queries exploratórias;
- deixa entrar perfis plausíveis com filtro mínimo;
- junta evidência quando o mesmo perfil aparece em várias queries;
- ranqueia depois por qualidade LinkedIn, match temático, sinais de formador,
  evidência multi-query, slug LinkedIn e localização.

```env
SEARCH_PROVIDER=brave_search
BRAVE_SEARCH_API_KEY=coloca_a_tua_key_aqui
BRAVE_SEARCH_URL=https://api.search.brave.com/res/v1/web/search
PUBLIC_SEARCH_URL=https://www.bing.com/search
PUBLIC_SEARCH_TIMEOUT_SECONDS=5
PUBLIC_SEARCH_MAX_RESULTS=25
PUBLIC_SEARCH_FALLBACK_TO_MOCK=false
```

Se `SEARCH_PROVIDER=brave_search` estiver ativo sem `BRAVE_SEARCH_API_KEY`, a
app mostra um erro de configuração explícito.

Com `PUBLIC_SEARCH_FALLBACK_TO_MOCK=false`, a app não inventa candidatos: se a
pesquisa pública não encontrar perfis pessoais públicos do LinkedIn que passem
o filtro mínimo, mostra zero candidatos.

O provider antigo de HTML SERP continua disponível apenas para desenvolvimento:

```env
SEARCH_PROVIDER=public_web
```

Para testar só com dados fictícios:

```env
SEARCH_PROVIDER=mock
```

Para voltar a permitir dados de demonstração quando a pesquisa pública falhar:

```env
PUBLIC_SEARCH_FALLBACK_TO_MOCK=true
```
