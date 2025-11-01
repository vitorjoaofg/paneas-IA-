# TJSP Process Scraper – Notas da Tarefa

> Última atualização: <!--DATE-->2025-10-20<!--/DATE-->

## Resumo
- Objetivo: expor uma API (e manifesto MCP) chamada `tjsp_consulta_processo` que consulta o e-SAJ/TJSP usando Playwright e retorna informações estruturadas do processo.
- A API FastAPI vive em `scrapper/api/`, com modelos Pydantic (`models.py`) e automação Playwright (`scraper.py`).
- A infraestrutura docker (`Dockerfile`, `docker-compose.yml`) executa a API com Playwright headless, ouvindo em `8080` e publicado localmente em `8089`.

## Implementação Atual
- Endpoints:
  - `POST /tools/tjsp_consulta_processo` – corpo `TJSPProcessoQuery`, retorna `ProcessoTJSP`.
  - `POST /v1/processos/consulta` – alias útil para testes diretos.
  - `GET /tools` – manifesto MCP (incluído.
- Playwright:
  - Navega `open.do` → preenche formulário → envia → tenta abrir `show.do`.
  - `scraper.py` contém lógica de fallback para inputs (aria-labels), tratamento parcial de `search.do` e expansão de seções “Mais”.
  - Extração `_EXTRACT_SCRIPT` captura campos principais, partes, movimentações, distribuição e audiências.
  - Pós-processamento `_parse_*` converte em `ProcessoTJSP` e infere `situacaoProcessual`, `tipoJuizo`, `inicio/ultima_atualizacao`.
- Configuração:
  - `config.py` define `SCRAPPER_*` envs (browser, timeout, headless).
  - Requisitos: Playwright 1.49, FastAPI 0.119, Pydantic v2, httpx 0.28.

## Como Rodar
1. `cd scrapper`
2. `docker compose up -d --build`
3. Testes:
   ```bash
   curl -s http://localhost:8089/tools
   curl -s -X POST http://localhost:8089/tools/tjsp_consulta_processo \
        -H 'Content-Type: application/json' \
        -d '{"numero_processo":"1014843-66.2025.8.26.0554","foro":"554"}'
   ```
4. Logs: `docker compose logs -f`
5. Debug dentro do container:
   ```bash
   docker compose exec tools python - <<'PY'
   import asyncio
   from api.scraper import fetch_tjsp_process
   from api.models import TJSPProcessoQuery

   async def main():
       result = await fetch_tjsp_process(TJSPProcessoQuery(numero_processo="1014843-66.2025.8.26.0554", foro="554"))
       print(result.model_dump())

   asyncio.run(main())
   PY
   ```

## Problemas Conhecidos
- `ensure_page_is_ready` ainda executa `page.content()` enquanto navegação `open.do → search.do` acontece dentro do container, ocasionando `Page.content: Unable to retrieve content because the page is navigating`.
  - Fora do container (via MCP Playwright manual) o fluxo funciona, então a sincronização precisa de ajustes (espera explícita por `search.do` + `show.do`).
- Quando o portal responde “O tipo de pesquisa informado é inválido” (queda eventual), a lógica precisa refazer o submit com o hidden `dadosConsulta.valorConsultaNuUnificado` preenchido corretamente.
- Resiliência a 503 (`Service Unavailable`) ainda depende de retry manual (há stub com três tentativas, mas precisa observar se o status 503 é propagado antes).
- Extração:
  - `requerente/advogadoConsumidor` retornam `None` quando o HTML usa uppercase extra (necessário sanitizar com `.title()` ou regex).
  - `tipoJuizo` é inferido por heurística (`area`); validar com mais casos.

## Próximos Passos Imediatos
1. **Sincronização Playwright** – substituir `page.content()` por uma espera mais segura (`wait_for_load_state('networkidle', timeout)`, `page.wait_for_url`, ou `page.expect_navigation`) e, se necessário, detectar quando `page.url` permanece em `search.do` e clicar no primeiro `a[href*="show.do"]`.
2. **Retry inteligente** – se o alerta “O tipo de pesquisa informado é inválido” aparecer, recompor o formulário (incluindo campo hidden) e reenviar, com um pequeno atraso.
3. **Validar campos** – adicionar asserts/exceções claras caso valores essenciais (`numeroProcesso`, `partes`, `movimentos`) venham vazios; criar testes unitários com HTML salva (fixtures) para garantir parsing estável.
4. **Monitorar limite TJSP** – considerar backoff exponencial quando a API detectar `Service Unavailable`.

## Referências Úteis
- Página alvo: `https://esaj.tjsp.jus.br/cpopg/open.do`
- Exemplo de processo válido: `1014843-66.2025.8.26.0554` (Foro 554)
- Ferramentas MCP Playwright (histórico desta sessão) mostram seletor dos inputs e mensagens de erro para replicar ajustes.

Mantenha este arquivo atualizado ao final de cada iteração para facilitar retomadas futuras.

## Sessão 2025-10-20
- `docker compose up -d --build` iniciou o container `scrapper-tools` sem erros (Uvicorn ouvindo em `0.0.0.0:8080`).
- `GET /tools` respondeu com o manifesto MCP contendo a tool `tjsp_consulta_processo`.
- `POST /tools/tjsp_consulta_processo` (processo `1014843-66.2025.8.26.0554`, foro 554) retornou o payload completo em ~5s.
- `POST /v1/processos/consulta` reproduziu `Page.content: Unable to retrieve content because the page is navigating...`, consistente com o problema listado em “Sincronização Playwright”.
- Implementada a tool `tjsp_listar_processos` (`POST /tools/tjsp_listar_processos` / `/v1/processos/listar`) que consulta a listagem do TJSP por documento/nome, suporta filtro opcional `contra_parte` e paginação (`max_paginas`, `max_processos`).
