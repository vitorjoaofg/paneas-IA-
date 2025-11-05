// ==================== Processos Salvos Functions ====================

let processosState = {
    currentTribunal: null,
    currentPage: 0,
    pageSize: 15,
    stats: null,
    currentView: 'initial'
};

// Navigation between views
function showProcessosView(view) {
    const initialView = document.getElementById('scrapperInitialView');
    const bancoView = document.getElementById('processosBancoView');
    const scrappingView = document.getElementById('processosScrappingView');

    // Hide all views
    if (initialView) initialView.style.display = 'none';
    if (bancoView) bancoView.style.display = 'none';
    if (scrappingView) scrappingView.style.display = 'none';

    // Show selected view
    if (view === 'initial') {
        if (initialView) initialView.style.display = 'grid';
        processosState.currentView = 'initial';
    } else if (view === 'banco') {
        if (bancoView) bancoView.style.display = 'block';
        processosState.currentView = 'banco';
        // Load dashboard when entering banco view
        setTimeout(() => carregarDashboardProcessos(), 100);
    } else if (view === 'scrapping') {
        if (scrappingView) scrappingView.style.display = 'block';
        processosState.currentView = 'scrapping';
    }
}

// Carregar dashboard ao trocar para a aba scrapper
document.addEventListener('DOMContentLoaded', () => {
    const scrapperTab = document.querySelector('[data-tab="scrapper"]');
    if (scrapperTab) {
        scrapperTab.addEventListener('click', () => {
            // Always show initial view when opening the tab
            showProcessosView('initial');
        });
    }
});

async function carregarDashboardProcessos() {
    try {
        const response = await fetch('/api/v1/processos/stats/geral', {
            headers: {
                'Authorization': 'Bearer token_abc123'
            }
        });

        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }

        const stats = await response.json();
        processosState.stats = stats;

        // Update dashboard
        document.getElementById('totalProcessos').textContent = stats.total_processos.toLocaleString('pt-BR');
        document.getElementById('totalTJSP').textContent = (stats.por_tribunal.TJSP || 0).toLocaleString('pt-BR');
        document.getElementById('totalPJE').textContent = (stats.por_tribunal.PJE || 0).toLocaleString('pt-BR');
        document.getElementById('totalTJRJ').textContent = (stats.por_tribunal.TJRJ || 0).toLocaleString('pt-BR');

        // Update last update
        const lastUpdateEl = document.getElementById('lastUpdate');
        if (stats.ultima_atualizacao) {
            const date = new Date(stats.ultima_atualizacao);
            lastUpdateEl.textContent = 'Última atualização: ' + date.toLocaleString('pt-BR');
        } else {
            lastUpdateEl.textContent = 'Nenhuma coleta realizada ainda';
        }
    } catch (error) {
        console.error('Erro ao carregar dashboard:', error);
    }
}

