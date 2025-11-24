# Changelog - IZZI Intelligence Dashboard

## 2025-01-23 - Implementação de 5 Novas Features

### Contexto
Dashboard de inteligência para análise de chamadas do call center IZZI, com dados de setembro (600 chamadas) e outubro (~9.000 chamadas).

### Features Implementadas

#### 1. Heatmap de Tabulação Melhorado
**Arquivo**: `src/App.tsx` (Componente ComparativoTab)

**Funcionalidades adicionadas**:
- **Exportação CSV da matriz de confusão completa**
  - Botão "Exportar CSV" no topo do heatmap
  - Exporta todas as transições de status com contagem e percentual
  - Formato: IZZI Status, Real Status, Count, Percentage

- **Células clicáveis**
  - Células com dados (count > 0) agora são clicáveis
  - Efeito hover com escala para indicar interatividade
  - Células vazias permanecem desabilitadas

- **Modal de detalhamento**
  - Ao clicar em uma célula, abre modal com lista de chamadas
  - Exibe: ID, Data/Hora, Duração, Agente, Status IZZI, Status Real, Motivo
  - Botão "Exportar CSV" específico para as chamadas da célula
  - Animação suave com Framer Motion

- **Instruções visuais**
  - Texto explicativo: "Clique em uma célula para ver as chamadas específicas"

**Código relevante**:
```typescript
// Estado para célula selecionada
const [selectedCell, setSelectedCell] = useState<{ izzi: string; real: string } | null>(null);

// Filtro de chamadas da célula
const cellCalls = useMemo(() => {
  if (!selectedCell) return [];
  return filtered.filter(
    call => call.izzi_status_normalizado === selectedCell.izzi &&
            call.status_real_detectado === selectedCell.real
  );
}, [filtered, selectedCell]);
```

---

#### 2. Filtros de Data
**Arquivo**: `src/App.tsx`

**Funcionalidades adicionadas**:
- **Campo de filtro por mês**
  - Adicionado campo `month: string` ao tipo `DashboardFilters`
  - Valor padrão: "all"

- **Dropdown de seleção de mês**
  - Extrai mês/ano do campo `call_datetime` (formato DD/MM/YYYY)
  - Mostra contador de chamadas por mês em cada opção
  - Ordenação cronológica (mais antigo para mais recente)

- **Lógica de filtro**
  - Integrado ao filtro principal `applyFilters`
  - Compara o mês da chamada com o mês selecionado

**Código relevante**:
```typescript
// Opções de mês com contadores
const monthOptions = useMemo(() => {
  const monthCounts = new Map<string, number>();
  data.per_call_details.forEach((row) => {
    const month = row.call_datetime?.split(" ")[0]?.split("/")[1];
    const year = row.call_datetime?.split(" ")[0]?.split("/")[2];
    if (month && year) {
      const key = `${month}/${year}`;
      monthCounts.set(key, (monthCounts.get(key) || 0) + 1);
    }
  });
  // ... ordenação e formatação
}, [data]);
```

---

#### 3. Dashboard Comparação Mensal
**Arquivo**: `src/components/MonthlyComparisonTab.tsx` (NOVO)

**Funcionalidades**:
- **Nova aba "Evolução Mensal"**
  - Ícone: TrendingUp
  - Componente completo para análise temporal

- **6 Cards de Comparação Mês-a-Mês**
  - Chamadas Conectadas
  - Taxa de Divergência
  - Engajamento Médio
  - Pitch Satisfatório
  - Follow-up Agendado
  - Provável Venda
  - Cada card mostra valor atual e mudança percentual vs. mês anterior
  - Ícones de tendência (TrendingUp/Down/Minus)

- **3 Gráficos Interativos**
  - **Volume de Chamadas**: BarChart (Total + Conectadas por mês)
  - **Métricas de Qualidade**: LineChart (Taxa Conexão, Divergência, Pitch)
  - **Funil de Vendas**: LineChart (Pitch, Follow-up, Venda Provável)

- **Tabela Detalhada**
  - Todas as métricas por mês em formato tabular
  - Colunas: Mês, Total, Conectadas, Divergência, Engajamento, Pitch OK, Follow-up, Venda Provável

