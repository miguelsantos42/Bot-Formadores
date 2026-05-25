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

Por defeito, a app tenta usar pesquisa pública via Bing com um critério
restrito:

- só perfis pessoais de LinkedIn (`linkedin.com/in`);
- têm de ter sinal público de freelancer/independente;
- têm de ter sinal de experiência em formação, como formador, trainer,
  speaker, mentor ou workshop;
- o título ou snippet público tem de referir o tópico da formação.

```env
SEARCH_PROVIDER=public_web
PUBLIC_SEARCH_URL=https://www.bing.com/search
PUBLIC_SEARCH_TIMEOUT_SECONDS=5
PUBLIC_SEARCH_FALLBACK_TO_MOCK=true
```

Se a pesquisa pública não encontrar candidatos aproveitáveis, o fallback mostra
candidatos de demonstração para permitir testar o fluxo completo da app.

Para testar só com dados fictícios:

```env
SEARCH_PROVIDER=mock
```

Para desativar o fallback e ver zero candidatos quando a pesquisa pública falhar:

```env
PUBLIC_SEARCH_FALLBACK_TO_MOCK=false
```
