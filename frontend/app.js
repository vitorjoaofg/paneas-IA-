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
    insightToggle: document.getElementById("insightToggle"),
    insightModel: document.getElementById("insightModel"),
    chatLog: document.getElementById("chatLog"),
    chatForm: document.getElementById("chatForm"),
    chatInput: document.getElementById("chatInput"),
    chatModel: document.getElementById("chatModel"),
    chatPlaceholder: document.querySelector(".chat__placeholder"),
    chatClear: document.getElementById("clearChat"),
    listeningIndicator: document.getElementById("listeningIndicator"),
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
    awaitingStopAck: false,
};

function trimTrailingSlash(url) {
    return url.replace(/\/$/, "");
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
            }, index * 80); // 80ms de delay entre cada palavra
        });

        // Atualiza previousTranscript depois que todas as palavras forem agendadas
        setTimeout(() => {
            state.previousTranscript = currentText;
        }, words.length * 80);
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

function resetSessionState() {
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
    state.streaming = false;
    state.sessionStarted = false;
    stopAudio();
    closeWebSocket();
    ui.startButton.disabled = false;
    ui.stopButton.disabled = true;
    ui.listeningIndicator.classList.add("hidden");
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
    let base = ui.apiBase.value.trim();
    if (!base) {
        base = window.location.origin;
    }
    base = trimTrailingSlash(base);

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
            setStatus("Capturando audio e enviando para o ASR.", "streaming");
            flushChunks();
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
            renderTranscript();
            updateStats();
            break;
        }
        case "session_ended": {
            const message = state.awaitingStopAck ? "Sessao encerrada pelo cliente." : "Sessao encerrada pelo servidor.";
            cleanupSession(message);
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

async function openSession() {
    if (state.ws) {
        return;
    }
    ensureChunkSize();
    resetSessionState();
    setStatus("Conectando ao gateway...", "connecting");

    try {
        await setupAudio();
    } catch (err) {
        console.error("Permissao de microfone negada", err);
        setStatus("Permissao de microfone negada ou indisponivel.", "error");
        stopAudio();
        return;
    }

    const url = resolveWsUrl();
    const ws = new WebSocket(url);
    state.ws = ws;

    ws.onopen = () => {
        ui.startButton.disabled = true;
        ui.stopButton.disabled = false;
        ui.listeningIndicator.classList.remove("hidden");
        state.streaming = true;
        const payload = {
            event: "start",
            language: "pt",
            sample_rate: state.targetSampleRate,
            encoding: "pcm16",
            model: "whisper/medium",
            compute_type: "int8_float16",
            batch_window_sec: 5.0,
            max_batch_window_sec: 10.0,
            enable_insights: ui.insightToggle.checked,
            provider: "paneas",
        };
        if (ui.insightToggle.checked && ui.insightModel.value.trim()) {
            payload.insight_model = ui.insightModel.value.trim();
        }
        ws.send(JSON.stringify(payload));
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
    flushChunks(true);
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
    // Auto-detecta a URL base se não estiver configurada
    let base = ui.apiBase.value.trim();
    if (!base) {
        base = window.location.origin;
    }
    base = trimTrailingSlash(base);

    const token = ui.authToken.value.trim();
    const url = `${base}/api/v1/chat/completions`;

    state.chatHistory.push({ role: "user", content });
    renderChat();
    ui.chatInput.value = "";
    ui.chatInput.disabled = true;
    ui.chatModel.disabled = true;
    ui.chatPlaceholder && (ui.chatPlaceholder.style.display = "none");

    const payload = {
        model: ui.chatModel.value,
        messages: state.chatHistory.slice(-8),
        max_tokens: 384,
        temperature: 0.6,
        stream: true,
    };

    const headers = {
        "Content-Type": "application/json",
    };
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

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

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

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
                        const choice = data.choices && data.choices[0];
                        const delta = choice && choice.delta;
                        const deltaContent = delta && delta.content;

                        if (deltaContent) {
                            state.chatHistory[assistantMessageIndex].content += deltaContent;
                            renderChat();
                        }
                    } catch (parseErr) {
                        console.warn("Failed to parse SSE data:", trimmed, parseErr);
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

    ui.insightToggle.addEventListener("change", () => {
        ui.insightStatus.textContent = ui.insightToggle.checked ? "Habilitados" : "Desabilitados";
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

function bootstrap() {
    checkPassword();
    ensureChunkSize();
    resetSessionState();
    renderChat();
    bindEvents();
}

document.addEventListener("DOMContentLoaded", bootstrap);
