const ui = {
    statusBadge: document.getElementById("sessionStatus"),
    footerStatus: document.getElementById("footerStatus"),
    sessionId: document.getElementById("sessionId"),
    batchCount: document.getElementById("batchCount"),
    tokenCount: document.getElementById("tokenCount"),
    audioSeconds: document.getElementById("audioSeconds"),
    transcript: document.getElementById("transcriptText"),
    timeline: document.getElementById("batchTimeline"),
    insights: document.getElementById("insightsList"),
    insightStatus: document.getElementById("insightStatus"),
    startButton: document.getElementById("startButton"),
    stopButton: document.getElementById("stopButton"),
    apiBase: document.getElementById("apiBase"),
    authToken: document.getElementById("authToken"),
    chunkSize: document.getElementById("chunkSize"),
    diarizationToggle: document.getElementById("diarizationToggle"),
    insightToggle: document.getElementById("insightToggle"),
    insightModel: document.getElementById("insightModel"),
    chatLog: document.getElementById("chatLog"),
    chatForm: document.getElementById("chatForm"),
    chatInput: document.getElementById("chatInput"),
    chatModel: document.getElementById("chatModel"),
    chatKeepHistory: document.getElementById("chatKeepHistory"),
    chatTools: document.getElementById("chatTools"),
    chatSystemPrompt: document.getElementById("chatSystemPrompt"),
    chatPlaceholder: document.querySelector(".chat__placeholder"),
    chatClear: document.getElementById("clearChat"),
    listeningIndicator: document.getElementById("listeningIndicator"),
    roomId: document.getElementById("roomId"),
    roleSelector: document.getElementById("roleSelector"),
    roomStatus: document.getElementById("roomStatus"),
    asrFileInput: document.getElementById("asrFileInput"),
    asrUploadButton: document.getElementById("asrUploadButton"),
    asrResult: document.getElementById("asrResult"),
    streamFileInput: document.getElementById("streamFileInput"),
    streamFileButton: document.getElementById("streamFileButton"),
    streamStatus: document.getElementById("streamStatus"),
    ocrFileInput: document.getElementById("ocrFileInput"),
    ocrButton: document.getElementById("ocrButton"),
    ocrResult: document.getElementById("ocrResult"),
    diarFileInput: document.getElementById("diarFileInput"),
    diarButton: document.getElementById("diarButton"),
    diarResult: document.getElementById("diarResult"),
    numSpeakers: document.getElementById("numSpeakers"),
    ttsVoice: document.getElementById("ttsVoice"),
    ttsText: document.getElementById("ttsText"),
    ttsButton: document.getElementById("ttsButton"),
    ttsResult: document.getElementById("ttsResult"),
    ttsAudioPlayer: document.getElementById("ttsAudioPlayer"),
    ttsMetadata: document.getElementById("ttsMetadata"),
    ttsDownload: document.getElementById("ttsDownload"),
    ttsStatus: document.getElementById("ttsStatus"),
    ttsStreamButton: document.getElementById("ttsStreamButton"),
    ttsStreamResult: document.getElementById("ttsStreamResult"),
    ttsStreamPlayer: document.getElementById("ttsStreamPlayer"),
    ttsStreamMetadata: document.getElementById("ttsStreamMetadata"),
    ttsStreamStop: document.getElementById("ttsStreamStop"),
    streamingStatusText: document.getElementById("streamingStatusText"),
    streamingText: document.getElementById("streamingText"),
    scrapperConsultaForm: document.getElementById("scrapperConsultaForm"),
    scrapperConsultaSubmit: document.getElementById("scrapperConsultaSubmit"),
    scrapperConsultaReset: document.getElementById("scrapperConsultaReset"),
    scrapperConsultaResult: document.getElementById("scrapperConsultaResult"),
    scrapperListForm: document.getElementById("scrapperListForm"),
    scrapperListSubmit: document.getElementById("scrapperListSubmit"),
    scrapperListReset: document.getElementById("scrapperListReset"),
    scrapperListResult: document.getElementById("scrapperListResult"),
    scrapperToolsButton: document.getElementById("scrapperToolsButton"),
    scrapperToolsResult: document.getElementById("scrapperToolsResult"),
};

const state = {
    ws: null,
    sessionId: null,
    sessionStarted: false,
    streaming: false,
    insightsRequested: true,
    audioContext: null,
    processor: null,
    gainNode: null,
    mediaStream: null,
    inputSampleRate: 48000,
    targetSampleRate: 16000,
    chunkSamples: 12800,
    pcmBuffer: new Int16Array(0),
    batches: 0,
    tokens: 0,
    audioSeconds: 0,
    aggregatedTranscript: "",
    previousTranscript: "",
    timeline: [],
    insights: [],
    chatHistory: [],
    availableTools: {
        unimed: {
            type: "function",
            function: {
                name: "unimed_consult",
                description: "Consulta dados do beneficiário na Unimed",
                parameters: {
                    type: "object",
                    properties: {
                        url_template: {
                            type: "string",
                            description: "Template da URL",
                            default: "https://unimed-central-cobranca.paneas.net/api/v1/{cidade}/{tipo}/{protocolo}/{cpf}/{data_nascimento}"
                        },
                        cpf: {
                            type: "string",
                            description: "CPF do beneficiário (apenas números)"
                        },
                        data_nascimento: {
                            type: "string",
                            description: "Data de nascimento no formato AAAAMMDD"
                        },
                        cidade: {
                            type: "string",
                            description: "Cidade",
                            default: "Natal_Tasy"
                        },
                        tipo: {
                            type: "string",
                            description: "Tipo de consulta",
                            default: "Carteira_Virtual"
                        },
                        protocolo: {
                            type: "string",
                            description: "Número do protocolo",
                            default: "0"
                        },
                        method: {
                            type: "string",
                            description: "Método HTTP",
                            default: "GET"
                        }
                    },
                    required: ["cpf", "data_nascimento"]
                }
            }
        },
        weather: {
            type: "function",
            function: {
                name: "get_weather",
                description: "Consulta o clima atual de uma cidade",
                parameters: {
                    type: "object",
                    properties: {
                        cidade: {
                            type: "string",
                            description: "Nome da cidade"
                        },
                        pais: {
                            type: "string",
                            description: "País (opcional)",
                            default: "Brasil"
                        }
                    },
                    required: ["cidade"]
                }
            }
        }
    },
    awaitingStopAck: false,
    roomId: null,
    role: null,
    roomStatus: null,
    streamSource: "mic",
    useFileStream: false,
    fileStreamData: null,
    fileStreamOffset: 0,
    fileStreamTimer: null,
    currentAudioBlob: null,
    currentAudioMetadata: null,
    streamingAudio: false,
    streamMediaSource: null,
    streamSourceBuffer: null,
    streamingTextInterval: null,
    streamingTextWords: [],
    streamingStartTime: null,
    streamingTextDuration: 0,
};

function trimTrailingSlash(url) {
    return url.replace(/\/$/, "");
}

function resolveApiBase() {
    let base = ui.apiBase.value.trim();
    if (!base) {
        base = window.location.origin;
    }
    return trimTrailingSlash(base);
}

function buildAuthHeaders(extra = {}) {
    const headers = { ...extra };
    const token = ui.authToken.value.trim();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }
    return headers;
}

function setOutput(element, content) {
    if (!element) {
        return;
    }
    element.textContent = content;
}

function prettyPrintJson(data) {
    try {
        return JSON.stringify(data, null, 2);
    } catch (err) {
        return String(data);
    }
}

