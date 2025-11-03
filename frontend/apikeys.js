/**
 * API Keys Management JavaScript
 */

// Get stored token
function getStoredToken() {
    return sessionStorage.getItem('adminToken');
}

// Format date helper
function formatDate(dateString) {
    if (!dateString) return 'Nunca';
    const date = new Date(dateString);
    return date.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Format number with commas
function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return Number(num).toLocaleString('pt-BR');
}

// Load analytics data
async function loadAnalytics() {
    const token = getStoredToken();
    if (!token) return;

    try {
        const response = await fetch('/api/v1/admin/keys/analytics/overview', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            console.error('Failed to load analytics');
            return;
        }

        const data = await response.json();

        // Update stat cards
        document.getElementById('statTotalKeys').textContent = formatNumber(data.active_keys);
        document.getElementById('statRequests24h').textContent = formatNumber(data.total_requests_24h);
        document.getElementById('statAvgLatency').textContent = `${Math.round(data.avg_latency_ms)}ms`;
        document.getElementById('statTotalTokens').textContent = formatNumber(data.total_tokens);
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// Load API keys list
async function loadAPIKeys() {
    const token = getStoredToken();
    console.log('[loadAPIKeys] Token:', token ? 'exists' : 'missing');

    if (!token) {
        const tbody = document.getElementById('apiKeysTableBody');
        tbody.innerHTML = '<tr><td colspan="7" class="placeholder">Autenticação necessária</td></tr>';
        return;
    }

    const tbody = document.getElementById('apiKeysTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="placeholder">Carregando...</td></tr>';

    console.log('[loadAPIKeys] Fetching keys...');
    try {
        const response = await fetch('/api/v1/admin/keys?include_revoked=true', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        console.log('[loadAPIKeys] Response status:', response.status);

        if (!response.ok) {
            tbody.innerHTML = '<tr><td colspan="7" class="placeholder">Erro ao carregar keys</td></tr>';
            return;
        }

        const keys = await response.json();

        if (keys.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="placeholder">Nenhuma API key encontrada</td></tr>';
            return;
        }

        tbody.innerHTML = keys.map(key => `
            <tr>
                <td><strong>${escapeHtml(key.name)}</strong></td>
                <td><span class="apikeys-key-preview">${escapeHtml(key.key_prefix)}</span></td>
                <td>
                    ${key.is_active
                        ? '<span class="apikeys-status-badge apikeys-status-badge--active"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>Ativa</span>'
                        : '<span class="apikeys-status-badge apikeys-status-badge--revoked"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>Revogada</span>'
                    }
                </td>
                <td>
                    ${key.is_admin
                        ? '<span class="apikeys-admin-badge"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5z"/></svg>Admin</span>'
                        : '-'
                    }
                </td>
                <td>${formatDate(key.created_at)}</td>
                <td>${formatDate(key.last_used_at)}</td>
                <td>
                    <div class="apikeys-actions">
                        <button class="apikeys-action-btn apikeys-action-btn--view" onclick="viewKeyDetails('${key.id}')">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                            </svg>
                            Ver
                        </button>
                        ${key.is_active
                            ? `<button class="apikeys-action-btn apikeys-action-btn--revoke" onclick="revokeKey('${key.id}', '${escapeHtml(key.name)}')">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"/>
                                    <line x1="15" y1="9" x2="9" y2="15"/>
                                    <line x1="9" y1="9" x2="15" y2="15"/>
                                </svg>
                                Revogar
                            </button>`
                            : ''
                        }
                    </div>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading API keys:', error);
        tbody.innerHTML = '<tr><td colspan="7" class="placeholder">Erro ao carregar keys</td></tr>';
    }
}

// View key details
async function viewKeyDetails(keyId) {
    const token = getStoredToken();
    if (!token) return;

    try {
        const response = await fetch(`/api/v1/admin/keys/${keyId}/usage`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            alert('Erro ao carregar detalhes da key');
            return;
        }

        const stats = await response.json();

        const detailsContent = document.getElementById('keyDetailsContent');
        detailsContent.innerHTML = `
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Nome</span>
                <span class="apikeys-detail-value">${escapeHtml(stats.name)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Key Prefix</span>
                <span class="apikeys-detail-value">${escapeHtml(stats.key_prefix)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Status</span>
                <span class="apikeys-detail-value">${stats.is_active ? 'Ativa' : 'Revogada'}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Total de Requests</span>
                <span class="apikeys-detail-value">${formatNumber(stats.total_requests)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Requests (24h)</span>
                <span class="apikeys-detail-value">${formatNumber(stats.requests_24h)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Requests (7 dias)</span>
                <span class="apikeys-detail-value">${formatNumber(stats.requests_7d)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Requests (30 dias)</span>
                <span class="apikeys-detail-value">${formatNumber(stats.requests_30d)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Tokens Prompt</span>
                <span class="apikeys-detail-value">${formatNumber(stats.total_tokens_prompt)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Tokens Completion</span>
                <span class="apikeys-detail-value">${formatNumber(stats.total_tokens_completion)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Latência Média</span>
                <span class="apikeys-detail-value">${Math.round(stats.avg_latency_ms)}ms</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Criado em</span>
                <span class="apikeys-detail-value">${formatDate(stats.created_at)}</span>
            </div>
            <div class="apikeys-detail-row">
                <span class="apikeys-detail-label">Último uso</span>
                <span class="apikeys-detail-value">${formatDate(stats.last_used_at)}</span>
            </div>
        `;

        document.getElementById('keyDetailsSection').style.display = 'block';
        document.getElementById('keyDetailsSection').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error viewing key details:', error);
        alert('Erro ao carregar detalhes da key');
    }
}

// Revoke key
async function revokeKey(keyId, keyName) {
    if (!confirm(`Tem certeza que deseja revogar a key "${keyName}"?\n\nEsta ação não pode ser desfeita!`)) {
        return;
    }

    const token = getStoredToken();
    if (!token) return;

    try {
        const response = await fetch(`/api/v1/admin/keys/${keyId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            alert('Erro ao revogar key');
            return;
        }

        alert(`Key "${keyName}" revogada com sucesso!`);
        await loadAPIKeys();
        await loadAnalytics();
    } catch (error) {
        console.error('Error revoking key:', error);
        alert('Erro ao revogar key');
    }
}

// Create new key
async function createNewKey(event) {
    event.preventDefault();

    const name = document.getElementById('keyName').value.trim();
    const isAdmin = document.getElementById('keyIsAdmin').checked;

    if (!name) {
        alert('Por favor, informe um nome para a key');
        return;
    }

    const token = getStoredToken();
    if (!token) return;

    try {
        const response = await fetch('/api/v1/admin/keys', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                is_admin: isAdmin
            })
        });

        if (!response.ok) {
            const error = await response.json();
            alert(`Erro ao criar key: ${error.detail || 'Erro desconhecido'}`);
            return;
        }

        const data = await response.json();

        // Hide create modal
        const createModal = document.getElementById('createKeyModal');
        createModal.classList.remove('modal--active');
        createModal.style.display = 'none';

        // Show the new key modal
        document.getElementById('newKeyDisplay').textContent = data.key;
        const showModal = document.getElementById('showKeyModal');
        showModal.style.display = 'flex';
        showModal.classList.add('modal--active');

        // Reload keys
        await loadAPIKeys();
        await loadAnalytics();

        // Reset form
        document.getElementById('createKeyForm').reset();
    } catch (error) {
        console.error('Error creating key:', error);
        alert('Erro ao criar key');
    }
}

// Copy key to clipboard
async function copyKeyToClipboard() {
    const keyText = document.getElementById('newKeyDisplay').textContent;

    try {
        await navigator.clipboard.writeText(keyText);
        const btn = document.getElementById('copyKeyBtn');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>Copiado!';
        setTimeout(() => {
            btn.innerHTML = originalText;
        }, 2000);
    } catch (error) {
        console.error('Error copying to clipboard:', error);
        alert('Erro ao copiar key');
    }
}

// HTML escape helper
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Authenticate with token
async function authenticateWithToken(event) {
    event.preventDefault();

    const tokenInput = document.getElementById('adminToken');
    const token = tokenInput.value.trim();

    if (!token) {
        alert('Por favor, insira um token válido');
        return;
    }

    // Test the token
    try {
        const response = await fetch('/api/v1/admin/keys/analytics/overview', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            alert('Token inválido ou sem permissões');
            return;
        }

        // Token is valid, store it
        sessionStorage.setItem('adminToken', token);

        // Hide auth modal
        const authModal = document.getElementById('authModal');
        authModal.classList.remove('modal--active');
        authModal.style.display = 'none';

        // Load data
        await loadAPIKeys();
        await loadAnalytics();

        // Clear the form
        tokenInput.value = '';
    } catch (error) {
        console.error('Authentication error:', error);
        alert('Erro ao validar token');
    }
}

// Logout (clear token)
function logoutApiKeys() {
    sessionStorage.removeItem('adminToken');
    toggleApiKeysPanel(false);
}

// Toggle API Keys Panel
function toggleApiKeysPanel(show) {
    const panel = document.getElementById('apiKeysPanel');
    const hero = document.querySelector('.hero');
    const components = document.getElementById('components');
    const playground = document.getElementById('playground');
    const footer = document.querySelector('.footer');

    if (show) {
        panel.style.display = 'block';
        if (hero) hero.style.display = 'none';
        if (components) components.style.display = 'none';
        if (playground) playground.style.display = 'none';
        if (footer) footer.style.display = 'none';

        // Scroll to top
        window.scrollTo(0, 0);

        // Check if user is authenticated
        const token = getStoredToken();
        console.log('[toggleApiKeysPanel] Token:', token ? 'exists' : 'missing');

        if (!token) {
            // Show auth modal
            const authModal = document.getElementById('authModal');
            console.log('[toggleApiKeysPanel] Showing auth modal, element:', authModal);
            authModal.style.display = 'flex'; // Override inline style
            authModal.classList.add('modal--active');
            console.log('[toggleApiKeysPanel] Auth modal classes:', authModal.className);
        } else {
            // Load data
            console.log('[toggleApiKeysPanel] Loading keys and analytics...');
            loadAPIKeys();
            loadAnalytics();
        }

        // Re-attach event listeners for buttons inside the panel
        setTimeout(() => {
            attachApiKeysPanelListeners();
        }, 100);
    } else {
        panel.style.display = 'none';
        if (hero) hero.style.display = 'block';
        if (components) components.style.display = 'block';
        if (playground) playground.style.display = 'block';
        if (footer) footer.style.display = 'block';

        // Scroll to top
        window.scrollTo(0, 0);
    }
}

// Attach event listeners for API Keys panel buttons
function attachApiKeysPanelListeners() {
    console.log('[attachApiKeysPanelListeners] Attaching listeners...');

    // Create key button
    const createKeyBtn = document.getElementById('createKeyBtn');
    console.log('[attachApiKeysPanelListeners] createKeyBtn found:', !!createKeyBtn);
    if (createKeyBtn) {
        // Remove old listener if exists
        createKeyBtn.replaceWith(createKeyBtn.cloneNode(true));
        const newCreateKeyBtn = document.getElementById('createKeyBtn');
        newCreateKeyBtn.addEventListener('click', () => {
            console.log('[createKeyBtn] Clicked!');
            const createModal = document.getElementById('createKeyModal');
            console.log('[createKeyBtn] Modal found:', !!createModal);
            createModal.style.display = 'flex';
            createModal.classList.add('modal--active');
        });
        console.log('[attachApiKeysPanelListeners] createKeyBtn listener attached');
    }

    // Refresh keys button
    const refreshKeysBtn = document.getElementById('refreshKeysBtn');
    if (refreshKeysBtn) {
        refreshKeysBtn.replaceWith(refreshKeysBtn.cloneNode(true));
        const newRefreshKeysBtn = document.getElementById('refreshKeysBtn');
        newRefreshKeysBtn.addEventListener('click', async () => {
            await loadAPIKeys();
            await loadAnalytics();
        });
    }

    // Close key details button
    const closeKeyDetailsBtn = document.getElementById('closeKeyDetailsBtn');
    if (closeKeyDetailsBtn) {
        closeKeyDetailsBtn.replaceWith(closeKeyDetailsBtn.cloneNode(true));
        const newCloseKeyDetailsBtn = document.getElementById('closeKeyDetailsBtn');
        newCloseKeyDetailsBtn.addEventListener('click', () => {
            document.getElementById('keyDetailsSection').style.display = 'none';
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // API Keys panel toggle
    const apiKeysNavBtn = document.getElementById('apiKeysNavBtn');
    if (apiKeysNavBtn) {
        apiKeysNavBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleApiKeysPanel(true);
        });
    }

    const closeApiKeysPanelBtn = document.getElementById('closeApiKeysPanel');
    if (closeApiKeysPanelBtn) {
        closeApiKeysPanelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleApiKeysPanel(false);
        });
    }

    // Close API Keys panel when clicking on navbar links
    const navbarLinks = document.querySelectorAll('.navbar__link:not(#apiKeysNavBtn)');
    navbarLinks.forEach(link => {
        link.addEventListener('click', () => {
            const panel = document.getElementById('apiKeysPanel');
            if (panel && panel.style.display === 'block') {
                toggleApiKeysPanel(false);
            }
        });
    });

    // Logout button
    const logoutBtn = document.getElementById('logoutApiKeysBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (confirm('Tem certeza que deseja fazer logout?')) {
                logoutApiKeys();
            }
        });
    }

    // Close create modal buttons
    const closeCreateModal = document.getElementById('closeCreateKeyModal');
    const cancelCreateKey = document.getElementById('cancelCreateKeyBtn');
    if (closeCreateModal) {
        closeCreateModal.addEventListener('click', () => {
            const createModal = document.getElementById('createKeyModal');
            createModal.classList.remove('modal--active');
            createModal.style.display = 'none';
        });
    }
    if (cancelCreateKey) {
        cancelCreateKey.addEventListener('click', () => {
            const createModal = document.getElementById('createKeyModal');
            createModal.classList.remove('modal--active');
            createModal.style.display = 'none';
        });
    }

    // Create key form submission
    const createKeyForm = document.getElementById('createKeyForm');
    if (createKeyForm) {
        createKeyForm.addEventListener('submit', createNewKey);
    }

    // Close show key modal
    const closeShowKeyModal = document.getElementById('closeShowKeyModal');
    if (closeShowKeyModal) {
        closeShowKeyModal.addEventListener('click', () => {
            const showModal = document.getElementById('showKeyModal');
            showModal.classList.remove('modal--active');
            showModal.style.display = 'none';
        });
    }

    // Copy key button
    const copyKeyBtn = document.getElementById('copyKeyBtn');
    if (copyKeyBtn) {
        copyKeyBtn.addEventListener('click', copyKeyToClipboard);
    }

    // Auth modal buttons
    const authForm = document.getElementById('authForm');
    if (authForm) {
        authForm.addEventListener('submit', authenticateWithToken);
    }

    const closeAuthModal = document.getElementById('closeAuthModal');
    if (closeAuthModal) {
        closeAuthModal.addEventListener('click', () => {
            const authModal = document.getElementById('authModal');
            authModal.classList.remove('modal--active');
            authModal.style.display = 'none';
            toggleApiKeysPanel(false); // Return to main screen
        });
    }

    const cancelAuthBtn = document.getElementById('cancelAuthBtn');
    if (cancelAuthBtn) {
        cancelAuthBtn.addEventListener('click', () => {
            const authModal = document.getElementById('authModal');
            authModal.classList.remove('modal--active');
            authModal.style.display = 'none';
            toggleApiKeysPanel(false); // Return to main screen
        });
    }
});

// Make functions global for onclick handlers
window.viewKeyDetails = viewKeyDetails;
window.revokeKey = revokeKey;
window.toggleApiKeysPanel = toggleApiKeysPanel;
