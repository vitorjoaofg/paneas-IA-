# Izzi Intelligence Dashboard – Guía Operacional

Este documento consolida todo o fluxo para gerar análises completas das 600 chamadas (ou novos lotes), atualizar o dashboard e operar a biblioteca de áudios.

---

## Status atual (out/2025)

- Base completa de 600 chamadas reprocessada com o pipeline `generate_full_analysis_v3.py --all --workers 8`, garantindo que o `public/data/full_analysis.json` reflita os resultados mais recentes.
- Não geramos novas diarizações via OpenAI; o fluxo presente prioriza as heurísticas locais + embeddings (SpeechBrain) e reaproveita as anotações existentes em `engine/diarization/output/` quando disponíveis.
- A aba **Visão Executiva** foi reconstruída para exibir KPIs estratégicos (resumo geral, qualidade operacional, alertas inteligentes, gráficos Recharts e exportação consolidada) calculados diretamente do JSON final.
- Exportações CSV incluem agora tanto as métricas agregadas quanto o detalhamento por chamada gerado pelo pipeline.

---

## Estrutura do Projeto

O diretório relevante fica em `~/Documents/Projects/izzi-intelligence-dashboard`. Dentro dele temos:

```
izzi-intelligence-dashboard/
├── engine/                # scripts + transcrições que geram o JSON analítico
│   ├── generate_full_analysis.py
│   ├── metadata.csv
│   ├── *.json             # 600 transcrições originais
│   └── full_analysis.json # saída processada mais recente
├── public/
│   ├── audio/             # áudios WAV copiados do lote original
│   └── data/
│       └── full_analysis.json # arquivo consumido pelo frontend
├── src/                   # código React/TypeScript do dashboard
│   └── App.tsx, types.ts, ...
├── package.json, vite.config.ts, etc.
└── ...
```

---

## Engine de processamento (`engine/`)

### Objetivo

`generate_full_analysis.py` consolida as transcrições e metadados, detecta divergências entre o status da Izzi e o comportamento real, calcula métricas agregadas e gera um JSON completo (`full_analysis.json`).

### Inputs

- `metadata.csv`: planilha original com status Izzi, fila, produto, duração, etc.
- `*.json`: arquivos de transcrição (uma chamada por arquivo).

### Saída

- `engine/full_analysis.json`: contém `dataset_summary`, `status_analysis`, `divergence_summary` e `per_call_details` (600 itens). O dashboard consome esse JSON.

### Comandos principais

1. Gerar/Regerar o arquivo analítico:
   ```bash
   cd ~/Documents/Projects/izzi-intelligence-dashboard
   python engine/generate_full_analysis.py
   ```

2. Copiar o JSON para o frontend (obrigatório após cada geração):
   ```bash
   cp engine/full_analysis.json public/data/full_analysis.json
   ```

3. (Opcional) Copiar novos áudios para uso no player:
   ```bash
   rsync -av ~/Downloads/izzi_batch_600_casos_01/audio/ public/audio/
   ```

### Personalizações implementadas

- Heurística para reconhecer fala de agente mesmo quando o ASR marcou erroneamente como “customer” (`AGENT_LANGUAGE_PATTERNS`).
- Heurística de “hold” para diferenciar chamadas em espera (`HOLD_KEYWORDS`).
- Ajuste automático de `status_real_detectado` em casos como “número inexistente” com diálogo, “sem áudio” com interação, etc.
- Campo `agent_language_detected` sinaliza onde o motor identificou linguagem típica de atendimento humano.
- **Diarização assistida por LLM (v3.1)**: novo fluxo `engine/diarization/run_diarization.py` roda uma heurística inicial e valida cada segmento com o modelo `gpt-4o-mini`, gerando `engine/diarization/output/<call_id>.annotated.json`. Esses arquivos substituem os papéis do transcript quando presentes, garantindo que IVR / cliente / agente apareçam corretamente no dashboard.
- `engine/generate_full_analysis_v3.py` detecta automaticamente as anotações em `diarization/output/` e recalcula métricas de tempo/palavras já com os papéis corrigidos (dispensa o uso do LLM para “segment corrections”).
- O frontend (`AudioLibraryTab`) agora prioriza as anotações em `diarization/output/` ao renderizar os turnos, mantendo a transcrição original porém com o papel correto.

### Como adicionar novos lotes de chamadas

1. Coloque os novos JSONs de transcrição em `engine/` (mesmo formato do lote original).
2. Atualize/mescle `metadata.csv` com as linhas correspondentes (mantendo `file_id` coerente).
3. (Se houver novos áudios) copie para `public/audio/` com o mesmo padrão de nome (`<call_id>.WAV`).
4. Execute `python engine/generate_full_analysis.py` e depois copie o novo `full_analysis.json` para `public/data/`.

> **Dica:** mantenha os arquivos antigos como backup em outro diretório, caso queira processamento incremental.

---

## Frontend (`src/`)

### Objetivo

Dashboard React + Vite inspirado em Cupertino (dark/glassmorphism) com múltiplas abas analíticas, filtros persistentes e biblioteca de áudios com player.

### Rodar localmente

```bash
cd ~/Documents/Projects/izzi-intelligence-dashboard
npm install      # apenas na primeira vez
npm run dev      # inicia em modo desenvolvimento
# ou
npm run build    # build de produção (output em dist/)
```

