"use client";

import { useState } from "react";
import { analyzeBinanceWithAI, BinanceAIAnalysis, BinanceAIProposal } from "@/lib/api";

interface BinanceAICardProps {
  onApplyProposal: (proposal: BinanceAIProposal) => void;
}

export default function BinanceAICard({ onApplyProposal }: BinanceAICardProps) {
  const [analysis, setAnalysis] = useState<BinanceAIAnalysis | null>(null);
  const [riskPct, setRiskPct] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyze() {
    setLoading(true);
    setError(null);
    try {
      setAnalysis(await analyzeBinanceWithAI({ symbol: "BTC/USDT:USDT", timeframe: "1h", risk_pct: Number(riskPct) }));
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "No se pudo generar el análisis IA.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-xl border border-neutral/40 bg-panel-muted/40 p-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs uppercase tracking-[0.18em] text-neutral">Binance Futures AI Analyst</p><h3 className="mt-1 text-lg font-semibold">Contratos y escenarios con evidencia</h3><p className="mt-1 max-w-2xl text-sm text-muted">La biblioteca de conocimiento es requisito para proponer operaciones y debe incluir gestión de riesgo. El mercado en vivo solo confirma si sus reglas se cumplen. Sin fuente adecuada, la IA devuelve NO TRADE. Aplicar solo rellena el ticket; nunca envía la orden.</p></div>
        <div className="flex items-end gap-2"><label className="text-xs text-muted">Riesgo máximo %<input className="mt-1 w-24 rounded-lg border border-border bg-panel px-2 py-2 text-sm" type="number" min="0.1" max="5" step="0.1" value={riskPct} onChange={(event) => setRiskPct(event.target.value)} /></label><button className="rounded-lg bg-neutral px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" onClick={analyze} disabled={loading}>{loading ? "Razonando..." : "Analizar mercado"}</button></div>
      </div>
      {error && <p className="rounded-lg border border-bear p-3 text-sm text-bear">{error}</p>}
      {analysis && <div className="space-y-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-6"><div className="rounded-lg border border-border bg-panel p-3"><p className="text-[11px] text-muted">Veredicto</p><p className={analysis.verdict === "NO_TRADE" ? "text-warning" : analysis.verdict === "LONG" ? "text-bull" : "text-bear"}>{analysis.verdict}</p></div><div className="rounded-lg border border-border bg-panel p-3"><p className="text-[11px] text-muted">Confianza IA</p><p>{analysis.confidence}/100</p></div><div className="rounded-lg border border-border bg-panel p-3"><p className="text-[11px] text-muted">Propuestas</p><p>{analysis.proposals.length}</p></div><div className="rounded-lg border border-border bg-panel p-3"><p className="text-[11px] text-muted">Disponible</p><p>{analysis.account_connected === false ? "Sin conectar" : `${analysis.account_available_usdt?.toLocaleString() ?? "-"} USDT`}</p></div><div className="rounded-lg border border-border bg-panel p-3"><p className="text-[11px] text-muted">Posiciones</p><p>{analysis.open_positions_count ?? 0}</p></div><div className="rounded-lg border border-border bg-panel p-3"><p className="text-[11px] text-muted">Multi-TF (1h/4h/1d)</p><p className={analysis.multi_timeframe_consensus === "bullish" ? "text-bull" : analysis.multi_timeframe_consensus === "bearish" ? "text-bear" : ""}>{analysis.multi_timeframe_consensus ?? "N/D"}</p></div></div>
        {analysis.account_connected === false && <p className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-muted">Binance no está conectado: el análisis técnico es real, pero el tamaño sugerido queda en 0 hasta que configures tus claves.</p>}
        <p className="text-sm text-foreground">{analysis.summary}</p>
        {analysis.knowledge_sources.length === 0 ? (
          <p className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-muted">
            Sin evidencia sustantiva de gestión de riesgo en la biblioteca: esta evaluación no puede proponer operaciones.
            Agrega material real en <code>knowledge_library/risk_management/</code> y sincroniza la biblioteca.
          </p>
        ) : (
          <div className="space-y-2 rounded-lg border border-neutral/30 bg-panel p-3">
            <p className="text-xs uppercase tracking-wide text-neutral">
              Fundamento documental de la decisión ({analysis.knowledge_sources.length} fragmentos)
            </p>
            {analysis.knowledge_sources.map((source) => (
              <details key={`${source.document_id}-${source.chunk_index}`} className="border-l-2 border-neutral/40 pl-2 text-xs">
                <summary className="cursor-pointer text-foreground">
                  {source.document_title} ({source.category.replace(/_/g, " ")}) · fragmento {source.chunk_index} · relevancia {source.score.toFixed(2)}
                </summary>
                <p className="mt-2 whitespace-pre-wrap text-muted">{source.content}</p>
              </details>
            ))}
          </div>
        )}
        {analysis.proposals.length === 0 && <p className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-muted">NO TRADE: la IA no encontró una propuesta con datos y confluencia suficientes.</p>}
        <div className="grid gap-3 lg:grid-cols-2">{analysis.proposals.map((proposal, index) => <Proposal key={`${proposal.direction}-${index}`} proposal={proposal} onApply={() => onApplyProposal(proposal)} />)}</div>
        {analysis.evidence.length > 0 && <div><p className="mb-2 text-xs uppercase tracking-wide text-muted">Evidencia usada</p><div className="grid gap-2 md:grid-cols-2">{analysis.evidence.slice(0, 8).map((item, index) => <div className="rounded-lg border border-border bg-panel p-3 text-xs" key={`${item.kind}-${index}`}><span className="text-neutral">{item.kind}</span> · {item.text} <span className="text-muted">{item.source}</span></div>)}</div></div>}
        <p className="text-xs text-muted">{analysis.disclaimer}</p>
      </div>}
    </section>
  );
}

function Proposal({ proposal, onApply }: { proposal: BinanceAIProposal; onApply: () => void }) {
  return <article className="rounded-lg border border-border bg-panel p-4 space-y-3"><div className="flex items-center justify-between"><div><span className={proposal.direction === "LONG" ? "text-bull" : "text-bear"}>{proposal.direction}</span><h4 className="mt-1 font-semibold">{proposal.setup}</h4></div><span className="text-sm text-neutral">R:R {proposal.reward_risk.toFixed(2)}</span></div><div className="grid grid-cols-2 gap-2 sm:grid-cols-5"><Metric label="Entrada" value={proposal.entry} /><Metric label="Stop" value={proposal.stop_loss} /><Metric label="Target" value={proposal.take_profit} /><Metric label="ROI margen" value={`${proposal.margin_roi_pct}%`} /><Metric label="Riesgo" value={`${proposal.risk_usdt ?? "-"} USDT`} /></div><p className="text-xs text-muted">Tamaño calculado por riesgo: {proposal.suggested_amount} · Activación: {proposal.activation}</p><p className="text-xs text-muted">Invalidación: {proposal.invalidation}</p>{proposal.warnings.length > 0 && <p className="text-xs text-warning">Riesgos: {proposal.warnings.join(" · ")}</p>}<button className="w-full rounded-lg border border-neutral px-3 py-2 text-sm font-semibold text-neutral hover:bg-neutral/10" onClick={onApply}>Aplicar al ticket</button></article>;
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return <div><p className="text-[11px] text-muted">{label}</p><p className="font-semibold tabular-nums">{typeof value === "number" ? value.toLocaleString() : value}</p></div>;
}