function collectScrapperPayload(form, numericFields = []) {
    if (!form) {
        return {};
    }
    const numericSet = new Set(numericFields);
    const formData = new FormData(form);
    const payload = {};

    formData.forEach((value, key) => {
        if (typeof value !== "string") {
            return;
        }
        const trimmed = value.trim();
        if (!trimmed) {
            return;
        }

        if (numericSet.has(key)) {
            const parsed = parseInt(trimmed, 10);
            if (!Number.isNaN(parsed)) {
                payload[key] = parsed;
            }
            return;
        }

        payload[key] = trimmed;
    });

    return payload;
}

function resetScrapperForm(form, resultElement, placeholder) {
    form?.reset();
    if (placeholder && resultElement) {
        setOutput(resultElement, placeholder);
    }
}

async function callScrapperEndpoint(path, { method = "GET", payload = null } = {}) {
    const base = resolveApiBase();
    const url = `${base}/api/v1/scrapper/${path}`;
    const headers = payload
        ? buildAuthHeaders({ "Content-Type": "application/json" })
        : buildAuthHeaders();

    const response = await fetch(url, {
        method,
        headers,
        body: payload ? JSON.stringify(payload) : undefined,
    });

    if (!response.ok) {
        const errorText = await response.text().catch(() => "");
        const message = errorText || `HTTP ${response.status}: ${response.statusText}`;
        throw new Error(message);
    }

    return response.json();
}

async function submitScrapperConsulta() {
    if (!ui.scrapperConsultaResult || !ui.scrapperConsultaForm) {
        return;
    }

    const payload = collectScrapperPayload(ui.scrapperConsultaForm);
    if (Object.keys(payload).length === 0) {
        setOutput(ui.scrapperConsultaResult, "Informe pelo menos um critério de busca.");
        return;
    }

    setOutput(ui.scrapperConsultaResult, "Consultando processo...");
    const originalLabel = ui.scrapperConsultaSubmit?.textContent;
    if (ui.scrapperConsultaSubmit) {
        ui.scrapperConsultaSubmit.disabled = true;
        ui.scrapperConsultaSubmit.textContent = "Consultando...";
    }

    try {
        const data = await callScrapperEndpoint("processos/consulta", {
            method: "POST",
            payload,
        });
        setOutput(ui.scrapperConsultaResult, prettyPrintJson(data));
    } catch (err) {
        console.error("[Scrapper] Falha ao consultar processo", err);
        setOutput(ui.scrapperConsultaResult, `Erro: ${err.message || err}`);
    } finally {
        if (ui.scrapperConsultaSubmit) {
            ui.scrapperConsultaSubmit.disabled = false;
            ui.scrapperConsultaSubmit.textContent = originalLabel || "Consultar";
        }
    }
}

async function submitScrapperList() {
    if (!ui.scrapperListForm || !ui.scrapperListResult) {
        return;
    }

    const payload = collectScrapperPayload(ui.scrapperListForm, ["max_paginas", "max_processos"]);
    if (Object.keys(payload).length === 0) {
        setOutput(ui.scrapperListResult, "Informe pelo menos um critério de busca.");
        return;
    }

    setOutput(ui.scrapperListResult, "Carregando lista de processos...");
    const originalLabel = ui.scrapperListSubmit?.textContent;
    if (ui.scrapperListSubmit) {
        ui.scrapperListSubmit.disabled = true;
        ui.scrapperListSubmit.textContent = "Listando...";
    }

    try {
        const data = await callScrapperEndpoint("processos/listar", {
            method: "POST",
            payload,
        });
        setOutput(ui.scrapperListResult, prettyPrintJson(data));
    } catch (err) {
        console.error("[Scrapper] Falha ao listar processos", err);
        setOutput(ui.scrapperListResult, `Erro: ${err.message || err}`);
    } finally {
        if (ui.scrapperListSubmit) {
            ui.scrapperListSubmit.disabled = false;
            ui.scrapperListSubmit.textContent = originalLabel || "Listar Processos";
        }
    }
}

async function loadScrapperManifest() {
    if (!ui.scrapperToolsResult) {
        return;
    }

    setOutput(ui.scrapperToolsResult, "Carregando manifesto...");
    const originalLabel = ui.scrapperToolsButton?.textContent;
    if (ui.scrapperToolsButton) {
        ui.scrapperToolsButton.disabled = true;
        ui.scrapperToolsButton.textContent = "Carregando...";
    }

    try {
        const data = await callScrapperEndpoint("tools");
        setOutput(ui.scrapperToolsResult, prettyPrintJson(data));
    } catch (err) {
        console.error("[Scrapper] Falha ao carregar manifesto", err);
        setOutput(ui.scrapperToolsResult, `Erro: ${err.message || err}`);
    } finally {
        if (ui.scrapperToolsButton) {
            ui.scrapperToolsButton.disabled = false;
            ui.scrapperToolsButton.textContent = originalLabel || "Carregar manifesto";
        }
    }
}

function setStatus(message, tone = "idle") {
    const toneMap = {
        idle: { text: "Offline", className: "" },
        connecting: { text: "Conectando", className: "" },
        ready: { text: "Pronto", className: "" },
        streaming: { text: "Transmitindo", className: "" },
        stopping: { text: "Encerrando", className: "" },
        error: { text: "Erro", className: "" },
    };
    if (tone in toneMap) {
        ui.statusBadge.textContent = toneMap[tone].text;
    } else {
        ui.statusBadge.textContent = tone;
    }
    ui.footerStatus.textContent = message;
}

function updateStats() {
    ui.batchCount.textContent = state.batches.toString();
    ui.tokenCount.textContent = state.tokens.toString();
    ui.audioSeconds.textContent = state.audioSeconds.toFixed(1);
}

