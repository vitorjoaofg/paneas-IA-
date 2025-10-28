# Paneas Real-Time Studio

Interface estatica para testar a captura por microfone, transcricao em tempo quase real, insights e chat com o LLM expostos pelo gateway FastAPI.

## Como executar

1. Garanta que o stack core esteja em execucao (`make up` ou `./scripts/start_core_stack.sh core`).
2. Sirva os arquivos estaticos (exemplo):
   ```bash
   cd frontend
   python3 -m http.server 5173
   ```
3. Abra `http://localhost:5173` no navegador, informe a URL da API (ex: `http://localhost:8000`) e um token valido.

## Recursos

- Envio de audio PCM16 (16 kHz) via WebSocket para `/api/v1/asr/stream` com janelas configuraveis.
- Controle para ativar ou desativar insights antes de iniciar a sessao.
- Painel de transcricao com timeline por lote, contadores de tokens e segundos.
- Painel de insights em tempo real.
- Chat completo com o endpoint `/api/v1/chat/completions` utilizando o mesmo token.