**Interface**:
```typescript
interface MonthMetrics {
  month: string;
  monthLabel: string;
  totalCalls: number;
  connectedCalls: number;
  connectedRate: number;
  divergentCalls: number;
  divergenceRate: number;
  avgDuration: number;
  avgEngagement: number;
  avgSentimentCustomer: number;
  avgSentimentAgent: number;
  scriptAlignedRate: number;
  sourceAwareRate: number;
  pitchSatisfactoryRate: number;
  followUpRate: number;
  likelySalesRate: number;
  objectionHandledRate: number;
  angerRate: number;
}
```

---

#### 4. Visão por Agente
**Arquivo**: `src/components/AgentPerformanceTab.tsx` (NOVO)

**Funcionalidades**:
- **Nova aba "Performance por Agente"**
  - Ícone: User
  - Análise individual de performance dos agentes
  - Cobertura: 94.8% das chamadas com nome de agente detectado

- **4 Cards Resumo**
  - Total de Agentes
  - Média de Chamadas/Agente
  - Top Performer (maior engajamento)
  - Atenção Necessária (menor engajamento)

- **Tabela Ordenável**
  - 8 colunas sortáveis:
    - Agente
    - Total de Chamadas
    - Taxa de Conexão
    - Engajamento Médio
    - Pitch Satisfatório
    - Follow-up
    - Provável Venda
    - Sentimento Médio
  - Ícones ChevronUp/Down indicando direção da ordenação
  - Click no cabeçalho alterna ordenação ascendente/descendente

- **Modal de Detalhamento**
  - Click na linha do agente abre modal
  - Detalhamento completo com 17 métricas:
    - Métricas de Volume
    - Métricas de Qualidade
    - Métricas de Vendas
    - Métricas de Sentimento
  - Animação suave com Framer Motion

**Interface**:
```typescript
interface AgentMetrics {
  agent: string;
  totalCalls: number;
  connectedCalls: number;
  connectionRate: number;
  avgEngagement: number;
  avgSentimentCustomer: number;
  avgSentimentAgent: number;
  avgDuration: number;
  divergenceRate: number;
  scriptAlignedRate: number;
  sourceAwareRate: number;
  pitchSatisfactoryRate: number;
  followUpRate: number;
  likelySalesRate: number;
  objectionHandledRate: number;
  angerRate: number;
  avgSilence: number;
}
```

---

#### 5. Indicadores Proxy de Venda
**Arquivos**: `src/types.ts`, `src/App.tsx`

**Funcionalidades**:
- **Novo campo calculado `likely_sale`**
  - Adicionado ao tipo `PerCallDetail`
  - Lógica: `likely_sale = 1` SE `follow_up_commitment === 1` E `sales_pitch_label === 'satisfatório'`
  - Proxy para identificar chamadas com alta probabilidade de conversão

- **Card "Funil de Conversão"**
  - 4 métricas em sequência:
    1. **Conectadas**: Chamadas onde cliente falou após agente
    2. **Pitch OK**: Pitch de vendas satisfatório
    3. **Follow-up**: Compromisso de follow-up estabelecido
    4. **Venda Provável**: Ambos pitch e follow-up presentes
  - Cada métrica mostra:
    - Contagem absoluta
    - Percentual sobre total de conectadas
    - Cor progressiva (azul → ciano → verde)

**Código relevante**:
```typescript
// Cálculo do likely_sale
const dataWithSales = data.per_call_details.map(row => ({
  ...row,
  likely_sale: row.follow_up_commitment === 1 &&
               (row.sales_pitch_label === 'satisfatório' ||
                row.sales_pitch_label === 'satisfatorio') ? 1 : 0
}));

// Métricas do funil
const connectedCalls = filtered.filter(row => row.customer_after_agent === 1).length;
const pitchSatisfactory = filtered.filter(
  row => row.sales_pitch_label === 'satisfatório' ||
         row.sales_pitch_label === 'satisfatorio'
).length;
const followUpCount = filtered.filter(row => row.follow_up_commitment === 1).length;
const likelySales = filtered.filter(row => row.likely_sale === 1).length;
```