async function visualizarTribunal(tribunal) {
    processosState.currentTribunal = tribunal;
    processosState.currentPage = 0;

    // Mostrar tabela dentro do dashboard
    const listagemDiv = document.getElementById('processosListagem');
    if (listagemDiv) {
        listagemDiv.style.display = 'block';
        listagemDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Update title
    const tribunalNames = {
        'TJSP': 'Tribunal de Justiça de São Paulo',
        'PJE': 'Processo Judicial Eletrônico',
        'TJRJ': 'Tribunal de Justiça do Rio de Janeiro'
    };
    document.getElementById('tribunalTitle').textContent = tribunal + ' - ' + tribunalNames[tribunal];
    const subtitleEl = document.getElementById('tribunalSubtitle');
    if (subtitleEl) {
        const total = processosState.stats?.por_tribunal?.[tribunal] || 0;
        subtitleEl.textContent = `${total.toLocaleString('pt-BR')} processos cadastrados`;
    }

    // Load processes
    await carregarProcessos();
}

function voltarDashboard() {
    const listagemDiv = document.getElementById('processosListagem');
    if (listagemDiv) listagemDiv.style.display = 'none';
    const subtitleEl = document.getElementById('tribunalSubtitle');
    if (subtitleEl) subtitleEl.textContent = '';
    processosState.currentTribunal = null;

    // Scroll back to top of banco view
    const bancoView = document.getElementById('processosBancoView');
    if (bancoView) {
        bancoView.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

async function carregarProcessos() {
    const tableContainer = document.getElementById('processosTable');
    tableContainer.innerHTML = '<div class="loading-message">Carregando processos...</div>';

    try {
        const params = new URLSearchParams({
            tribunal: processosState.currentTribunal,
            limit: processosState.pageSize,
            offset: processosState.currentPage * processosState.pageSize
        });

        const response = await fetch('/api/v1/processos?' + params, {
            headers: {
                'Authorization': 'Bearer token_abc123'
            }
        });

        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }

        const data = await response.json();
        renderProcessosTable(data);
        renderPagination(data);
    } catch (error) {
        console.error('Erro ao carregar processos:', error);
        tableContainer.innerHTML = '<div class="empty-message"><div class="empty-message-icon">⚠️</div><p>Erro ao carregar processos</p></div>';
    }
}

function renderProcessosTable(data) {
    const container = document.getElementById('processosTable');

    if (!data.processos || data.processos.length === 0) {
        container.innerHTML = `
            <div class="empty-message">
                <div class="empty-message-icon">📋</div>
                <h4>Nenhum processo encontrado</h4>
                <p>Não há processos cadastrados para este tribunal.</p>
            </div>
        `;
        return;
    }

    const rows = data.processos.map((processo, idx) => {
        const dc = processo.dados_completos || {};
        const partes = dc.partes || [];
        const movimentos = dc.movimentos || [];
        const audiencias = dc.audiencias || [];
        const publicacoes = dc.publicacoes || [];
        const documentos = dc.documentos || [];

        return `
        <tr onclick="toggleDetails('details-${idx}')" style="cursor: pointer;">
            <td>
                <span class="processo-numero">${processo.numero_processo}</span>
            </td>
            <td>
                <span class="tribunal-badge ${processo.tribunal.toLowerCase()}">${processo.tribunal}</span>
            </td>
            <td>${processo.classe || '-'}</td>
            <td>${processo.assunto || '-'}</td>
            <td>${processo.comarca || '-'}</td>
            <td>${formatarData(processo.data_distribuicao)}</td>
            <td>
                <span class="badge-info">
                    ${partes.length} partes | ${movimentos.length} mov. | ${audiencias.length} aud. | ${publicacoes.length} pub. | ${documentos.length} docs
                </span>
            </td>
            <td>
                <button class="btn btn--sm btn--ghost" onclick="event.stopPropagation(); toggleDetails('details-${idx}')">
                    <span id="details-icon-${idx}">▼</span> Ver detalhes
                </button>
            </td>
        </tr>
        <tr id="details-${idx}" style="display: none;" class="details-row">
            <td colspan="8" style="padding: 0;">
                <div class="processo-detalhes">
                    ${renderDetalhesProcesso(processo)}
                </div>
            </td>
        </tr>
        `;
    }).join('');

    const tableHtml = `
        <div class="processos-table-container">
            <table class="processos-table">
                <thead>
                    <tr>
                        <th>Número</th>
                        <th>Tribunal</th>
                        <th>Classe</th>
                        <th>Assunto</th>
                        <th>Comarca</th>
                        <th>Data Distrib.</th>
                        <th>Dados</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = tableHtml;
}

function toggleDetails(id) {
    const row = document.getElementById(id);
    const icon = document.getElementById('icon-' + id);
    if (row.style.display === 'none') {
        row.style.display = 'table-row';
        if (icon) icon.textContent = '▲';
    } else {
        row.style.display = 'none';
        if (icon) icon.textContent = '▼';
    }
}

function renderDetalhesProcesso(processo) {
    const dc = processo.dados_completos || {};
    const partes = dc.partes || [];
    const movimentos = dc.movimentos || [];
    const audiencias = dc.audiencias || [];
    const publicacoes = dc.publicacoes || [];
    const documentos = dc.documentos || [];

    return `
        <div class="detalhes-sections">
            <div class="detalhes-section">
                <h4>👥 Partes (${partes.length})</h4>
                ${partes.length > 0 ? `
                    <div class="partes-list">
                        ${partes.map(p => `
                            <div class="parte-item">
                                <strong>${p.tipo || 'Parte'}:</strong> ${p.nome || '-'}
                                ${p.documento ? `<br><small>Doc: ${p.documento}</small>` : ''}
                                ${p.advogados && p.advogados.length > 0 ? `
                                    <div class="advogados-list">
                                        ${p.advogados.map(adv => `
                                            <div class="advogado-item">⚖️ ${adv.nome || '-'} ${adv.oab ? `(OAB: ${adv.oab})` : ''}</div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : '<p class="empty-text">Nenhuma parte cadastrada</p>'}
            </div>

            <div class="detalhes-section">
                <h4>📝 Movimentos (${movimentos.length})</h4>
                ${movimentos.length > 0 ? `
                    <div class="movimentos-list">
                        ${movimentos.slice(0, 5).map(m => `
                            <div class="movimento-item">
                                <span class="movimento-data">${formatarData(m.data || m.dataMovimentacao)}</span>
                                <span class="movimento-desc">${m.descricao || '-'}</span>
                            </div>
                        `).join('')}
                        ${movimentos.length > 5 ? `<p class="more-text">... e mais ${movimentos.length - 5} movimentos</p>` : ''}
                    </div>
                ` : '<p class="empty-text">Nenhum movimento registrado</p>'}
            </div>

            <div class="detalhes-section">
                <h4>📅 Audiências (${audiencias.length})</h4>
                ${audiencias.length > 0 ? `
                    <div class="audiencias-list">
                        ${audiencias.map(aud => `
                            <div class="audiencia-item">
                                ${aud.data ? `<span class="aud-data">📆 ${aud.data}</span>` : ''}
                                ${aud.tipo ? `<span class="aud-tipo">${aud.tipo}</span>` : ''}
                                ${aud.local ? `<span class="aud-local">📍 ${aud.local}</span>` : ''}
                                ${aud.status ? `<span class="aud-status">${aud.status}</span>` : ''}
                                ${aud.observacoes ? `<div class="aud-obs">${aud.observacoes}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : '<p class="empty-text">Nenhuma audiência agendada</p>'}
            </div>

            <div class="detalhes-section">
                <h4>📰 Publicações (${publicacoes.length})</h4>
                ${publicacoes.length > 0 ? `
                    <div class="publicacoes-list">
                        ${publicacoes.slice(0, 3).map(pub => `
                            <div class="publicacao-item">
                                ${pub.data ? `<span class="pub-data">📅 ${pub.data}</span>` : ''}
                                ${pub.tipo ? `<span class="pub-tipo">${pub.tipo}</span>` : ''}
                                ${pub.descricao ? `<div class="pub-desc">${pub.descricao.substring(0, 200)}${pub.descricao.length > 200 ? '...' : ''}</div>` : ''}
                                ${pub.link ? `<a href="${pub.link}" target="_blank" class="pub-link">🔗 Ver publicação</a>` : ''}
                            </div>
                        `).join('')}
                        ${publicacoes.length > 3 ? `<p class="more-text">... e mais ${publicacoes.length - 3} publicações</p>` : ''}
                    </div>
                ` : '<p class="empty-text">Nenhuma publicação disponível</p>'}
            </div>

            <div class="detalhes-section">
                <h4>📄 Documentos (${documentos.length})</h4>
                ${documentos.length > 0 ? `
                    <div class="documentos-list">
                        ${documentos.slice(0, 5).map(doc => `
                            <div class="documento-item">
                                <span class="doc-nome">📎 ${doc.nome}</span>
                                ${doc.tipo ? `<span class="doc-tipo">${doc.tipo}</span>` : ''}
                                ${doc.data_juntada ? `<span class="doc-data">${doc.data_juntada}</span>` : ''}
                                ${doc.link ? `<a href="${doc.link}" target="_blank" class="doc-link">🔗 Download</a>` : ''}
                            </div>
                        `).join('')}
                        ${documentos.length > 5 ? `<p class="more-text">... e mais ${documentos.length - 5} documentos</p>` : ''}
                    </div>
                ` : '<p class="empty-text">Nenhum documento anexado</p>'}
            </div>
        </div>
    `;
}

function renderPagination(data) {
    const container = document.getElementById('processosPagination');
    const totalPages = Math.ceil(data.total / processosState.pageSize);
    const currentPageNum = processosState.currentPage + 1;

    const prevDisabled = processosState.currentPage === 0 ? 'disabled' : '';
    const nextDisabled = !data.has_more ? 'disabled' : '';

    container.innerHTML = `
        <button ${prevDisabled} onclick="mudarPaginaProcessos(${processosState.currentPage - 1})">
            ← Anterior
        </button>
        <span class="pagination-info">Página ${currentPageNum} de ${totalPages} (${data.total} processos)</span>
        <button ${nextDisabled} onclick="mudarPaginaProcessos(${processosState.currentPage + 1})">
            Próxima →
        </button>
    `;
}

function mudarPaginaProcessos(page) {
    processosState.currentPage = page;
    carregarProcessos();
}

function formatarData(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('pt-BR');
    } catch {
        return dateStr;
    }
}
