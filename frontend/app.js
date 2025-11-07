// ========================================
// Password Protection
// ========================================

const CORRECT_PASSWORD = 'Paneas@321';
let isAuthenticated = false;

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', () => {
    const passwordModal = document.getElementById('passwordModal');
    const passwordInput = document.getElementById('passwordInput');
    const passwordForm = document.getElementById('passwordForm');
    const passwordError = document.getElementById('passwordError');

    // Clean up old localStorage system (migration)
    if (localStorage.getItem('paneas_unlocked')) {
        localStorage.removeItem('paneas_unlocked');
    }

    // Check if already authenticated (session storage)
    if (sessionStorage.getItem('paneas_authenticated') === 'true') {
        isAuthenticated = true;
        passwordModal.style.display = 'none';
        passwordModal.style.opacity = '0';
        document.body.classList.remove('modal-open');
    } else {
        // Show modal and add body class
        passwordModal.style.display = 'flex';
        passwordModal.style.opacity = '1';
        document.body.classList.add('modal-open');
        // Focus input
        setTimeout(() => {
            passwordInput.focus();
        }, 300);
    }

    // Password form handler
    passwordForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const submitButton = e.target.querySelector('button[type="submit"]');
        const enteredPassword = passwordInput.value;

        if (enteredPassword === CORRECT_PASSWORD) {
            // Success
            isAuthenticated = true;
            sessionStorage.setItem('paneas_authenticated', 'true');

            // Set admin API token
            const adminToken = 'token_abc123';
            sessionStorage.setItem('adminToken', adminToken);

            // Update the auth token input field if it exists
            const authTokenInput = document.getElementById('authToken');
            if (authTokenInput) {
                authTokenInput.value = adminToken;
            }

            // Success animation
            submitButton.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
                Acesso Liberado!
            `;
            submitButton.style.background = '#10b981';

            // Hide error if visible
            passwordError.style.display = 'none';

            // Close modal with animation
            setTimeout(() => {
                passwordModal.style.opacity = '0';
                document.body.classList.remove('modal-open');
                setTimeout(() => {
                    passwordModal.style.display = 'none';
                }, 300);
            }, 800);
        } else {
            // Error
            passwordError.style.display = 'flex';
            passwordInput.value = '';
            passwordInput.focus();

            // Shake animation
            passwordInput.style.animation = 'none';
            setTimeout(() => {
                passwordInput.style.animation = 'shake 0.5s ease-in-out';
            }, 10);

            // Reset button
            submitButton.disabled = false;
        }
    });

    // Logout button handler
    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            if (confirm('Tem certeza que deseja sair?')) {
                // Clear authentication
                sessionStorage.removeItem('paneas_authenticated');
                isAuthenticated = false;

                // Reset form
                passwordInput.value = '';
                const submitButton = document.querySelector('#passwordForm button[type="submit"]');
                submitButton.innerHTML = `
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
                        <polyline points="10 17 15 12 10 7"/>
                        <line x1="15" x2="3" y1="12" y2="12"/>
                    </svg>
                    Entrar
                `;
                submitButton.style.background = '';

                // Show modal
                document.body.classList.add('modal-open');
                passwordModal.style.display = 'flex';
                passwordModal.style.opacity = '1';

                setTimeout(() => {
                    passwordInput.focus();
                }, 300);
            }
        });
    }
});

// Prevent access to functionality if not authenticated
function checkAuth() {
    if (!isAuthenticated) {
        alert('Por favor, faça login primeiro.');
        return false;
    }
    return true;
}

// ========================================
// Navigation & UI Handlers
// ========================================

// Product card navigation
document.addEventListener('DOMContentLoaded', () => {
    // Product cards - navigate to playground
    const productCards = document.querySelectorAll('.product-card');
    productCards.forEach(card => {
        const ctaButton = card.querySelector('.product-card__cta');
        const productType = card.dataset.product;

        if (ctaButton && productType) {
            ctaButton.addEventListener('click', () => {
                // Navigate to playground section
                document.getElementById('playground').scrollIntoView({ behavior: 'smooth' });

                // Switch to the corresponding tab
                setTimeout(() => {
                    switchPlaygroundTab(productType);
                }, 500);
            });
        }
    });

    // Playground navigation
    const playgroundNavItems = document.querySelectorAll('.playground__nav-item');
    playgroundNavItems.forEach(item => {
        item.addEventListener('click', () => {
            const tab = item.dataset.tab;
            if (tab) {
                switchPlaygroundTab(tab);
            }
        });
    });
});

function switchPlaygroundTab(tabName) {
    // Update nav items
    const navItems = document.querySelectorAll('.playground__nav-item');
    navItems.forEach(item => {
        if (item.dataset.tab === tabName) {
            item.classList.add('playground__nav-item--active');
        } else {
            item.classList.remove('playground__nav-item--active');
        }
    });

    // Update panels
    const panels = document.querySelectorAll('.playground__panel');
    panels.forEach(panel => {
        if (panel.dataset.content === tabName) {
            panel.classList.add('playground__panel--active');
        } else {
            panel.classList.remove('playground__panel--active');
        }
    });

    // Auto-load mock analytics when tab is opened
    if (tabName === 'analytics') {
        // Use setTimeout to ensure DOM is ready
        setTimeout(() => {
            if (typeof loadMockAnalytics === 'function') {
                loadMockAnalytics();
            }
        }, 100);
    }
}

// ========================================
// UI Elements & State
// ========================================

const ui = {
    statusBadge: document.getElementById("sessionStatus"),
    footerStatus: document.getElementById("footerStatus"),
    sessionId: document.getElementById("sessionId"),
    batchCount: document.getElementById("batchCount"),
    tokenCount: document.getElementById("tokenCount"),
    audioSeconds: document.getElementById("audioSeconds"),
    transcript: document.getElementById("transcriptText"),
    // timeline: document.getElementById("batchTimeline"), // Removed
    // insights: document.getElementById("insightsList"), // Removed
    // insightStatus: document.getElementById("insightStatus"), // Removed
    startButton: document.getElementById("startButton"),
    stopButton: document.getElementById("stopButton"),
    apiBase: document.getElementById("apiBase"),
    authToken: document.getElementById("authToken"),
    chunkSize: document.getElementById("chunkSize"),
    diarizationToggle: document.getElementById("diarizationToggle"),
    // insightToggle: document.getElementById("insightToggle"), // Removed
    // insightModel: document.getElementById("insightModel"), // Removed
    chatLog: document.getElementById("chatLog"),
    chatForm: document.getElementById("chatForm"),
    chatInput: document.getElementById("chatInput"),
    chatTarget: document.getElementById("chatTarget"),
    chatModel: document.getElementById("chatTarget"), // Alias para compatibilidade
    chatKeepHistory: document.getElementById("chatKeepHistory"),
    chatTools: document.getElementById("chatTools"),
    chatSystemPrompt: document.getElementById("chatSystemPrompt"),
    chatPlaceholder: document.querySelector(".chat-welcome"),
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
    ttsAccentGroup: document.getElementById("ttsAccentGroup"),
    ttsAccent: document.getElementById("ttsAccent"),
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
    lastHighlightedWordIndex: -1,
    // Chat with agents/teams
    chatType: 'model',              // 'model' | 'agent' | 'team'
    chatTargetId: 'paneas-q32b',    // ID do modelo/agente/team
    conversationId: null,            // Para contexto de agentes/teams
    availableAgents: [],            // Lista de agentes
    availableTeams: [],             // Lista de teams
    // Diarization tracking
    diarizedConversation: [],      // Stores the diarized conversation
    diarizedMessageCount: 0,       // Number of diarized messages
    // TTS Language and Accent
    ttsLanguage: 'pt-br',
    ttsAccent: 'co'
};

// TTS Voice Configuration
const voiceConfig = {
    'pt-br': {
        label: 'Português',
        language: 'pt',
        voices: [
            { value: '/voices/perola_optimized.wav', label: 'Pérola (Feminina)' },
            { value: '/voices/Guilherme_optimized.wav', label: 'Guilherme (Masculina)' }
        ]
    },
    'es': {
        label: 'Español',
        language: 'es',
        accents: {
            'co': {
                label: 'Colombiano',
                voices: [
                    { value: '/voices/es_co_female_optimized.wav', label: 'Colombiana (Feminina)' },
                    { value: '/voices/es_co_male_optimized.wav', label: 'Colombiano (Masculino)' }
                ]
            },
            'ar': {
                label: 'Argentino',
                voices: [
                    { value: '/voices/es_ar_female_optimized.wav', label: 'Argentina (Feminina)' },
                    { value: '/voices/es_ar_male_optimized.wav', label: 'Argentino (Masculino)' }
                ]
            },
            'pe': {
                label: 'Peruano',
                voices: [
                    { value: '/voices/es_pe_female_optimized.wav', label: 'Peruana (Feminina)' },
                    { value: '/voices/es_pe_male_optimized.wav', label: 'Peruano (Masculino)' }
                ]
            }
        }
    }
};

function trimTrailingSlash(url) {
    return url.replace(/\/$/, "");
}

function resolveApiBase() {
    let base = ui.apiBase.value.trim();
    if (!base) {
        // Default to window.location.origin but replace port 8765 with 8000 for API
        base = window.location.origin;
        if (base.includes(':8765')) {
            base = base.replace(':8765', ':8000');
        }
    }
    console.log("[API] Base URL resolvida:", base);
    return trimTrailingSlash(base);
}

function buildAuthHeaders(extra = {}) {
    const headers = { ...extra };
    // Try to get token from sessionStorage first (from API Keys panel)
    let token = sessionStorage.getItem('adminToken');
    // If not found, try to get from the input field
    if (!token && ui.authToken) {
        token = ui.authToken.value.trim();
    }
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

    // Collect text and numeric fields
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

    // Collect checkboxes (FormData doesn't include unchecked checkboxes)
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach((checkbox) => {
        if (checkbox.name) {
            payload[checkbox.name] = checkbox.checked;
        }
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

    // Get selected tribunal
    const tribunalSelector = document.getElementById("scrapperTribunalSelector");
    const tribunal = tribunalSelector ? tribunalSelector.value : "tjsp";

    setOutput(ui.scrapperConsultaResult, "Consultando processo...");
    const originalLabel = ui.scrapperConsultaSubmit?.textContent;
    if (ui.scrapperConsultaSubmit) {
        ui.scrapperConsultaSubmit.disabled = true;
        ui.scrapperConsultaSubmit.textContent = "Consultando...";
    }

    try {
        if (tribunal === "pje") {
            // For PJE, we need to first list to get the link, then fetch details
            setOutput(ui.scrapperConsultaResult, "Buscando processos PJE...");

            // Check if user provided a link_publico or ca directly
            if (payload.link_publico || payload.ca) {
                const data = await callScrapperEndpoint("processos/pje/consulta", {
                    method: "POST",
                    payload,
                });
                setOutput(ui.scrapperConsultaResult, prettyPrintJson(data));
            } else {
                // First, list processes with the given filters
                const listData = await callScrapperEndpoint("processos/pje/listar", {
                    method: "POST",
                    payload,
                });

                if (!listData.processos || listData.processos.length === 0) {
                    setOutput(ui.scrapperConsultaResult, "Nenhum processo encontrado com os filtros fornecidos.");
                    return;
                }

                // Get the first process link
                const firstProcess = listData.processos[0];
                const linkPublico = firstProcess.linkPublico;

                if (!linkPublico) {
                    setOutput(ui.scrapperConsultaResult, "Processo encontrado mas sem link público disponível.");
                    return;
                }

                setOutput(ui.scrapperConsultaResult, `Encontrado ${listData.processos.length} processo(s). Buscando detalhes...`);

                // Now fetch the detailed information
                const detailData = await callScrapperEndpoint("processos/pje/consulta", {
                    method: "POST",
                    payload: { link_publico: linkPublico },
                });

                setOutput(ui.scrapperConsultaResult, prettyPrintJson(detailData));
            }
        } else if (tribunal === "tjrj") {
            // For TJRJ, similar to PJE - first list to get the process, then fetch details
            setOutput(ui.scrapperConsultaResult, "Buscando processos TJRJ...");

            // Check if user provided numero_processo directly
            if (payload.numero_processo && !payload.nome_parte && !payload.documento_parte) {
                const data = await callScrapperEndpoint("processos/tjrj/consulta", {
                    method: "POST",
                    payload,
                });
                setOutput(ui.scrapperConsultaResult, prettyPrintJson(data));
            } else {
                // First, list processes with the given filters
                const listData = await callScrapperEndpoint("processos/tjrj/listar", {
                    method: "POST",
                    payload,
                });

                if (!listData.processos || listData.processos.length === 0) {
                    setOutput(ui.scrapperConsultaResult, "Nenhum processo encontrado com os filtros fornecidos.");
                    return;
                }

                // Get the first process
                const firstProcess = listData.processos[0];
                const numeroProcesso = firstProcess.numeroProcesso;

                if (!numeroProcesso) {
                    setOutput(ui.scrapperConsultaResult, "Processo encontrado mas sem número disponível.");
                    return;
                }

                setOutput(ui.scrapperConsultaResult, `Encontrado ${listData.processos.length} processo(s). Buscando detalhes...`);

                // Now fetch the detailed information
                const detailData = await callScrapperEndpoint("processos/tjrj/consulta", {
                    method: "POST",
                    payload: { numero_processo: numeroProcesso },
                });

                setOutput(ui.scrapperConsultaResult, prettyPrintJson(detailData));
            }
        } else {
            // TJSP uses the same endpoint for both list and individual query
            const endpoint = "processos/consulta";
            const data = await callScrapperEndpoint(endpoint, {
                method: "POST",
                payload,
            });
            setOutput(ui.scrapperConsultaResult, prettyPrintJson(data));
        }
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

    // Get selected tribunal
    const tribunalSelector = document.getElementById("scrapperListTribunalSelector");
    const tribunal = tribunalSelector ? tribunalSelector.value : "tjsp";

    const payload = collectScrapperPayload(ui.scrapperListForm, ["max_paginas", "max_processos"]);

    // Smart handling for TJSP: auto-enable nome_completo for short names
    if (tribunal === "tjsp" && payload.nome_parte) {
        const nomeParte = payload.nome_parte.trim();
        // If name is short (single word or 2 words) and nome_completo is not set, enable it
        const wordCount = nomeParte.split(/\s+/).length;
        if (wordCount <= 2 && !payload.nome_completo) {
            payload.nome_completo = true;
            console.log(`[Auto] Enabling nome_completo for short name: "${nomeParte}"`);
        }
    }

    // Remove TJSP-specific fields when using PJE or TJRJ
    if (tribunal === "pje" || tribunal === "tjrj") {
        delete payload.nome_completo;
        delete payload.max_paginas;
        delete payload.max_processos;
    }

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
        let endpoint = "processos/listar";
        if (tribunal === "pje") {
            endpoint = "processos/pje/listar";
        } else if (tribunal === "tjrj") {
            endpoint = "processos/tjrj/listar";
        }

        const data = await callScrapperEndpoint(endpoint, {
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
    if (ui.statusBadge) {
        if (tone in toneMap) {
            ui.statusBadge.textContent = toneMap[tone].text;
        } else {
            ui.statusBadge.textContent = tone;
        }
    }
    if (ui.footerStatus) {
        ui.footerStatus.textContent = message;
    }
}

// Connection status indicator
function updateConnectionStatus(status) {
    const indicator = document.getElementById('connectionIndicator');
    if (!indicator) return;

    const dot = indicator.querySelector('.connection-dot');
    const text = indicator.querySelector('.connection-text');

    // Remove all status classes
    dot.classList.remove('connection-dot--connected', 'connection-dot--connecting', 'connection-dot--disconnected');

    if (status === 'connected') {
        dot.classList.add('connection-dot--connected');
        text.textContent = 'Conectado';
    } else if (status === 'connecting') {
        dot.classList.add('connection-dot--connecting');
        text.textContent = 'Conectando...';
    } else {
        dot.classList.add('connection-dot--disconnected');
        text.textContent = 'Desconectado';
    }
}

// Audio visualizer
let visualizerCanvas = null;
let visualizerContext = null;
let visualizerAnimationId = null;

function initAudioVisualizer() {
    const container = document.getElementById('audioVisualizerContainer');
    visualizerCanvas = document.getElementById('audioVisualizer');

    if (!visualizerCanvas) return;

    visualizerContext = visualizerCanvas.getContext('2d');
    visualizerCanvas.width = visualizerCanvas.offsetWidth * window.devicePixelRatio;
    visualizerCanvas.height = 80 * window.devicePixelRatio;

    container.classList.remove('hidden');

    // Start animation
    animateVisualizer();
}

function animateVisualizer() {
    if (!visualizerContext || !visualizerCanvas) return;

    const ctx = visualizerContext;
    const width = visualizerCanvas.width;
    const height = visualizerCanvas.height;
    const barCount = 60;
    const barWidth = width / barCount;

    ctx.clearRect(0, 0, width, height);

    // Simple animated bars (will be replaced with actual audio data if needed)
    for (let i = 0; i < barCount; i++) {
        const barHeight = Math.random() * height * 0.7 + height * 0.1;
        const x = i * barWidth;
        const y = (height - barHeight) / 2;

        // Gradient
        const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
        gradient.addColorStop(0, 'rgba(124, 106, 255, 0.8)');
        gradient.addColorStop(1, 'rgba(85, 81, 255, 0.4)');

        ctx.fillStyle = gradient;
        ctx.fillRect(x + 1, y, barWidth - 2, barHeight);
    }

    visualizerAnimationId = requestAnimationFrame(animateVisualizer);
}

function stopAudioVisualizer() {
    const container = document.getElementById('audioVisualizerContainer');
    if (container) {
        container.classList.add('hidden');
    }

    if (visualizerAnimationId) {
        cancelAnimationFrame(visualizerAnimationId);
        visualizerAnimationId = null;
    }

    if (visualizerContext && visualizerCanvas) {
        visualizerContext.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
    }
}

function updateStats() {
    if (ui.batchCount) ui.batchCount.textContent = state.batches.toString();
    if (ui.tokenCount) ui.tokenCount.textContent = state.tokens.toString();
    if (ui.audioSeconds) ui.audioSeconds.textContent = state.audioSeconds.toFixed(1);
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

// Removed: renderTimeline function - Timeline box was removed from UI
// function renderTimeline() {
//     ui.timeline.innerHTML = "";
//     const fragment = document.createDocumentFragment();
//     state.timeline.slice(-20).forEach((item) => {
//         const div = document.createElement("div");
//         div.className = "timeline__item";
//         const top = document.createElement("div");
//         top.className = "timeline__meta";
//         const tokensInfo = typeof item.tokens === "number" && item.tokens > 0 ? ` | ${item.tokens} tokens` : "";
//         top.innerHTML = `<span>Lote #${item.batch}</span><span>${item.duration.toFixed(1)}s${tokensInfo}</span>`;
//         const body = document.createElement("div");
//         body.textContent = item.text || "(texto vazio)";
//         div.appendChild(top);
//         div.appendChild(body);
//         fragment.appendChild(div);
//     });
//     ui.timeline.appendChild(fragment);
//     ui.timeline.scrollTop = ui.timeline.scrollHeight;
// }

// Removed: renderInsights function - Insights box was removed from UI
// function renderInsights() {
//     ui.insights.innerHTML = "";
//     if (!state.insights.length) {
//         const p = document.createElement("p");
//         p.className = "placeholder";
//         p.textContent = "Nenhum insight emitido ainda.";
//         ui.insights.appendChild(p);
//         return;
//     }
//     const fragment = document.createDocumentFragment();
//     state.insights.forEach((insight) => {
//         const container = document.createElement("div");
//         container.className = "insight";
//         const meta = document.createElement("div");
//         meta.className = "insight__meta";
//         const ts = new Date(insight.generated_at || Date.now());
//         meta.innerHTML = `<span>${insight.type || "Insight"}</span><span>${ts.toLocaleTimeString()}</span>`;
//         const body = document.createElement("div");
//         body.textContent = insight.text || "(sem texto)";
//         container.appendChild(meta);
//         container.appendChild(body);
//         fragment.appendChild(container);
//     });
//     ui.insights.appendChild(fragment);
// }

function renderChat() {
    ui.chatLog.innerHTML = "";
    if (!state.chatHistory.length) {
        const placeholder = document.createElement("div");
        placeholder.className = "chat-welcome";
        placeholder.innerHTML = `
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <p>Converse com o modelo de linguagem</p>
        `;
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
    // renderTimeline(); // Removed - Timeline box was removed from UI
    // renderInsights(); // Removed - Insights box was removed from UI
}

async function setupAudio() {
    if (state.audioContext) {
        return;
    }

    console.log("[Audio] Solicitando permissão de microfone...");
    const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
        }
    });

    console.log("[Audio] Permissão concedida. Criando AudioContext...");
    const AudioCtx = window.AudioContext || window.webkitAudioContext;

    // Não força sample rate específico, usa o padrão do navegador
    const audioContext = new AudioCtx();
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    const gainNode = audioContext.createGain();
    gainNode.gain.value = 0;

    state.inputSampleRate = audioContext.sampleRate;
    console.log("[Audio] AudioContext criado. Sample rate:", audioContext.sampleRate);

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

    console.log("[Audio] Setup completo!");
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

    // Stop visualizer and update connection status
    stopAudioVisualizer();
    updateConnectionStatus('disconnected');
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

    console.log("[WebSocket] Base URL:", base);
    console.log("[WebSocket] Protocol:", window.location.protocol);

    // Se a página está em HTTPS, force WSS. Se HTTP, force WS.
    let wsBase;
    if (window.location.protocol === "https:") {
        wsBase = base.replace(/^http:/i, "wss:").replace(/^https:/i, "wss:");
    } else {
        wsBase = base.replace(/^https:/i, "ws:").replace(/^http:/i, "ws:");
    }

    console.log("[WebSocket] WS Base:", wsBase);

    const url = new URL(`${wsBase}/api/v1/asr/stream`);
    if (token) {
        url.searchParams.set("token", token);
    }

    console.log("[WebSocket] URL final:", url.toString());
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
            // ui.insightStatus.textContent = state.insightsRequested ? "Habilitados" : "Desabilitados"; // Removed - insightStatus element was removed from UI
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
            // renderTimeline(); // Removed - Timeline box was removed from UI
            updateStats();
            break;
        }
        case "insight": {
            if (!state.insightsRequested) {
                return;
            }
            state.insights.unshift(payload);
            state.insights = state.insights.slice(0, 12);
            // renderInsights(); // Removed - Insights box was removed from UI
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
        case "diarization_update": {
            // Handle streaming diarization updates
            console.log("Diarization update received:", payload);
            if (payload.conversation && payload.conversation.length > 0) {
                state.diarizedConversation = payload.conversation;
                state.diarizedMessageCount = payload.total_messages || payload.conversation.length;

                // Display diarized conversation in streaming mode
                if (ui.asrDiarResult) {
                    displayStreamingDiarizedConversation(payload.conversation);
                }
            }
            break;
        }
        case "final_diarization": {
            // Handle final diarization result
            console.log("Final diarization received:", payload);
            if (payload.conversation && payload.conversation.length > 0) {
                state.diarizedConversation = payload.conversation;
                state.diarizedMessageCount = payload.total_messages || payload.conversation.length;

                // Display final diarized conversation
                if (ui.asrDiarResult) {
                    displayFinalDiarizedConversation(payload.conversation);
                }
            }
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
    updateConnectionStatus('connecting');

    if (source === "mic") {
        try {
            await setupAudio();
        } catch (err) {
            console.error("Permissao de microfone negada", err);
            setStatus("Permissao de microfone negada ou indisponivel.", "error");
            updateConnectionStatus('disconnected');
            stopAudio();
            return;
        }
    } else {
        stopAudio();
    }

    const url = resolveWsUrl();
    console.log("[WebSocket] Conectando a:", url.toString());

    let ws;
    try {
        ws = new WebSocket(url);
        state.ws = ws;
    } catch (err) {
        console.error("[WebSocket] Erro ao criar WebSocket:", err);
        setStatus("Erro ao criar conexão WebSocket: " + err.message, "error");
        cleanupSession("Falha ao criar WebSocket.");
        return;
    }

    ws.onopen = () => {
        console.log("[WebSocket] Conexão estabelecida!");

        if (source === "mic") {
            ui.startButton.disabled = true;
            ui.listeningIndicator.classList.remove("hidden");
        }
        ui.stopButton.disabled = false;
        state.streaming = true;

        // Update connection status and initialize visualizer
        updateConnectionStatus('connected');
        initAudioVisualizer();

        // Captura room_id e role se fornecidos
        const roomId = source === "mic" && ui.roomId ? (ui.roomId.value.trim() || null) : null;
        const role = source === "mic" && ui.roleSelector ? (ui.roleSelector.value || null) : null;

        if (roomId) {
            state.roomId = roomId;
            state.role = role;
        }

        // Get selected output language
        const realtimeLanguageSelect = document.getElementById('realtimeLanguage');
        const outputLanguage = realtimeLanguageSelect ? realtimeLanguageSelect.value : 'pt';
        console.log("[Real-time] Idioma de saída selecionado:", outputLanguage);

        const payload = {
            event: "start",
            language: outputLanguage,
            sample_rate: state.targetSampleRate,
            encoding: "pcm16",
            model: "whisper/medium",
            compute_type: "int8_float16",
            batch_window_sec: 2.0,
            max_batch_window_sec: 10.0,
            enable_insights: false, // Insights feature removed
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
        console.error("[WebSocket] Erro:", event);
        console.error("[WebSocket] readyState:", ws.readyState);
        console.error("[WebSocket] URL:", ws.url);
        const errorMsg = `Falha no WebSocket (readyState: ${ws.readyState}). Verifique: 1) Token válido 2) Conexão HTTPS 3) Console do navegador`;
        setStatus(errorMsg, "error");
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

// ============================================================================
// CHAT WITH AGENTS/TEAMS
// ============================================================================

async function loadAgentsForChat() {
    const agentsApiBase = 'https://paneas-agents-dev.paneas.net';
    try {
        const response = await fetch(`${agentsApiBase}/v1/agents`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        state.availableAgents = await response.json();
        console.log('Agentes carregados:', state.availableAgents.length);

        // Atualizar select se tipo atual for 'agent'
        if (state.chatType === 'agent') {
            updateChatTargetSelect();
        }
    } catch (error) {
        console.error('Erro ao carregar agentes:', error);
        state.availableAgents = [];
    }
}

async function loadTeamsForChat() {
    const agentsApiBase = 'https://paneas-agents-dev.paneas.net';
    try {
        const response = await fetch(`${agentsApiBase}/v1/teams`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        state.availableTeams = await response.json();
        console.log('Teams carregados:', state.availableTeams.length);

        // Atualizar select se tipo atual for 'team'
        if (state.chatType === 'team') {
            updateChatTargetSelect();
        }
    } catch (error) {
        console.error('Erro ao carregar teams:', error);
        state.availableTeams = [];
    }
}

function updateChatTargetSelect() {
    const select = document.getElementById('chatTarget');
    if (!select) return;

    const type = state.chatType;

    if (type === 'model') {
        select.innerHTML = '<option value="paneas-q32b">paneas-q32b (Paneas-32B)</option>';
        state.chatTargetId = 'paneas-q32b';
    } else if (type === 'agent') {
        if (state.availableAgents.length === 0) {
            select.innerHTML = '<option value="">Carregando agentes...</option>';
        } else {
            select.innerHTML = state.availableAgents
                .map(a => `<option value="${a.id}">${a.name}</option>`)
                .join('');
            // Selecionar primeiro agente
            if (state.availableAgents.length > 0) {
                state.chatTargetId = state.availableAgents[0].id;
                select.value = state.chatTargetId;
            }
        }
    } else if (type === 'team') {
        if (state.availableTeams.length === 0) {
            select.innerHTML = '<option value="">Carregando teams...</option>';
        } else {
            select.innerHTML = state.availableTeams
                .map(t => `<option value="${t.id}">${t.name}</option>`)
                .join('');
            // Selecionar primeiro team
            if (state.availableTeams.length > 0) {
                state.chatTargetId = state.availableTeams[0].id;
                select.value = state.chatTargetId;
            }
        }
    }
}

async function sendToAgent(message) {
    const agentId = state.chatTargetId;
    const agentsApiBase = 'https://paneas-agents-dev.paneas.net';

    // Gerar conversation_id na primeira mensagem
    if (!state.conversationId) {
        state.conversationId = `conv-${Date.now()}-${Math.random().toString(36).substring(7)}`;
        console.log('Nova conversa com agente:', state.conversationId);
    }

    const url = `${agentsApiBase}/v1/agents/${agentId}/run`;

    // Adicionar mensagem do usuário ao histórico
    state.chatHistory.push({ role: "user", content: message });
    renderChat();

    ui.chatInput.value = "";
    ui.chatInput.disabled = true;

    const payload = {
        input: message,
        conversation_id: state.conversationId
    };

    setStatus("Consultando agente...", "loading");

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();

        // Adicionar resposta do agente
        state.chatHistory.push({
            role: "assistant",
            content: data.output || "(resposta vazia)"
        });
        renderChat();

        setStatus("Resposta do agente recebida.", "ready");

    } catch (err) {
        console.error("Erro ao consultar agente:", err);
        state.chatHistory.push({
            role: "assistant",
            content: `[erro] ${err.message}`
        });
        renderChat();
        setStatus("Falha ao consultar o agente.", "error");
    } finally {
        ui.chatInput.disabled = false;
        ui.chatInput.focus();
    }
}

async function sendToTeam(message) {
    const teamId = state.chatTargetId;
    const agentsApiBase = 'https://paneas-agents-dev.paneas.net';

    if (!state.conversationId) {
        state.conversationId = `conv-${Date.now()}-${Math.random().toString(36).substring(7)}`;
        console.log('Nova conversa com team:', state.conversationId);
    }

    const url = `${agentsApiBase}/v1/teams/${teamId}/run`;

    state.chatHistory.push({ role: "user", content: message });
    renderChat();

    ui.chatInput.value = "";
    ui.chatInput.disabled = true;

    const payload = {
        input: message,
        conversation_id: state.conversationId
    };

    setStatus("Consultando team...", "loading");

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();

        state.chatHistory.push({
            role: "assistant",
            content: data.output || "(resposta vazia)"
        });
        renderChat();

        setStatus("Resposta do team recebida.", "ready");

    } catch (err) {
        console.error("Erro ao consultar team:", err);
        state.chatHistory.push({
            role: "assistant",
            content: `[erro] ${err.message}`
        });
        renderChat();
        setStatus("Falha ao consultar o team.", "error");
    } finally {
        ui.chatInput.disabled = false;
        ui.chatInput.focus();
    }
}

async function sendChatMessage(text) {
    const content = text.trim();
    if (!content) {
        return;
    }

    // Rotear baseado no tipo selecionado
    const chatType = state.chatType;

    if (chatType === 'agent') {
        return await sendToAgent(content);
    } else if (chatType === 'team') {
        return await sendToTeam(content);
    }

    // Continuar com o fluxo de modelo direto...
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

    // Get selected language
    const language = document.getElementById('asrLanguage')?.value || 'pt';
    // Check if native diarization is enabled
    const enableNativeDiarization = document.getElementById('asrEnableDiarization')?.checked || false;
    // Get number of speakers if diarization is enabled
    const numSpeakers = enableNativeDiarization ? (document.getElementById('asrNumSpeakers')?.value || '2') : null;
    // Check if LLM post-processing is enabled
    const enableLlmPostprocess = document.getElementById('asrEnableLlmPostprocess')?.checked || false;
    // Get post-processing mode if enabled
    const postprocessMode = enableLlmPostprocess ? (document.querySelector('input[name="asrPostprocessMode"]:checked')?.value || 'paneas-default') : null;

    console.log("[ASR] Arquivo selecionado:", file.name, file.size, "bytes");
    console.log("[ASR] Idioma selecionado:", language);
    console.log("[ASR] Diarização Nativa (PyAnnote):", enableNativeDiarization ? "ativada" : "desativada");
    if (enableNativeDiarization) {
        console.log("[ASR] Número de speakers:", numSpeakers);
    }
    const modeLabelMap = {
        'paneas-default': 'Default',
        'paneas-hybrid': 'Hybrid',
        'paneas-large': 'Large'
    };
    console.log("[ASR] Pós-processamento:", enableLlmPostprocess ? `ativado (Modelo: ${modeLabelMap[postprocessMode] || 'Default'})` : "desativado");

    // Show processing animation
    let processingTitle = "Processando Transcrição";
    let processingDesc = "Analisando áudio";

    if (enableNativeDiarization) {
        processingDesc += ` com diarização de ${numSpeakers} speakers`;
    }

    let detailsText = "";

    // Get audio duration to calculate estimated time
    let audioDuration = 300; // Default 5 minutes if we can't read it
    try {
        const audio = document.createElement('audio');
        const audioURL = URL.createObjectURL(file);
        audio.src = audioURL;

        await new Promise((resolve) => {
            audio.addEventListener('loadedmetadata', () => {
                audioDuration = Math.ceil(audio.duration);
                URL.revokeObjectURL(audioURL);
                console.log('[ASR] Duração do áudio:', audioDuration, 'segundos');
                resolve();
            });
            audio.addEventListener('error', () => {
                URL.revokeObjectURL(audioURL);
                console.warn('[ASR] Não foi possível ler duração do áudio, usando padrão');
                resolve();
            });
        });
    } catch (err) {
        console.warn('[ASR] Erro ao ler duração do áudio:', err);
    }

    // Calculate estimated time based on audio duration
    // Formula: overhead + (duration * factor)
    let estimatedTime = 20;
    if (enableLlmPostprocess) {
        const modeLabel = modeLabelMap[postprocessMode] || 'Hybrid';
        detailsText = `Pós-processamento com modelo ${modeLabel} será aplicado após transcrição`;

        // Factors based on 5min audio tests:
        // Base (no postprocess): 20s for 300s = overhead 5s + 0.05*duration
        // Hybrid: 37s for 300s = overhead 10s + 0.09*duration
        // Default: 40s for 300s = overhead 10s + 0.10*duration
        // Large: 44s for 300s = overhead 10s + 0.113*duration

        if (postprocessMode === 'paneas-default') {
            estimatedTime = Math.ceil(10 + audioDuration * 0.10);
        } else if (postprocessMode === 'paneas-hybrid') {
            estimatedTime = Math.ceil(10 + audioDuration * 0.09);
        } else if (postprocessMode === 'paneas-large') {
            estimatedTime = Math.ceil(10 + audioDuration * 0.113);
        }
    } else {
        // Base ASR without post-processing
        estimatedTime = Math.ceil(5 + audioDuration * 0.05);
    }

    console.log('[ASR] Tempo estimado de processamento:', estimatedTime, 'segundos');

    // Clear result box and update button to loading state
    ui.asrResult.innerHTML = '';

    const uploadButton = document.getElementById('asrUploadButton');
    const originalButtonText = uploadButton.innerHTML;

    // Update button to loading state
    uploadButton.disabled = true;
    uploadButton.innerHTML = `
        <span class="btn-spinner"></span>
        Processando... <span id="buttonTimeCounter">0</span>s / ~${estimatedTime}s
    `;

    // Start seconds counter
    let elapsedSeconds = 0;
    const secondsInterval = setInterval(() => {
        elapsedSeconds++;
        const counterElement = document.getElementById('buttonTimeCounter');
        if (counterElement) {
            counterElement.textContent = elapsedSeconds;
        }
    }, 1000);

    window.asrSecondsInterval = secondsInterval;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("language", language);

    // Enable native diarization if toggle is checked
    if (enableNativeDiarization) {
        formData.append("enable_diarization", "true");
        formData.append("num_speakers", numSpeakers);
    }

    // Enable LLM post-processing if toggle is checked
    if (enableLlmPostprocess) {
        formData.append("enable_llm_postprocess", "true");
        formData.append("postprocess_mode", postprocessMode);
    }

    const base = resolveApiBase();
    const url = `${base}/api/v1/asr`;
    console.log("[ASR] URL do endpoint:", url);

    try {
        console.log("[ASR] Iniciando requisição fetch...");
        const startTime = Date.now();

        const response = await fetch(url, {
            method: "POST",
            headers: buildAuthHeaders(),
            body: formData,
        });

        const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
        console.log("[ASR] Resposta recebida - status:", response.status, "tempo:", elapsedTime + "s");

        if (!response.ok) {
            const errorText = await response.text();
            console.error("[ASR] Erro na resposta:", errorText);
            if (window.asrSecondsInterval) clearInterval(window.asrSecondsInterval);
            uploadButton.disabled = false;
            uploadButton.innerHTML = originalButtonText;
            setOutput(ui.asrResult, `Erro ${response.status}: ${errorText || "Falha ao processar a transcrição."}`);
            return;
        }

        const data = await response.json();
        console.log("[ASR] Dados recebidos:", data);
        console.log("[ASR] Tempo de processamento:", elapsedTime + "s");

        // Stop counter and restore button
        if (window.asrSecondsInterval) clearInterval(window.asrSecondsInterval);
        uploadButton.disabled = false;
        uploadButton.innerHTML = originalButtonText;

        // Sempre mostrar o JSON formatado
        const resultContainer = document.getElementById('asrResult');
        if (resultContainer) {
            // Adicionar informação se diarização foi usada
            let headerInfo = '';
            if (enableNativeDiarization && data.segments && data.segments.length > 0) {
                const hasSpeakers = data.segments[0].hasOwnProperty('speaker');
                if (hasSpeakers) {
                    const speakers = [...new Set(data.segments.map(seg => seg.speaker))];
                    headerInfo = `<div style="color: #5551ff; margin-bottom: 10px;">✅ Diarização aplicada - ${speakers.length} speakers detectados - Tempo: ${elapsedTime}s</div>`;
                }
            }

            // Adicionar informação se pós-processamento foi usado
            if (enableLlmPostprocess && data.raw_text) {
                headerInfo += `<div style="color: #10b981; margin-bottom: 10px;">✅ Pós-processamento aplicado</div>`;
            }

            // Mostrar JSON formatado
            resultContainer.innerHTML = headerInfo + `<pre style="white-space: pre-wrap; word-wrap: break-word; overflow-x: auto; text-align: left;">${JSON.stringify(data, null, 2)}</pre>`;
        }
    } catch (err) {
        console.error("[ASR] Falha na transcrição por arquivo", err);
        if (window.asrSecondsInterval) clearInterval(window.asrSecondsInterval);
        uploadButton.disabled = false;
        uploadButton.innerHTML = originalButtonText;
        setOutput(ui.asrResult, `Erro: ${err.message || err}`);
    }
}

// New function to display native diarized transcription
function displayDiarizedTranscription(data, elapsedTime) {
    const resultBox = ui.asrResult;
    if (!resultBox) return;

    // Extract unique speakers
    const speakers = [...new Set(data.segments.map(seg => seg.speaker))].sort();

    // Build conversation array
    const conversation = data.segments.map(segment => ({
        speaker: segment.speaker,
        text: segment.text.trim(),
        start: segment.start,
        end: segment.end
    }));

    // Create HTML for display
    let html = `
        <div class="conversation-container">
            <div class="conversation-header">
                <div class="conversation-header__title">
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                    </svg>
                    Transcrição com Diarização Nativa (PyAnnote)
                </div>
                <div class="conversation-header__stats">
                    <span>${speakers.length} speakers detectados</span>
                    <span>${conversation.length} segmentos</span>
                    <span>Tempo: ${elapsedTime}s</span>
                </div>
            </div>
            <div class="conversation-body">`;

    // Add each conversation turn
    conversation.forEach((turn, index) => {
        const speakerLabel = turn.speaker.replace('SPEAKER_', 'Falante ');
        const isEven = index % 2 === 0;
        html += `
            <div class="conversation-turn ${isEven ? 'even' : 'odd'}">
                <div class="speaker-label ${turn.speaker}">${speakerLabel}</div>
                <div class="speaker-text">${turn.text}</div>
                <div class="time-label">${formatTime(turn.start)} - ${formatTime(turn.end)}</div>
            </div>`;
    });

    html += `
            </div>
            <div class="conversation-footer">
                <div class="metadata">
                    <strong>Metadata:</strong>
                    <div>Modelo: ${data.metadata?.model || 'N/A'}</div>
                    <div>Duração: ${data.duration_seconds?.toFixed(2) || 'N/A'}s</div>
                    <div>Idioma: ${data.language || 'N/A'}</div>
                </div>
            </div>
        </div>`;

    resultBox.innerHTML = html;
}

// Helper function to format time in seconds to MM:SS
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

async function diarizeWithLLM(transcriptText) {
    const resultBox = ui.asrResult;
    if (!resultBox) return;

    // Show loading status
    resultBox.innerHTML = `
        <div class="diarization-status">
            <div class="diarization-status__spinner"></div>
            <span class="diarization-status__text">Separando canais com LLM...</span>
        </div>
    `;

    const base = resolveApiBase();
    const chatUrl = `${base}/api/v1/chat/completions`;

    const diarizationPrompt = `Você é um especialista em análise de transcrições de call center. Separe a transcrição em diálogo entre "Atendente" e "Cliente".

CARACTERÍSTICAS PARA IDENTIFICAÇÃO:

ATENDENTE (Operador/Vendedor):
- Se apresenta com nome e empresa (ex: "Meu nome é Carlos, sou da Claro")
- Faz perguntas sobre dados pessoais (CPF, nome completo, endereço)
- Oferece produtos, planos ou serviços
- Explica condições, valores e benefícios
- Usa linguagem mais formal e técnica
- Faz perguntas procedimentais ("Posso confirmar seus dados?")
- Pede confirmações ("Correto?", "Ok?", "Tudo bem?")
- Agradece e se despede formalmente

CLIENTE:
- Responde às perguntas do atendente
- Geralmente fala menos em cada turno
- Fornece dados pessoais quando solicitado
- Faz perguntas sobre o serviço
- Aceita ou recusa ofertas ("Sim", "Não", "Vamos", "Ok")
- Expressa dúvidas ou problemas pessoais
- Fala de forma mais informal

REGRAS IMPORTANTES:
1. O primeiro "Oi" ou "Alô" geralmente é do CLIENTE atendendo a ligação
2. Quem se apresenta com nome e empresa é SEMPRE o Atendente
3. Respostas curtas como "Sim", "Ok", "Tá" são geralmente do Cliente
4. Mantenha a ordem cronológica exata das falas
5. Cada mudança de speaker deve ser uma nova entrada
6. Corrija pequenos erros de transcrição mas mantenha o sentido

FORMATO DE SAÍDA:
Retorne APENAS um JSON array, sem explicações:
[{"speaker": "Cliente", "text": "..."}, {"speaker": "Atendente", "text": "..."}]

Transcrição para separar:
${transcriptText}`;

    try {
        console.log("[Diarization] Enviando para LLM...");
        console.log("[Diarization] Tamanho do texto:", transcriptText.length, "chars");

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 min timeout

        const response = await fetch(chatUrl, {
            method: "POST",
            headers: buildAuthHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
                model: "paneas-q32b",
                messages: [
                    { role: "user", content: diarizationPrompt }
                ],
                temperature: 0.3,
                max_tokens: 4000,
                stream: true
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        console.log("[Diarization] Stream iniciado, status:", response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error("[Diarization] Erro:", errorText);
            throw new Error(`LLM request failed: ${response.status} - ${errorText}`);
        }

        // Setup streaming conversation display
        resultBox.innerHTML = `
            <div class="conversation-header">
                <div class="conversation-header__title">
                    <svg style="width: 18px; height: 18px; display: inline-block; vertical-align: middle; margin-right: 8px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                    Conversa Diarizada
                    <div class="diarization-status__spinner" style="width: 14px; height: 14px; margin-left: 8px; display: inline-block;"></div>
                </div>
                <div class="conversation-header__count">
                    <span id="messageCount">0 mensagens</span>
                </div>
            </div>
            <div class="conversation-container"></div>
        `;

        const container = resultBox.querySelector('.conversation-container');
        let llmResponse = "";

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n').filter(line => line.trim() !== '');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;

                    try {
                        const parsed = JSON.parse(data);
                        const content = parsed.choices?.[0]?.delta?.content || '';
                        if (content) {
                            llmResponse += content;

                            // Try to parse incrementally and display messages
                            const partialConversation = tryParsePartialJSON(llmResponse);
                            if (partialConversation.length > 0) {
                                displayStreamingConversation(container, partialConversation);
                                document.getElementById('messageCount').textContent = `${partialConversation.length} mensagens`;
                            }
                        }
                    } catch (e) {
                        // Ignore parse errors during streaming
                    }
                }
            }
        }

        console.log("[Diarization] Stream completo");

        // Final parse
        let conversation = [];
        try {
            let cleanedResponse = llmResponse.trim();
            if (cleanedResponse.startsWith('```json')) {
                cleanedResponse = cleanedResponse.replace(/```json\n?/g, '').replace(/```\n?$/g, '');
            } else if (cleanedResponse.startsWith('```')) {
                cleanedResponse = cleanedResponse.replace(/```\n?/g, '');
            }
            conversation = JSON.parse(cleanedResponse);
        } catch (parseError) {
            console.error("[Diarization] Failed to parse final JSON", parseError);
            const lines = llmResponse.split('\n').filter(l => l.trim());
            for (const line of lines) {
                const match = line.match(/^(Atendente|Cliente):\s*(.+)$/);
                if (match) {
                    conversation.push({
                        speaker: match[1],
                        text: match[2].trim()
                    });
                }
            }
        }

        if (conversation.length === 0) {
            throw new Error("Não foi possível extrair a conversa do LLM");
        }

        // Final display
        displayDiarizedConversation(conversation);

    } catch (err) {
        console.error("[Diarization] Erro:", err);
        setOutput(resultBox, `Erro na diarização: ${err.message}`);
    }
}

function tryParsePartialJSON(text) {
    // Try to extract complete JSON objects from partial stream
    try {
        // Look for complete objects in the stream
        const jsonMatch = text.match(/\[\s*(\{[\s\S]*\})\s*\]/);
        if (jsonMatch) {
            return JSON.parse(jsonMatch[0]);
        }

        // Try to find individual complete objects
        const objectMatches = text.matchAll(/\{\s*"speaker"\s*:\s*"(Atendente|Cliente)"\s*,\s*"text"\s*:\s*"([^"]+)"\s*\}/g);
        const results = [];
        for (const match of objectMatches) {
            results.push({
                speaker: match[1],
                text: match[2]
            });
        }
        return results;
    } catch (e) {
        return [];
    }
}

function displayStreamingConversation(container, conversation) {
    // Smart update: only add new messages instead of clearing everything
    const existingMessages = container.querySelectorAll('.conversation-message');
    const startIndex = existingMessages.length;

    // Only add new messages
    for (let i = startIndex; i < conversation.length; i++) {
        const message = conversation[i];
        const isAgent = message.speaker.toLowerCase().includes('atendente');
        const messageDiv = document.createElement('div');
        messageDiv.className = `conversation-message conversation-message--${isAgent ? 'agent' : 'client'}`;
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(20px)';

        const speakerIcon = isAgent
            ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';

        messageDiv.innerHTML = `
            <div class="conversation-speaker conversation-speaker--${isAgent ? 'agent' : 'client'}">
                ${speakerIcon}
                ${message.speaker}
            </div>
            <div class="conversation-bubble conversation-bubble--${isAgent ? 'agent' : 'client'}">
                ${message.text}
            </div>
        `;

        container.appendChild(messageDiv);

        // Smooth fade-in animation
        setTimeout(() => {
            messageDiv.style.transition = 'all 0.3s ease-out';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        }, 10);
    }

    // Smooth scroll to bottom
    container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
    });
}

function displayStreamingDiarizedConversation(conversation) {
    const resultBox = ui.asrDiarResult || ui.asrResult;
    if (!resultBox) return;

    // Create header if not exists
    if (!resultBox.querySelector('.conversation-header')) {
        const header = `
            <div class="conversation-header">
                <div class="conversation-header__title">
                    <svg style="width: 18px; height: 18px; display: inline-block; vertical-align: middle; margin-right: 8px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                    Diarização em Tempo Real
                    <div class="diarization-status__spinner" style="width: 14px; height: 14px; margin-left: 8px; display: inline-block;"></div>
                </div>
                <div class="conversation-header__count">
                    <span id="diarMessageCount">${conversation.length} mensagens</span>
                </div>
            </div>
            <div class="conversation-container"></div>
        `;
        resultBox.innerHTML = header;
    } else {
        // Update message count
        const countEl = resultBox.querySelector('#diarMessageCount');
        if (countEl) {
            countEl.textContent = `${conversation.length} mensagens`;
        }
    }

    const container = resultBox.querySelector('.conversation-container');
    if (container) {
        displayStreamingConversation(container, conversation);
    }
}

function displayFinalDiarizedConversation(conversation) {
    const resultBox = ui.asrDiarResult || ui.asrResult;
    if (!resultBox) return;

    // Update header to show final status
    const header = `
        <div class="conversation-header">
            <div class="conversation-header__title">
                <svg style="width: 18px; height: 18px; display: inline-block; vertical-align: middle; margin-right: 8px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                Conversa Diarizada (Final)
            </div>
            <div class="conversation-header__count">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                </svg>
                ${conversation.length} mensagens
            </div>
        </div>
    `;

    resultBox.innerHTML = header + '<div class="conversation-container"></div>';
    const container = resultBox.querySelector('.conversation-container');

    // Display all messages
    displayDiarizedConversation(conversation);
}

function displayDiarizedConversation(conversation) {
    const resultBox = ui.asrResult;
    if (!resultBox) return;

    // Create header with conversation stats
    const header = `
        <div class="conversation-header">
            <div class="conversation-header__title">
                <svg style="width: 18px; height: 18px; display: inline-block; vertical-align: middle; margin-right: 8px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                Conversa Diarizada
            </div>
            <div class="conversation-header__count">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                </svg>
                ${conversation.length} mensagens
            </div>
        </div>
    `;

    // Check if we already have content to avoid flickering
    const existingContainer = resultBox.querySelector('.conversation-container');
    if (!existingContainer) {
        resultBox.innerHTML = header + '<div class="conversation-container"></div>';
    }

    const container = resultBox.querySelector('.conversation-container');
    const existingMessages = container.querySelectorAll('.conversation-message');
    const startIndex = existingMessages.length;

    // Only add new messages
    for (let i = startIndex; i < conversation.length; i++) {
        const message = conversation[i];
        const isAgent = message.speaker.toLowerCase().includes('atendente');
        const messageDiv = document.createElement('div');
        messageDiv.className = `conversation-message conversation-message--${isAgent ? 'agent' : 'client'}`;
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(10px)';

        const speakerIcon = isAgent
            ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';

        messageDiv.innerHTML = `
            <div class="conversation-speaker conversation-speaker--${isAgent ? 'agent' : 'client'}">
                ${speakerIcon}
                ${message.speaker}
            </div>
            <div class="conversation-bubble conversation-bubble--${isAgent ? 'agent' : 'client'}">
                ${message.text}
            </div>
        `;

        container.appendChild(messageDiv);

        // Smooth fade-in animation with minimal delay
        requestAnimationFrame(() => {
            messageDiv.style.transition = 'all 0.3s ease-out';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        });
    }

    // Smooth scroll to bottom
    container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
    });
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
    state.conversationId = null; // Resetar contexto de conversa com agente/team
    renderChat();
}

function bindEvents() {
    // Config collapsible toggle
    const configToggle = document.getElementById('configToggle');
    const configContent = document.getElementById('configContent');

    configToggle?.addEventListener('click', () => {
        const isActive = configToggle.classList.toggle('active');
        if (isActive) {
            configContent.classList.add('active');
        } else {
            configContent.classList.remove('active');
        }
    });

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

    // Chat type selector (model/agent/team)
    document.querySelectorAll('input[name="chatType"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            state.chatType = e.target.value;
            updateChatTargetSelect();

            // Resetar conversation_id ao trocar tipo
            state.conversationId = null;

            // Mostrar/esconder system prompt (só para modelo direto)
            const systemPromptGroup = document.getElementById('chatSystemPromptGroup');
            if (systemPromptGroup) {
                systemPromptGroup.style.display = state.chatType === 'model' ? 'block' : 'none';
            }
        });
    });

    // Chat target selector
    const chatTarget = document.getElementById('chatTarget');
    if (chatTarget) {
        chatTarget.addEventListener('change', (e) => {
            state.chatTargetId = e.target.value;
            state.conversationId = null; // Resetar ao trocar alvo
        });
    }

    // Carregar agentes/teams ao inicializar
    loadAgentsForChat();
    loadTeamsForChat();

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
        // Keep result box empty until processing starts
        ui.asrResult.innerHTML = '';
    });

    // Toggle number of speakers field when diarization is enabled
    const asrDiarizationCheckbox = document.getElementById('asrEnableDiarization');
    const asrNumSpeakersGroup = document.getElementById('asrNumSpeakersGroup');

    asrDiarizationCheckbox?.addEventListener('change', () => {
        if (asrDiarizationCheckbox.checked) {
            asrNumSpeakersGroup.style.display = 'block';
        } else {
            asrNumSpeakersGroup.style.display = 'none';
        }
    });

    const asrPostprocessCheckbox = document.getElementById('asrEnableLlmPostprocess');
    const asrPostprocessModeGroup = document.getElementById('asrPostprocessModeGroup');

    asrPostprocessCheckbox?.addEventListener('change', () => {
        if (asrPostprocessCheckbox.checked) {
            asrPostprocessModeGroup.style.display = 'block';
        } else {
            asrPostprocessModeGroup.style.display = 'none';
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

        // Clear result box
        ui.ocrResult.innerHTML = '';

        // Calculate estimated time for OCR (typically 8-10 seconds for most files)
        const estimatedTime = 10;

        // Save original button text
        const originalButtonText = ui.ocrButton.innerHTML;

        // Update button to loading state
        ui.ocrButton.disabled = true;
        ui.ocrButton.innerHTML = `
            <span class="btn-spinner"></span>
            Processando... <span id="ocrTimeCounter">0</span>s / ~${estimatedTime}s
        `;

        // Start seconds counter
        let elapsedSeconds = 0;
        const secondsInterval = setInterval(() => {
            elapsedSeconds++;
            const counterElement = document.getElementById('ocrTimeCounter');
            if (counterElement) {
                counterElement.textContent = elapsedSeconds;
            }
        }, 1000);

        window.ocrSecondsInterval = secondsInterval;

        try {
            await runOcr();
        } finally {
            // Stop counter and restore button
            if (window.ocrSecondsInterval) clearInterval(window.ocrSecondsInterval);
            ui.ocrButton.disabled = false;
            ui.ocrButton.innerHTML = originalButtonText;
        }
    });

    ui.ocrFileInput?.addEventListener("change", () => {
        if (!ui.ocrResult) {
            return;
        }
        // Keep result box empty until processing starts
        ui.ocrResult.innerHTML = '';
    });

    ui.insightToggle?.addEventListener("change", () => {
        if (ui.insightStatus && ui.insightToggle) {
            ui.insightStatus.textContent = ui.insightToggle.checked ? "Habilitados" : "Desabilitados";
        }
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

    // TTS Language and Accent selection
    function updateVoiceOptions() {
        const voiceSelect = ui.ttsVoice;
        if (!voiceSelect) return;

        voiceSelect.innerHTML = '';

        if (state.ttsLanguage === 'pt-br') {
            const voices = voiceConfig['pt-br'].voices;
            voices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.value;
                option.textContent = voice.label;
                voiceSelect.appendChild(option);
            });
        } else if (state.ttsLanguage === 'es') {
            const voices = voiceConfig['es'].accents[state.ttsAccent].voices;
            voices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.value;
                option.textContent = voice.label;
                voiceSelect.appendChild(option);
            });
        }
    }

    function setTTSLanguage(lang) {
        state.ttsLanguage = lang;

        // Update button states
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.lang === lang) {
                btn.classList.add('active');
            }
        });

        // Show/hide accent selector
        if (ui.ttsAccentGroup) {
            if (lang === 'es') {
                ui.ttsAccentGroup.style.display = 'block';
            } else {
                ui.ttsAccentGroup.style.display = 'none';
            }
        }

        updateVoiceOptions();
    }

    // Language button click handlers
    setTimeout(() => {
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                setTTSLanguage(btn.dataset.lang);
            });
        });

        // Accent selector change handler
        ui.ttsAccent?.addEventListener('change', (event) => {
            state.ttsAccent = event.target.value;
            updateVoiceOptions();
        });

        // Initialize with default language
        setTTSLanguage('pt-br');
    }, 100);

    // Analytics event listeners
    document.getElementById('analyticsSubmit')?.addEventListener("click", async (event) => {
        event.preventDefault();
        await handleAnalyticsSubmit();
    });

    document.getElementById('analyticsLoadMock')?.addEventListener("click", (event) => {
        event.preventDefault();
        loadMockAnalytics();
    });

    document.getElementById('analyticsClear')?.addEventListener("click", (event) => {
        event.preventDefault();
        clearAnalytics();
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

    // Handle tribunal selector change to show/hide TJSP-specific fields
    const tribunalListSelector = document.getElementById("scrapperListTribunalSelector");
    const tribunalConsultaSelector = document.getElementById("scrapperTribunalSelector");

    function toggleTJSPFields(tribunal) {
        const nomeCompletoGroup = document.getElementById("scrapperListNomeCompletoGroup");
        const maxPaginasGroup = document.getElementById("scrapperListMaxPaginasGroup");
        const maxProcessosGroup = document.getElementById("scrapperListMaxProcessosGroup");

        const isTJSP = tribunal === "tjsp";
        if (nomeCompletoGroup) nomeCompletoGroup.style.display = isTJSP ? "" : "none";
        if (maxPaginasGroup) maxPaginasGroup.style.display = isTJSP ? "" : "none";
        if (maxProcessosGroup) maxProcessosGroup.style.display = isTJSP ? "" : "none";
    }

    tribunalListSelector?.addEventListener("change", (event) => {
        toggleTJSPFields(event.target.value);
    });

    // Initialize field visibility
    if (tribunalListSelector) {
        toggleTJSPFields(tribunalListSelector.value);
    }

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

// DEPRECATED: Old password check function - replaced by new system at top of file
// Kept here for reference only - DO NOT USE
function checkPassword() {
    // Do nothing - new system handles everything
    return;
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

    const useLLM = document.getElementById('diarUseLLM')?.checked || false;
    const numSpeakers = ui.numSpeakers.value ? parseInt(ui.numSpeakers.value) : null;

    setOutput(ui.diarResult, useLLM ? "Transcrevendo áudio..." : "Processando diarização...");
    ui.diarButton.disabled = true;

    try {
        if (useLLM) {
            // LLM mode: transcribe first, then diarize with LLM
            const transcriptFormData = new FormData();
            transcriptFormData.append("file", file);
            transcriptFormData.append("language", "pt");

            const apiBase = resolveApiBase();

            // Step 1: Transcribe
            const asrResponse = await fetch(`${apiBase}/api/v1/asr`, {
                method: "POST",
                headers: buildAuthHeaders(),
                body: transcriptFormData,
            });

            if (!asrResponse.ok) {
                throw new Error(`Transcription failed: ${asrResponse.status}`);
            }

            const asrData = await asrResponse.json();

            if (!asrData.text) {
                throw new Error("No transcription text received");
            }

            // Step 2: Diarize with LLM (reuse existing function)
            await diarizeWithLLMForDiarBox(asrData.text);

        } else {
            // Traditional diarization mode
            const formData = new FormData();
            formData.append("file", file);
            formData.append("use_llm", "false");
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
        }
    } catch (err) {
        console.error("Erro na diarização:", err);
        setOutput(ui.diarResult, `Erro: ${err.message}`);
    } finally {
        ui.diarButton.disabled = false;
    }
}

async function diarizeWithLLMForDiarBox(transcriptText) {
    const resultBox = ui.diarResult;
    if (!resultBox) return;

    // Show loading status
    resultBox.innerHTML = `
        <div class="diarization-status">
            <div class="diarization-status__spinner"></div>
            <span class="diarization-status__text">Separando canais com LLM...</span>
        </div>
    `;

    const base = resolveApiBase();
    const chatUrl = `${base}/api/v1/chat/completions`;

    const diarizationPrompt = `Você é um especialista em análise de transcrições de call center. Separe a transcrição em diálogo entre "Atendente" e "Cliente".

CARACTERÍSTICAS PARA IDENTIFICAÇÃO:

ATENDENTE (Operador/Vendedor):
- Se apresenta com nome e empresa (ex: "Meu nome é Carlos, sou da Claro")
- Faz perguntas sobre dados pessoais (CPF, nome completo, endereço)
- Oferece produtos, planos ou serviços
- Explica condições, valores e benefícios
- Usa linguagem mais formal e técnica
- Faz perguntas procedimentais ("Posso confirmar seus dados?")
- Pede confirmações ("Correto?", "Ok?", "Tudo bem?")
- Agradece e se despede formalmente

CLIENTE:
- Responde às perguntas do atendente
- Geralmente fala menos em cada turno
- Fornece dados pessoais quando solicitado
- Faz perguntas sobre o serviço
- Aceita ou recusa ofertas ("Sim", "Não", "Vamos", "Ok")
- Expressa dúvidas ou problemas pessoais
- Fala de forma mais informal

REGRAS IMPORTANTES:
1. O primeiro "Oi" ou "Alô" geralmente é do CLIENTE atendendo a ligação
2. Quem se apresenta com nome e empresa é SEMPRE o Atendente
3. Respostas curtas como "Sim", "Ok", "Tá" são geralmente do Cliente
4. Mantenha a ordem cronológica exata das falas
5. Cada mudança de speaker deve ser uma nova entrada
6. Corrija pequenos erros de transcrição mas mantenha o sentido

FORMATO DE SAÍDA:
Retorne APENAS um JSON array, sem explicações:
[{"speaker": "Cliente", "text": "..."}, {"speaker": "Atendente", "text": "..."}]

Transcrição para separar:
${transcriptText}`;

    try {
        console.log("[Diarization] Enviando para LLM...");
        console.log("[Diarization] Tamanho do texto:", transcriptText.length, "chars");

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 min timeout

        const response = await fetch(chatUrl, {
            method: "POST",
            headers: buildAuthHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
                model: "paneas-q32b",
                messages: [
                    { role: "user", content: diarizationPrompt }
                ],
                temperature: 0.3,
                max_tokens: 4000,
                stream: true
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        console.log("[Diarization] Stream iniciado, status:", response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error("[Diarization] Erro:", errorText);
            throw new Error(`LLM request failed: ${response.status} - ${errorText}`);
        }

        // Setup streaming conversation display
        resultBox.innerHTML = `
            <div class="conversation-header">
                <div class="conversation-header__title">
                    <svg style="width: 18px; height: 18px; display: inline-block; vertical-align: middle; margin-right: 8px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                    Conversa Diarizada
                    <div class="diarization-status__spinner" style="width: 14px; height: 14px; margin-left: 8px; display: inline-block;"></div>
                </div>
                <div class="conversation-header__count">
                    <span id="messageCountDiar">0 mensagens</span>
                </div>
            </div>
            <div class="conversation-container"></div>
        `;

        const container = resultBox.querySelector('.conversation-container');
        let llmResponse = "";

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n').filter(line => line.trim() !== '');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;

                    try {
                        const parsed = JSON.parse(data);
                        const content = parsed.choices?.[0]?.delta?.content || '';
                        if (content) {
                            llmResponse += content;

                            // Try to parse incrementally and display messages
                            const partialConversation = tryParsePartialJSON(llmResponse);
                            if (partialConversation.length > 0) {
                                displayStreamingConversation(container, partialConversation);
                                document.getElementById('messageCountDiar').textContent = `${partialConversation.length} mensagens`;
                            }
                        }
                    } catch (e) {
                        // Ignore parse errors during streaming
                    }
                }
            }
        }

        console.log("[Diarization] Stream completo");

        // Final parse
        let conversation = [];
        try {
            let cleanedResponse = llmResponse.trim();
            if (cleanedResponse.startsWith('```json')) {
                cleanedResponse = cleanedResponse.replace(/```json\n?/g, '').replace(/```\n?$/g, '');
            } else if (cleanedResponse.startsWith('```')) {
                cleanedResponse = cleanedResponse.replace(/```\n?/g, '');
            }
            conversation = JSON.parse(cleanedResponse);
        } catch (parseError) {
            console.error("[Diarization] Failed to parse final JSON", parseError);
            const lines = llmResponse.split('\n').filter(l => l.trim());
            for (const line of lines) {
                const match = line.match(/^(Atendente|Cliente):\s*(.+)$/);
                if (match) {
                    conversation.push({
                        speaker: match[1],
                        text: match[2].trim()
                    });
                }
            }
        }

        if (conversation.length === 0) {
            throw new Error("Não foi possível extrair a conversa do LLM");
        }

        // Display final conversation for diar box
        displayDiarizedConversationInDiarBox(conversation);

    } catch (err) {
        console.error("[Diarization] Erro:", err);
        setOutput(resultBox, `Erro na diarização: ${err.message}`);
    }
}

function displayDiarizedConversationInDiarBox(conversation) {
    const resultBox = ui.diarResult;
    if (!resultBox) return;

    // Create header with conversation stats
    const header = `
        <div class="conversation-header">
            <div class="conversation-header__title">
                <svg style="width: 18px; height: 18px; display: inline-block; vertical-align: middle; margin-right: 8px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                Conversa Diarizada
            </div>
            <div class="conversation-header__count">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                </svg>
                ${conversation.length} mensagens
            </div>
        </div>
    `;

    // Check if we already have content to avoid flickering
    const existingContainer = resultBox.querySelector('.conversation-container');
    if (!existingContainer) {
        resultBox.innerHTML = header + '<div class="conversation-container"></div>';
    }

    const container = resultBox.querySelector('.conversation-container');
    const existingMessages = container.querySelectorAll('.conversation-message');
    const startIndex = existingMessages.length;

    // Only add new messages
    for (let i = startIndex; i < conversation.length; i++) {
        const message = conversation[i];
        const isAgent = message.speaker.toLowerCase().includes('atendente');
        const messageDiv = document.createElement('div');
        messageDiv.className = `conversation-message conversation-message--${isAgent ? 'agent' : 'client'}`;
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(10px)';

        const speakerIcon = isAgent
            ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';

        messageDiv.innerHTML = `
            <div class="conversation-speaker conversation-speaker--${isAgent ? 'agent' : 'client'}">
                ${speakerIcon}
                ${message.speaker}
            </div>
            <div class="conversation-bubble conversation-bubble--${isAgent ? 'agent' : 'client'}">
                ${message.text}
            </div>
        `;

        container.appendChild(messageDiv);

        // Smooth fade-in animation with minimal delay
        requestAnimationFrame(() => {
            messageDiv.style.transition = 'all 0.3s ease-out';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        });
    }

    // Smooth scroll to bottom
    container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
    });
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

        const lang = state.ttsLanguage === 'pt-br' ? 'pt' : voiceConfig[state.ttsLanguage].language;
        const payload = {
            text: text,
            language: lang,
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
    state.lastHighlightedWordIndex = -1;

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

        const lang = state.ttsLanguage === 'pt-br' ? 'pt' : voiceConfig[state.ttsLanguage].language;
        const payload = {
            text: text,
            language: lang,
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

    // Only update if word changed
    if (state.lastHighlightedWordIndex !== currentWordIndex) {
        // Remove highlight from previous word
        if (state.lastHighlightedWordIndex >= 0) {
            const prevWord = ui.streamingText.querySelector(`[data-index="${state.lastHighlightedWordIndex}"]`);
            if (prevWord) {
                prevWord.classList.remove('highlight');
                prevWord.classList.add('spoken');
            }
        }

        // Highlight current word
        const currentWord = ui.streamingText.querySelector(`[data-index="${currentWordIndex}"]`);
        if (currentWord && !currentWord.classList.contains('spoken')) {
            currentWord.classList.add('highlight');
            currentWord.classList.remove('spoken');
        }

        state.lastHighlightedWordIndex = currentWordIndex;
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

// ========================================
// Analytics Functions
// ========================================

let analyticsJobId = null;
let analyticsPollInterval = null;

// Mock data for demonstration
const MOCK_ANALYTICS_DATA = {
    call_info: {
        duration: 222,  // 3min 42s
        speakers: 2,
        language: "pt-BR",
        date: "2025-11-04 14:30:00"
    },
    sentiment: {
        overall: {
            label: "positive",
            score: 0.85,
            probabilities: {
                positive: 0.85,
                neutral: 0.12,
                negative: 0.03
            }
        },
        per_speaker: {
            "Atendente": {
                label: "positive",
                score: 0.92,
                probabilities: {
                    positive: 0.92,
                    neutral: 0.07,
                    negative: 0.01
                }
            },
            "Cliente": {
                label: "neutral",
                score: 0.78,
                probabilities: {
                    positive: 0.78,
                    neutral: 0.18,
                    negative: 0.04
                },
                evolution: {
                    start: 0.45,
                    end: 0.78
                }
            }
        }
    },
    emotion: {
        overall: {
            label: "satisfação",
            confidence: 0.65
        },
        distribution: {
            "satisfação": 0.65,
            "frustração": 0.20,
            "gratidão": 0.15
        },
        per_speaker: {
            "Atendente": {
                label: "profissionalismo",
                confidence: 0.88,
                emotions: {
                    "profissionalismo": 0.88,
                    "empatia": 0.10,
                    "paciência": 0.02
                }
            },
            "Cliente": {
                label: "satisfação",
                confidence: 0.65,
                emotions: {
                    "frustração": 0.35,
                    "satisfação": 0.45,
                    "gratidão": 0.20
                }
            }
        }
    },
    intent: {
        intents: {
            "suporte": {
                score: 0.89,
                evidence: ["problema", "internet lenta", "ajuda", "suporte técnico"]
            },
            "cancelamento": {
                score: 0.05,
                evidence: []
            },
            "upgrade": {
                score: 0.03,
                evidence: []
            },
            "downgrade": {
                score: 0.02,
                evidence: []
            },
            "venda": {
                score: 0.01,
                evidence: []
            }
        },
        outcome: {
            label: "accepted",
            score: 0.78,
            confidence: 0.82
        }
    },
    compliance: {
        score: 0.75,
        passed: ["greeting", "operator_identification", "offer_presented"],
        failed: ["call_closure"],
        details: [
            {
                check: "greeting",
                passed: true,
                score: 0.95,
                evidence: "Bom dia! Meu nome é Carlos"
            },
            {
                check: "operator_identification",
                passed: true,
                score: 1.0,
                evidence: "Meu nome é Carlos, atendente do suporte técnico"
            },
            {
                check: "offer_presented",
                passed: true,
                score: 0.82,
                evidence: "Vou reiniciar seu modem remotamente"
            },
            {
                check: "call_closure",
                passed: false,
                score: 0.45,
                evidence: "Encerramento abrupto"
            }
        ]
    },
    summary: {
        summary: [
            "Cliente relatou lentidão na internet residencial",
            "Atendente diagnosticou problema no modem e realizou reset remoto",
            "Problema resolvido com sucesso, cliente satisfeito"
        ],
        next_actions: [
            "Acompanhar estabilidade da conexão nas próximas 24h",
            "Considerar upgrade de plano se problema persistir",
            "Melhorar script de encerramento da chamada"
        ],
        confidence: 0.80
    },
    acoustic: {
        duration: 222,
        speech_rate: 145,  // words per minute
        avg_pitch: 180,  // Hz
        silence_ratio: 0.18,
        overlap_ratio: 0.02,
        per_speaker: {
            "Atendente": {
                total_seconds: 135,
                percentage: 60.8,
                turns: 12,
                avg_turn_duration: 11.25,
                speech_rate: 152
            },
            "Cliente": {
                total_seconds: 87,
                percentage: 39.2,
                turns: 11,
                avg_turn_duration: 7.91,
                speech_rate: 138
            }
        }
    },
    timeline: [
        {
            timestamp: 5,
            type: "compliance",
            label: "Saudação detectada",
            confidence: 0.95,
            speaker: "Atendente"
        },
        {
            timestamp: 12,
            type: "compliance",
            label: "Identificação do operador",
            confidence: 1.0,
            speaker: "Atendente"
        },
        {
            timestamp: 45,
            type: "emotion",
            label: "Cliente expressa frustração",
            confidence: 0.75,
            speaker: "Cliente"
        },
        {
            timestamp: 62,
            type: "intent",
            label: "Solicitação de suporte técnico",
            confidence: 0.89,
            speaker: "Cliente"
        },
        {
            timestamp: 80,
            type: "compliance",
            label: "Diagnóstico iniciado",
            confidence: 0.82,
            speaker: "Atendente"
        },
        {
            timestamp: 135,
            type: "action",
            label: "Solução proposta (reset de modem)",
            confidence: 0.88,
            speaker: "Atendente"
        },
        {
            timestamp: 170,
            type: "emotion",
            label: "Cliente demonstra satisfação",
            confidence: 0.85,
            speaker: "Cliente"
        },
        {
            timestamp: 210,
            type: "outcome",
            label: "Confirmação de resolução",
            confidence: 0.78,
            speaker: "Cliente"
        },
        {
            timestamp: 220,
            type: "compliance",
            label: "Encerramento",
            confidence: 0.45,
            speaker: "Atendente"
        }
    ]
};

async function handleAnalyticsSubmit() {
    const audioFile = document.getElementById('analyticsAudioFile')?.files[0];
    const transcriptText = document.getElementById('analyticsTranscript')?.value?.trim();
    const statusEl = document.getElementById('analyticsStatus');

    if (!audioFile && !transcriptText) {
        statusEl && (statusEl.textContent = '⚠️ Forneça um arquivo de áudio OU a transcrição');
        return;
    }

    statusEl && (statusEl.textContent = '🔄 Preparando análise...');

    try {
        let audioUri = null;
        let transcriptUri = null;

        // Upload audio file if provided
        if (audioFile) {
            statusEl && (statusEl.textContent = '📤 Fazendo upload do áudio...');
            const formData = new FormData();
            formData.append('file', audioFile);

            const base = resolveApiBase();
            const authHeaders = buildAuthHeaders();
            const uploadResp = await fetch(`${base}/api/v1/analytics/upload-audio`, {
                method: 'POST',
                headers: authHeaders,
                body: formData
            });

            if (!uploadResp.ok) {
                const error = await uploadResp.json();
                throw new Error(error.detail || 'Falha no upload do áudio');
            }

            const uploadData = await uploadResp.json();
            audioUri = uploadData.path;

            // If audio uploaded, transcribe it first
            statusEl && (statusEl.textContent = '🎤 Transcrevendo áudio...');
            const transcribeResp = await fetch(`${base}/api/v1/asr/transcribe`, {
                method: 'POST',
                headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    audio_path: audioUri,
                    language: 'pt',
                    task: 'transcribe'
                })
            });

            if (!transcribeResp.ok) throw new Error('Falha na transcrição do áudio');
            const transcribeData = await transcribeResp.json();

            // Save transcript to file
            statusEl && (statusEl.textContent = '📝 Salvando transcrição...');
            const timestamp = Date.now();
            const filename = `analytics_transcript_${timestamp}.json`;

            const saveResp = await fetch(`${base}/api/v1/analytics/save-transcript`, {
                method: 'POST',
                headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    filename: filename,
                    data: transcribeData
                })
            });

            if (!saveResp.ok) throw new Error('Falha ao salvar transcrição');
            const saveData = await saveResp.json();
            transcriptUri = saveData.path;

            // Update textarea with transcript
            const transcriptEl = document.getElementById('analyticsTranscript');
            if (transcriptEl && transcribeData.text) {
                transcriptEl.value = transcribeData.text;
            }
        } else if (transcriptText) {
            // No audio, just use provided transcript
            let transcriptData;
            try {
                transcriptData = JSON.parse(transcriptText);
            } catch {
                transcriptData = { text: transcriptText, segments: [] };
            }

            statusEl && (statusEl.textContent = '📝 Salvando transcrição...');
            const timestamp = Date.now();
            const filename = `analytics_transcript_${timestamp}.json`;

            const base = resolveApiBase();
            const saveResp = await fetch(`${base}/api/v1/analytics/save-transcript`, {
                method: 'POST',
                headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    filename: filename,
                    data: transcriptData
                })
            });

            if (!saveResp.ok) throw new Error('Falha ao salvar transcrição');
            const saveData = await saveResp.json();
            transcriptUri = saveData.path;
            audioUri = transcriptUri; // Use transcript path as audio path if no audio
        }

        // Build analysis types array
        const analysisTypes = [];
        if (document.getElementById('analyticsSentiment')?.checked) analysisTypes.push('sentiment');
        if (document.getElementById('analyticsEmotion')?.checked) analysisTypes.push('emotion');
        if (document.getElementById('analyticsIntent')?.checked) analysisTypes.push('intent', 'outcome');
        if (document.getElementById('analyticsCompliance')?.checked) analysisTypes.push('compliance');
        if (document.getElementById('analyticsSummary')?.checked) analysisTypes.push('summary');
        if (document.getElementById('analyticsAcoustic')?.checked) analysisTypes.push('vad_advanced');

        // Submit analytics job
        statusEl && (statusEl.textContent = '🔄 Submetendo job de análise...');
        const base = resolveApiBase();
        const analyticsResp = await fetch(`${base}/api/v1/analytics/speech`, {
            method: 'POST',
            headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                call_id: crypto.randomUUID(),
                audio_uri: audioUri,
                transcript_uri: transcriptUri,
                analysis_types: analysisTypes,
                keywords: []
            })
        });

        if (!analyticsResp.ok) throw new Error('Falha ao submeter job');
        const analyticsData = await analyticsResp.json();
        analyticsJobId = analyticsData.job_id;

        statusEl && (statusEl.textContent = `⏳ Processando... Job ID: ${analyticsJobId}`);

        // Start polling for results
        startAnalyticsPolling();

    } catch (error) {
        console.error('Analytics error:', error);
        statusEl && (statusEl.textContent = `❌ Erro: ${error.message}`);
    }
}

function startAnalyticsPolling() {
    if (analyticsPollInterval) clearInterval(analyticsPollInterval);

    analyticsPollInterval = setInterval(async () => {
        try {
            const base = resolveApiBase();
            const resp = await fetch(`${base}/api/v1/analytics/speech/${analyticsJobId}`, {
                headers: buildAuthHeaders()
            });
            const data = await resp.json();

            const statusEl = document.getElementById('analyticsStatus');

            if (data.status === 'completed') {
                clearInterval(analyticsPollInterval);
                statusEl && (statusEl.textContent = '✅ Análise concluída!');
                displayAnalyticsResults(data.results);
            } else if (data.status === 'failed') {
                clearInterval(analyticsPollInterval);
                statusEl && (statusEl.textContent = `❌ Falha: ${data.error || 'Erro desconhecido'}`);
            } else {
                statusEl && (statusEl.textContent = `⏳ Processando... (${data.status})`);
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000);
}

function displayAnalyticsResults(results) {
    const resultsContainer = document.getElementById('analyticsResults');
    if (!resultsContainer) return;

    resultsContainer.style.display = 'grid';

    // Sentiment
    if (results.sentiment) {
        displaySentiment(results.sentiment);
    }

    // Emotion
    if (results.emotion) {
        displayEmotion(results.emotion);
    }

    // Intent
    if (results.intent) {
        displayIntent(results.intent);
    }

    // Compliance
    if (results.compliance) {
        displayCompliance(results.compliance);
    }

    // Summary
    if (results.summary) {
        displaySummary(results.summary);
    }

    // Timeline
    if (results.timeline) {
        displayTimeline(results.timeline);
    }
}

function displaySentiment(sentiment) {
    const container = document.getElementById('sentimentContent');
    if (!container) return;

    const overall = sentiment.overall;
    const badgeClass = overall.label === 'positive' ? 'positive' :
                       overall.label === 'negative' ? 'negative' : 'neutral';

    let html = `
        <div class="analytics-metric">
            <span class="analytics-metric-label">Sentimento Geral</span>
            <span class="analytics-badge ${badgeClass}">${overall.label}</span>
        </div>
        <div class="analytics-metric">
            <span class="analytics-metric-label">Score</span>
            <span class="analytics-metric-value">${overall.score.toFixed(3)}</span>
        </div>
    `;

    if (overall.probabilities) {
        html += '<div style="margin-top: 1rem;"><strong>Probabilidades:</strong></div>';
        for (const [label, prob] of Object.entries(overall.probabilities)) {
            const percentage = (prob * 100).toFixed(1);
            html += `
                <div class="analytics-metric">
                    <span class="analytics-metric-label">${label}</span>
                    <span class="analytics-metric-value">${percentage}%</span>
                </div>
                <div class="analytics-progress-bar">
                    <div class="analytics-progress-fill" style="width: ${percentage}%"></div>
                </div>
            `;
        }
    }

    // Per speaker
    if (sentiment.per_speaker) {
        html += '<div style="margin-top: 1.5rem;"><strong>Por Speaker:</strong></div>';
        for (const [speaker, data] of Object.entries(sentiment.per_speaker)) {
            const speakerBadgeClass = data.label === 'positive' ? 'positive' :
                                     data.label === 'negative' ? 'negative' : 'neutral';
            html += `
                <div class="analytics-speaker-card">
                    <div class="analytics-speaker-header">
                        <span class="analytics-speaker-name">${speaker}</span>
                        <span class="analytics-badge ${speakerBadgeClass}">${data.label}</span>
                    </div>
                    <div class="analytics-metric">
                        <span class="analytics-metric-label">Score</span>
                        <span class="analytics-metric-value">${data.score.toFixed(3)}</span>
                    </div>
                </div>
            `;
        }
    }

    container.innerHTML = html;
}

function displayEmotion(emotion) {
    const container = document.getElementById('emotionContent');
    if (!container) return;

    const emotionColors = {
        'satisfação': '#43e97b',
        'frustração': '#f5576c',
        'gratidão': '#a8edea',
        'profissionalismo': '#5551ff',
        'empatia': '#ffa726',
        'paciência': '#9c27b0'
    };

    let html = '';

    // Create donut chart if distribution is available
    if (emotion.distribution) {
        const total = Object.values(emotion.distribution).reduce((sum, val) => sum + val, 0);
        let currentAngle = -90; // Start from top

        html += '<div class="emotion-donut-container"><svg class="emotion-donut" viewBox="0 0 200 200">';

        Object.entries(emotion.distribution).forEach(([label, value]) => {
            const percentage = value / total;
            const angle = percentage * 360;
            const endAngle = currentAngle + angle;

            const startX = 100 + 80 * Math.cos((currentAngle * Math.PI) / 180);
            const startY = 100 + 80 * Math.sin((currentAngle * Math.PI) / 180);
            const endX = 100 + 80 * Math.cos((endAngle * Math.PI) / 180);
            const endY = 100 + 80 * Math.sin((endAngle * Math.PI) / 180);

            const largeArcFlag = angle > 180 ? 1 : 0;
            const color = emotionColors[label] || '#5551ff';

            html += `
                <path d="M 100 100 L ${startX} ${startY} A 80 80 0 ${largeArcFlag} 1 ${endX} ${endY} Z"
                      fill="${color}40"
                      stroke="${color}"
                      stroke-width="2"
                      class="emotion-slice" />
            `;

            currentAngle = endAngle;
        });

        // Center hole
        html += '<circle cx="100" cy="100" r="50" fill="rgba(15, 23, 42, 0.95)" />';
        html += '</svg></div>';

        // Legend
        html += '<div class="emotion-legend">';
        Object.entries(emotion.distribution).forEach(([label, value]) => {
            const percentage = ((value / total) * 100).toFixed(0);
            const color = emotionColors[label] || '#5551ff';
            html += `
                <div class="emotion-legend-item">
                    <div class="legend-color" style="background: ${color};"></div>
                    <div class="legend-label">${label.charAt(0).toUpperCase() + label.slice(1)}</div>
                    <div class="legend-value">${percentage}%</div>
                </div>
            `;
        });
        html += '</div>';
    }

    container.innerHTML = html;
}

function displayIntent(intent) {
    const container = document.getElementById('intentContent');
    if (!container) return;

    const intentColors = {
        'suporte': '#43e97b',
        'cancelamento': '#f5576c',
        'upgrade': '#5551ff',
        'downgrade': '#ffa726',
        'venda': '#a8edea'
    };

    let html = '<div class="intent-chart">';

    if (intent.intents) {
        const sortedIntents = Object.entries(intent.intents).sort((a, b) => b[1].score - a[1].score);

        sortedIntents.forEach(([label, data]) => {
            const percentage = (data.score * 100).toFixed(1);
            const color = intentColors[label] || '#5551ff';
            const barWidth = Math.max(percentage, 2); // Minimum 2% for visibility

            html += `
                <div class="intent-bar-item">
                    <div class="intent-bar-label">
                        <span class="intent-name">${label.charAt(0).toUpperCase() + label.slice(1)}</span>
                        <span class="intent-value">${percentage}%</span>
                    </div>
                    <div class="intent-bar-track">
                        <div class="intent-bar-fill" style="width: ${barWidth}%; background: ${color};"></div>
                    </div>
                </div>
            `;
        });
    }

    html += '</div>';

    if (intent.outcome) {
        const outcomeColor = intent.outcome.label === 'accepted' ? '#43e97b' :
                           intent.outcome.label === 'rejected' ? '#f5576c' : '#ffa726';
        html += `
            <div class="outcome-badge" style="background: linear-gradient(135deg, ${outcomeColor}20, ${outcomeColor}10); border-color: ${outcomeColor}50;">
                <div class="outcome-icon" style="background: ${outcomeColor}30; color: ${outcomeColor};">
                    ${intent.outcome.label === 'accepted' ? '✓' : intent.outcome.label === 'rejected' ? '✗' : '⏱'}
                </div>
                <div class="outcome-info">
                    <div class="outcome-label">Resultado</div>
                    <div class="outcome-status">${intent.outcome.label === 'accepted' ? 'Aceito' :
                                                   intent.outcome.label === 'rejected' ? 'Rejeitado' : 'Pendente'}</div>
                </div>
                <div class="outcome-confidence">${(intent.outcome.score * 100).toFixed(0)}%</div>
            </div>
        `;
    }

    container.innerHTML = html;
}

function displayCompliance(compliance) {
    const container = document.getElementById('complianceContent');
    if (!container) return;

    const scorePercentage = (compliance.score * 100).toFixed(0);
    const circumference = 2 * Math.PI * 70; // radius = 70
    const offset = circumference - (scorePercentage / 100) * circumference;
    const strokeColor = scorePercentage >= 75 ? '#43e97b' : scorePercentage >= 50 ? '#ffa726' : '#f5576c';

    let html = `
        <div class="compliance-gauge-container">
            <svg class="compliance-gauge" viewBox="0 0 160 160">
                <circle class="gauge-bg" cx="80" cy="80" r="70" />
                <circle class="gauge-progress" cx="80" cy="80" r="70"
                        stroke="${strokeColor}"
                        stroke-dasharray="${circumference}"
                        stroke-dashoffset="${offset}" />
            </svg>
            <div class="gauge-text">
                <div class="gauge-value">${scorePercentage}%</div>
                <div class="gauge-label">Compliance</div>
            </div>
        </div>
        <div class="compliance-checks">
    `;

    if (compliance.details && compliance.details.length > 0) {
        compliance.details.forEach(check => {
            const checkNames = {
                'greeting': 'Saudação',
                'operator_identification': 'Identificação',
                'offer_presented': 'Oferta',
                'call_closure': 'Encerramento'
            };
            const checkName = checkNames[check.check] || check.check;
            const checkScore = (check.score * 100).toFixed(0);
            const icon = check.passed ? '✓' : '✗';
            const statusClass = check.passed ? 'check-passed' : 'check-failed';

            html += `
                <div class="compliance-check-item ${statusClass}">
                    <div class="check-icon">${icon}</div>
                    <div class="check-content">
                        <div class="check-name">${checkName}</div>
                        ${check.evidence ? `<div class="check-evidence">"${check.evidence}"</div>` : ''}
                    </div>
                    <div class="check-score">${checkScore}%</div>
                </div>
            `;
        });
    }

    html += '</div>';

    container.innerHTML = html;
}

function displaySummary(summary) {
    const container = document.getElementById('summaryContent');
    if (!container) return;

    let html = '';

    if (summary.summary && summary.summary.length > 0) {
        html += '<div style="margin-bottom: 1rem;"><strong>Resumo:</strong></div>';
        summary.summary.forEach(item => {
            html += `<div style="padding: 0.5rem; margin-bottom: 0.5rem; background: rgba(255,255,255,0.05); border-radius: 8px;">• ${item}</div>`;
        });
    }

    if (summary.next_actions && summary.next_actions.length > 0) {
        html += '<div style="margin-top: 1rem; margin-bottom: 1rem;"><strong>Próximos Passos:</strong></div>';
        summary.next_actions.forEach(item => {
            html += `<div style="padding: 0.5rem; margin-bottom: 0.5rem; background: rgba(85,81,255,0.08); border: 1px solid rgba(85,81,255,0.25); border-radius: 8px;">→ ${item}</div>`;
        });
    }

    container.innerHTML = html || '<p style="color: rgba(255,255,255,0.5);">Nenhum resumo disponível</p>';
}

function displayTimeline(timeline) {
    const container = document.getElementById('timelineContent');
    if (!container) return;

    if (!timeline || timeline.length === 0) {
        container.innerHTML = '<p style="color: rgba(255,255,255,0.5);">Nenhum evento na timeline</p>';
        return;
    }

    let html = '';
    timeline.forEach(item => {
        const time = item.timestamp !== null ? `${item.timestamp.toFixed(1)}s` : 'N/A';
        const confidence = (item.confidence * 100).toFixed(0);
        html += `
            <div class="analytics-timeline-item">
                <div class="analytics-timeline-time">${time}</div>
                <div class="analytics-timeline-content">
                    <div class="analytics-timeline-label">${item.label}</div>
                    <div class="analytics-timeline-type">${item.type} · ${confidence}%</div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function clearAnalytics() {
    const audioFileEl = document.getElementById('analyticsAudioFile');
    const transcriptEl = document.getElementById('analyticsTranscript');
    const statusEl = document.getElementById('analyticsStatus');
    const resultsEl = document.getElementById('analyticsResults');
    const kpiSection = document.getElementById('analyticsKPISection');

    if (audioFileEl) audioFileEl.value = '';
    if (transcriptEl) transcriptEl.value = '';
    if (statusEl) statusEl.textContent = '';
    if (resultsEl) resultsEl.style.display = 'none';
    if (kpiSection) kpiSection.style.display = 'none';

    if (analyticsPollInterval) {
        clearInterval(analyticsPollInterval);
        analyticsPollInterval = null;
    }
}

function loadMockAnalytics() {
    const data = MOCK_ANALYTICS_DATA;

    // Show KPI Section
    const kpiSection = document.getElementById('analyticsKPISection');
    if (kpiSection) {
        kpiSection.style.display = 'block';

        // Update KPI values
        const durationEl = document.getElementById('kpiDuration');
        const sentimentEl = document.getElementById('kpiSentiment');
        const complianceEl = document.getElementById('kpiCompliance');
        const intentEl = document.getElementById('kpiIntent');

        if (durationEl) {
            const minutes = Math.floor(data.call_info.duration / 60);
            const seconds = data.call_info.duration % 60;
            durationEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }

        if (sentimentEl) {
            const label = data.sentiment.overall.label === 'positive' ? 'Positivo' :
                         data.sentiment.overall.label === 'negative' ? 'Negativo' : 'Neutro';
            const score = Math.round(data.sentiment.overall.score * 100);
            sentimentEl.textContent = `${label} (${score}%)`;
        }

        if (complianceEl) {
            const score = Math.round(data.compliance.score * 100);
            complianceEl.textContent = `${score}%`;
        }

        if (intentEl) {
            // Find highest intent
            let highestIntent = '';
            let highestScore = 0;
            Object.entries(data.intent.intents).forEach(([intent, info]) => {
                if (info.score > highestScore) {
                    highestScore = info.score;
                    highestIntent = intent;
                }
            });
            const intentLabel = highestIntent.charAt(0).toUpperCase() + highestIntent.slice(1);
            intentEl.textContent = intentLabel;
        }
    }

    // Show results section
    const resultsEl = document.getElementById('analyticsResults');
    if (resultsEl) {
        resultsEl.style.display = 'grid';
    }

    // Display all analytics
    if (data.sentiment) displaySentiment(data.sentiment);
    if (data.emotion) displayEmotion(data.emotion);
    if (data.intent) displayIntent(data.intent);
    if (data.compliance) displayCompliance(data.compliance);
    if (data.summary) displaySummary(data.summary);
    if (data.acoustic) displayAcoustic(data.acoustic);
    if (data.acoustic && data.acoustic.per_speaker) displaySpeakers(data.acoustic.per_speaker);
    if (data.timeline) displayTimeline(data.timeline);

    // Update status
    const statusEl = document.getElementById('analyticsStatus');
    if (statusEl) {
        statusEl.textContent = '✅ Exemplo de análise carregado com sucesso!';
        statusEl.style.color = '#43e97b';
    }
}

function displayAcoustic(acoustic) {
    const container = document.getElementById('acousticContent');
    if (!container || !acoustic) return;

    const minutes = Math.floor(acoustic.duration / 60);
    const seconds = acoustic.duration % 60;
    const durationText = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    const silencePercent = Math.round(acoustic.silence_ratio * 100);
    const overlapPercent = Math.round(acoustic.overlap_ratio * 100);

    container.innerHTML = `
        <div class="analytics-metric">
            <span class="analytics-metric-label">Duração Total</span>
            <span class="analytics-metric-value">${durationText}</span>
        </div>
        <div class="analytics-metric">
            <span class="analytics-metric-label">Taxa de Fala</span>
            <span class="analytics-metric-value">${acoustic.speech_rate} palavras/min</span>
        </div>
        <div class="analytics-metric">
            <span class="analytics-metric-label">Pitch Médio</span>
            <span class="analytics-metric-value">${acoustic.avg_pitch} Hz</span>
        </div>
        <div class="analytics-metric">
            <span class="analytics-metric-label">Silêncio</span>
            <span class="analytics-metric-value">${silencePercent}%</span>
        </div>
        <div class="analytics-metric">
            <span class="analytics-metric-label">Sobreposição de Fala</span>
            <span class="analytics-metric-value">${overlapPercent}%</span>
        </div>
    `;
}

function displaySpeakers(speakers) {
    const container = document.getElementById('speakerContent');
    if (!container || !speakers) return;

    let html = '';

    Object.entries(speakers).forEach(([speaker, data]) => {
        const minutes = Math.floor(data.total_seconds / 60);
        const seconds = Math.round(data.total_seconds % 60);
        const durationText = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        const percentage = Math.round(data.percentage);

        html += `
            <div class="analytics-speaker-card">
                <div class="analytics-speaker-header">
                    <span class="analytics-speaker-name">${speaker}</span>
                    <span class="analytics-badge">${percentage}%</span>
                </div>
                <div class="analytics-progress-bar">
                    <div class="analytics-progress-fill" style="width: ${percentage}%"></div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; margin-top: 0.75rem;">
                    <div class="analytics-metric">
                        <span class="analytics-metric-label">Tempo</span>
                        <span class="analytics-metric-value">${durationText}</span>
                    </div>
                    <div class="analytics-metric">
                        <span class="analytics-metric-label">Turnos</span>
                        <span class="analytics-metric-value">${data.turns}</span>
                    </div>
                    <div class="analytics-metric">
                        <span class="analytics-metric-label">Duração Média</span>
                        <span class="analytics-metric-value">${data.avg_turn_duration.toFixed(1)}s</span>
                    </div>
                    <div class="analytics-metric">
                        <span class="analytics-metric-label">Palavras/min</span>
                        <span class="analytics-metric-value">${data.speech_rate}</span>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function bootstrap() {
    checkPassword();
    ensureChunkSize();
    resetSessionState();
    renderChat();
    bindEvents();
    initTabs();
    setupFileDisplays();
    loadAuthTokenFromStorage();

    // Bind diarization
    if (ui.diarButton) {
        ui.diarButton.addEventListener('click', handleDiarization);
    }

    // Initialize Agents Module
    if (typeof window.initializeAgentsModule === 'function') {
        window.initializeAgentsModule();
    }
}

function loadAuthTokenFromStorage() {
    // Try to load API key from sessionStorage (set by API Keys panel)
    const adminToken = sessionStorage.getItem('adminToken');
    if (adminToken && ui.authToken) {
        ui.authToken.value = adminToken;
        console.log('[Auth] Loaded API key from sessionStorage');
    }
}

// ============================================================================
// Internationalization (i18n)
// ============================================================================

const translations = {
    'pt-br': {
        // Modal
        'modal-title': 'Acesso Restrito',
        'modal-description': 'Digite a senha para acessar o Paneas Studio',
        'modal-placeholder': 'Digite a senha',
        'modal-button': 'Entrar',
        'modal-error': 'Senha incorreta! Tente novamente.',

        // Navbar
        'navbar-components': 'Componentes',
        'navbar-playground': 'Playground',
        'navbar-api-keys': 'API Keys',
        'navbar-logout-title': 'Sair',

        // Hero
        'hero-title': 'Biblioteca de Componentes de IA',
        'hero-subtitle': 'Ferramentas profissionais de IA para desenvolvimento rápido',

        // Tabs
        'tab-realtime': 'Tempo Real',
        'tab-transcription': 'Transcrição',
        'tab-diar': 'Diarização',
        'tab-analytics': 'Analytics',
        'tab-agents': 'Agents',
        'tab-ocr': 'OCR',
        'tab-tts': 'TTS',
        'tab-scrapper': 'Processos',
        'tab-chat': 'Chat',

        // Common buttons
        'btn-send': 'Enviar',
        'btn-clear': 'Limpar',
        'btn-download': 'Baixar',
        'btn-stop': 'Parar',
        'btn-execute': 'Executar',
        'btn-upload': 'Upload',
        'btn-cancel': 'Cancelar',

        // ASR
        'asr-title': 'Reconhecimento de Fala (ASR)',
        'asr-subtitle': 'Transcreva áudio para texto em tempo real',
        'asr-start': 'Iniciar Gravação',
        'asr-stop': 'Parar Gravação',
        'asr-language': 'Idioma',
        'asr-model': 'Modelo',

        // Diarization
        'diar-title': 'Diarização de Áudio',
        'diar-description': 'Identifique e separe diferentes falantes',
        'diar-upload': 'Clique ou arraste um arquivo de áudio',
        'diar-button': 'Executar Diarização',

        // OCR
        'ocr-title': 'Reconhecimento de Texto (OCR)',
        'ocr-description': 'Extraia texto de imagens ou PDFs',
        'ocr-upload': 'Clique ou arraste uma imagem ou PDF',
        'ocr-button': 'Executar OCR',
        'ocr-filetypes': 'PNG, JPG, JPEG, GIF, PDF',

        // TTS
        'tts-title': 'Síntese de Voz (TTS)',
        'tts-description': 'Clone de voz com Paneas-XXTS-v2',
        'tts-language': 'Idioma',
        'tts-accent': 'Sotaque',
        'tts-voice': 'Voz',
        'tts-text': 'Texto para Sintetizar',
        'tts-placeholder': 'Digite o texto que deseja converter em áudio...',
        'tts-maxchars': 'Máximo 500 caracteres',
        'tts-button': 'Sintetizar Áudio',
        'tts-streaming': 'Modo Streaming',

        // Chat
        'chat-title': 'Chat com LLM',
        'chat-model': 'Modelo Direto',
        'chat-agent': 'Agente',
        'chat-team': 'Team',
        'chat-select': 'Selecione:',
        'chat-history': 'Manter Histórico',
        'chat-system': 'System Prompt (opcional):',
        'chat-placeholder': 'Digite sua mensagem...',

        // Scrapper
        'scrapper-title': 'Consulta de Processo (TJSP)',
        'scrapper-description': 'Busque processos específicos',
        'scrapper-number': 'Número do Processo',
        'scrapper-party': 'Nome da Parte',
        'scrapper-document': 'Documento da Parte',
        'scrapper-lawyer': 'Nome do Advogado',
        'scrapper-oab': 'Número da OAB',
        'scrapper-court': 'Foro',
        'scrapper-search': 'Consultar',
        'scrapper-list': 'Listagem de Processos',

        // Analytics
        'analytics-title': 'Analytics de Conversação',
        'analytics-description': 'Análise de sentimentos e insights',
        'analytics-run': 'Executar Analytics',
        'analytics-load-mock': 'Ver Exemplo',
        'analytics-kpi-duration': 'Duração',
        'analytics-kpi-sentiment': 'Sentimento Geral',
        'analytics-kpi-compliance': 'Compliance',
        'analytics-kpi-intent': 'Intento Principal',
        'analytics-acoustic-title': 'Métricas Acústicas',
        'analytics-speakers-title': 'Distribuição por Speaker',

        // Hero Section
        'hero-badge': 'Stack de IA Completa',
        'hero-main-title': 'Ecossistema',
        'hero-btn-try': 'Experimentar agora',
        'hero-btn-components': 'Ver componentes',
        'hero-btn-docs': 'Documentação',
        'hero-stat-components': 'Componentes de IA',
        'hero-stat-private': 'Local & Privado',
        'hero-stat-latency': 'Baixa Latência',
        'hero-stat-lgpd': 'Conforme LGPD',
        'hero-stat-gpu': 'GPU Acelerado',
        'hero-stat-active': 'Sempre Ativo',

        // Components Library
        'lib-title': 'Biblioteca',
        'lib-subtitle': 'Componentes modulares e reutilizáveis para construir soluções de IA',
        'lib-try-btn': 'Experimentar →',

        // Product Cards
        'card-realtime-title': 'Real-time Transcription',
        'card-realtime-desc': 'Componente de transcrição em tempo real com diarização. Integre streaming de áudio em sua aplicação.',
        'card-realtime-feat1': 'Streaming de áudio em tempo real',
        'card-realtime-feat2': 'Identificação de speakers (diarização)',
        'card-realtime-feat3': 'Insights gerados por LLM',
        'card-realtime-feat4': 'Suporte a múltiplos idiomas',

        'card-transcription-title': 'Audio Transcription',
        'card-transcription-desc': 'Componente de transcrição em lote para múltiplos formatos de áudio. API RESTful pronta para uso.',
        'card-transcription-feat1': 'Upload de múltiplos formatos',
        'card-transcription-feat2': 'Transcrição em lote',
        'card-transcription-feat3': 'Processamento rápido',

        'card-ocr-title': 'OCR Intelligence',
        'card-ocr-desc': 'Componente de OCR para extração de texto de documentos. Integre reconhecimento de caracteres facilmente.',
        'card-ocr-feat1': 'Suporte a múltiplos idiomas',
        'card-ocr-feat2': 'PDFs e imagens',
        'card-ocr-feat3': 'Alta precisão',

        'card-scrapper-title': 'Legal Process Tracker',
        'card-scrapper-desc': 'Componente de consulta jurídica automatizada. Integre busca e monitoramento de processos TJSP.',
        'card-scrapper-feat1': 'Busca por CPF/CNPJ',
        'card-scrapper-feat2': 'Monitoramento automatizado',
        'card-scrapper-feat3': 'Exportação de dados',

        'card-chat-title': 'Chat LLM',
        'card-chat-desc': 'Componente de LLM conversacional com function calling. Adicione inteligência às suas aplicações.',
        'card-chat-feat1': 'Modelo Paneas-32B INT4',
        'card-chat-feat2': 'Function calling',
        'card-chat-feat3': 'Histórico persistente',

        'card-tts-title': 'Voice Synthesis',
        'card-tts-desc': 'Componente de síntese de voz neural. Integre clonagem e geração de voz em suas aplicações.',
        'card-tts-feat1': 'Múltiplas vozes',
        'card-tts-feat2': 'Streaming em tempo real',
        'card-tts-feat3': 'Qualidade de estúdio',

        'card-analytics-title': 'Speech Analytics',
        'card-analytics-desc': 'Componente de análise de sentimentos e emoções. Extraia insights de conversas com NLP avançado.',
        'card-analytics-feat1': 'Análise de sentimentos (positivo/negativo/neutro)',
        'card-analytics-feat2': 'Detecção de emoções',
        'card-analytics-feat3': 'Identificação de intenções',
        'card-analytics-feat4': 'Compliance checks automatizados',

        'card-agents-title': 'AI Agents Framework',
        'card-agents-desc': 'Framework completo para criação de agentes de IA com ferramentas, conhecimento e templates. Suporte a multi-agente com Teams hierárquicos. Construa assistentes inteligentes personalizados e coordenados.',
        'card-agents-feat1': 'Criação e gerenciamento de agentes',
        'card-agents-feat2': 'Teams multi-agente com hierarquia',
        'card-agents-feat3': 'Tools customizáveis (function calling)',
        'card-agents-feat4': 'Knowledge bases com RAG',
        'card-agents-feat5': 'Templates reutilizáveis',
        'card-agents-feat6': 'Execução e validação de agentes/teams'
    },
    'es': {
        // Modal
        'modal-title': 'Acceso Restringido',
        'modal-description': 'Ingrese la contraseña para acceder a Paneas Studio',
        'modal-placeholder': 'Ingrese la contraseña',
        'modal-button': 'Entrar',
        'modal-error': '¡Contraseña incorrecta! Inténtelo de nuevo.',

        // Navbar
        'navbar-components': 'Componentes',
        'navbar-playground': 'Playground',
        'navbar-api-keys': 'Claves API',
        'navbar-logout-title': 'Salir',

        // Hero
        'hero-title': 'Biblioteca de Componentes de IA',
        'hero-subtitle': 'Herramientas profesionales de IA para desarrollo rápido',

        // Tabs
        'tab-realtime': 'Tiempo Real',
        'tab-transcription': 'Transcripción',
        'tab-diar': 'Diarización',
        'tab-analytics': 'Analytics',
        'tab-agents': 'Agentes',
        'tab-ocr': 'OCR',
        'tab-tts': 'TTS',
        'tab-scrapper': 'Procesos',
        'tab-chat': 'Chat',

        // Common buttons
        'btn-send': 'Enviar',
        'btn-clear': 'Limpiar',
        'btn-download': 'Descargar',
        'btn-stop': 'Detener',
        'btn-execute': 'Ejecutar',
        'btn-upload': 'Subir',
        'btn-cancel': 'Cancelar',

        // ASR
        'asr-title': 'Reconocimiento de Voz (ASR)',
        'asr-subtitle': 'Transcriba audio a texto en tiempo real',
        'asr-start': 'Iniciar Grabación',
        'asr-stop': 'Detener Grabación',
        'asr-language': 'Idioma',
        'asr-model': 'Modelo',

        // Diarization
        'diar-title': 'Diarización de Audio',
        'diar-description': 'Identifique y separe diferentes hablantes',
        'diar-upload': 'Haga clic o arrastre un archivo de audio',
        'diar-button': 'Ejecutar Diarización',

        // OCR
        'ocr-title': 'Reconocimiento de Texto (OCR)',
        'ocr-description': 'Extraiga texto de imágenes o PDFs',
        'ocr-upload': 'Haga clic o arrastre una imagen o PDF',
        'ocr-button': 'Ejecutar OCR',
        'ocr-filetypes': 'PNG, JPG, JPEG, GIF, PDF',

        // TTS
        'tts-title': 'Síntesis de Voz (TTS)',
        'tts-description': 'Clonación de voz con Paneas-XXTS-v2',
        'tts-language': 'Idioma',
        'tts-accent': 'Acento',
        'tts-voice': 'Voz',
        'tts-text': 'Texto para Sintetizar',
        'tts-placeholder': 'Escriba el texto que desea convertir en audio...',
        'tts-maxchars': 'Máximo 500 caracteres',
        'tts-button': 'Sintetizar Audio',
        'tts-streaming': 'Modo Streaming',

        // Chat
        'chat-title': 'Chat con LLM',
        'chat-model': 'Modelo Directo',
        'chat-agent': 'Agente',
        'chat-team': 'Equipo',
        'chat-select': 'Seleccione:',
        'chat-history': 'Mantener Historial',
        'chat-system': 'System Prompt (opcional):',
        'chat-placeholder': 'Escriba su mensaje...',

        // Scrapper
        'scrapper-title': 'Consulta de Proceso (TJSP)',
        'scrapper-description': 'Busque procesos específicos',
        'scrapper-number': 'Número de Proceso',
        'scrapper-party': 'Nombre de la Parte',
        'scrapper-document': 'Documento de la Parte',
        'scrapper-lawyer': 'Nombre del Abogado',
        'scrapper-oab': 'Número de OAB',
        'scrapper-court': 'Tribunal',
        'scrapper-search': 'Consultar',
        'scrapper-list': 'Listado de Procesos',

        // Analytics
        'analytics-title': 'Analytics de Conversación',
        'analytics-description': 'Análisis de sentimientos e insights',
        'analytics-run': 'Ejecutar Analytics',
        'analytics-load-mock': 'Ver Ejemplo',
        'analytics-kpi-duration': 'Duración',
        'analytics-kpi-sentiment': 'Sentimiento General',
        'analytics-kpi-compliance': 'Cumplimiento',
        'analytics-kpi-intent': 'Intención Principal',
        'analytics-acoustic-title': 'Métricas Acústicas',
        'analytics-speakers-title': 'Distribución por Hablante',

        // Hero Section
        'hero-badge': 'Stack de IA Completo',
        'hero-main-title': 'Ecosistema',
        'hero-btn-try': 'Probar ahora',
        'hero-btn-components': 'Ver componentes',
        'hero-btn-docs': 'Documentación',
        'hero-stat-components': 'Componentes de IA',
        'hero-stat-private': 'Local y Privado',
        'hero-stat-latency': 'Baja Latencia',
        'hero-stat-lgpd': 'Conforme LGPD',
        'hero-stat-gpu': 'Acelerado por GPU',
        'hero-stat-active': 'Siempre Activo',

        // Components Library
        'lib-title': 'Biblioteca',
        'lib-subtitle': 'Componentes modulares y reutilizables para construir soluciones de IA',
        'lib-try-btn': 'Probar →',

        // Product Cards
        'card-realtime-title': 'Transcripción en Tiempo Real',
        'card-realtime-desc': 'Componente de transcripción en tiempo real con diarización. Integre streaming de audio en su aplicación.',
        'card-realtime-feat1': 'Streaming de audio en tiempo real',
        'card-realtime-feat2': 'Identificación de hablantes (diarización)',
        'card-realtime-feat3': 'Insights generados por LLM',
        'card-realtime-feat4': 'Soporte para múltiples idiomas',

        'card-transcription-title': 'Transcripción de Audio',
        'card-transcription-desc': 'Componente de transcripción por lotes para múltiples formatos de audio. API RESTful lista para usar.',
        'card-transcription-feat1': 'Carga de múltiples formatos',
        'card-transcription-feat2': 'Transcripción por lotes',
        'card-transcription-feat3': 'Procesamiento rápido',

        'card-ocr-title': 'OCR Intelligence',
        'card-ocr-desc': 'Componente OCR para extracción de texto de documentos. Integre reconocimiento de caracteres fácilmente.',
        'card-ocr-feat1': 'Soporte para múltiples idiomas',
        'card-ocr-feat2': 'PDFs e imágenes',
        'card-ocr-feat3': 'Alta precisión',

        'card-scrapper-title': 'Rastreador de Procesos Legales',
        'card-scrapper-desc': 'Componente de consulta jurídica automatizada. Integre búsqueda y monitoreo de procesos TJSP.',
        'card-scrapper-feat1': 'Búsqueda por CPF/CNPJ',
        'card-scrapper-feat2': 'Monitoreo automatizado',
        'card-scrapper-feat3': 'Exportación de datos',

        'card-chat-title': 'Chat LLM',
        'card-chat-desc': 'Componente LLM conversacional con function calling. Agregue inteligencia a sus aplicaciones.',
        'card-chat-feat1': 'Modelo Paneas-32B INT4',
        'card-chat-feat2': 'Function calling',
        'card-chat-feat3': 'Historial persistente',

        'card-tts-title': 'Síntesis de Voz',
        'card-tts-desc': 'Componente de síntesis de voz neural. Integre clonación y generación de voz en sus aplicaciones.',
        'card-tts-feat1': 'Múltiples voces',
        'card-tts-feat2': 'Streaming en tiempo real',
        'card-tts-feat3': 'Calidad de estudio',

        'card-analytics-title': 'Speech Analytics',
        'card-analytics-desc': 'Componente de análisis de sentimientos y emociones. Extraiga insights de conversaciones con NLP avanzado.',
        'card-analytics-feat1': 'Análisis de sentimientos (positivo/negativo/neutro)',
        'card-analytics-feat2': 'Detección de emociones',
        'card-analytics-feat3': 'Identificación de intenciones',
        'card-analytics-feat4': 'Verificaciones de cumplimiento automatizadas',

        'card-agents-title': 'Framework de Agentes IA',
        'card-agents-desc': 'Framework completo para creación de agentes de IA con herramientas, conocimiento y plantillas. Soporte para multi-agente con Teams jerárquicos. Construya asistentes inteligentes personalizados y coordinados.',
        'card-agents-feat1': 'Creación y gestión de agentes',
        'card-agents-feat2': 'Teams multi-agente con jerarquía',
        'card-agents-feat3': 'Tools personalizables (function calling)',
        'card-agents-feat4': 'Bases de conocimiento con RAG',
        'card-agents-feat5': 'Plantillas reutilizables',
        'card-agents-feat6': 'Ejecución y validación de agentes/teams'
    }
};

let currentPageLanguage = localStorage.getItem('pageLanguage') || 'pt-br';

function setPageLanguage(lang) {
    currentPageLanguage = lang;
    localStorage.setItem('pageLanguage', lang);

    // Update button states
    document.querySelectorAll('.language-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.language === lang) {
            btn.classList.add('active');
        }
    });

    // Apply translations
    const t = translations[lang];
    if (!t) return;

    // Navbar
    const navComponents = document.querySelector('a[href="#components"]');
    if (navComponents) navComponents.textContent = t['navbar-components'];

    const navPlayground = document.querySelector('a[href="#playground"]');
    if (navPlayground) navPlayground.textContent = t['navbar-playground'];

    const logoutBtn = document.getElementById('logoutButton');
    if (logoutBtn) logoutBtn.setAttribute('title', t['navbar-logout-title']);

    // Hero subtitle
    const heroSubtitle = document.querySelector('.hero__subtitle');
    if (heroSubtitle) heroSubtitle.textContent = t['hero-subtitle'];

    // API Keys button
    const apiKeysBtn = document.getElementById('apiKeysNavBtn');
    if (apiKeysBtn) {
        const textNode = Array.from(apiKeysBtn.childNodes).find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
        if (textNode) textNode.textContent = ' ' + t['navbar-api-keys'];
    }

    // Tabs - preserve icons, only update text in span
    document.querySelectorAll('.playground__nav-item').forEach(tab => {
        const tabId = tab.dataset.tab;
        if (tabId && t[`tab-${tabId}`]) {
            const span = tab.querySelector('span');
            if (span) {
                span.textContent = t[`tab-${tabId}`];
            }
        }
    });

    // Modal de senha
    const modalTitle = document.querySelector('.modal__title');
    if (modalTitle) modalTitle.textContent = t['modal-title'];

    const modalDesc = document.querySelector('.modal__description');
    if (modalDesc) modalDesc.textContent = t['modal-description'];

    const passwordInput = document.getElementById('passwordInput');
    if (passwordInput) passwordInput.setAttribute('placeholder', t['modal-placeholder']);

    const modalButton = document.querySelector('.modal__content button[type="submit"]');
    if (modalButton) {
        const btnText = modalButton.childNodes[modalButton.childNodes.length - 1];
        if (btnText && btnText.nodeType === Node.TEXT_NODE) {
            btnText.textContent = t['modal-button'];
        }
    }

    const passwordError = document.getElementById('passwordError');
    if (passwordError) {
        const errorText = passwordError.childNodes[passwordError.childNodes.length - 1];
        if (errorText && errorText.nodeType === Node.TEXT_NODE) {
            errorText.textContent = t['modal-error'];
        }
    }

    // Helper function to translate by selector
    const translate = (selector, key, attr = 'textContent') => {
        const el = document.querySelector(selector);
        if (el && t[key]) {
            if (attr === 'placeholder') {
                el.setAttribute('placeholder', t[key]);
            } else if (attr === 'title') {
                el.setAttribute('title', t[key]);
            } else {
                el[attr] = t[key];
            }
        }
    };

    // TTS Tab
    translate('[data-content="tts"] .playground-card__title', 'tts-title');
    translate('[data-content="tts"] .card__description', 'tts-description');
    translate('label[for="ttsVoice"]', 'tts-voice');
    translate('label[for="ttsText"]', 'tts-text');
    translate('#ttsText', 'tts-placeholder', 'placeholder');
    translate('[data-content="tts"] small.text-muted', 'tts-maxchars');

    // TTS Buttons - preserve SVG icons
    const ttsButton = document.getElementById('ttsButton');
    if (ttsButton && t['tts-button']) {
        const textNodes = Array.from(ttsButton.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
        textNodes.forEach(n => n.remove());
        ttsButton.appendChild(document.createTextNode(t['tts-button']));
    }

    const ttsStreamButton = document.getElementById('ttsStreamButton');
    if (ttsStreamButton && t['tts-streaming']) {
        const textNodes = Array.from(ttsStreamButton.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
        textNodes.forEach(n => n.remove());
        ttsStreamButton.appendChild(document.createTextNode(t['tts-streaming']));
    }

    // OCR Tab
    translate('[data-content="ocr"] .playground-card__title', 'ocr-title');
    translate('[data-content="ocr"] .card__description', 'ocr-description');

    const ocrButton = document.getElementById('ocrButton');
    if (ocrButton && t['ocr-button']) {
        const textNodes = Array.from(ocrButton.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
        textNodes.forEach(n => n.remove());
        ocrButton.appendChild(document.createTextNode(t['ocr-button']));
    }

    // Diarization Tab
    translate('[data-content="diarization"] .playground-card__title', 'diar-title');
    translate('[data-content="diarization"] .card__description', 'diar-description');

    const diarButton = document.getElementById('diarButton');
    if (diarButton && t['diar-button']) {
        const textNodes = Array.from(diarButton.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
        textNodes.forEach(n => n.remove());
        diarButton.appendChild(document.createTextNode(t['diar-button']));
    }

    // Chat Tab
    translate('[data-content="chat"] .playground-card__title', 'chat-title');
    translate('[data-content="chat"] textarea', 'chat-placeholder', 'placeholder');

    // Analytics Tab
    translate('[data-content="analytics"] .playground-card__title', 'analytics-title');
    translate('[data-content="analytics"] .card__description', 'analytics-description');

    // Hero Section
    translate('.hero__badge span:last-child', 'hero-badge');

    const heroTitleEl = document.querySelector('.hero__title');
    if (heroTitleEl && t['hero-main-title']) {
        // Keep the gradient-text span, only update text before it
        const gradientSpan = heroTitleEl.querySelector('.gradient-text');
        if (gradientSpan) {
            const textNodes = Array.from(heroTitleEl.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
            textNodes.forEach(n => n.remove());
            heroTitleEl.insertBefore(document.createTextNode(t['hero-main-title'] + ' '), gradientSpan);
        }
    }

    const heroBtnTry = document.querySelector('.btn.btn--hero');
    if (heroBtnTry && t['hero-btn-try']) {
        const textNodes = Array.from(heroBtnTry.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
        textNodes.forEach(n => n.remove());
        heroBtnTry.appendChild(document.createTextNode(t['hero-btn-try']));
    }

    const heroBtnComponents = document.querySelector('.btn.btn--ghost');
    if (heroBtnComponents && t['hero-btn-components']) {
        const textNodes = Array.from(heroBtnComponents.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
        textNodes.forEach(n => n.remove());
        heroBtnComponents.appendChild(document.createTextNode(t['hero-btn-components']));
    }

    const heroBtnDocs = document.querySelector('a.btn.btn--ghost[href="docs.html"]');
    if (heroBtnDocs && t['hero-btn-docs']) {
        const textNodes = Array.from(heroBtnDocs.childNodes).filter(n => n.nodeType === Node.TEXT_NODE);
        textNodes.forEach(n => n.remove());
        heroBtnDocs.appendChild(document.createTextNode(t['hero-btn-docs']));
    }

    // Hero Stats
    const statLabels = document.querySelectorAll('.stat-item__label');
    if (statLabels[0]) statLabels[0].textContent = t['hero-stat-components'];
    if (statLabels[1]) statLabels[1].textContent = t['hero-stat-private'];
    if (statLabels[2]) statLabels[2].textContent = t['hero-stat-latency'];
    if (statLabels[3]) statLabels[3].textContent = t['hero-stat-lgpd'];
    if (statLabels[4]) statLabels[4].textContent = t['hero-stat-gpu'];
    if (statLabels[5]) statLabels[5].textContent = t['hero-stat-active'];

    // Library Section
    translate('.section-title', 'lib-title');
    translate('.section-subtitle', 'lib-subtitle');

    // Product Cards
    const products = ['realtime', 'transcription', 'ocr', 'scrapper', 'chat', 'tts', 'analytics', 'agents'];
    products.forEach(product => {
        const card = document.querySelector(`.product-card[data-product="${product}"]`);
        if (!card) return;

        const title = card.querySelector('.product-card__title');
        if (title) title.textContent = t[`card-${product}-title`];

        const desc = card.querySelector('.product-card__description');
        if (desc) desc.textContent = t[`card-${product}-desc`];

        const features = card.querySelectorAll('.product-card__features li');
        features.forEach((feat, idx) => {
            const key = `card-${product}-feat${idx + 1}`;
            if (t[key]) feat.textContent = t[key];
        });

        const cta = card.querySelector('.product-card__cta');
        if (cta) cta.textContent = t['lib-try-btn'];
    });
}

function initializeLanguageSelector() {
    document.querySelectorAll('.language-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            setPageLanguage(btn.dataset.language);
        });
    });

    // Apply saved language
    setPageLanguage(currentPageLanguage);
}

document.addEventListener("DOMContentLoaded", () => {
    bootstrap();
    initializeLanguageSelector();
});