function renderTranscript() {
    if (!state.aggregatedTranscript) {
        ui.transcript.innerHTML = '<span class="transcript__placeholder">Fale apos iniciar a captura para ver a transcricao acumulada aqui.</span>';
        return;
    }

    const currentText = state.aggregatedTranscript;
    const previousText = state.previousTranscript;

    // Se é a primeira transcrição (estava vazio), remove o placeholder
    if (!previousText && currentText) {
        ui.transcript.innerHTML = '';
    }

    // Se o texto é completamente diferente, renderiza tudo de uma vez
    if (!currentText.startsWith(previousText)) {
        ui.transcript.innerHTML = escapeHtml(currentText);
        state.previousTranscript = currentText;
        smoothScrollTranscript();
        return;
    }

    // Extrai apenas o texto novo
    const newText = currentText.slice(previousText.length);

    if (newText) {
        // Separa em palavras
        const words = newText.split(/(\s+)/);

        // Adiciona palavras com delay progressivo para efeito de "digitação"
        words.forEach((word, index) => {
            setTimeout(() => {
                if (word.trim()) {
                    const span = document.createElement('span');
                    span.className = 'word-new';
                    span.textContent = word;
                    ui.transcript.appendChild(span);

                    // Remove highlight depois de 1.5s
                    setTimeout(() => {
                        span.classList.remove('word-new');
                        span.classList.add('word-faded');
                    }, 1500);
                } else if (word) {
                    // Adiciona espaços
                    ui.transcript.appendChild(document.createTextNode(word));
                }

                smoothScrollTranscript();
            }, index * 50); // 50ms de delay entre cada palavra
        });

        // Atualiza previousTranscript depois que todas as palavras forem agendadas
        setTimeout(() => {
            state.previousTranscript = currentText;
        }, words.length * 50);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function smoothScrollTranscript() {
    ui.transcript.scrollTo({
        top: ui.transcript.scrollHeight,
        behavior: 'smooth'
    });
}

function renderTimeline() {
    ui.timeline.innerHTML = "";
    const fragment = document.createDocumentFragment();
    state.timeline.slice(-20).forEach((item) => {
        const div = document.createElement("div");
        div.className = "timeline__item";
        const top = document.createElement("div");
        top.className = "timeline__meta";
        const tokensInfo = typeof item.tokens === "number" && item.tokens > 0 ? ` | ${item.tokens} tokens` : "";
        top.innerHTML = `<span>Lote #${item.batch}</span><span>${item.duration.toFixed(1)}s${tokensInfo}</span>`;
        const body = document.createElement("div");
        body.textContent = item.text || "(texto vazio)";
        div.appendChild(top);
        div.appendChild(body);
        fragment.appendChild(div);
    });
    ui.timeline.appendChild(fragment);
    ui.timeline.scrollTop = ui.timeline.scrollHeight;
}

function renderInsights() {
    ui.insights.innerHTML = "";
    if (!state.insights.length) {
        const p = document.createElement("p");
        p.textContent = "Nenhum insight emitido ainda.";
        ui.insights.appendChild(p);
        return;
    }
    const fragment = document.createDocumentFragment();
    state.insights.forEach((insight) => {
        const container = document.createElement("div");
        container.className = "insight";
        const meta = document.createElement("div");
        meta.className = "insight__meta";
        const ts = new Date(insight.generated_at || Date.now());
        meta.innerHTML = `<span>${insight.type || "Insight"}</span><span>${ts.toLocaleTimeString()}</span>`;
        const body = document.createElement("div");
        body.textContent = insight.text || "(sem texto)";
        container.appendChild(meta);
        container.appendChild(body);
        fragment.appendChild(container);
    });
    ui.insights.appendChild(fragment);
}

function renderChat() {
    ui.chatLog.innerHTML = "";
    if (!state.chatHistory.length) {
        const placeholder = document.createElement("div");
        placeholder.className = "chat__placeholder";
        placeholder.textContent = "Converse com o modelo enquanto a chamada acontece.";
        ui.chatLog.appendChild(placeholder);
        return;
    }
    const fragment = document.createDocumentFragment();
    state.chatHistory.forEach((message, index) => {
        const bubble = document.createElement("div");
        bubble.className = `chat__bubble chat__bubble--${message.role}`;

        // Se é a última mensagem do assistente e está vazia, mostra cursor piscando
        if (message.role === "assistant" && !message.content && index === state.chatHistory.length - 1) {
            bubble.innerHTML = '<span class="chat__cursor">▊</span>';
        } else {
            bubble.textContent = message.content || "";
            // Se está sendo streamado (última mensagem não vazia do assistente), adiciona cursor
            if (message.role === "assistant" && message.content && index === state.chatHistory.length - 1 && ui.chatInput.disabled) {
                bubble.innerHTML = message.content + '<span class="chat__cursor">▊</span>';
            }
        }
        fragment.appendChild(bubble);
    });
    ui.chatLog.appendChild(fragment);
    ui.chatLog.scrollTop = ui.chatLog.scrollHeight;
}

function concatInt16(a, b) {
    if (!a.length) return new Int16Array(b);
    if (!b.length) return new Int16Array(a);
    const merged = new Int16Array(a.length + b.length);
    merged.set(a, 0);
    merged.set(b, a.length);
    return merged;
}

function downsampleBuffer(buffer, sampleRate, outSampleRate) {
    if (!buffer.length) return new Float32Array();
    if (sampleRate === outSampleRate) return buffer;
    const ratio = sampleRate / outSampleRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
        const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
        let accum = 0;
        let count = 0;
        for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
            accum += buffer[i];
            count += 1;
        }
        result[offsetResult] = count > 0 ? accum / count : 0;
        offsetResult += 1;
        offsetBuffer = nextOffsetBuffer;
    }
    return result;
}

function floatTo16BitPCM(float32Array) {
    const output = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i += 1) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return output;
}

function chunkToBase64(int16Array) {
    if (!int16Array.length) return "";
    const view = new Uint8Array(int16Array.buffer, int16Array.byteOffset, int16Array.byteLength);
    let binary = "";
    for (let i = 0; i < view.length; i += 1) {
        binary += String.fromCharCode(view[i]);
    }
    return btoa(binary);
}

function handleAudioBuffer(float32Array) {
    if (!state.streaming || !state.sessionStarted) return;
    const downsampled = downsampleBuffer(float32Array, state.inputSampleRate, state.targetSampleRate);
    if (!downsampled.length) return;
    const pcm16 = floatTo16BitPCM(downsampled);
    state.pcmBuffer = concatInt16(state.pcmBuffer, pcm16);
    flushChunks();
}

function flushChunks(force = false) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
    const chunkSamples = state.chunkSamples;
    while (state.pcmBuffer.length >= chunkSamples || (force && state.pcmBuffer.length > 0)) {
        const take = force && state.pcmBuffer.length < chunkSamples ? state.pcmBuffer.length : chunkSamples;
        const chunk = state.pcmBuffer.slice(0, take);
        state.pcmBuffer = state.pcmBuffer.slice(take);
        if (!chunk.length) {
            continue;
        }
        const payload = {
            event: "audio",
            chunk: chunkToBase64(chunk),
        };
        try {
            state.ws.send(JSON.stringify(payload));
            state.audioSeconds += chunk.length / state.targetSampleRate;
            updateStats();
        } catch (err) {
            console.error("Falha ao enviar chunk", err);
            break;
        }
    }
}

function sendNextFileChunk() {
    if (!state.useFileStream || !state.ws || state.ws.readyState !== WebSocket.OPEN) {
        return;
    }

    const total = state.fileStreamData ? state.fileStreamData.length : 0;
    if (!total || state.fileStreamOffset >= total) {
        if (!state.awaitingStopAck) {
            state.awaitingStopAck = true;
            try {
                state.ws.send(JSON.stringify({ event: "stop" }));
                ui.streamStatus && (ui.streamStatus.textContent = "Arquivo enviado. Aguardando processamento...");
            } catch (err) {
                console.warn("Falha ao enviar stop apos arquivo", err);
            }
        }
        return;
    }

    const chunkSamples = state.chunkSamples;
    const end = Math.min(state.fileStreamOffset + chunkSamples, total);
    const chunk = state.fileStreamData.slice(state.fileStreamOffset, end);
    state.fileStreamOffset = end;

    try {
        state.ws.send(JSON.stringify({ event: "audio", chunk: chunkToBase64(chunk) }));
        state.audioSeconds += chunk.length / state.targetSampleRate;
        updateStats();
    } catch (err) {
        console.error("Falha ao enviar chunk de arquivo", err);
        setStatus("Falha ao transmitir áudio do arquivo.", "error");
        return;
    }

    const remaining = total - state.fileStreamOffset;
    if (remaining <= 0) {
        state.fileStreamTimer = setTimeout(sendNextFileChunk, 10);
        return;
    }

    const delayMs = Math.max(Math.round((chunk.length / state.targetSampleRate) * 1000), 20);
    state.fileStreamTimer = setTimeout(sendNextFileChunk, delayMs);
}

function resetSessionState() {
    if (state.fileStreamTimer) {
        clearTimeout(state.fileStreamTimer);
        state.fileStreamTimer = null;
    }
    state.sessionId = null;
    state.sessionStarted = false;
    state.streaming = false;
    state.awaitingStopAck = false;
    state.pcmBuffer = new Int16Array(0);
    state.batches = 0;
    state.tokens = 0;
    state.audioSeconds = 0;
    state.timeline = [];
    state.insights = [];
    state.aggregatedTranscript = "";
    state.previousTranscript = "";
    state.streamSource = "mic";
    state.useFileStream = false;
    state.fileStreamData = null;
    state.fileStreamOffset = 0;
    updateStats();
    renderTranscript();
    renderTimeline();
    renderInsights();
}

