import { useMemo, useState } from "react";
import { User, ChevronUp, ChevronDown, X } from "lucide-react";
import type { PerCallDetail } from "../types";
import { useTranslate } from "../i18n";
import { formatNumber, formatPercent } from "../utils/numberFormat";
import { AnimatePresence, motion } from "framer-motion";

interface AgentPerformanceTabProps {
  filtered: PerCallDetail[];
}

interface AgentMetrics {
  agentName: string;
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
  likelySales: number;
  likelySalesRate: number;
  objectionHandledRate: number;
  angerRate: number;
}

type SortKey = keyof AgentMetrics;
type SortDirection = "asc" | "desc";

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-white/5 to-white/[0.02] p-6 shadow-2xl backdrop-blur-xl">
      {children}
    </div>
  );
}

export function AgentPerformanceTab({ filtered }: AgentPerformanceTabProps) {
  const t = useTranslate();
  const [sortKey, setSortKey] = useState<SortKey>("totalCalls");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const agentMetrics = useMemo<AgentMetrics[]>(() => {
    const agentGroups = new Map<string, PerCallDetail[]>();

    filtered.forEach((call) => {
      const agentName = call.agent_name_detected || t("Desconhecido", "Desconocido");
      if (!agentGroups.has(agentName)) {
        agentGroups.set(agentName, []);
      }
      agentGroups.get(agentName)!.push(call);
    });

    const metrics: AgentMetrics[] = [];

    agentGroups.forEach((calls, agentName) => {
      const totalCalls = calls.length;
      const connectedCalls = calls.filter(c => c.status_real_detectado === "dialogo_conectado").length;
      const divergentCalls = calls.filter(c => c.divergente === 1).length;

      const avgDuration = calls.reduce((acc, c) => acc + c.duration_seconds_transcript, 0) / totalCalls;
      const avgEngagement = calls.reduce((acc, c) => acc + c.customer_engagement_score, 0) / totalCalls;
      const avgSentimentCustomer = calls.reduce((acc, c) => acc + c.customer_sentiment_score, 0) / totalCalls;
      const avgSentimentAgent = calls.reduce((acc, c) => acc + c.agent_sentiment_score, 0) / totalCalls;

      const scriptApplicable = calls.filter(c => c.script_keyword_total > 0).length;
      const scriptAligned = calls.filter(c => c.script_alignment_label === "aligned").length;
      const sourceAware = calls.filter(c => c.operator_source_awareness === 1).length;
      const pitchSatisfactory = calls.filter(c => {
        const label = c.sales_pitch_label?.toLowerCase();
        return label === "satisfactory" || label === "satisfatório" || label === "satisfatorio";
      }).length;
      const followUp = calls.filter(c => c.follow_up_commitment === 1).length;
      const likelySales = calls.filter(c => c.likely_sale === 1).length;
      const objectionHandled = calls.filter(c => c.objection_handled === 1).length;
      const anger = calls.filter(c => c.customer_anger_detected === 1).length;

      metrics.push({
        agentName,
        totalCalls,
        connectedCalls,
        connectedRate: totalCalls > 0 ? connectedCalls / totalCalls : 0,
        divergentCalls,
        divergenceRate: totalCalls > 0 ? divergentCalls / totalCalls : 0,
        avgDuration,
        avgEngagement,
        avgSentimentCustomer,
        avgSentimentAgent,
        scriptAlignedRate: scriptApplicable > 0 ? scriptAligned / scriptApplicable : 0,
        sourceAwareRate: connectedCalls > 0 ? sourceAware / connectedCalls : 0,
        pitchSatisfactoryRate: connectedCalls > 0 ? pitchSatisfactory / connectedCalls : 0,
        followUpRate: connectedCalls > 0 ? followUp / connectedCalls : 0,
        likelySales,
        likelySalesRate: connectedCalls > 0 ? likelySales / connectedCalls : 0,
        objectionHandledRate: connectedCalls > 0 ? objectionHandled / connectedCalls : 0,
        angerRate: connectedCalls > 0 ? anger / connectedCalls : 0,
      });
    });

    return metrics;
  }, [filtered, t]);

  const sortedAgents = useMemo(() => {
    const sorted = [...agentMetrics];
    sorted.sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
      }
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDirection === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return 0;
    });
    return sorted;
  }, [agentMetrics, sortKey, sortDirection]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDirection("desc");
    }
  };

  const selectedAgentData = useMemo(() => {
    return agentMetrics.find(a => a.agentName === selectedAgent);
  }, [agentMetrics, selectedAgent]);

  const SortIcon = ({ column }: { column: SortKey }) => {
    if (sortKey !== column) return <ChevronUp className="h-3 w-3 text-slate-500 opacity-0 group-hover:opacity-50" />;
    return sortDirection === "asc" ? (
      <ChevronUp className="h-3 w-3 text-accent-soft" />
    ) : (
      <ChevronDown className="h-3 w-3 text-accent-soft" />
    );
  };

  const SortableHeader = ({ column, children }: { column: SortKey; children: React.ReactNode }) => (
    <th
      className="group cursor-pointer pb-3 text-left text-xs uppercase tracking-wider text-slate-400 hover:text-slate-200"
      onClick={() => handleSort(column)}
    >
      <div className="flex items-center gap-1">
        {children}
        <SortIcon column={column} />
      </div>
    </th>
  );

  if (agentMetrics.length === 0) {
    return (
      <div className="space-y-8">
        <Card>
          <p className="text-center text-slate-400">
            {t("Sem dados de agentes disponíveis.", "No hay datos de agentes disponibles.")}
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <Card>
        <div className="flex items-center gap-3">
          <User className="h-6 w-6 text-accent-soft" />
          <div>
            <h2 className="text-2xl font-semibold text-slate-50">
              {t("Performance por Agente", "Rendimiento por Agente")}
            </h2>
            <p className="text-sm text-slate-400">
              {t(
                `${agentMetrics.length} agentes com métricas agregadas`,
                `${agentMetrics.length} agentes con métricas agregadas`
              )}
            </p>
          </div>
        </div>
      </Card>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Total de Agentes", "Total de Agentes")}
          </p>
          <div className="mt-2 flex items-end justify-between">
            <span className="text-3xl font-semibold text-slate-50">{formatNumber(agentMetrics.length)}</span>
            <User className="h-5 w-5 text-accent-soft" />
          </div>
        </Card>

        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Melhor Conexão", "Mejor Conexión")}
          </p>
          <div className="mt-2">
            {(() => {
              const qualified = agentMetrics.filter(a => a.totalCalls >= 10);
              const best = qualified.sort((a, b) => b.connectedRate - a.connectedRate)[0];
              return best ? (
                <>
                  <span className="text-2xl font-semibold text-green-400">
                    {formatPercent(best.connectedRate)}
                  </span>
                  <p className="mt-1 text-xs text-slate-400">{best.agentName}</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    ({best.connectedCalls}/{best.totalCalls} {t("chamadas", "llamadas")})
                  </p>
                </>
              ) : <span className="text-2xl text-slate-500">-</span>;
            })()}
          </div>
        </Card>

        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Melhor Conversão", "Mejor Conversión")}
          </p>
          <div className="mt-2">
            {(() => {
              const qualified = agentMetrics.filter(a => a.connectedCalls >= 10);
              const best = qualified.sort((a, b) => b.likelySalesRate - a.likelySalesRate)[0];
              return best ? (
                <>
                  <span className="text-2xl font-semibold text-cyan-400">
                    {formatPercent(best.likelySalesRate)}
                  </span>
                  <p className="mt-1 text-xs text-slate-400">{best.agentName}</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    ({best.likelySales}/{best.connectedCalls} {t("conectadas", "conectadas")})
                  </p>
                </>
              ) : <span className="text-2xl text-slate-500">-</span>;
            })()}
          </div>
        </Card>

        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Menor Divergência", "Menor Divergencia")}
          </p>
          <div className="mt-2">
            {(() => {
              const qualified = agentMetrics.filter(a => a.totalCalls >= 10);
              const best = qualified.sort((a, b) => a.divergenceRate - b.divergenceRate)[0];
              return best ? (
                <>
                  <span className="text-2xl font-semibold text-blue-400">
                    {formatPercent(best.divergenceRate)}
                  </span>
                  <p className="mt-1 text-xs text-slate-400">{best.agentName}</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    ({best.divergentCalls}/{best.totalCalls} {t("divergente", "divergente")})
                  </p>
                </>
              ) : <span className="text-2xl text-slate-500">-</span>;
            })()}
          </div>
        </Card>
      </div>

      {/* Agent Table */}
      <Card>
        <h3 className="mb-4 text-lg font-semibold text-slate-50">
          {t("Tabela de Performance", "Tabla de Rendimiento")}
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10">
                <SortableHeader column="agentName">{t("Agente", "Agente")}</SortableHeader>
                <SortableHeader column="totalCalls">{t("Chamadas", "Llamadas")}</SortableHeader>
                <SortableHeader column="connectedRate">{t("Conexão", "Conexión")}</SortableHeader>
                <SortableHeader column="divergenceRate">{t("Divergência", "Divergencia")}</SortableHeader>
                <SortableHeader column="avgEngagement">{t("Engajamento", "Compromiso")}</SortableHeader>
                <SortableHeader column="pitchSatisfactoryRate">{t("Pitch OK", "Pitch OK")}</SortableHeader>
                <SortableHeader column="followUpRate">{t("Follow-up", "Seguimiento")}</SortableHeader>
                <SortableHeader column="likelySalesRate">{t("Venda", "Venta")}</SortableHeader>
                <th className="pb-3 text-right text-xs uppercase tracking-wider text-slate-400">
                  {t("Ações", "Acciones")}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedAgents.map((agent) => (
                <tr key={agent.agentName} className="border-b border-white/5 hover:bg-white/5">
                  <td className="py-3 font-medium text-slate-50">{agent.agentName}</td>
                  <td className="py-3 text-slate-300">{formatNumber(agent.totalCalls)}</td>
                  <td className="py-3 text-slate-300">{formatPercent(agent.connectedRate)}</td>
                  <td className="py-3 text-rose-300">{formatPercent(agent.divergenceRate)}</td>
                  <td className="py-3 text-slate-300">{agent.avgEngagement.toFixed(2)}</td>
                  <td className="py-3 text-cyan-300">{formatPercent(agent.pitchSatisfactoryRate)}</td>
                  <td className="py-3 text-blue-300">{formatPercent(agent.followUpRate)}</td>
                  <td className="py-3 text-green-400">{formatPercent(agent.likelySalesRate)}</td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => setSelectedAgent(agent.agentName)}
                      className="text-xs text-accent-soft hover:text-accent-bright"
                    >
                      {t("Ver Detalhes", "Ver Detalles")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Agent Detail Modal */}
      <AnimatePresence>
        {selectedAgent && selectedAgentData && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
            onClick={() => setSelectedAgent(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 to-slate-950 p-8 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => setSelectedAgent(null)}
                className="absolute right-6 top-6 text-slate-400 hover:text-slate-200"
              >
                <X className="h-6 w-6" />
              </button>

              <div className="mb-6 flex items-center gap-3">
                <User className="h-8 w-8 text-accent-soft" />
                <div>
                  <h2 className="text-3xl font-semibold text-slate-50">{selectedAgentData.agentName}</h2>
                  <p className="text-sm text-slate-400">
                    {t("Performance Detalhada", "Rendimiento Detallado")}
                  </p>
                </div>
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                {/* Volume */}
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-slate-300">{t("Volume", "Volumen")}</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Total de Chamadas", "Total de Llamadas")}</span>
                      <span className="font-semibold text-slate-50">{formatNumber(selectedAgentData.totalCalls)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Conectadas", "Conectadas")}</span>
                      <span className="font-semibold text-green-400">{formatNumber(selectedAgentData.connectedCalls)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Taxa de Conexão", "Tasa de Conexión")}</span>
                      <span className="font-semibold text-green-400">{formatPercent(selectedAgentData.connectedRate)}</span>
                    </div>
                  </div>
                </div>

                {/* Quality */}
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-slate-300">{t("Qualidade", "Calidad")}</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Divergências", "Divergencias")}</span>
                      <span className="font-semibold text-rose-400">{formatPercent(selectedAgentData.divergenceRate)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Engajamento Médio", "Compromiso Promedio")}</span>
                      <span className="font-semibold text-slate-50">{selectedAgentData.avgEngagement.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Duração Média", "Duración Promedio")}</span>
                      <span className="font-semibold text-slate-50">{Math.floor(selectedAgentData.avgDuration)}s</span>
                    </div>
                  </div>
                </div>

                {/* Sentiment */}
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-slate-300">{t("Sentimento", "Sentimiento")}</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Sentimento Cliente", "Sentimiento Cliente")}</span>
                      <span className="font-semibold text-cyan-400">{selectedAgentData.avgSentimentCustomer.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Sentimento Agente", "Sentimiento Agente")}</span>
                      <span className="font-semibold text-blue-400">{selectedAgentData.avgSentimentAgent.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Clientes Irritados", "Clientes Molestos")}</span>
                      <span className="font-semibold text-rose-400">{formatPercent(selectedAgentData.angerRate)}</span>
                    </div>
                  </div>
                </div>

                {/* Playbook */}
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-slate-300">{t("Playbook", "Playbook")}</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Alinhamento Script", "Alineamiento Guión")}</span>
                      <span className="font-semibold text-purple-400">{formatPercent(selectedAgentData.scriptAlignedRate)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Consciente da Origem", "Consciente del Origen")}</span>
                      <span className="font-semibold text-amber-400">{formatPercent(selectedAgentData.sourceAwareRate)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">{t("Objeções Tratadas", "Objeciones Tratadas")}</span>
                      <span className="font-semibold text-orange-400">{formatPercent(selectedAgentData.objectionHandledRate)}</span>
                    </div>
                  </div>
                </div>

                {/* Sales Funnel */}
                <div className="col-span-2 rounded-2xl border border-green-400/30 bg-green-400/10 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-green-300">{t("Funil de Vendas", "Embudo de Ventas")}</h3>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="text-center">
                      <p className="text-xs text-green-200">{t("Pitch Satisfatório", "Pitch Satisfactorio")}</p>
                      <p className="mt-1 text-2xl font-semibold text-green-400">
                        {formatPercent(selectedAgentData.pitchSatisfactoryRate)}
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-green-200">{t("Follow-up Agendado", "Seguimiento Programado")}</p>
                      <p className="mt-1 text-2xl font-semibold text-green-400">
                        {formatPercent(selectedAgentData.followUpRate)}
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-green-200">{t("Provável Venda", "Venta Probable")}</p>
                      <p className="mt-1 text-2xl font-semibold text-green-400">
                        {formatPercent(selectedAgentData.likelySalesRate)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