### Seções principais

1. **Panorama**: KPIs gerais, detecção automática de casos críticos, insights inteligentes, tabela por fila, tendência diária, etc.
2. **Comparativo**: heatmap IZZI × Realidade, top erros de classificação, ranking por filtros.
3. **Correlação**: scatter/hist com silêncio, duração, fala do cliente vs. divergência, sentiment × divergência.
4. **Temporal**: linha com divergência por hora/dia e filtros por data.
5. **Precisão & Ruído**: histogramas de silêncio, top 10 ruído, correlação SNR.
6. **Biblioteca de Áudios**: grid paginado com player, filtros avançados `chave:valor` (status, duração, engajamento, silêncio, motivo, etc.) e busca livre.

### Dados consumidos pelo front

- `public/data/full_analysis.json`: carregado via `fetch('/data/full_analysis.json')`. Atualize sempre que a engine gerar um novo arquivo.
- `public/audio/*.WAV`: os players `<audio>` usam o caminho `/audio/<call_id>.WAV`.

### Exemplo de filtros avançados na biblioteca

```
status:dialogo motivo:dialogo silencio:0-0.3 engajamento:0.4-1 produto:internet
```

Use espaços para combinar (`token` separado). Termos livres também funcionam (ex.: `gonzález`, `fax`, `premium`).

Filtros disponíveis:
- `status`, `status_real`
- `produto`, `fila`, `contato`
- `sentimento`, `sentimento_agente`
- `divergente` (sim/nao)
- `duracao`, `engajamento`, `silencio`, `palavras`
- `motivo`

---

## Dados brutos (áudios & transcrições)

- Áudios originais (lote 600) em `~/Downloads/izzi_batch_600_casos_01/audio`. Cópia usada pelo projeto em `public/audio/`.
- Transcrições `.json` em `engine/` (mesmo nome base do áudio). Importante mantê-los sincronizados.

Se receber novos lotes, repita o padrão de nomes (ou atualize o script caso o formato mude).

---

## Fluxo recomendado ao atualizar

1. **Sincronizar audios e metadados**
   - Copiar novos `.json` para `engine/`.
   - Atualizar `metadata.csv` com as novas linhas.
   - Opcional: copiar `.WAV` para `public/audio/`.

2. **Rodar engine**
   - Pipeline heurístico (v1):
     ```bash
     cd ~/Documents/Projects/izzi-intelligence-dashboard
     python engine/generate_full_analysis.py
     cp engine/full_analysis.json public/data/full_analysis.json
     ```
   - Pipeline completo (v2):
     ```bash
     python engine/generate_full_analysis_v2.py --model gpt-4o-mini
     ```
     Use `--no-llm` para gerar apenas as heurísticas sem enriquecimento.
   - **Pipeline com diarização de alta precisão (v3.1):**
     ```bash
     # 1. Gera as anotações (uma vez por chamada)
     python engine/diarization/run_diarization.py --call-id <CALL_ID>
     # ou para várias chamadas
     python engine/diarization/run_diarization.py --call-id <ID1> --call-id <ID2> ...

     # 2. Recalcula o full_analysis com os papéis corrigidos
     python engine/generate_full_analysis_v3.py --call-id <CALL_ID>
     ```
     O script de diarização carrega a transcrição original, aplica heurísticas e valida cada segmento via `gpt-4o-mini`. O resultado fica em `engine/diarization/output/<call_id>.annotated.json` e passa a ser consumido automaticamente pelo pipeline v3 e pela biblioteca de áudios.

3. **Validar**
   - `npm run dev` e conferir as abas (Panorama, Comparativo, Biblioteca…).
   - Usar filtros avançados para auditar os casos recém-gerados.
   - Na aba **Biblioteca de áudios**, conferir se os chips de papel (IVR, Cliente, Atendente) refletem o diálogo real. Com o novo pipeline, os cinco IDs validados (`0105-04965-25090100083024-5544389947-20250901-081937-5593478000`, `0105-04965-25090100224687-5544389980-20250901-094632-5585261962`, `0105-04965-25090100340034-5544389989-20250901-105814-5541668256`, `0105-04965-25090100357014-5544389941-20250901-110901-5526022382`, `0105-04965-25090100367700-5544389973-20250901-111540-5524852542`) já estão corrigidos e servem como referência.

4. **Build (opcional)**
   ```bash
   npm run build
   ```

---

## Observações finais

- `full_analysis.json` inclui sinais auxiliares (`agent_language_detected`, `contains_*_keywords`, `silence_ratio`, etc.) para investigações rápidas.
- Mudanças na heurística (ex.: falar outro idioma, novos padrões de hold) devem ser feitas em `engine/generate_full_analysis.py`. Depois regenere e copie o JSON para `public/data/`.
- Os filtros superiores (Panorama) ficam salvos no `localStorage` (`izzi-dashboard-filters-v2`). Para resetar tudo, use o botão “Resetar filtros” ou limpe esse item no console do navegador.
- O player de áudio usa arquivos `.WAV` com o mesmo `call_id`. Qualquer mismatch de nome impede a reprodução (verifique ao adicionar novos áudios).

Qualquer nova fonte (ex.: transcrições em outro formato) precisa seguir esse pipeline: transcrição → `metadata.csv` → engine → `public/data/full_analysis.json` → frontend.