async function setupAudio() {
    if (state.audioContext) {
        return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const audioContext = new AudioCtx({ sampleRate: state.targetSampleRate });
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    const gainNode = audioContext.createGain();
    gainNode.gain.value = 0;

    state.inputSampleRate = audioContext.sampleRate;

    processor.onaudioprocess = (event) => {
        const channelData = event.inputBuffer.getChannelData(0);
        handleAudioBuffer(channelData);
    };

    source.connect(processor);
    processor.connect(gainNode);
    gainNode.connect(audioContext.destination);

    state.audioContext = audioContext;
    state.processor = processor;
    state.gainNode = gainNode;
    state.mediaStream = stream;
}

function stopAudio() {
    if (state.processor) {
        state.processor.disconnect();
        state.processor.onaudioprocess = null;
        state.processor = null;
    }
    if (state.gainNode) {
        state.gainNode.disconnect();
        state.gainNode = null;
    }
    if (state.audioContext) {
        state.audioContext.close().catch(() => undefined);
        state.audioContext = null;
    }
    if (state.mediaStream) {
        state.mediaStream.getTracks().forEach((track) => track.stop());
        state.mediaStream = null;
    }
}

function closeWebSocket() {
    if (state.ws) {
        try {
            state.ws.close();
        } catch (err) {
            console.warn("Falha ao fechar WebSocket", err);
        }
        state.ws = null;
    }
}

function cleanupSession(message = "Sessao finalizada.") {
    if (state.fileStreamTimer) {
        clearTimeout(state.fileStreamTimer);
        state.fileStreamTimer = null;
    }
    const wasFileStream = state.streamSource === "file";

    state.streaming = false;
    state.sessionStarted = false;
    stopAudio();
    closeWebSocket();

    ui.startButton.disabled = false;
    ui.stopButton.disabled = true;
    ui.listeningIndicator.classList.add("hidden");

    if (wasFileStream && ui.streamFileButton) {
        ui.streamFileButton.disabled = false;
        ui.streamStatus && (ui.streamStatus.textContent = message);
    }

    state.useFileStream = false;
    state.fileStreamData = null;
    state.fileStreamOffset = 0;
    state.streamSource = "mic";

    setStatus(message, "idle");
}

function ensureChunkSize() {
    const chunkMs = Number(ui.chunkSize.value) || 800;
    const bounded = Math.min(Math.max(chunkMs, 200), 2000);
    ui.chunkSize.value = bounded.toString();
    state.chunkSamples = Math.round((state.targetSampleRate * bounded) / 1000);
}

function resolveWsUrl() {
    // Auto-detecta a URL base se não estiver configurada
    const base = resolveApiBase();
    const token = ui.authToken.value.trim();

    // Se a página está em HTTPS, force WSS. Se HTTP, force WS.
    let wsBase;
    if (window.location.protocol === "https:") {
        wsBase = base.replace(/^http:/i, "wss:").replace(/^https:/i, "wss:");
    } else {
        wsBase = base.replace(/^https:/i, "ws:").replace(/^http:/i, "ws:");
    }

    const url = new URL(`${wsBase}/api/v1/asr/stream`);
    if (token) {
        url.searchParams.set("token", token);
    }
    return url;
}

function handleWsMessage(event) {
    let payload;
    try {
        payload = JSON.parse(event.data);
    } catch (err) {
        console.warn("Mensagem WS invalida", event.data);
        return;
    }
    const type = payload.event;
    switch (type) {
        case "ready": {
            state.sessionId = payload.session_id;
            ui.sessionId.textContent = `Sessao ${state.sessionId}`;
            setStatus("Sessao criada, aguardando inicio do processamento.", "ready");
            break;
        }
        case "session_started": {
            state.sessionStarted = true;
            state.streaming = true;
            state.insightsRequested = Boolean(payload.insights_enabled);
            ui.insightStatus.textContent = state.insightsRequested ? "Habilitados" : "Desabilitados";
            if (state.streamSource === "file") {
                setStatus("Transmitindo arquivo para o ASR.", "streaming");
                ui.streamStatus && (ui.streamStatus.textContent = "Enviando áudio do arquivo...");
                sendNextFileChunk();
            } else {
                setStatus("Capturando audio e enviando para o ASR.", "streaming");
                flushChunks();
            }
            break;
        }
        case "room_joined": {
            state.roomId = payload.room_id;
            state.role = payload.role;
            state.roomStatus = payload.room_status;
            const roleLabel = payload.role === "agent" ? "Atendente" : "Cliente";
            const statusLabel = payload.room_status === "active" ? "ATIVA" : "Aguardando";
            const participantsText = `${payload.participants_count}/2 participantes`;
            ui.roomStatus.textContent = `Sala: ${payload.room_id} | ${roleLabel} | ${statusLabel} | ${participantsText}`;
            ui.roomStatus.style.display = "block";
            console.log(`Entrou na sala ${payload.room_id} como ${roleLabel}`);
            break;
        }
        case "batch_processed": {
            state.batches = payload.batch_index || state.batches;
            if (typeof payload.total_tokens === "number") {
                state.tokens = payload.total_tokens;
            } else if (typeof payload.tokens === "number") {
                state.tokens += payload.tokens;
            }
            state.aggregatedTranscript = payload.transcript || state.aggregatedTranscript;
            if (payload.text || payload.transcript) {
                state.timeline.push({
                    batch: payload.batch_index,
                    duration: payload.duration_sec || 0,
                    tokens: payload.tokens || 0,
                    text: payload.text,
                });
            }
            if (state.streamSource === "file" && ui.streamStatus) {
                const batchLabel = payload.batch_index != null ? `#${payload.batch_index}` : "";
                ui.streamStatus.textContent = `Lote ${batchLabel} processado (${(payload.duration_sec || 0).toFixed(1)}s).`;
            }
            renderTranscript();
            renderTimeline();
            updateStats();
            break;
        }
        case "insight": {
            if (!state.insightsRequested) {
                return;
            }
            state.insights.unshift(payload);
            state.insights = state.insights.slice(0, 12);
            renderInsights();
            break;
        }
        case "final_summary": {
            const stats = payload.stats || {};
            if (typeof stats.total_batches === "number") {
                state.batches = stats.total_batches;
            }
            if (typeof stats.total_tokens === "number") {
                state.tokens = stats.total_tokens;
            }
            if (typeof stats.total_audio_seconds === "number") {
                state.audioSeconds = stats.total_audio_seconds;
            }
            if (stats.transcript) {
                state.aggregatedTranscript = stats.transcript;
            }
            if (state.streamSource === "file" && ui.streamStatus) {
                ui.streamStatus.textContent = "Processamento concluído. Gerando resumo final...";
            }
            renderTranscript();
            updateStats();
            break;
        }
        case "session_ended": {
            const message = state.awaitingStopAck ? "Sessao encerrada pelo cliente." : "Sessao encerrada pelo servidor.";
            const finalMessage = state.streamSource === "file" ? "Streaming finalizado." : message;
            cleanupSession(finalMessage);
            break;
        }
        case "error": {
            console.error("Erro do gateway:", payload.message);
            setStatus(`Erro: ${payload.message || "desconhecido"}`, "error");
            cleanupSession("Sessao interrompida apos erro.");
            break;
        }
        default: {
            console.log("Evento WS", payload);
        }
    }
}

async function openSession(options = {}) {
    if (state.ws) {
        return;
    }
    const source = options.source || "mic";
    ensureChunkSize();
    resetSessionState();
    state.streamSource = source;

    if (source === "file") {
        state.useFileStream = true;
        state.fileStreamData = options.pcm16 || null;
        state.fileStreamOffset = 0;
        ui.streamStatus && (ui.streamStatus.textContent = state.fileStreamData && state.fileStreamData.length
            ? "Arquivo preparado. Conectando ao gateway..."
            : "Arquivo inválido para streaming.");
        if (!state.fileStreamData || !state.fileStreamData.length) {
            setStatus("Arquivo inválido para streaming.", "error");
            state.useFileStream = false;
            return;
        }
    }

    setStatus("Conectando ao gateway...", "connecting");

    if (source === "mic") {
        try {
            await setupAudio();
        } catch (err) {
            console.error("Permissao de microfone negada", err);
            setStatus("Permissao de microfone negada ou indisponivel.", "error");
            stopAudio();
            return;
        }
    } else {
        stopAudio();
    }

    const url = resolveWsUrl();
    const ws = new WebSocket(url);
    state.ws = ws;

    ws.onopen = () => {
        if (source === "mic") {
            ui.startButton.disabled = true;
            ui.listeningIndicator.classList.remove("hidden");
        }
        ui.stopButton.disabled = false;
        state.streaming = true;

        // Captura room_id e role se fornecidos
        const roomId = source === "mic" && ui.roomId ? (ui.roomId.value.trim() || null) : null;
        const role = source === "mic" && ui.roleSelector ? (ui.roleSelector.value || null) : null;

        if (roomId) {
            state.roomId = roomId;
            state.role = role;
        }

        const payload = {
            event: "start",
            language: "pt",
            sample_rate: state.targetSampleRate,
            encoding: "pcm16",
            model: "whisper/medium",
            compute_type: "int8_float16",
            batch_window_sec: 2.0,
            max_batch_window_sec: 10.0,
            enable_insights: ui.insightToggle ? ui.insightToggle.checked : false,
            enable_diarization: ui.diarizationToggle ? ui.diarizationToggle.checked : false,
            provider: "paneas",
        };

        // Adiciona room_id e role se estiverem presentes
        if (roomId) {
            payload.room_id = roomId;
            if (role) {
                payload.role = role;
            }
        }

        if (ui.insightToggle && ui.insightToggle.checked && ui.insightModel && ui.insightModel.value.trim()) {
            payload.insight_model = ui.insightModel.value.trim();
        }
        ws.send(JSON.stringify(payload));

        if (source === "file" && ui.streamStatus) {
            ui.streamStatus.textContent = "Sessão iniciada. Enviando áudio...";
        }
    };

    ws.onmessage = handleWsMessage;

    ws.onerror = (event) => {
        console.error("Erro no WebSocket", event);
        setStatus("Falha no WebSocket.", "error");
        cleanupSession("Falha no WebSocket.");
    };

    ws.onclose = () => {
        cleanupSession("Conexao fechada.");
    };
}

function stopSession() {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
        cleanupSession("Sessao finalizada.");
        return;
    }
    state.awaitingStopAck = true;
    state.streaming = false;
    if (state.useFileStream) {
        if (state.fileStreamTimer) {
            clearTimeout(state.fileStreamTimer);
            state.fileStreamTimer = null;
        }
        ui.streamStatus && (ui.streamStatus.textContent = "Envio interrompido. Aguardando encerramento...");
    } else {
        flushChunks(true);
    }
    try {
        state.ws.send(JSON.stringify({ event: "stop" }));
    } catch (err) {
        console.warn("Falha ao enviar stop", err);
    }
    setStatus("Aguardando confirmacao de encerramento...", "stopping");
    ui.stopButton.disabled = true;
}