---

### Processo de Build e Deploy

#### Configuração do Vite
O dashboard é servido em um subpath `/izzi/` via ngrok. Para isso, é necessário configurar a variável de ambiente `VITE_BASE`:

```bash
VITE_BASE=/izzi/ npm run build
```

Isso garante que todos os assets (JS, CSS, imagens) sejam carregados com o prefixo correto.

#### Estrutura do Dist
Após o build, a pasta `dist/` contém:
```
dist/
├── index.html              # HTML principal com referências aos assets
├── assets/
│   ├── index-*.js          # Bundle JavaScript principal (~869 KB)
│   └── index-*.css         # Estilos compilados (~33 KB)
└── vite.svg                # Favicon
```

#### Deploy no Container Docker
O dashboard roda em um container Docker chamado `stack-izzi-dashboard`. Para atualizar:

```bash
# 1. Build com base path configurada
VITE_BASE=/izzi/ npm run build

# 2. Copiar dist para o container
sudo docker cp dist/. stack-izzi-dashboard:/app/dist/

# 3. Verificar deploy
# Acessar https://jota.ngrok.app/izzi/
```

**Notas importantes**:
- O container serve arquivos estáticos da pasta `/app/dist/`
- Não é necessário reiniciar o container após copiar os arquivos
- O ngrok expõe o container publicamente no subpath `/izzi/`

#### Troubleshooting
Se o dashboard aparecer em branco:
1. Verificar se o build foi feito com `VITE_BASE=/izzi/`
2. Verificar no browser DevTools se os assets estão sendo carregados de `/izzi/assets/`
3. Confirmar que `dist/index.html` tem os paths corretos:
   ```html
   <link rel="icon" type="image/svg+xml" href="/izzi/vite.svg" />
   <script type="module" crossorigin src="/izzi/assets/index-*.js"></script>
   <link rel="stylesheet" crossorigin href="/izzi/assets/index-*.css">
   ```

---

### Dependências Utilizadas

**Frontend**:
- React 19.1.1
- TypeScript (verbatimModuleSyntax enabled)
- Vite 7.1.9
- Tailwind CSS
- Recharts 3.2.1 (BarChart, LineChart, ResponsiveContainer)
- Framer Motion (AnimatePresence, motion.div)
- Lucide React (ícones)

**Build**:
- Node.js + npm
- Docker para deploy

---

### Cobertura de Dados

**Dataset analisado**:
- Setembro/2024: ~600 chamadas
- Outubro/2024: ~9.000 chamadas
- Total: ~9.600 chamadas

**Qualidade dos dados**:
- 94.8% das chamadas com nome do agente detectado
- Campos de análise: duração, sentimento, engajamento, alinhamento ao script, pitch de vendas, follow-up, objeções, raiva do cliente

---

### Arquivos Modificados/Criados

**Arquivos criados**:
- `src/components/MonthlyComparisonTab.tsx`
- `src/components/AgentPerformanceTab.tsx`

**Arquivos modificados**:
- `src/types.ts` (adicionado campo `likely_sale`, campo `month` em DashboardFilters)
- `src/App.tsx` (5 features implementadas)

**Total de linhas adicionadas**: ~1.500 linhas de código TypeScript/React

---

### Próximos Passos Sugeridos

1. **Otimização de Performance**
   - Considerar code-splitting para reduzir bundle principal (869 KB)
   - Implementar lazy loading para as abas

2. **Funcionalidades Adicionais**
   - Exportação de relatórios em PDF
   - Comparação de múltiplos agentes lado a lado
   - Gráficos de dispersão para correlações entre métricas
   - Filtros avançados (por faixa de data, por ilha, por produto)

3. **Análises Avançadas**
   - Clustering de agentes por padrão de performance
   - Detecção de anomalias em performance de agentes
   - Análise de palavras-chave mais correlacionadas com vendas
   - Timeline de evolução intradiária

---

### Autores
- Implementação: Claude Code (Anthropic)
- Data: 23/01/2025
