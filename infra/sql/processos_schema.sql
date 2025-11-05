-- Schema para armazenamento de processos judiciais
-- Criado para coleta automatizada de processos dos tribunais TJSP, PJE e TJRJ

-- Criar schema se não existir
CREATE SCHEMA IF NOT EXISTS processos;

-- ==============================================================================
-- Tabela principal: processos_judiciais
-- Armazena os dados principais de cada processo
-- ==============================================================================
CREATE TABLE IF NOT EXISTS processos.processos_judiciais (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identificação do processo
    numero_processo TEXT NOT NULL,
    tribunal TEXT NOT NULL CHECK (tribunal IN ('TJSP', 'PJE', 'TJRJ')),
    uf TEXT,

    -- Dados principais (campos comuns aos 3 tribunais)
    classe TEXT,
    assunto TEXT,
    comarca TEXT,
    vara TEXT,
    juiz TEXT,
    data_distribuicao DATE,
    valor_causa TEXT,
    situacao TEXT,
    link_publico TEXT,

    -- JSON completo original do scraper (para campos específicos de cada tribunal)
    dados_completos JSONB NOT NULL,

    -- Metadados
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraint: processo único por tribunal
    UNIQUE(numero_processo, tribunal)
);

-- Índices para otimizar consultas
CREATE INDEX IF NOT EXISTS idx_processos_numero ON processos.processos_judiciais(numero_processo);
CREATE INDEX IF NOT EXISTS idx_processos_tribunal ON processos.processos_judiciais(tribunal);
CREATE INDEX IF NOT EXISTS idx_processos_data_dist ON processos.processos_judiciais(data_distribuicao);
CREATE INDEX IF NOT EXISTS idx_processos_updated ON processos.processos_judiciais(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_processos_classe ON processos.processos_judiciais(classe);
CREATE INDEX IF NOT EXISTS idx_processos_comarca ON processos.processos_judiciais(comarca);

-- Índice GIN para busca full-text no JSONB
CREATE INDEX IF NOT EXISTS idx_processos_dados_gin ON processos.processos_judiciais USING GIN(dados_completos);

-- ==============================================================================
-- Tabela: processos_partes
-- Armazena partes (autores, réus) e advogados relacionados aos processos
-- ==============================================================================
CREATE TABLE IF NOT EXISTS processos.processos_partes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processo_id UUID NOT NULL REFERENCES processos.processos_judiciais(id) ON DELETE CASCADE,

    -- Tipo da parte
    tipo TEXT NOT NULL CHECK (tipo IN ('autor', 'reu', 'advogado', 'outro')),

    -- Dados da parte
    nome TEXT NOT NULL,
    documento TEXT,  -- CPF ou CNPJ

    -- Dados adicionais em JSON (para campos específicos como polo, situação, etc)
    dados_adicionais JSONB,

    -- Metadados
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_partes_processo ON processos.processos_partes(processo_id);
CREATE INDEX IF NOT EXISTS idx_partes_tipo ON processos.processos_partes(tipo);
CREATE INDEX IF NOT EXISTS idx_partes_nome ON processos.processos_partes(nome);
CREATE INDEX IF NOT EXISTS idx_partes_documento ON processos.processos_partes(documento);

-- ==============================================================================
-- Tabela: coletas_historico
-- Registra histórico de execuções das tarefas de coleta
-- ==============================================================================
CREATE TABLE IF NOT EXISTS processos.coletas_historico (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identificação da coleta
    tribunal TEXT NOT NULL CHECK (tribunal IN ('TJSP', 'PJE', 'TJRJ', 'TODOS')),

    -- Timing
    inicio TIMESTAMPTZ NOT NULL,
    fim TIMESTAMPTZ,
    duracao_segundos INTEGER GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (fim - inicio))::INTEGER
    ) STORED,

    -- Status da execução
    status TEXT NOT NULL CHECK (status IN ('em_andamento', 'sucesso', 'erro', 'parcial')),

    -- Estatísticas
    total_processos_encontrados INTEGER DEFAULT 0,
    total_processos_novos INTEGER DEFAULT 0,
    total_processos_atualizados INTEGER DEFAULT 0,
    total_processos_ignorados INTEGER DEFAULT 0,

    -- Detalhes do erro (se houver)
    erro_mensagem TEXT,
    erro_traceback TEXT,

    -- Dados adicionais da execução
    detalhes JSONB,

    -- Metadados
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_coletas_tribunal ON processos.coletas_historico(tribunal);
CREATE INDEX IF NOT EXISTS idx_coletas_inicio ON processos.coletas_historico(inicio DESC);
CREATE INDEX IF NOT EXISTS idx_coletas_status ON processos.coletas_historico(status);