async function sendChatMessage(text) {
    const content = text.trim();
    if (!content) {
        return;
    }
    const base = resolveApiBase();
    const url = `${base}/api/v1/chat/completions`;

    state.chatHistory.push({ role: "user", content });
    renderChat();
    ui.chatInput.value = "";
    ui.chatInput.disabled = true;
    ui.chatModel.disabled = true;
    ui.chatPlaceholder && (ui.chatPlaceholder.style.display = "none");

    // Se "Manter Histórico" estiver marcado, envia todas as mensagens
    // Caso contrário, envia apenas a última mensagem do usuário
    const keepHistory = ui.chatKeepHistory && ui.chatKeepHistory.checked;
    let messagesToSend = keepHistory ? [...state.chatHistory] : [state.chatHistory[state.chatHistory.length - 1]];

    // Adiciona system prompt se fornecido
    const systemPrompt = ui.chatSystemPrompt && ui.chatSystemPrompt.value.trim();
    if (systemPrompt) {
        // Verifica se já existe um system message
        const hasSystemMessage = messagesToSend.some(msg => msg.role === "system");
        if (!hasSystemMessage) {
            messagesToSend = [{ role: "system", content: systemPrompt }, ...messagesToSend];
        }
    }

    const payload = {
        model: ui.chatModel.value,
        messages: messagesToSend,
        max_tokens: 1500,
        temperature: 0.6,
        stream: true,
    };

    // Adiciona tools ao payload se alguma foi selecionada
    const selectedTool = ui.chatTools && ui.chatTools.value;
    if (selectedTool && state.availableTools[selectedTool]) {
        payload.tools = [state.availableTools[selectedTool]];
        payload.tool_choice = "auto";
    }

    // Log do payload para debug
    console.log("📤 Enviando payload para LLM:", JSON.stringify(payload, null, 2));

    const headers = buildAuthHeaders({ "Content-Type": "application/json" });

    // Adiciona mensagem do assistente vazia que será preenchida gradualmente
    const assistantMessageIndex = state.chatHistory.length;
    state.chatHistory.push({ role: "assistant", content: "" });
    renderChat();

    try {
        const response = await fetch(url, {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        // Verifica se é streaming ou resposta completa
        const contentType = response.headers.get("content-type");
        console.log("📡 Content-Type:", contentType);

        if (contentType && contentType.includes("application/json")) {
            // Resposta completa (não-streaming)
            console.log("📄 Resposta completa (não-streaming)");
            const data = await response.json();
            console.log("📦 Resposta recebida:", data);

            const choice = data.choices && data.choices[0];
            const message = choice && choice.message;
            const content = message && message.content;

            if (content) {
                state.chatHistory[assistantMessageIndex].content = content;
                renderChat();
            } else {
                console.warn("⚠️ Nenhum conteúdo na resposta:", data);
            }
        } else {
            // Resposta em streaming (SSE)
            console.log("🔄 Resposta em streaming (SSE)");
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let chunkCount = 0;

            console.log("🔄 Iniciando leitura do stream...");

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    console.log("✅ Stream finalizado. Total de chunks:", chunkCount);
                    break;
                }

                chunkCount++;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed || trimmed === "data: [DONE]") continue;

                    if (trimmed.startsWith("data: ")) {
                        try {
                            const jsonStr = trimmed.substring(6);
                            const data = JSON.parse(jsonStr);

                            console.log("📦 Chunk SSE recebido:", data);

                            const choice = data.choices && data.choices[0];
                            const delta = choice && choice.delta;
                            const deltaContent = delta && delta.content;

                            if (deltaContent) {
                                state.chatHistory[assistantMessageIndex].content += deltaContent;
                                renderChat();
                            }
                        } catch (parseErr) {
                            console.warn("⚠️ Erro ao parsear SSE:", trimmed, parseErr);
                        }
                    }
                }
            }
        }

        // Se não recebeu nenhum conteúdo, mostra erro
        if (!state.chatHistory[assistantMessageIndex].content) {
            state.chatHistory[assistantMessageIndex].content = "(resposta vazia)";
            renderChat();
        }

        setStatus("Resposta do LLM recebida.", "ready");
    } catch (err) {
        console.error("Falha no chat", err);
        state.chatHistory[assistantMessageIndex].content = `[erro] ${err.message}`;
        renderChat();
        setStatus("Falha ao consultar o LLM.", "error");
    } finally {
        ui.chatInput.disabled = false;
        ui.chatModel.disabled = false;
        ui.chatInput.focus();
    }
}

