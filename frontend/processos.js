// Configuration
const API_BASE_URL = window.location.origin + '/api/v1';
const API_TOKEN = 'token_abc123';

// State
let currentTribunal = null;
let currentPage = 1;
const pageSize = 20;
let totalPages = 1;
let totalItems = 0;
let currentFilters = {};
let allStats = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    carregarDashboard();
});

// Dashboard functions
async function carregarDashboard() {
    try {
        const stats = await fetchStats();
        allStats = stats;
        renderTribunaisCards(stats);
        updateLastUpdate(stats.ultima_atualizacao);
    } catch (error) {
        console.error('Erro ao carregar dashboard:', error);
        showError('Erro ao carregar estatísticas dos tribunais');
    }
}

async function fetchStats() {
    const response = await fetch(`${API_BASE_URL}/processos/stats/geral`, {
        headers: {
            'Authorization': `Bearer ${API_TOKEN}`
        }
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
}

function renderTribunaisCards(stats) {
    const grid = document.getElementById('tribunais-grid');

    const tribunais = [
        {
            sigla: 'TJSP',
            nome: 'Tribunal de Justiça de São Paulo',
            className: 'tjsp',
            count: stats.por_tribunal.TJSP || 0
        },
        {
            sigla: 'PJE',
            nome: 'Processo Judicial Eletrônico (Justiça Federal)',
            className: 'pje',
            count: stats.por_tribunal.PJE || 0
        },
        {
            sigla: 'TJRJ',
            nome: 'Tribunal de Justiça do Rio de Janeiro',
            className: 'tjrj',
            count: stats.por_tribunal.TJRJ || 0
        }
    ];

    grid.innerHTML = tribunais.map(tribunal => `
        <div class="tribunal-card ${tribunal.className}" onclick="abrirTribunal('${tribunal.sigla}')">
            <div class="sigla">${tribunal.sigla}</div>
            <div class="nome-completo">${tribunal.nome}</div>
            <div class="periodo-badge">📅 Período: 2022-2025</div>
            <div class="tribunal-stats">
                <div class="stat-item">
                    <div class="stat-value">${tribunal.count.toLocaleString('pt-BR')}</div>
                    <div class="stat-label">Processos</div>
                </div>
            </div>
        </div>
    `).join('');
}

function updateLastUpdate(timestamp) {
    const element = document.getElementById('last-update');
    if (timestamp) {
        const date = new Date(timestamp);
        element.textContent = `Última atualização: ${date.toLocaleString('pt-BR')}`;
    } else {
        element.textContent = 'Nenhuma coleta realizada ainda';
    }
}

// Tribunal view functions
async function abrirTribunal(tribunal) {
    currentTribunal = tribunal;
    currentPage = 1;
    currentFilters = {};

    // Update UI
    document.getElementById('dashboard-view').style.display = 'none';
    document.getElementById('processos-view').classList.add('active');

    // Update title
    const tribunalInfo = getTribunalInfo(tribunal);
    document.getElementById('tribunal-title').textContent = `${tribunal} - ${tribunalInfo.nome}`;
    document.getElementById('tribunal-subtitle').textContent = `${allStats?.por_tribunal[tribunal] || 0} processos encontrados (período 2022-2025)`;

    // Clear filters
    document.getElementById('filter-numero').value = '';
    document.getElementById('filter-classe').value = '';
    document.getElementById('filter-comarca').value = '';

    // Load processes
    await carregarProcessos();
}

function getTribunalInfo(sigla) {
    const infos = {
        'TJSP': { nome: 'Tribunal de Justiça de São Paulo' },
        'PJE': { nome: 'Processo Judicial Eletrônico' },
        'TJRJ': { nome: 'Tribunal de Justiça do Rio de Janeiro' }
    };
    return infos[sigla] || { nome: sigla };
}

async function carregarProcessos() {
    showLoading();

    try {
        const data = await fetchProcessos();
        renderProcessosTable(data);
        renderPagination(data);
    } catch (error) {
        console.error('Erro ao carregar processos:', error);
        showError('Erro ao carregar processos');
    }
}

async function fetchProcessos() {
    const params = new URLSearchParams({
        tribunal: currentTribunal,
        page: currentPage,
        per_page: pageSize,
        ...currentFilters
    });

    const response = await fetch(`${API_BASE_URL}/processos?${params}`, {
        headers: {
            'Authorization': `Bearer ${API_TOKEN}`
        }
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    currentPage = data.page || currentPage;
    totalItems = data.total || 0;
    totalPages = data.total_pages || Math.max(1, Math.ceil((data.total || 0) / pageSize));
    return data;
}

function renderProcessosTable(data) {
    const container = document.getElementById('processos-list');

    if (!data.processos || data.processos.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <h3>Nenhum processo encontrado</h3>
                <p>Não há processos cadastrados para este tribunal com os filtros aplicados.</p>
            </div>
        `;
        return;
    }

    const tableHtml = `
        <table class="processos-table">
            <thead>
                <tr>
                    <th>Número</th>
                    <th>Tribunal</th>
                    <th>Classe</th>
                    <th>Assunto</th>
                    <th>Comarca</th>
                    <th>Data Distribuição</th>
                    <th>Situação</th>
                </tr>
            </thead>
            <tbody>
                ${data.processos.map(processo => `
                    <tr>
                        <td>
                            <span class="numero-processo">${processo.numero_processo}</span>
                        </td>
                        <td>
                            <span class="badge tribunal-${processo.tribunal.toLowerCase()}">${processo.tribunal}</span>
                        </td>
                        <td>${processo.classe || '-'}</td>
                        <td>${processo.assunto || '-'}</td>
                        <td>${processo.comarca || '-'}</td>
                        <td>${formatDate(processo.data_distribuicao)}</td>
                        <td>${processo.situacao || '-'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    container.innerHTML = tableHtml;
}

function renderPagination(data) {
    const container = document.getElementById('pagination');
    const currentPageNum = data.page || currentPage || 1;
    const total = data.total ?? totalItems;
    const totalPagesFromResponse = data.total_pages || totalPages || 1;

    totalPages = totalPagesFromResponse;
    totalItems = total ?? totalItems;
    currentPage = currentPageNum;

    container.innerHTML = `
        <button ${currentPageNum <= 1 ? 'disabled' : ''} onclick="mudarPagina(${currentPageNum - 1})">
            ← Anterior
        </button>
        <span>Página ${currentPageNum} de ${totalPagesFromResponse} (${total} processos)</span>
        <button ${currentPageNum >= totalPagesFromResponse ? 'disabled' : ''} onclick="mudarPagina(${currentPageNum + 1})">
            Próxima →
        </button>
    `;
}

function mudarPagina(page) {
    if (!page || page < 1 || page > totalPages) {
        return;
    }
    if (page === currentPage) {
        return;
    }
    currentPage = page;
    carregarProcessos();
}

function aplicarFiltros() {
    const numero = document.getElementById('filter-numero').value.trim();
    const classe = document.getElementById('filter-classe').value.trim();
    const comarca = document.getElementById('filter-comarca').value.trim();

    currentFilters = {};
    if (numero) currentFilters.numero_processo = numero;
    if (classe) currentFilters.classe = classe;
    if (comarca) currentFilters.comarca = comarca;

    currentPage = 1;
    carregarProcessos();
}

function limparFiltros() {
    document.getElementById('filter-numero').value = '';
    document.getElementById('filter-classe').value = '';
    document.getElementById('filter-comarca').value = '';
    currentFilters = {};
    currentPage = 1;
    carregarProcessos();
}

function recarregarProcessos() {
    carregarProcessos();
}

function voltarDashboard() {
    document.getElementById('dashboard-view').style.display = 'block';
    document.getElementById('processos-view').classList.remove('active');
    currentTribunal = null;
    carregarDashboard();
}

// Utility functions
function showLoading() {
    document.getElementById('processos-list').innerHTML = `
        <div class="loading">
            <p>Carregando processos...</p>
        </div>
    `;
}

function showError(message) {
    document.getElementById('processos-list').innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">⚠️</div>
            <h3>Erro</h3>
            <p>${message}</p>
            <button onclick="carregarProcessos()" style="margin-top: 16px; padding: 8px 16px; background: #1e88e5; color: white; border: none; border-radius: 4px; cursor: pointer;">
                Tentar novamente
            </button>
        </div>
    `;
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('pt-BR');
    } catch {
        return dateStr;
    }
}