-- ==============================================================================
-- Função: Atualizar updated_at automaticamente
-- ==============================================================================
CREATE OR REPLACE FUNCTION processos.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para atualizar updated_at em processos_judiciais
DROP TRIGGER IF EXISTS trigger_update_processos_updated_at ON processos.processos_judiciais;
CREATE TRIGGER trigger_update_processos_updated_at
    BEFORE UPDATE ON processos.processos_judiciais
    FOR EACH ROW
    EXECUTE FUNCTION processos.update_updated_at_column();

-- ==============================================================================
-- Views úteis para consultas
-- ==============================================================================

-- View: Últimas coletas por tribunal
CREATE OR REPLACE VIEW processos.v_ultimas_coletas AS
SELECT DISTINCT ON (tribunal)
    tribunal,
    inicio,
    fim,
    status,
    total_processos_encontrados,
    total_processos_novos,
    total_processos_atualizados,
    duracao_segundos
FROM processos.coletas_historico
WHERE status != 'em_andamento'
ORDER BY tribunal, inicio DESC;

-- View: Estatísticas de processos
CREATE OR REPLACE VIEW processos.v_estatisticas AS
SELECT
    tribunal,
    COUNT(*) as total_processos,
    COUNT(DISTINCT EXTRACT(YEAR FROM data_distribuicao)) as anos_distintos,
    MIN(data_distribuicao) as data_mais_antiga,
    MAX(data_distribuicao) as data_mais_recente,
    MAX(updated_at) as ultima_atualizacao
FROM processos.processos_judiciais
GROUP BY tribunal;

-- View: Processos com partes
CREATE OR REPLACE VIEW processos.v_processos_completos AS
SELECT
    p.id,
    p.numero_processo,
    p.tribunal,
    p.uf,
    p.classe,
    p.assunto,
    p.data_distribuicao,
    p.situacao,
    p.link_publico,
    -- Agregar autores
    STRING_AGG(DISTINCT CASE WHEN pp.tipo = 'autor' THEN pp.nome END, '; ' ORDER BY CASE WHEN pp.tipo = 'autor' THEN pp.nome END) as autores,
    -- Agregar réus
    STRING_AGG(DISTINCT CASE WHEN pp.tipo = 'reu' THEN pp.nome END, '; ' ORDER BY CASE WHEN pp.tipo = 'reu' THEN pp.nome END) as reus,
    -- Agregar advogados
    STRING_AGG(DISTINCT CASE WHEN pp.tipo = 'advogado' THEN pp.nome END, '; ' ORDER BY CASE WHEN pp.tipo = 'advogado' THEN pp.nome END) as advogados,
    p.created_at,
    p.updated_at
FROM processos.processos_judiciais p
LEFT JOIN processos.processos_partes pp ON p.id = pp.processo_id
GROUP BY p.id, p.numero_processo, p.tribunal, p.uf, p.classe, p.assunto,
         p.data_distribuicao, p.situacao, p.link_publico, p.created_at, p.updated_at;

-- ==============================================================================
-- Comentários nas tabelas (documentação)
-- ==============================================================================
COMMENT ON TABLE processos.processos_judiciais IS 'Tabela principal de processos judiciais coletados de TJSP, PJE e TJRJ';
COMMENT ON TABLE processos.processos_partes IS 'Partes e advogados relacionados aos processos';
COMMENT ON TABLE processos.coletas_historico IS 'Histórico de execuções das tarefas de coleta automatizada';

COMMENT ON COLUMN processos.processos_judiciais.dados_completos IS 'JSON completo original retornado pelo scraper, contém campos específicos de cada tribunal';
COMMENT ON COLUMN processos.processos_judiciais.numero_processo IS 'Número do processo no formato CNJ: 0000000-00.0000.0.00.0000';
COMMENT ON COLUMN processos.coletas_historico.status IS 'Status: em_andamento (rodando), sucesso (100% ok), erro (falhou), parcial (alguns processos falharam)';