async function transcribeUploadedAudio() {
    console.log("[ASR] Função transcribeUploadedAudio iniciada");

    if (!ui.asrResult) {
        console.log("[ASR] ui.asrResult não encontrado");
        return;
    }
    const file = ui.asrFileInput?.files?.[0];
    if (!file) {
        console.log("[ASR] Nenhum arquivo selecionado");
        setOutput(ui.asrResult, "Selecione um arquivo de áudio para transcrever.");
        return;
    }

    console.log("[ASR] Arquivo selecionado:", file.name, file.size, "bytes");
    setOutput(ui.asrResult, "Enviando áudio para transcrição...");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("language", "pt");
    if (ui.diarizationToggle?.checked) {
        formData.append("enable_diarization", "true");
    }

    const base = resolveApiBase();
    const url = `${base}/api/v1/asr`;
    console.log("[ASR] URL do endpoint:", url);

    try {
        console.log("[ASR] Iniciando requisição fetch...");
        const response = await fetch(url, {
            method: "POST",
            headers: buildAuthHeaders(),
            body: formData,
        });

        console.log("[ASR] Resposta recebida - status:", response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error("[ASR] Erro na resposta:", errorText);
            setOutput(ui.asrResult, `Erro ${response.status}: ${errorText || "Falha ao processar a transcrição."}`);
            return;
        }

        const data = await response.json();
        console.log("[ASR] Dados recebidos:", data);
        setOutput(ui.asrResult, prettyPrintJson(data));
    } catch (err) {
        console.error("[ASR] Falha na transcrição por arquivo", err);
        setOutput(ui.asrResult, `Erro: ${err.message || err}`);
    }
}

async function runOcr() {
    console.log("[OCR] Função runOcr iniciada");

    if (!ui.ocrResult) {
        console.log("[OCR] ui.ocrResult não encontrado");
        return;
    }
    const file = ui.ocrFileInput?.files?.[0];
    if (!file) {
        console.log("[OCR] Nenhum arquivo selecionado");
        setOutput(ui.ocrResult, "Selecione uma imagem ou PDF para processar.");
        return;
    }

    console.log("[OCR] Arquivo selecionado:", file.name, file.size, "bytes");
    setOutput(ui.ocrResult, "Enviando arquivo para OCR...");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("languages", "pt");
    formData.append("output_format", "json");

    const base = resolveApiBase();
    const url = `${base}/api/v1/ocr`;
    console.log("[OCR] URL do endpoint:", url);

    try {
        console.log("[OCR] Iniciando requisição fetch...");
        const response = await fetch(url, {
            method: "POST",
            headers: buildAuthHeaders(),
            body: formData,
        });

        console.log("[OCR] Resposta recebida - status:", response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error("[OCR] Erro na resposta:", errorText);
            setOutput(ui.ocrResult, `Erro ${response.status}: ${errorText || "Falha ao processar o OCR."}`);
            return;
        }

        const data = await response.json();
        console.log("[OCR] Dados recebidos:", data);
        setOutput(ui.ocrResult, prettyPrintJson(data));
    } catch (err) {
        console.error("[OCR] Falha no OCR", err);
        setOutput(ui.ocrResult, `Erro: ${err.message || err}`);
    }
}

async function decodeAudioFileToPCM16(file) {
    const arrayBuffer = await file.arrayBuffer();
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const audioContext = new AudioCtx();
    try {
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));
        const { numberOfChannels, length, sampleRate } = audioBuffer;
        if (!length) {
            return new Int16Array(0);
        }
        const combined = new Float32Array(length);
        const channels = Math.max(1, numberOfChannels);
        for (let channel = 0; channel < channels; channel += 1) {
            const channelData = audioBuffer.getChannelData(channel);
            for (let i = 0; i < length; i += 1) {
                combined[i] += channelData[i];
            }
        }
        for (let i = 0; i < length; i += 1) {
            combined[i] /= channels;
        }

        const resampled = downsampleBuffer(combined, sampleRate, state.targetSampleRate);
        return floatTo16BitPCM(resampled);
    } finally {
        await audioContext.close().catch(() => undefined);
    }
}

async function streamAudioFile() {
    if (!ui.streamStatus) {
        return;
    }
    const file = ui.streamFileInput?.files?.[0];
    if (!file) {
        ui.streamStatus.textContent = "Selecione um arquivo de áudio para streaming.";
        return;
    }

    ui.streamFileButton && (ui.streamFileButton.disabled = true);
    ui.streamStatus.textContent = "Convertendo áudio...";

    try {
        const pcm16 = await decodeAudioFileToPCM16(file);
        if (!pcm16.length) {
            ui.streamStatus.textContent = "Não foi possível extrair áudio deste arquivo.";
            ui.streamFileButton && (ui.streamFileButton.disabled = false);
            return;
        }
        await openSession({ source: "file", pcm16 });
        if (!state.ws) {
            ui.streamFileButton && (ui.streamFileButton.disabled = false);
        }
    } catch (err) {
        console.error("Falha ao preparar streaming do arquivo", err);
        ui.streamStatus.textContent = `Erro: ${err.message || err}`;
        ui.streamFileButton && (ui.streamFileButton.disabled = false);
        state.useFileStream = false;
        state.fileStreamData = null;
        state.fileStreamOffset = 0;
    }
}

function clearChat() {
    state.chatHistory = [];
    renderChat();
}

