// ============================================================================
// PANEAS AGENTS MANAGEMENT MODULE
// ============================================================================
// Module for managing AI agents, tools, knowledge sources, and templates
// Consumes external Paneas Agents API (Agno-based)
// ============================================================================

// ============================================================================
// STATE MANAGEMENT
// ============================================================================
const agentsState = {
    apiBase: 'https://paneas-agents-dev.paneas.net',
    authToken: '',
    currentAgent: null,
    agents: [],
    tools: [],
    knowledgeSources: [],
    templates: [],
    toolsCatalog: [],
    teams: [],
    currentTeam: null,
    currentTeamMembers: []
};

// ============================================================================
// API CLIENT
// ============================================================================
class AgentsAPIClient {
    constructor(baseURL, token = '') {
        this.baseURL = baseURL;
        this.token = token;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true',
            ...(this.token && { 'Authorization': `Bearer ${this.token}` })
        };

        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    ...headers,
                    ...options.headers
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(errorMessage);
            }

            // Handle 204 No Content
            if (response.status === 204) {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('API Request Error:', error);
            // Ensure we always have a readable error message
            if (error instanceof Error) {
                throw error;
            } else if (typeof error === 'string') {
                throw new Error(error);
            } else if (error && error.message) {
                throw new Error(error.message);
            } else {
                throw new Error('Erro ao comunicar com a API. Verifique a conexão e tente novamente.');
            }
        }
    }

    // Health & Connection
    async healthCheck() {
        return await this.request('/health');
    }

    // Agents
    async listAgents(enabledOnly = false) {
        const params = enabledOnly ? '?enabled_only=true' : '';
        return await this.request(`/v1/agents${params}`);
    }

    async getAgent(agentId) {
        return await this.request(`/v1/agents/${agentId}`);
    }

    async createAgent(data) {
        return await this.request('/v1/agents', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateAgent(agentId, data) {
        return await this.request(`/v1/agents/${agentId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteAgent(agentId) {
        return await this.request(`/v1/agents/${agentId}`, {
            method: 'DELETE'
        });
    }

    async runAgent(agentId, input, options = {}) {
        return await this.request(`/v1/agents/${agentId}/run`, {
            method: 'POST',
            body: JSON.stringify({ input, options })
        });
    }

    async validateAgent(agentId) {
        return await this.request(`/v1/agents/${agentId}/validate`, {
            method: 'POST'
        });
    }

    // Agent Tools
    async attachTool(agentId, toolId) {
        return await this.request(`/v1/agents/${agentId}/tools/${toolId}`, {
            method: 'POST'
        });
    }

    async detachTool(agentId, toolId) {
        return await this.request(`/v1/agents/${agentId}/tools/${toolId}`, {
            method: 'DELETE'
        });
    }

    // Agent Knowledge
    async attachKnowledge(agentId, knowledgeId) {
        return await this.request(`/v1/agents/${agentId}/knowledge/${knowledgeId}`, {
            method: 'POST'
        });
    }

    async detachKnowledge(agentId, knowledgeId) {
        return await this.request(`/v1/agents/${agentId}/knowledge/${knowledgeId}`, {
            method: 'DELETE'
        });
    }

    // Tools
    async listTools() {
        return await this.request('/v1/tools');
    }

    async getTool(toolId) {
        return await this.request(`/v1/tools/${toolId}`);
    }

    async createTool(data) {
        return await this.request('/v1/tools', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateTool(toolId, data) {
        return await this.request(`/v1/tools/${toolId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteTool(toolId) {
        return await this.request(`/v1/tools/${toolId}`, {
            method: 'DELETE'
        });
    }

    async getToolsCatalog() {
        return await this.request('/v1/tools/catalog');
    }

    // Knowledge Sources
    async listKnowledgeSources() {
        return await this.request('/v1/knowledge/sources');
    }

    async getKnowledgeSource(sourceId) {
        return await this.request(`/v1/knowledge/sources/${sourceId}`);
    }

    async createKnowledgeSource(data) {
        return await this.request('/v1/knowledge/sources', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async deleteKnowledgeSource(sourceId) {
        return await this.request(`/v1/knowledge/sources/${sourceId}`, {
            method: 'DELETE'
        });
    }

    async ingestKnowledgeSource(sourceId) {
        return await this.request(`/v1/knowledge/sources/${sourceId}/ingest`, {
            method: 'POST'
        });
    }

    // Templates
    async listTemplates(category = null, publicOnly = false) {
        const params = new URLSearchParams();
        if (category) params.append('category', category);
        if (publicOnly) params.append('public_only', 'true');
        const queryString = params.toString();
        return await this.request(`/v1/templates${queryString ? '?' + queryString : ''}`);
    }

    async getTemplate(templateId) {
        return await this.request(`/v1/templates/${templateId}`);
    }

    async createTemplate(data) {
        return await this.request('/v1/templates', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateTemplate(templateId, data) {
        return await this.request(`/v1/templates/${templateId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteTemplate(templateId) {
        return await this.request(`/v1/templates/${templateId}`, {
            method: 'DELETE'
        });
    }

    async createAgentFromTemplate(templateId, agentName, overrides = {}) {
        return await this.request(`/v1/templates/${templateId}/create-agent`, {
            method: 'POST',
            body: JSON.stringify({ agent_name: agentName, overrides })
        });
    }

    // Teams
    async listTeams(enabledOnly = false) {
        const params = enabledOnly ? '?enabled_only=true' : '';
        return await this.request(`/v1/teams${params}`);
    }

    async getTeam(teamId) {
        return await this.request(`/v1/teams/${teamId}`);
    }

    async createTeam(data) {
        return await this.request('/v1/teams', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateTeam(teamId, data) {
        return await this.request(`/v1/teams/${teamId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteTeam(teamId) {
        return await this.request(`/v1/teams/${teamId}`, {
            method: 'DELETE'
        });
    }

    // Team Members
    async listTeamMembers(teamId) {
        return await this.request(`/v1/teams/${teamId}/members`);
    }

    async addTeamMember(teamId, memberData) {
        return await this.request(`/v1/teams/${teamId}/members`, {
            method: 'POST',
            body: JSON.stringify(memberData)
        });
    }

    async removeTeamMember(teamId, memberId) {
        return await this.request(`/v1/teams/${teamId}/members/${memberId}`, {
            method: 'DELETE'
        });
    }

    // Team Tools & Knowledge
    async attachToolToTeam(teamId, toolId) {
        return await this.request(`/v1/teams/${teamId}/tools/${toolId}`, {
            method: 'POST'
        });
    }

    async attachKnowledgeToTeam(teamId, knowledgeId) {
        return await this.request(`/v1/teams/${teamId}/knowledge/${knowledgeId}`, {
            method: 'POST'
        });
    }

    // Team Operations
    async runTeam(teamId, message, stream = false) {
        return await this.request(`/v1/teams/${teamId}/run`, {
            method: 'POST',
            body: JSON.stringify({ message, stream })
        });
    }

    async validateTeam(teamId) {
        return await this.request(`/v1/teams/${teamId}/validate`, {
            method: 'POST'
        });
    }

    async getTeamHierarchy(teamId) {
        return await this.request(`/v1/teams/${teamId}/hierarchy`);
    }
}

// ============================================================================
// UTILITIES
// ============================================================================
function showNotification(message, type = 'info') {
    // Ensure message is a string
    let displayMessage = message;
    if (typeof message !== 'string') {
        if (message && message.message) {
            displayMessage = message.message;
        } else if (message && message.toString) {
            displayMessage = message.toString();
        } else {
            displayMessage = 'Erro desconhecido';
        }
    }

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification--${type}`;
    notification.textContent = displayMessage;

    // Add to body
    document.body.appendChild(notification);

    // Auto-remove after 4 seconds
    setTimeout(() => {
        notification.classList.add('notification--hide');
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('pt-BR');
}

function truncateText(text, maxLength = 100) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// ============================================================================
// AGENTS MANAGEMENT
// ============================================================================
async function loadAgents() {
    const enabledOnly = document.getElementById('agentsEnabledFilter')?.checked || false;
    const agentsList = document.getElementById('agentsList');

    if (!agentsList) return;

    agentsList.innerHTML = '<p class="placeholder">Carregando agentes...</p>';

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        agentsState.agents = await apiClient.listAgents(enabledOnly);

        if (agentsState.agents.length === 0) {
            agentsList.innerHTML = '<p class="placeholder">Nenhum agente encontrado.</p>';
            return;
        }

        agentsList.innerHTML = agentsState.agents.map(agent => `
            <div class="item-card" data-agent-id="${agent.id}">
                <div class="item-card__header">
                    <h4 class="item-card__title">${agent.name}</h4>
                    <div class="item-card__badges">
                        ${agent.enabled ? '<span class="badge badge--success">Ativo</span>' : '<span class="badge badge--inactive">Inativo</span>'}
                    </div>
                </div>
                <p class="item-card__description">${truncateText(agent.description || 'Sem descrição')}</p>
                <div class="item-card__meta">
                    <span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                        </svg>
                        ${agent.model_provider}
                    </span>
                    <span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                        </svg>
                        ${agent.model_name}
                    </span>
                </div>
                <div class="item-card__actions">
                    <button class="btn btn--sm btn--secondary" onclick="selectAgent('${agent.id}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                        Editar
                    </button>
                    <button class="btn btn--sm btn--primary" onclick="viewAgentDetails('${agent.id}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                        Ver
                    </button>
                    <button class="btn btn--sm btn--danger" onclick="deleteAgentConfirm('${agent.id}', '${agent.name}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                        Deletar
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading agents:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        agentsList.innerHTML = `<p class="placeholder error">Erro ao carregar agentes: ${errorMsg}</p>`;
        showNotification('Erro ao carregar agentes: ' + errorMsg, 'error');
    }
}

function selectAgent(agentId) {
    const agent = agentsState.agents.find(a => a.id === agentId);
    if (!agent) return;

    // Populate form
    document.getElementById('agentId').value = agent.id;
    document.getElementById('agentName').value = agent.name;
    document.getElementById('agentDescription').value = agent.description || '';
    document.getElementById('agentProvider').value = agent.model_provider;
    document.getElementById('agentModel').value = agent.model_name;
    document.getElementById('agentTemperature').value = agent.temperature || 0.7;
    document.getElementById('agentSystemPrompt').value = agent.system_prompt || '';
    document.getElementById('agentEnabled').checked = agent.enabled;

    // Update form title
    document.getElementById('agentFormTitle').textContent = 'Editar Agente';

    // Scroll to form
    document.getElementById('agentForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function viewAgentDetails(agentId) {
    agentsState.currentAgent = agentId;

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const agent = await apiClient.getAgent(agentId);

        // Show details section
        const detailsSection = document.getElementById('agentDetails');
        detailsSection.classList.remove('hidden');

        // Populate tools list
        const toolsList = document.getElementById('agentToolsList');
        if (agent.tools && agent.tools.length > 0) {
            toolsList.innerHTML = agent.tools.map(tool => `
                <span class="tag tag--tool">
                    ${tool.name}
                    <button class="tag__remove" onclick="detachToolFromAgent('${agentId}', '${tool.id}', '${tool.name}')" title="Remover">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </span>
            `).join('');
        } else {
            toolsList.innerHTML = '<p class="placeholder-sm">Nenhuma tool vinculada</p>';
        }

        // Populate knowledge list
        const knowledgeList = document.getElementById('agentKnowledgeList');
        if (agent.knowledge_sources && agent.knowledge_sources.length > 0) {
            knowledgeList.innerHTML = agent.knowledge_sources.map(source => `
                <span class="tag tag--knowledge">
                    ${source.title}
                    <button class="tag__remove" onclick="detachKnowledgeFromAgent('${agentId}', '${source.id}', '${source.title}')" title="Remover">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </span>
            `).join('');
        } else {
            knowledgeList.innerHTML = '<p class="placeholder-sm">Nenhuma fonte de conhecimento vinculada</p>';
        }

        // Scroll to details
        detailsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        // Refresh dropdowns for adding tools/knowledge
        await refreshAddToolsDropdown();
        await refreshAddKnowledgeDropdown();

    } catch (error) {
        console.error('Error loading agent details:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao carregar detalhes do agente: ' + errorMsg, 'error');
    }
}

async function deleteAgentConfirm(agentId, agentName) {
    if (!confirm(`Tem certeza que deseja deletar o agente "${agentName}"?\n\nEsta ação é irreversível.`)) {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.deleteAgent(agentId);

        showNotification('Agente deletado com sucesso!', 'success');
        await loadAgents();

        // Hide details if current agent was deleted
        if (agentsState.currentAgent === agentId) {
            document.getElementById('agentDetails').classList.add('hidden');
            agentsState.currentAgent = null;
        }

    } catch (error) {
        console.error('Error deleting agent:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao deletar agente: ' + errorMsg, 'error');
    }
}

// ============================================================================
// TOOLS MANAGEMENT
// ============================================================================
async function loadTools() {
    const toolsList = document.getElementById('toolsList');
    if (!toolsList) return;

    toolsList.innerHTML = '<p class="placeholder">Carregando tools...</p>';

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        agentsState.tools = await apiClient.listTools();

        if (agentsState.tools.length === 0) {
            toolsList.innerHTML = '<p class="placeholder">Nenhuma tool registrada.</p>';
            return;
        }

        toolsList.innerHTML = agentsState.tools.map(tool => `
            <div class="item-card" data-tool-id="${tool.id}">
                <div class="item-card__header">
                    <h4 class="item-card__title">${tool.name}</h4>
                </div>
                <p class="item-card__description">${truncateText(tool.description)}</p>
                <div class="item-card__meta">
                    <span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                            <line x1="8" y1="21" x2="16" y2="21"/>
                            <line x1="12" y1="17" x2="12" y2="21"/>
                        </svg>
                        ${truncateText(tool.module_path, 30)}
                    </span>
                    <span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="16 18 22 12 16 6"/>
                            <polyline points="8 6 2 12 8 18"/>
                        </svg>
                        ${tool.function_name}
                    </span>
                </div>
                <div class="item-card__actions">
                    <button class="btn btn--sm btn--secondary" onclick="selectTool('${tool.id}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                        Editar
                    </button>
                    <button class="btn btn--sm btn--danger" onclick="deleteToolConfirm('${tool.id}', '${tool.name}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                        Deletar
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading tools:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        toolsList.innerHTML = `<p class="placeholder error">Erro ao carregar tools: ${errorMsg}</p>`;
        showNotification('Erro ao carregar tools: ' + errorMsg, 'error');
    }
}

function selectTool(toolId) {
    const tool = agentsState.tools.find(t => t.id === toolId);
    if (!tool) return;

    // Populate form
    document.getElementById('toolId').value = tool.id;
    document.getElementById('toolName').value = tool.name;
    document.getElementById('toolDescription').value = tool.description || '';
    document.getElementById('toolModulePath').value = tool.module_path;
    document.getElementById('toolFunctionName').value = tool.function_name;
    document.getElementById('toolSchema').value = JSON.stringify(tool.schema_json, null, 2);

    // Update form title
    document.getElementById('toolFormTitle').textContent = 'Editar Tool';

    // Scroll to form
    document.getElementById('toolForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function deleteToolConfirm(toolId, toolName) {
    if (!confirm(`Tem certeza que deseja deletar a tool "${toolName}"?\n\nEsta ação é irreversível.`)) {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.deleteTool(toolId);

        showNotification('Tool deletada com sucesso!', 'success');
        await loadTools();

    } catch (error) {
        console.error('Error deleting tool:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao deletar tool: ' + errorMsg, 'error');
    }
}

async function loadToolsCatalog() {
    const catalog = document.getElementById('toolsCatalog');
    if (!catalog) return;

    catalog.innerHTML = '<p class="placeholder">Carregando catálogo...</p>';

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const catalogData = await apiClient.getToolsCatalog();

        console.log('Tools catalog response:', catalogData);

        // Ensure catalogData is an array
        if (!Array.isArray(catalogData)) {
            console.error('Tools catalog is not an array:', catalogData);
            catalog.innerHTML = '<p class="placeholder">Catálogo indisponível ou em formato inválido.</p>';
            return;
        }

        agentsState.toolsCatalog = catalogData;

        if (agentsState.toolsCatalog.length === 0) {
            catalog.innerHTML = '<p class="placeholder">Nenhuma tool disponível no catálogo.</p>';
            return;
        }

        catalog.innerHTML = agentsState.toolsCatalog.map(tool => `
            <div class="item-card item-card--catalog">
                <div class="item-card__header">
                    <h4 class="item-card__title">${tool.name || 'Tool sem nome'}</h4>
                    <span class="badge badge--info">Catálogo</span>
                </div>
                <p class="item-card__description">${truncateText(tool.description || 'Sem descrição')}</p>
                <div class="item-card__meta">
                    <span class="meta-item">${tool.module_path || 'N/A'}</span>
                </div>
                <button class="btn btn--sm btn--primary btn--block" onclick="registerToolFromCatalog('${tool.name}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="5" x2="12" y2="19"/>
                        <line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                    Registrar Tool
                </button>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading tools catalog:', error);
        console.error('Error details:', {
            message: error.message,
            stack: error.stack,
            type: typeof error,
            error: error
        });

        let errorMsg = 'Erro desconhecido';
        if (error instanceof Error) {
            errorMsg = error.message;
        } else if (typeof error === 'string') {
            errorMsg = error;
        } else if (error && typeof error === 'object') {
            errorMsg = JSON.stringify(error);
        }

        catalog.innerHTML = `<p class="placeholder">Catálogo de tools não disponível nesta API.</p>`;
        // Don't show notification - catalog is optional
    }
}

function registerToolFromCatalog(toolName) {
    const tool = agentsState.toolsCatalog.find(t => t.name === toolName);
    if (!tool) return;

    // Populate form with catalog data
    document.getElementById('toolId').value = '';
    document.getElementById('toolName').value = tool.name;
    document.getElementById('toolDescription').value = tool.description || '';
    document.getElementById('toolModulePath').value = tool.module_path;
    document.getElementById('toolFunctionName').value = tool.function_name;
    document.getElementById('toolSchema').value = JSON.stringify(tool.schema || {}, null, 2);

    // Update form title
    document.getElementById('toolFormTitle').textContent = 'Registrar Nova Tool';

    // Switch to tools tab
    switchAgentsTab('manage-tools');

    // Scroll to form
    document.getElementById('toolForm').scrollIntoView({ behavior: 'smooth', block: 'start' });

    showNotification('Tool carregada do catálogo. Revise os dados e salve.', 'info');
}

// ============================================================================
// KNOWLEDGE SOURCES MANAGEMENT
// ============================================================================
async function loadKnowledgeSources() {
    const knowledgeList = document.getElementById('knowledgeList');
    if (!knowledgeList) return;

    knowledgeList.innerHTML = '<p class="placeholder">Carregando fontes...</p>';

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        agentsState.knowledgeSources = await apiClient.listKnowledgeSources();

        if (agentsState.knowledgeSources.length === 0) {
            knowledgeList.innerHTML = '<p class="placeholder">Nenhuma fonte de conhecimento criada.</p>';
            return;
        }

        knowledgeList.innerHTML = agentsState.knowledgeSources.map(source => `
            <div class="item-card" data-knowledge-id="${source.id}">
                <div class="item-card__header">
                    <h4 class="item-card__title">${source.title}</h4>
                    <span class="badge badge--${getKnowledgeTypeBadge(source.type)}">${source.type}</span>
                </div>
                <p class="item-card__description">${truncateText(source.location)}</p>
                <div class="item-card__meta">
                    <span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <polyline points="12 6 12 12 16 14"/>
                        </svg>
                        ${formatDate(source.created_at)}
                    </span>
                </div>
                <div class="item-card__actions">
                    <button class="btn btn--sm btn--secondary" onclick="ingestKnowledgeSource('${source.id}', '${source.title}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="17 8 12 3 7 8"/>
                            <line x1="12" x2="12" y1="3" y2="15"/>
                        </svg>
                        Ingerir
                    </button>
                    <button class="btn btn--sm btn--danger" onclick="deleteKnowledgeConfirm('${source.id}', '${source.title}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                        Deletar
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading knowledge sources:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        knowledgeList.innerHTML = `<p class="placeholder error">Erro ao carregar fontes: ${errorMsg}</p>`;
        showNotification('Erro ao carregar fontes de conhecimento: ' + errorMsg, 'error');
    }
}

function getKnowledgeTypeBadge(type) {
    const badges = {
        'file': 'info',
        'folder': 'warning',
        'url': 'primary',
        'markdown': 'success'
    };
    return badges[type] || 'secondary';
}

async function ingestKnowledgeSource(sourceId, sourceTitle) {
    if (!confirm(`Iniciar ingestão da fonte "${sourceTitle}"?\n\nEste processo pode levar alguns minutos.`)) {
        return;
    }

    showNotification('Iniciando ingestão...', 'info');

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const result = await apiClient.ingestKnowledgeSource(sourceId);

        showNotification(
            `Ingestão concluída! ${result.items_created} items criados.`,
            'success'
        );

    } catch (error) {
        console.error('Error ingesting knowledge source:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao ingerir fonte: ' + errorMsg, 'error');
    }
}

async function deleteKnowledgeConfirm(sourceId, sourceTitle) {
    if (!confirm(`Tem certeza que deseja deletar a fonte "${sourceTitle}"?\n\nTodos os dados ingeridos serão perdidos. Esta ação é irreversível.`)) {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.deleteKnowledgeSource(sourceId);

        showNotification('Fonte de conhecimento deletada com sucesso!', 'success');
        await loadKnowledgeSources();

    } catch (error) {
        console.error('Error deleting knowledge source:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao deletar fonte: ' + errorMsg, 'error');
    }
}

// ============================================================================
// TEMPLATES MANAGEMENT
// ============================================================================
async function loadTemplates() {
    const publicOnly = document.getElementById('templatesPublicFilter')?.checked || false;
    const templatesList = document.getElementById('templatesList');

    if (!templatesList) return;

    templatesList.innerHTML = '<p class="placeholder">Carregando templates...</p>';

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        agentsState.templates = await apiClient.listTemplates(null, publicOnly);

        if (agentsState.templates.length === 0) {
            templatesList.innerHTML = '<p class="placeholder">Nenhum template encontrado.</p>';
            return;
        }

        templatesList.innerHTML = agentsState.templates.map(template => `
            <div class="item-card" data-template-id="${template.id}">
                <div class="item-card__header">
                    <h4 class="item-card__title">${template.name}</h4>
                    <div class="item-card__badges">
                        ${template.is_public ? '<span class="badge badge--success">Público</span>' : '<span class="badge badge--secondary">Privado</span>'}
                        ${template.category ? `<span class="badge badge--info">${template.category}</span>` : ''}
                    </div>
                </div>
                <p class="item-card__description">${truncateText(template.description || 'Sem descrição')}</p>
                <div class="item-card__meta">
                    <span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                        </svg>
                        ${template.model_provider} / ${template.model_name}
                    </span>
                    ${template.author ? `<span class="meta-item">por ${template.author}</span>` : ''}
                </div>
                <div class="item-card__actions">
                    <button class="btn btn--sm btn--primary" onclick="createAgentFromTemplate('${template.id}', '${template.name}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="12" y1="5" x2="12" y2="19"/>
                            <line x1="5" y1="12" x2="19" y2="12"/>
                        </svg>
                        Criar Agente
                    </button>
                    <button class="btn btn--sm btn--danger" onclick="deleteTemplateConfirm('${template.id}', '${template.name}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                        Deletar
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading templates:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        templatesList.innerHTML = `<p class="placeholder error">Erro ao carregar templates: ${errorMsg}</p>`;
        showNotification('Erro ao carregar templates: ' + errorMsg, 'error');
    }
}

async function createAgentFromTemplate(templateId, templateName) {
    const agentName = prompt(`Criar agente a partir do template "${templateName}".\n\nDigite o nome do novo agente:`);

    if (!agentName || agentName.trim() === '') {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const result = await apiClient.createAgentFromTemplate(templateId, agentName.trim());

        showNotification('Agente criado com sucesso a partir do template!', 'success');

        // Switch to agents tab and refresh
        switchAgentsTab('manage-agents');
        await loadAgents();

    } catch (error) {
        console.error('Error creating agent from template:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao criar agente: ' + errorMsg, 'error');
    }
}

async function deleteTemplateConfirm(templateId, templateName) {
    if (!confirm(`Tem certeza que deseja deletar o template "${templateName}"?\n\nEsta ação é irreversível.`)) {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.deleteTemplate(templateId);

        showNotification('Template deletado com sucesso!', 'success');
        await loadTemplates();

    } catch (error) {
        console.error('Error deleting template:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao deletar template: ' + errorMsg, 'error');
    }
}

// ============================================================================
// AGENT-TOOL/KNOWLEDGE ATTACHMENT
// ============================================================================
async function refreshAddToolsDropdown() {
    const select = document.getElementById('addToolSelect');
    if (!select || !agentsState.tools) return;

    select.innerHTML = '<option value="">Selecione uma tool...</option>' +
        agentsState.tools.map(tool => `<option value="${tool.id}">${tool.name}</option>`).join('');
}

async function refreshAddKnowledgeDropdown() {
    const select = document.getElementById('addKnowledgeSelect');
    if (!select || !agentsState.knowledgeSources) return;

    select.innerHTML = '<option value="">Selecione uma fonte...</option>' +
        agentsState.knowledgeSources.map(source => `<option value="${source.id}">${source.title}</option>`).join('');
}

async function attachToolToAgent() {
    const toolId = document.getElementById('addToolSelect')?.value;
    const agentId = agentsState.currentAgent;

    if (!toolId || !agentId) {
        showNotification('Selecione uma tool para adicionar', 'warning');
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.attachTool(agentId, toolId);

        showNotification('Tool vinculada com sucesso!', 'success');
        await viewAgentDetails(agentId);

    } catch (error) {
        console.error('Error attaching tool:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao vincular tool: ' + errorMsg, 'error');
    }
}

async function detachToolFromAgent(agentId, toolId, toolName) {
    if (!confirm(`Desvincular a tool "${toolName}" deste agente?`)) {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.detachTool(agentId, toolId);

        showNotification('Tool desvinculada com sucesso!', 'success');
        await viewAgentDetails(agentId);

    } catch (error) {
        console.error('Error detaching tool:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao desvincular tool: ' + errorMsg, 'error');
    }
}

async function attachKnowledgeToAgent() {
    const knowledgeId = document.getElementById('addKnowledgeSelect')?.value;
    const agentId = agentsState.currentAgent;

    if (!knowledgeId || !agentId) {
        showNotification('Selecione uma fonte de conhecimento para adicionar', 'warning');
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.attachKnowledge(agentId, knowledgeId);

        showNotification('Fonte de conhecimento vinculada com sucesso!', 'success');
        await viewAgentDetails(agentId);

    } catch (error) {
        console.error('Error attaching knowledge:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao vincular conhecimento: ' + errorMsg, 'error');
    }
}

async function detachKnowledgeFromAgent(agentId, knowledgeId, knowledgeTitle) {
    if (!confirm(`Desvincular a fonte "${knowledgeTitle}" deste agente?`)) {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.detachKnowledge(agentId, knowledgeId);

        showNotification('Fonte de conhecimento desvinculada com sucesso!', 'success');
        await viewAgentDetails(agentId);

    } catch (error) {
        console.error('Error detaching knowledge:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao desvincular conhecimento: ' + errorMsg, 'error');
    }
}

// ============================================================================
// FORM HANDLERS
// ============================================================================
async function handleAgentFormSubmit(e) {
    e.preventDefault();

    const agentId = document.getElementById('agentId').value;
    const isEdit = !!agentId;

    const data = {
        name: document.getElementById('agentName').value,
        description: document.getElementById('agentDescription').value || null,
        model_provider: document.getElementById('agentProvider').value,
        model_name: document.getElementById('agentModel').value,
        temperature: parseFloat(document.getElementById('agentTemperature').value),
        system_prompt: document.getElementById('agentSystemPrompt').value || null,
        enabled: document.getElementById('agentEnabled').checked
    };

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);

        if (isEdit) {
            await apiClient.updateAgent(agentId, data);
            showNotification('Agente atualizado com sucesso!', 'success');
        } else {
            await apiClient.createAgent(data);
            showNotification('Agente criado com sucesso!', 'success');
        }

        // Reset form and reload agents
        document.getElementById('agentForm').reset();
        document.getElementById('agentId').value = '';
        document.getElementById('agentFormTitle').textContent = 'Criar Novo Agente';

        await loadAgents();

    } catch (error) {
        console.error('Error saving agent:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao salvar agente: ' + errorMsg, 'error');
    }
}

async function handleToolFormSubmit(e) {
    e.preventDefault();

    const toolId = document.getElementById('toolId').value;
    const isEdit = !!toolId;

    // Parse schema JSON
    let schemaJson = {};
    const schemaText = document.getElementById('toolSchema').value;
    if (schemaText) {
        try {
            schemaJson = JSON.parse(schemaText);
        } catch (error) {
            showNotification('Schema JSON inválido. Verifique a sintaxe.', 'error');
            return;
        }
    }

    const data = {
        name: document.getElementById('toolName').value,
        description: document.getElementById('toolDescription').value,
        module_path: document.getElementById('toolModulePath').value,
        function_name: document.getElementById('toolFunctionName').value,
        schema_json: schemaJson
    };

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);

        if (isEdit) {
            await apiClient.updateTool(toolId, data);
            showNotification('Tool atualizada com sucesso!', 'success');
        } else {
            await apiClient.createTool(data);
            showNotification('Tool registrada com sucesso!', 'success');
        }

        // Reset form and reload tools
        document.getElementById('toolForm').reset();
        document.getElementById('toolId').value = '';
        document.getElementById('toolFormTitle').textContent = 'Registrar Nova Tool';

        await loadTools();

    } catch (error) {
        console.error('Error saving tool:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao salvar tool: ' + errorMsg, 'error');
    }
}

async function handleKnowledgeFormSubmit(e) {
    e.preventDefault();

    // Parse metadata JSON
    let metaJson = null;
    const metaText = document.getElementById('knowledgeMeta').value;
    if (metaText) {
        try {
            metaJson = JSON.parse(metaText);
        } catch (error) {
            showNotification('Metadados JSON inválidos. Verifique a sintaxe.', 'error');
            return;
        }
    }

    const data = {
        title: document.getElementById('knowledgeTitle').value,
        type: document.getElementById('knowledgeType').value,
        location: document.getElementById('knowledgeLocation').value,
        meta_json: metaJson
    };

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.createKnowledgeSource(data);

        showNotification('Fonte de conhecimento criada com sucesso!', 'success');

        // Reset form and reload sources
        document.getElementById('knowledgeForm').reset();
        await loadKnowledgeSources();

    } catch (error) {
        console.error('Error creating knowledge source:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao criar fonte: ' + errorMsg, 'error');
    }
}

async function handleTemplateFormSubmit(e) {
    e.preventDefault();

    const data = {
        name: document.getElementById('templateName').value,
        description: document.getElementById('templateDescription').value || null,
        category: document.getElementById('templateCategory').value || null,
        author: document.getElementById('templateAuthor').value || null,
        model_provider: document.getElementById('templateProvider').value,
        model_name: document.getElementById('templateModel').value,
        temperature: parseFloat(document.getElementById('templateTemperature').value),
        system_prompt: document.getElementById('templateSystemPrompt').value || null,
        is_public: document.getElementById('templateIsPublic').checked
    };

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.createTemplate(data);

        showNotification('Template criado com sucesso!', 'success');

        // Reset form and reload templates
        document.getElementById('templateForm').reset();
        await loadTemplates();

    } catch (error) {
        console.error('Error creating template:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao criar template: ' + errorMsg, 'error');
    }
}

async function handleRunAgentFormSubmit(e) {
    e.preventDefault();

    const agentId = agentsState.currentAgent;
    const input = document.getElementById('agentInput').value;

    if (!input || !agentId) {
        showNotification('Digite um input para executar o agente', 'warning');
        return;
    }

    const outputBox = document.getElementById('agentOutput');
    const outputContent = document.getElementById('agentOutputContent');
    const outputStats = document.getElementById('agentOutputStats');

    outputBox.classList.remove('hidden');
    outputContent.innerHTML = '<p class="placeholder">Executando agente...</p>';
    outputStats.innerHTML = '';

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const result = await apiClient.runAgent(agentId, input);

        outputContent.innerHTML = `<pre>${result.output}</pre>`;
        outputStats.innerHTML = `
            <div class="stat">
                <span class="stat__label">Status</span>
                <span class="stat__value">${result.status}</span>
            </div>
            <div class="stat">
                <span class="stat__label">Tempo</span>
                <span class="stat__value">${result.execution_time?.toFixed(2) || 0}s</span>
            </div>
            <div class="stat">
                <span class="stat__label">Tools Usadas</span>
                <span class="stat__value">${result.tools_used?.length || 0}</span>
            </div>
        `;

        showNotification('Execução concluída!', 'success');

    } catch (error) {
        console.error('Error running agent:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        outputContent.innerHTML = `<p class="error">Erro: ${errorMsg}</p>`;
        showNotification('Erro ao executar agente: ' + errorMsg, 'error');
    }
}

async function validateCurrentAgent() {
    const agentId = agentsState.currentAgent;
    if (!agentId) return;

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const result = await apiClient.validateAgent(agentId);

        if (result.valid) {
            showNotification('✓ Agente válido e pronto para uso!', 'success');
        } else {
            const issues = result.issues.join('\n• ');
            showNotification(`⚠ Problemas encontrados:\n• ${issues}`, 'warning');
        }

    } catch (error) {
        console.error('Error validating agent:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao validar agente: ' + errorMsg, 'error');
    }
}

// ============================================================================
// TAB SWITCHING
// ============================================================================
function switchAgentsTab(tabName) {
    // Update nav items
    const navItems = document.querySelectorAll('.agents-tabs__item');
    navItems.forEach(item => {
        if (item.dataset.agentsTab === tabName) {
            item.classList.add('agents-tabs__item--active');
        } else {
            item.classList.remove('agents-tabs__item--active');
        }
    });

    // Update panels
    const panels = document.querySelectorAll('.agents-tabs__panel');
    panels.forEach(panel => {
        if (panel.dataset.agentsContent === tabName) {
            panel.classList.add('agents-tabs__panel--active');
        } else {
            panel.classList.remove('agents-tabs__panel--active');
        }
    });
}

// ============================================================================
// AUTO-LOAD DATA
// ============================================================================
let agentsDataLoaded = false;

async function loadAgentsData() {
    if (agentsDataLoaded) {
        return; // Already loaded
    }

    console.log('Loading agents data...');

    try {
        await Promise.all([
            loadAgents(),
            loadTools(),
            loadKnowledgeSources(),
            loadTemplates(),
            loadTeams()
        ]);

        // Load catalog separately (it may fail without breaking other loads)
        try {
            await loadToolsCatalog();
        } catch (catalogError) {
            console.warn('Tools catalog not available:', catalogError);
            // Don't show notification for catalog errors - it's optional
        }

        agentsDataLoaded = true;
        console.log('Agents data loaded successfully');

    } catch (error) {
        console.error('Failed to load agents data:', error);
        const errorMsg = error.message || error.toString() || 'Erro ao carregar dados';
        showNotification('Erro ao carregar dados dos agentes: ' + errorMsg, 'error');
    }
}

// ============================================================================
// TEAMS MANAGEMENT
// ============================================================================
async function loadTeams() {
    const teamsList = document.getElementById('teamsList');

    if (!teamsList) return;

    teamsList.innerHTML = '<p class="placeholder">Carregando teams...</p>';

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        agentsState.teams = await apiClient.listTeams();

        // Populate team selects
        populateTeamSelects();

        if (agentsState.teams.length === 0) {
            teamsList.innerHTML = '<p class="placeholder">Nenhum team encontrado.</p>';
            return;
        }

        teamsList.innerHTML = agentsState.teams.map(team => `
            <div class="item-card" data-team-id="${team.id}">
                <div class="item-card__header">
                    <h4 class="item-card__title">${team.name}</h4>
                    <div class="item-card__badges">
                        ${team.enabled ? '<span class="badge badge--success">Ativo</span>' : '<span class="badge badge--secondary">Inativo</span>'}
                    </div>
                </div>
                <p class="item-card__description">${truncateText(team.description || 'Sem descrição')}</p>
                <div class="item-card__meta">
                    <span class="meta-item">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="9" cy="7" r="4"/>
                        </svg>
                        Líder: ${team.leader_agent_id || 'N/A'}
                    </span>
                </div>
                <div class="item-card__actions">
                    <button class="btn btn--sm btn--secondary" onclick="selectTeam('${team.id}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                        Editar
                    </button>
                    <button class="btn btn--sm btn--danger" onclick="deleteTeamConfirm('${team.id}', '${team.name}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                        Deletar
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading teams:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        teamsList.innerHTML = `<p class="placeholder error">Erro ao carregar teams: ${errorMsg}</p>`;
        showNotification('Erro ao carregar teams: ' + errorMsg, 'error');
    }
}

async function handleTeamFormSubmit(e) {
    e.preventDefault();

    const teamId = document.getElementById('teamId').value;
    const isEdit = !!teamId;

    const data = {
        name: document.getElementById('teamName').value,
        description: document.getElementById('teamDescription').value || null,
        leader_agent_id: document.getElementById('teamLeaderAgent').value,
        enabled: document.getElementById('teamEnabled').checked
    };

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);

        if (isEdit) {
            await apiClient.updateTeam(teamId, data);
            showNotification('Team atualizado com sucesso!', 'success');
        } else {
            const newTeam = await apiClient.createTeam(data);
            agentsState.currentTeam = newTeam.id;
            document.getElementById('teamId').value = newTeam.id;
            document.getElementById('teamFormTitle').textContent = 'Editar Team';

            // Show members section after creating team
            const membersSection = document.getElementById('teamMembersSection');
            if (membersSection) {
                membersSection.style.display = 'block';
            }

            showNotification('Team criado com sucesso! Adicione membros agora.', 'success');
        }

        await loadTeams();
        populateAgentSelects();

    } catch (error) {
        console.error('Error saving team:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao salvar team: ' + errorMsg, 'error');
    }
}

async function resetTeamForm() {
    document.getElementById('teamForm').reset();
    document.getElementById('teamId').value = '';
    document.getElementById('teamFormTitle').textContent = 'Criar Novo Team';
    agentsState.currentTeam = null;
    agentsState.currentTeamMembers = [];

    const membersSection = document.getElementById('teamMembersSection');
    if (membersSection) {
        membersSection.style.display = 'none';
    }

    const membersList = document.getElementById('currentMembersList');
    if (membersList) {
        membersList.innerHTML = '<p class="placeholder">Nenhum membro adicionado ainda</p>';
    }
}

async function selectTeam(teamId) {
    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const team = await apiClient.getTeam(teamId);

        agentsState.currentTeam = teamId;

        document.getElementById('teamId').value = team.id;
        document.getElementById('teamName').value = team.name;
        document.getElementById('teamDescription').value = team.description || '';
        document.getElementById('teamLeaderAgent').value = team.leader_agent_id || '';
        document.getElementById('teamEnabled').checked = team.enabled;
        document.getElementById('teamFormTitle').textContent = 'Editar Team';

        // Show members section
        const membersSection = document.getElementById('teamMembersSection');
        if (membersSection) {
            membersSection.style.display = 'block';
        }

        // Load team members
        await loadTeamMembers(teamId);

        // Scroll to form
        document.getElementById('teamForm').scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error('Error loading team:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao carregar team: ' + errorMsg, 'error');
    }
}

async function loadTeamMembers(teamId) {
    const membersList = document.getElementById('currentMembersList');
    if (!membersList) return;

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const members = await apiClient.listTeamMembers(teamId);

        agentsState.currentTeamMembers = members;

        if (members.length === 0) {
            membersList.innerHTML = '<p class="placeholder">Nenhum membro adicionado ainda</p>';
            return;
        }

        membersList.innerHTML = members.map(member => `
            <div class="item-card" style="margin-bottom: 8px;">
                <div class="item-card__header">
                    <h4 class="item-card__title">${member.member_type === 'agent' ? 'Agente' : 'Sub-Team'}: ${member.member_id}</h4>
                    <button class="btn btn--sm btn--danger" onclick="removeTeamMember('${teamId}', '${member.id}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                        Remover
                    </button>
                </div>
                ${member.role ? `<p class="item-card__description">Papel: ${member.role}</p>` : ''}
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading team members:', error);
        membersList.innerHTML = '<p class="placeholder error">Erro ao carregar membros</p>';
    }
}

async function addTeamMember() {
    const teamId = agentsState.currentTeam;
    if (!teamId) {
        showNotification('Salve o team primeiro antes de adicionar membros', 'warning');
        return;
    }

    const memberType = document.getElementById('memberType').value;
    const role = document.getElementById('memberRole').value || null;

    let memberId;
    if (memberType === 'agent') {
        memberId = document.getElementById('memberAgent').value;
    } else {
        memberId = document.getElementById('memberTeam').value;
    }

    if (!memberId) {
        showNotification('Selecione um membro para adicionar', 'warning');
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.addTeamMember(teamId, {
            member_type: memberType,
            member_id: memberId,
            role: role
        });

        showNotification('Membro adicionado com sucesso!', 'success');

        // Clear form fields
        document.getElementById('memberAgent').value = '';
        document.getElementById('memberTeam').value = '';
        document.getElementById('memberRole').value = '';

        // Reload members
        await loadTeamMembers(teamId);

    } catch (error) {
        console.error('Error adding team member:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao adicionar membro: ' + errorMsg, 'error');
    }
}

async function removeTeamMember(teamId, memberId) {
    if (!confirm('Remover este membro do team?')) {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.removeTeamMember(teamId, memberId);

        showNotification('Membro removido com sucesso!', 'success');
        await loadTeamMembers(teamId);

    } catch (error) {
        console.error('Error removing team member:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao remover membro: ' + errorMsg, 'error');
    }
}

async function deleteTeamConfirm(teamId, teamName) {
    if (!confirm(`Tem certeza que deseja deletar o team "${teamName}"?\n\nEsta ação é irreversível.`)) {
        return;
    }

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        await apiClient.deleteTeam(teamId);

        showNotification('Team deletado com sucesso!', 'success');

        // Reset form if this was the current team
        if (agentsState.currentTeam === teamId) {
            resetTeamForm();
        }

        await loadTeams();

    } catch (error) {
        console.error('Error deleting team:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao deletar team: ' + errorMsg, 'error');
    }
}

function handleMemberTypeChange() {
    const memberType = document.getElementById('memberType').value;
    const agentGroup = document.getElementById('memberAgentGroup');
    const teamGroup = document.getElementById('memberTeamGroup');

    if (memberType === 'agent') {
        agentGroup.style.display = 'block';
        teamGroup.style.display = 'none';
    } else {
        agentGroup.style.display = 'none';
        teamGroup.style.display = 'block';
    }
}

async function viewTeamHierarchy() {
    const teamId = document.getElementById('hierarchyTeamSelect').value;

    if (!teamId) {
        showNotification('Selecione um team para visualizar', 'warning');
        return;
    }

    const hierarchyDisplay = document.getElementById('teamHierarchyDisplay');
    const hierarchyContent = document.getElementById('hierarchyContent');

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const hierarchy = await apiClient.getTeamHierarchy(teamId);

        hierarchyDisplay.style.display = 'block';
        hierarchyContent.innerHTML = renderHierarchyTree(hierarchy);

    } catch (error) {
        console.error('Error loading team hierarchy:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        showNotification('Erro ao carregar hierarquia: ' + errorMsg, 'error');
    }
}

function renderHierarchyTree(node, isRoot = true) {
    if (!node) return '<p style="color: #94a3b8;">Nenhuma hierarquia disponível</p>';

    const nodeType = node.type || 'team';
    const isTeam = nodeType === 'team';
    const isLeader = node.is_leader || false;

    // Icon based on type
    let icon = '';
    let iconColor = '';
    let nodeLabel = '';

    if (isTeam) {
        icon = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>`;
        iconColor = '#667eea';
        nodeLabel = 'Team';
    } else {
        icon = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                </svg>`;
        iconColor = isLeader ? '#10b981' : '#3b82f6';
        nodeLabel = isLeader ? 'Líder' : 'Agente';
    }

    const name = node.name || node.id || 'Sem nome';
    const description = node.description || '';
    const members = node.members || [];
    const hasMembers = members.length > 0;

    let html = `
        <div class="hierarchy-node ${isRoot ? 'hierarchy-node--root' : ''}">
            <div class="hierarchy-node__content">
                <div class="hierarchy-node__icon" style="background: ${iconColor};">
                    ${icon}
                </div>
                <div class="hierarchy-node__info">
                    <div class="hierarchy-node__header">
                        <span class="hierarchy-node__name">${name}</span>
                        <span class="hierarchy-node__badge" style="background: ${iconColor}20; color: ${iconColor};">
                            ${nodeLabel}
                        </span>
                        ${isLeader ? '<span class="hierarchy-node__badge" style="background: #10b98120; color: #10b981;">★ Líder</span>' : ''}
                    </div>
                    ${description ? `<p class="hierarchy-node__description">${description}</p>` : ''}
                    ${node.role ? `<p class="hierarchy-node__role">Papel: ${node.role}</p>` : ''}
                    ${node.model_name ? `<p class="hierarchy-node__meta">Modelo: ${node.model_provider}/${node.model_name}</p>` : ''}
                </div>
            </div>
            ${hasMembers ? `
                <div class="hierarchy-children">
                    ${members.map(member => renderHierarchyTree(member, false)).join('')}
                </div>
            ` : ''}
        </div>
    `;

    return html;
}

async function executeTeam() {
    const teamId = document.getElementById('executeTeamSelect').value;
    const message = document.getElementById('teamExecuteMessage').value;
    const stream = document.getElementById('teamExecuteStream').checked;

    if (!teamId || !message) {
        showNotification('Selecione um team e digite uma mensagem', 'warning');
        return;
    }

    const outputDiv = document.getElementById('teamExecutionOutput');
    const outputContent = document.getElementById('teamOutputContent');

    outputDiv.style.display = 'block';
    outputContent.textContent = 'Executando team...';

    try {
        const apiClient = new AgentsAPIClient(agentsState.apiBase, agentsState.authToken);
        const result = await apiClient.runTeam(teamId, message, stream);

        if (stream && result.session_id) {
            outputContent.textContent = `Sessão iniciada: ${result.session_id}\n\nAguardando resposta via streaming...`;
            // TODO: Implement SSE streaming for team execution
        } else {
            outputContent.textContent = JSON.stringify(result, null, 2);
        }

        showNotification('Team executado com sucesso!', 'success');

    } catch (error) {
        console.error('Error executing team:', error);
        const errorMsg = error.message || error.toString() || 'Erro desconhecido';
        outputContent.textContent = `Erro: ${errorMsg}`;
        showNotification('Erro ao executar team: ' + errorMsg, 'error');
    }
}

function clearTeamOutput() {
    const outputDiv = document.getElementById('teamExecutionOutput');
    const outputContent = document.getElementById('teamOutputContent');

    outputDiv.style.display = 'none';
    outputContent.textContent = '';
}

function populateTeamSelects() {
    // Populate team select dropdowns
    const selects = [
        document.getElementById('memberTeam'),
        document.getElementById('hierarchyTeamSelect'),
        document.getElementById('executeTeamSelect')
    ];

    const options = '<option value="">Selecione um team...</option>' +
        agentsState.teams.map(team => `<option value="${team.id}">${team.name}</option>`).join('');

    selects.forEach(select => {
        if (select) {
            select.innerHTML = options;
        }
    });
}

function populateAgentSelects() {
    // Populate agent select dropdowns for teams
    const selects = [
        document.getElementById('teamLeaderAgent'),
        document.getElementById('memberAgent')
    ];

    const leaderOptions = '<option value="">Selecione um agente...</option>' +
        agentsState.agents.map(agent => `<option value="${agent.id}">${agent.name}</option>`).join('');

    const memberOptions = '<option value="">Selecione um agente...</option>' +
        agentsState.agents.map(agent => `<option value="${agent.id}">${agent.name}</option>`).join('');

    if (selects[0]) selects[0].innerHTML = leaderOptions;
    if (selects[1]) selects[1].innerHTML = memberOptions;
}

// ============================================================================
// INITIALIZATION
// ============================================================================
function initializeAgentsModule() {
    console.log('Initializing Agents Module...');

    // Auto-load data when agents tab is first opened
    const agentsTab = document.querySelector('.playground__nav-item[data-tab="agents"]');
    if (agentsTab) {
        agentsTab.addEventListener('click', () => {
            loadAgentsData();
        });
    }

    // Agent form
    document.getElementById('agentForm')?.addEventListener('submit', handleAgentFormSubmit);
    document.getElementById('resetAgentForm')?.addEventListener('click', () => {
        document.getElementById('agentForm').reset();
        document.getElementById('agentId').value = '';
        document.getElementById('agentFormTitle').textContent = 'Criar Novo Agente';
    });

    // Tool form
    document.getElementById('toolForm')?.addEventListener('submit', handleToolFormSubmit);
    document.getElementById('resetToolForm')?.addEventListener('click', () => {
        document.getElementById('toolForm').reset();
        document.getElementById('toolId').value = '';
        document.getElementById('toolFormTitle').textContent = 'Registrar Nova Tool';
    });

    // Knowledge form
    document.getElementById('knowledgeForm')?.addEventListener('submit', handleKnowledgeFormSubmit);

    // Template form
    document.getElementById('templateForm')?.addEventListener('submit', handleTemplateFormSubmit);

    // Run agent form
    document.getElementById('runAgentForm')?.addEventListener('submit', handleRunAgentFormSubmit);

    // Refresh buttons
    document.getElementById('refreshAgents')?.addEventListener('click', loadAgents);
    document.getElementById('refreshTools')?.addEventListener('click', loadTools);
    document.getElementById('refreshKnowledge')?.addEventListener('click', loadKnowledgeSources);
    document.getElementById('refreshTemplates')?.addEventListener('click', loadTemplates);
    document.getElementById('refreshCatalog')?.addEventListener('click', loadToolsCatalog);

    // Filter checkboxes
    document.getElementById('agentsEnabledFilter')?.addEventListener('change', loadAgents);
    document.getElementById('templatesPublicFilter')?.addEventListener('change', loadTemplates);

    // Attach tool/knowledge buttons
    document.getElementById('addToolButton')?.addEventListener('click', attachToolToAgent);
    document.getElementById('addKnowledgeButton')?.addEventListener('click', attachKnowledgeToAgent);

    // Validate agent button
    document.getElementById('validateAgent')?.addEventListener('click', validateCurrentAgent);

    // Sub-tabs navigation
    const agentsTabButtons = document.querySelectorAll('.agents-tabs__item');
    agentsTabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.dataset.agentsTab;
            switchAgentsTab(tabName);
        });
    });

    // Knowledge type helper text
    document.getElementById('knowledgeType')?.addEventListener('change', (e) => {
        const helpText = document.getElementById('knowledgeLocationHelp');
        const type = e.target.value;
        const hints = {
            'file': 'Caminho do arquivo (ex: uploads/knowledge/manual.pdf)',
            'folder': 'Caminho da pasta (ex: uploads/docs/)',
            'url': 'URL completa (ex: https://example.com/docs)',
            'markdown': 'Conteúdo markdown direto'
        };
        if (helpText) {
            helpText.textContent = hints[type] || '';
        }
    });

    // Teams form
    document.getElementById('teamForm')?.addEventListener('submit', handleTeamFormSubmit);
    document.getElementById('resetTeamForm')?.addEventListener('click', resetTeamForm);

    // Team refresh button
    document.getElementById('refreshTeams')?.addEventListener('click', loadTeams);

    // Team member management
    document.getElementById('memberType')?.addEventListener('change', handleMemberTypeChange);
    document.getElementById('addTeamMember')?.addEventListener('click', addTeamMember);

    // Team hierarchy viewer
    document.getElementById('viewTeamHierarchy')?.addEventListener('click', viewTeamHierarchy);

    // Team execution
    document.getElementById('executeTeamBtn')?.addEventListener('click', executeTeam);
    document.getElementById('clearTeamOutput')?.addEventListener('click', clearTeamOutput);

    console.log('Agents Module initialized successfully');
}

// Export for use in main app.js
if (typeof window !== 'undefined') {
    window.initializeAgentsModule = initializeAgentsModule;
    window.switchAgentsTab = switchAgentsTab;
    window.selectAgent = selectAgent;
    window.viewAgentDetails = viewAgentDetails;
    window.deleteAgentConfirm = deleteAgentConfirm;
    window.selectTool = selectTool;
    window.deleteToolConfirm = deleteToolConfirm;
    window.registerToolFromCatalog = registerToolFromCatalog;
    window.deleteKnowledgeConfirm = deleteKnowledgeConfirm;
    window.ingestKnowledgeSource = ingestKnowledgeSource;
    window.deleteTemplateConfirm = deleteTemplateConfirm;
    window.createAgentFromTemplate = createAgentFromTemplate;
    window.attachToolToAgent = attachToolToAgent;
    window.detachToolFromAgent = detachToolFromAgent;
    window.attachKnowledgeToAgent = attachKnowledgeToAgent;
    window.detachKnowledgeFromAgent = detachKnowledgeFromAgent;
    window.selectTeam = selectTeam;
    window.deleteTeamConfirm = deleteTeamConfirm;
    window.removeTeamMember = removeTeamMember;
}