function bindEvents() {
    ui.startButton.addEventListener("click", () => {
        openSession();
    });

    ui.stopButton.addEventListener("click", () => {
        stopSession();
    });

    ui.chatForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const text = ui.chatInput.value;
        sendChatMessage(text);
    });

    ui.chatClear.addEventListener("click", (event) => {
        event.preventDefault();
        clearChat();
    });

    ui.asrUploadButton?.addEventListener("click", async (event) => {
        event.preventDefault();
        console.log("[ASR] Botão clicado - iniciando transcrição");
        ui.asrUploadButton.disabled = true;
        ui.asrUploadButton.textContent = "Processando...";
        try {
            await transcribeUploadedAudio();
        } finally {
            ui.asrUploadButton.disabled = false;
            ui.asrUploadButton.textContent = "Transcrever áudio";
        }
    });

    ui.asrFileInput?.addEventListener("change", () => {
        if (!ui.asrResult) {
            return;
        }
        if (ui.asrFileInput.files && ui.asrFileInput.files.length) {
            setOutput(ui.asrResult, `Arquivo selecionado: ${ui.asrFileInput.files[0].name}`);
        } else {
            setOutput(ui.asrResult, "Aguardando arquivo.");
        }
    });

    ui.streamFileButton?.addEventListener("click", async (event) => {
        event.preventDefault();
        console.log("[Streaming] Botão clicado - iniciando streaming de arquivo");
        await streamAudioFile();
    });

    ui.streamFileInput?.addEventListener("change", () => {
        if (!ui.streamStatus) {
            return;
        }
        if (ui.streamFileInput.files && ui.streamFileInput.files.length) {
            ui.streamStatus.textContent = `Arquivo selecionado: ${ui.streamFileInput.files[0].name}`;
        } else {
            ui.streamStatus.textContent = "Aguardando arquivo.";
        }
    });

    ui.ocrButton?.addEventListener("click", async (event) => {
        event.preventDefault();
        console.log("[OCR] Botão clicado - iniciando OCR");
        ui.ocrButton.disabled = true;
        ui.ocrButton.textContent = "Processando...";
        try {
            await runOcr();
        } finally {
            ui.ocrButton.disabled = false;
            ui.ocrButton.textContent = "Executar OCR";
        }
    });

    ui.ocrFileInput?.addEventListener("change", () => {
        if (!ui.ocrResult) {
            return;
        }
        if (ui.ocrFileInput.files && ui.ocrFileInput.files.length) {
            setOutput(ui.ocrResult, `Arquivo selecionado: ${ui.ocrFileInput.files[0].name}`);
        } else {
            setOutput(ui.ocrResult, "Aguardando arquivo.");
        }
    });

    ui.insightToggle.addEventListener("change", () => {
        ui.insightStatus.textContent = ui.insightToggle.checked ? "Habilitados" : "Desabilitados";
    });

    ui.ttsButton?.addEventListener("click", async (event) => {
        event.preventDefault();
        await synthesizeTTS();
    });

    ui.ttsDownload?.addEventListener("click", (event) => {
        event.preventDefault();
        downloadTTSAudio();
    });

    ui.ttsStreamButton?.addEventListener("click", async (event) => {
        event.preventDefault();
        await synthesizeTTSStream();
    });

    ui.ttsStreamStop?.addEventListener("click", (event) => {
        event.preventDefault();
        stopTTSStream();
    });

    ui.scrapperConsultaForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await submitScrapperConsulta();
    });

    ui.scrapperConsultaReset?.addEventListener("click", (event) => {
        event.preventDefault();
        resetScrapperForm(
            ui.scrapperConsultaForm,
            ui.scrapperConsultaResult,
            'Preencha os filtros e clique em "Consultar".'
        );
    });

    ui.scrapperListForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await submitScrapperList();
    });

    ui.scrapperListReset?.addEventListener("click", (event) => {
        event.preventDefault();
        resetScrapperForm(
            ui.scrapperListForm,
            ui.scrapperListResult,
            'Informe os filtros desejados e clique em "Listar Processos".'
        );
    });

    ui.scrapperToolsButton?.addEventListener("click", async (event) => {
        event.preventDefault();
        await loadScrapperManifest();
    });

    window.addEventListener("beforeunload", () => {
        try {
            if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                state.ws.send(JSON.stringify({ event: "stop" }));
            }
        } catch (err) {
            console.warn("Falha ao enviar stop no unload", err);
        }
    });
}

function checkPassword() {
    const CORRECT_PASSWORD = "Paneas@321";
    const unlocked = localStorage.getItem("paneas_unlocked");
    const modal = document.getElementById("passwordModal");
    const passwordForm = document.getElementById("passwordForm");
    const passwordInput = document.getElementById("passwordInput");
    const passwordError = document.getElementById("passwordError");

    if (unlocked === "true") {
        modal.classList.add("hidden");
        document.body.classList.remove("locked");
        return;
    }

    document.body.classList.add("locked");

    passwordForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const enteredPassword = passwordInput.value;

        if (enteredPassword === CORRECT_PASSWORD) {
            localStorage.setItem("paneas_unlocked", "true");
            modal.classList.add("hidden");
            document.body.classList.remove("locked");
            passwordError.style.display = "none";
            passwordInput.value = "";
        } else {
            passwordError.style.display = "block";
            passwordInput.value = "";
            passwordInput.focus();
        }
    });
}

// Tab Switching
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active from all
            tabs.forEach(t => t.classList.remove('tab--active'));
            tabContents.forEach(tc => tc.classList.remove('tab-content--active'));

            // Add active to clicked
            tab.classList.add('tab--active');
            const targetTab = tab.dataset.tab;
            const targetContent = document.querySelector(`[data-content="${targetTab}"]`);
            if (targetContent) {
                targetContent.classList.add('tab-content--active');
            }
        });
    });
}

// File Name Display
function setupFileDisplays() {
    const fileInputs = [
        { input: ui.asrFileInput, display: 'asrFileName' },
        { input: ui.diarFileInput, display: 'diarFileName' },
        { input: ui.streamFileInput, display: 'streamFileName' },
        { input: ui.ocrFileInput, display: 'ocrFileName' },
    ];

    fileInputs.forEach(({ input, display }) => {
        if (!input) return;
        input.addEventListener('change', (e) => {
            const displayEl = document.getElementById(display);
            if (displayEl && e.target.files.length > 0) {
                displayEl.textContent = e.target.files[0].name;
            }
        });
    });
}

// Diarization
async function handleDiarization() {
    const file = ui.diarFileInput?.files[0];
    if (!file) {
        setOutput(ui.diarResult, "Nenhum arquivo selecionado.");
        return;
    }

    const numSpeakers = ui.numSpeakers.value ? parseInt(ui.numSpeakers.value) : null;
    setOutput(ui.diarResult, "Processando diarização...");
    ui.diarButton.disabled = true;

    try {
        const formData = new FormData();
        formData.append("file", file);
        if (numSpeakers) {
            formData.append("num_speakers", numSpeakers.toString());
        }

        const apiBase = resolveApiBase();
        const response = await fetch(`${apiBase}/api/v1/diar`, {
            method: "POST",
            headers: buildAuthHeaders(),
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Format output
        let output = `Arquivo: ${file.name}\n`;
        output += `Speakers detectados: ${new Set(data.segments.map(s => s.speaker)).size}\n\n`;
        output += "Segmentos:\n";
        output += "─".repeat(60) + "\n\n";

        data.segments.forEach((seg, idx) => {
            output += `[${seg.start.toFixed(2)}s - ${seg.end.toFixed(2)}s] ${seg.speaker}\n`;
        });

        setOutput(ui.diarResult, output);
    } catch (err) {
        console.error("Erro na diarização:", err);
        setOutput(ui.diarResult, `Erro: ${err.message}`);
    } finally {
        ui.diarButton.disabled = false;
    }
}

// TTS Functions
async function synthesizeTTS() {
    const text = ui.ttsText?.value?.trim();
    const voice = ui.ttsVoice?.value;

    if (!text) {
        ui.ttsStatus && (ui.ttsStatus.textContent = "Digite um texto para sintetizar.");
        return;
    }

    if (text.length > 500) {
        ui.ttsStatus && (ui.ttsStatus.textContent = "Texto muito longo (máximo 500 caracteres).");
        return;
    }

    ui.ttsButton && (ui.ttsButton.disabled = true);
    ui.ttsButton && (ui.ttsButton.textContent = "Sintetizando...");
    ui.ttsStatus && (ui.ttsStatus.textContent = "Gerando áudio...");
    ui.ttsResult && (ui.ttsResult.style.display = "none");

    try {
        const base = resolveApiBase();
        const url = `${base}/api/v1/tts`;

        const payload = {
            text: text,
            language: "pt",
            speaker_reference: voice,
            format: "wav"
        };

        const headers = buildAuthHeaders({ "Content-Type": "application/json" });

        const response = await fetch(url, {
            method: "POST",
            headers: headers,
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        // Captura metadados dos headers
        const sampleRate = response.headers.get("X-Audio-Sample-Rate");
        const duration = response.headers.get("X-Audio-Duration");
        const requestId = response.headers.get("X-Request-ID");

        // Captura o blob do áudio
        const audioBlob = await response.blob();
        state.currentAudioBlob = audioBlob;
        state.currentAudioMetadata = { sampleRate, duration, requestId };

        // Cria URL para o player
        const audioUrl = URL.createObjectURL(audioBlob);
        ui.ttsAudioPlayer.src = audioUrl;

        // Mostra metadados
        if (ui.ttsMetadata) {
            const voiceName = voice.split('/').pop().replace('.wav', '');
            ui.ttsMetadata.innerHTML = `
                <small class="text-muted">
                    Duração: ${parseFloat(duration).toFixed(2)}s |
                    Sample Rate: ${sampleRate}Hz |
                    Voz: ${voiceName}
                </small>
            `;
        }

        // Mostra resultado
        ui.ttsResult && (ui.ttsResult.style.display = "block");
        ui.ttsStatus && (ui.ttsStatus.textContent = "Áudio gerado com sucesso!");

    } catch (err) {
        console.error("Erro na síntese TTS:", err);
        ui.ttsStatus && (ui.ttsStatus.textContent = `Erro: ${err.message}`);
    } finally {
        ui.ttsButton && (ui.ttsButton.disabled = false);
        ui.ttsButton && (ui.ttsButton.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
            </svg>
            Sintetizar Áudio
        `);
    }
}

function downloadTTSAudio() {
    if (!state.currentAudioBlob) {
        return;
    }

    const url = URL.createObjectURL(state.currentAudioBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tts_${Date.now()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function synthesizeTTSStream() {
    const text = ui.ttsText?.value?.trim();
    const voice = ui.ttsVoice?.value;

    if (!text) {
        ui.ttsStatus && (ui.ttsStatus.textContent = "Digite um texto para sintetizar.");
        return;
    }

    if (text.length > 500) {
        ui.ttsStatus && (ui.ttsStatus.textContent = "Texto muito longo (máximo 500 caracteres).");
        return;
    }

    // Disable buttons
    ui.ttsStreamButton && (ui.ttsStreamButton.disabled = true);
    ui.ttsStreamButton && (ui.ttsStreamButton.textContent = "Conectando...");

    // Hide regular result, show streaming result
    ui.ttsResult && (ui.ttsResult.style.display = "none");
    ui.ttsStreamResult && (ui.ttsStreamResult.style.display = "block");

    ui.streamingStatusText && (ui.streamingStatusText.textContent = "Conectando...");
    state.streamingAudio = true;

    // Prepare text animation
    state.streamingTextWords = text.split(/\s+/);
    if (ui.streamingText) {
        ui.streamingText.innerHTML = state.streamingTextWords
            .map((word, idx) => `<span class="word" data-index="${idx}">${word}</span>`)
            .join(' ');
    }

    try {
        const base = resolveApiBase();
        const url = `${base}/api/v1/tts/stream`;

        const payload = {
            text: text,
            language: "pt",
            speaker_reference: voice,
            format: "wav"
        };

        const headers = buildAuthHeaders({ "Content-Type": "application/json" });

        ui.streamingStatusText && (ui.streamingStatusText.textContent = "Buffering...");

        const response = await fetch(url, {
            method: "POST",
            headers: headers,
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        // Read the stream - collect all chunks first for smooth playback
        const reader = response.body.getReader();
        const chunks = [];

        ui.streamingStatusText && (ui.streamingStatusText.textContent = "Carregando...");

        // Collect all audio data
        while (state.streamingAudio) {
            const { done, value } = await reader.read();

            if (done) break;

            chunks.push(value);

            // Show progress
            const totalBytes = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
            const totalKB = (totalBytes / 1024).toFixed(1);
            ui.streamingStatusText && (ui.streamingStatusText.textContent = `Carregando... ${totalKB}KB`);
        }

        // Now create the complete audio and play
        if (chunks.length > 0 && state.streamingAudio) {
            ui.streamingStatusText && (ui.streamingStatusText.textContent = "Streamando...");

            const blob = new Blob(chunks, { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(blob);

            if (ui.ttsStreamPlayer.src) {
                URL.revokeObjectURL(ui.ttsStreamPlayer.src);
            }
            ui.ttsStreamPlayer.src = audioUrl;

            // Setup audio player event for text sync
            setupAudioTextSync();

            // Start playing
            ui.ttsStreamPlayer.play().catch(err => {
                console.error('Error playing audio:', err);
            });
        }

        ui.streamingStatusText && (ui.streamingStatusText.textContent = "Concluído!");
        ui.ttsStatus && (ui.ttsStatus.textContent = "Streaming de áudio concluído!");

    } catch (err) {
        console.error("Erro no streaming TTS:", err);
        ui.ttsStatus && (ui.ttsStatus.textContent = `Erro: ${err.message}`);
        ui.streamingStatusText && (ui.streamingStatusText.textContent = "Erro");
    } finally {
        state.streamingAudio = false;
        stopStreamingTextAnimation();
        ui.ttsStreamButton && (ui.ttsStreamButton.disabled = false);
        ui.ttsStreamButton && (ui.ttsStreamButton.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 3l14 9-14 9V3z"/>
                <path d="M19 12h2"/>
            </svg>
            Modo Streaming
        `);
    }
}

function setupAudioTextSync() {
    if (!ui.ttsStreamPlayer || !ui.streamingText) return;

    // Remove any existing listener
    ui.ttsStreamPlayer.removeEventListener('timeupdate', handleAudioTimeUpdate);

    // Add time update listener for syncing text with audio
    ui.ttsStreamPlayer.addEventListener('timeupdate', handleAudioTimeUpdate);

    // Store start time when audio begins playing
    ui.ttsStreamPlayer.addEventListener('play', () => {
        if (!state.streamingStartTime) {
            state.streamingStartTime = Date.now();
        }
    }, { once: true });
}

function handleAudioTimeUpdate() {
    if (!ui.streamingText || !state.streamingTextWords.length) return;

    const player = ui.ttsStreamPlayer;
    const currentTime = player.currentTime;
    const duration = player.duration;

    if (!duration || duration === 0 || isNaN(duration)) return;

    // Calculate which word should be highlighted based on audio progress
    const wordCount = state.streamingTextWords.length;
    const timePerWord = duration / wordCount;
    const currentWordIndex = Math.floor(currentTime / timePerWord);

    // Highlight current word and mark previous as spoken
    for (let i = 0; i < wordCount; i++) {
        const wordElement = ui.streamingText.querySelector(`[data-index="${i}"]`);
        if (!wordElement) continue;

        if (i < currentWordIndex) {
            // Already spoken
            wordElement.classList.remove('highlight');
            wordElement.classList.add('spoken');
        } else if (i === currentWordIndex) {
            // Currently speaking
            wordElement.classList.add('highlight');
            wordElement.classList.remove('spoken');
        } else {
            // Not yet spoken
            wordElement.classList.remove('highlight', 'spoken');
        }
    }
}

function stopStreamingTextAnimation() {
    // Remove audio event listener
    if (ui.ttsStreamPlayer) {
        ui.ttsStreamPlayer.removeEventListener('timeupdate', handleAudioTimeUpdate);
    }

    // Reset state
    state.streamingStartTime = null;

    // Mark all words as spoken
    if (ui.streamingText) {
        const words = ui.streamingText.querySelectorAll('.word');
        words.forEach(word => {
            word.classList.remove('highlight');
            word.classList.add('spoken');
        });
    }
}

function stopTTSStream() {
    state.streamingAudio = false;
    stopStreamingTextAnimation();

    if (ui.ttsStreamPlayer) {
        ui.ttsStreamPlayer.pause();
    }

    ui.ttsStreamResult && (ui.ttsStreamResult.style.display = "none");
    ui.streamingStatusText && (ui.streamingStatusText.textContent = "Parado");
    ui.ttsStatus && (ui.ttsStatus.textContent = "Streaming interrompido.");
}

function bootstrap() {
    checkPassword();
    ensureChunkSize();
    resetSessionState();
    renderChat();
    bindEvents();
    initTabs();
    setupFileDisplays();

    // Bind diarization
    if (ui.diarButton) {
        ui.diarButton.addEventListener('click', handleDiarization);
    }
}

document.addEventListener("DOMContentLoaded", bootstrap);
