"use client";

import { useState } from "react";
import {
  findTradeOpportunities,
  compareLongVsShort,
  STRATEGIES,
  TradeOpportunity,
  TradeFinderResult,
} from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  technical: "Técnico",
  market_structure: "Estructura",
  volume: "Volumen",
  derivatives: "Derivados",
  macro: "Macro",
  news: "Noticias",
  sentiment: "Sentimiento",
  historical_similarity: "Similitud histórica",
};

function fmtUsd(n?: number | null) {
  if (n === undefined || n === null) return "—";
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtPct(n?: number | null, sign = true) {
  if (n === undefined || n === null) return "—";
  const s = sign && n > 0 ? "+" : "";
  return `${s}${n.toFixed(2)}%`;
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    potential: "bg-bull/15 text-bull border-bull/40",
    conditional: "bg-neutral/15 text-neutral border-neutral/40",
    rejected: "bg-bear/15 text-bear border-bear/40",
  };
  const label: Record<string, string> = {
    potential: "🟢 POTENTIAL",
    conditional: "🟡 CONDITIONAL",
    rejected: "🔴 NO TRADE",
  };
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded border font-medium ${map[status] || ""}`}>
      {label[status] || status.toUpperCase()}
    </span>
  );
}

function confluenceColor(c: string) {
  if (c === "HIGH") return "text-bull";
  if (c === "MEDIUM") return "text-neutral";
  if (c === "LOW") return "text-bear";
  return "text-gray-500";
}

function OpportunityCard({ o }: { o: TradeOpportunity }) {
  const [expanded, setExpanded] = useState(false);
  const dirColor = o.direction === "long" ? "text-bull" : "text-bear";
  const dirLabel = o.direction === "long" ? "LONG" : "SHORT";

  return (
    <div className="border border-border rounded-lg p-3 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className={`font-semibold text-sm ${dirColor}`}>BTC {dirLabel}</span>
          {o.strategy && <span className="text-[10px] text-gray-500">· {o.strategy.replace(/_/g, " ")}</span>}
        </div>
        {statusBadge(o.status)}
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-xs">
        <div>
          <span className="text-gray-500 block">Entry</span>
          <span className="text-gray-200 font-medium">{fmtUsd(o.entry)}</span>
        </div>
        <div>
          <span className="text-gray-500 block">Stop</span>
          <span className="text-bear font-medium">{fmtUsd(o.stop)}</span>
        </div>
        <div>
          <span className="text-gray-500 block">Target</span>
          <span className="text-bull font-medium">{fmtUsd(o.target)}</span>
        </div>
        <div>
          <span className="text-gray-500 block">Risk</span>
          <span className="text-bear font-medium">-{o.risk_pct.toFixed(2)}%</span>
        </div>
        <div>
          <span className="text-gray-500 block">ROI potencial</span>
          <span className="text-bull font-medium">+{o.potential_roi_pct.toFixed(2)}%</span>
        </div>
        <div>
          <span className="text-gray-500 block">R:R</span>
          <span className="text-gray-200 font-medium">1:{o.risk_reward.toFixed(2)}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs border-t border-border pt-2">
        <span>
          Trade Score:{" "}
          <span className="font-semibold text-gray-200">
            {o.trade_score.toFixed(0)}/100 ({o.grade})
          </span>
        </span>
        <span>
          Confluence: <span className={`font-semibold ${confluenceColor(o.confluence)}`}>{o.confluence}</span>{" "}
          <span className="text-gray-500">
            ({o.bullish_factors}↑ / {o.bearish_factors}↓ de {o.categories_available}/{o.categories_total} factores)
          </span>
        </span>
        {o.position_size_usd !== null && (
          <span className="text-gray-500">
            Tamaño posición: {fmtUsd(o.position_size_usd)} · Ganancia pot.: {fmtUsd(o.potential_profit_usd)} ·
            Pérdida máx.: {fmtUsd(o.max_loss_usd)}
          </span>
        )}
      </div>

      <button
        onClick={() => setExpanded((e) => !e)}
        className="text-[11px] text-neutral hover:underline"
      >
        {expanded ? "Ocultar evidencia" : "Ver evidencia y escenarios"}
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-border pt-3">
          <div>
            <p className="text-[11px] text-gray-400 mb-1 font-semibold">Desglose del Trade Score</p>
            <div className="space-y-1">
              {Object.entries(o.score_breakdown).map(([key, cat]) => (
                <div key={key} className="flex items-center justify-between text-[11px] gap-2">
                  <span className="text-gray-400 w-32 shrink-0">{CATEGORY_LABELS[key] || key}</span>
                  <span className="text-gray-500 flex-1">{cat.note}</span>
                  <span className="text-gray-300 font-medium w-16 text-right">
                    {cat.subscore === null ? "sin datos" : `${cat.subscore.toFixed(1)}/${cat.max}`}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <p className="text-[11px] text-gray-400 mb-1 font-semibold">Escenarios (Scenario Engine)</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
              <div className="bg-panel rounded p-2 border border-border">
                <p className="text-bull font-medium">{o.scenario.primary.type}</p>
                <p className="text-gray-400 mt-1">{o.scenario.primary.conditions}</p>
              </div>
              <div className="bg-panel rounded p-2 border border-border">
                <p className="text-bear font-medium">{o.scenario.alternative.type}</p>
                <p className="text-gray-400 mt-1">{o.scenario.alternative.conditions}</p>
              </div>
              <div className="bg-panel rounded p-2 border border-border">
                <p className="text-neutral font-medium">{o.scenario.range.type}</p>
                <p className="text-gray-400 mt-1">{o.scenario.range.conditions}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TradeFinderCard({ symbol = "BTC/USDT" }: { symbol?: string }) {
  const [timeframe, setTimeframe] = useState("1h");
  const [tradeType, setTradeType] = useState<"LONG" | "SHORT" | "BOTH">("BOTH");
  const [capital, setCapital] = useState(100);
  const [maxRisk, setMaxRisk] = useState(1);
  const [minRoi, setMinRoi] = useState(2);
  const [minRR, setMinRR] = useState(2);
  const [minConfidence, setMinConfidence] = useState(60);
  const [strategy, setStrategy] = useState("");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TradeFinderResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [compareLoading, setCompareLoading] = useState(false);
  const [compareResult, setCompareResult] = useState<
    (TradeFinderResult & { long: TradeOpportunity | null; short: TradeOpportunity | null; winner: string | null; summary: string }) | null
  >(null);

  async function handleSearch() {
    setLoading(true);
    setError(null);
    setCompareResult(null);
    try {
      const res = await findTradeOpportunities({
        symbol,
        timeframe,
        trade_type: tradeType,
        capital,
        max_risk_pct: maxRisk,
        min_roi_pct: minRoi,
        min_risk_reward: minRR,
        min_confidence: minConfidence,
        strategy: strategy || null,
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Error buscando oportunidades.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCompare() {
    setCompareLoading(true);
    setError(null);
    try {
      const res = await compareLongVsShort(symbol, timeframe);
      setCompareResult(res);
      setResult(null);
    } catch (e: any) {
      setError(e.message || "Error comparando LONG vs SHORT.");
    } finally {
      setCompareLoading(false);
    }
  }

  const passing = result?.opportunities?.filter((o) => o.passed_filters) || [];
  const rejected = result?.opportunities?.filter((o) => !o.passed_filters) || [];

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <h3 className="font-semibold text-sm text-gray-300">🔎 Buscar oportunidad (Trade Finder)</h3>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <label className="space-y-1">
            <span className="text-gray-500 block">Timeframe</span>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
            >
              {["5m", "15m", "1h", "4h", "1d"].map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          </label>

          <label className="space-y-1">
            <span className="text-gray-500 block">Tipo</span>
            <select
              value={tradeType}
              onChange={(e) => setTradeType(e.target.value as any)}
              className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
            >
              <option value="BOTH">LONG + SHORT</option>
              <option value="LONG">Solo LONG</option>
              <option value="SHORT">Solo SHORT</option>
            </select>
          </label>

          <label className="space-y-1">
            <span className="text-gray-500 block">Estrategia</span>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
            >
              <option value="">Cualquiera</option>
              {STRATEGIES.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </select>
          </label>

          <label className="space-y-1">
            <span className="text-gray-500 block">Capital ($)</span>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
            />
          </label>

          <label className="space-y-1">
            <span className="text-gray-500 block">Riesgo máx (%)</span>
            <input
              type="number"
              step="0.1"
              value={maxRisk}
              onChange={(e) => setMaxRisk(Number(e.target.value))}
              className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
            />
          </label>

          <label className="space-y-1">
            <span className="text-gray-500 block">ROI mín (%)</span>
            <input
              type="number"
              step="0.1"
              value={minRoi}
              onChange={(e) => setMinRoi(Number(e.target.value))}
              className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
            />
          </label>

          <label className="space-y-1">
            <span className="text-gray-500 block">R:R mín</span>
            <input
              type="number"
              step="0.1"
              value={minRR}
              onChange={(e) => setMinRR(Number(e.target.value))}
              className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
            />
          </label>

          <label className="space-y-1">
            <span className="text-gray-500 block">Confianza mín</span>
            <input
              type="number"
              step="1"
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
            />
          </label>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleSearch}
            disabled={loading}
            className="bg-neutral text-black font-medium px-4 py-2 rounded text-sm hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Buscando..." : "SEARCH OPPORTUNITIES"}
          </button>
          <button
            onClick={handleCompare}
            disabled={compareLoading}
            className="bg-panel border border-border px-4 py-2 rounded text-sm hover:border-neutral disabled:opacity-50"
          >
            {compareLoading ? "Comparando..." : "Compare LONG vs SHORT"}
          </button>
        </div>

        {error && <p className="text-bear text-xs">{error}</p>}
      </div>

      {result?.status === "insufficient_data" && (
        <div className="card text-gray-400 text-sm">{result.message}</div>
      )}

      {result?.status === "ok" && (
        <div className="space-y-3">
          <div className="card text-xs text-gray-400 flex flex-wrap justify-between gap-2">
            <span>
              BTC/USDT @ {fmtUsd(result.price)} · Régimen: <span className="text-gray-200">{result.market_regime}</span>
            </span>
            <span>
              {result.num_passed_filters}/{result.num_candidates} oportunidades cumplen los filtros
            </span>
          </div>

          {passing.length === 0 && (
            <div className="card text-sm text-gray-400">
              🔴 <strong>NO TRADE.</strong> Ninguna dirección cumple los filtros pedidos con los datos actuales.
              Señales insuficientes o contradictorias para este timeframe.
            </div>
          )}

          {passing.map((o, i) => (
            <div key={i}>
              {i === 0 && <p className="text-[11px] text-gray-500 mb-1">🥇 Mejor oportunidad (ranking por R:R → riesgo → confluencia → score → ROI)</p>}
              <OpportunityCard o={o} />
            </div>
          ))}

          {rejected.length > 0 && (
            <details className="text-xs text-gray-500">
              <summary className="cursor-pointer">
                Ver {rejected.length} candidato(s) que no pasaron los filtros
              </summary>
              <div className="space-y-2 mt-2">
                {rejected.map((o, i) => (
                  <OpportunityCard key={i} o={o} />
                ))}
              </div>
            </details>
          )}

          <p className="text-[11px] text-gray-500 border-t border-border pt-2">{result.disclaimer}</p>
        </div>
      )}

      {compareResult?.status === "ok" && (
        <div className="card space-y-3">
          <h3 className="font-semibold text-sm text-gray-300">⚖️ Compare Trade — LONG vs SHORT</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 text-left border-b border-border">
                <th className="py-1">Métrica</th>
                <th className="py-1 text-right text-bull">LONG</th>
                <th className="py-1 text-right text-bear">SHORT</th>
              </tr>
            </thead>
            <tbody className="[&>tr]:border-b [&>tr]:border-border/50">
              <tr>
                <td className="py-1 text-gray-400">Trade Score</td>
                <td className="py-1 text-right">{compareResult.long ? `${compareResult.long.trade_score.toFixed(0)} (${compareResult.long.grade})` : "—"}</td>
                <td className="py-1 text-right">{compareResult.short ? `${compareResult.short.trade_score.toFixed(0)} (${compareResult.short.grade})` : "—"}</td>
              </tr>
              <tr>
                <td className="py-1 text-gray-400">Confluence</td>
                <td className="py-1 text-right">{compareResult.long?.confluence ?? "—"}</td>
                <td className="py-1 text-right">{compareResult.short?.confluence ?? "—"}</td>
              </tr>
              <tr>
                <td className="py-1 text-gray-400">Potential ROI</td>
                <td className="py-1 text-right text-bull">{fmtPct(compareResult.long?.potential_roi_pct)}</td>
                <td className="py-1 text-right text-bull">{fmtPct(compareResult.short?.potential_roi_pct)}</td>
              </tr>
              <tr>
                <td className="py-1 text-gray-400">Risk</td>
                <td className="py-1 text-right text-bear">{fmtPct(compareResult.long ? -compareResult.long.risk_pct : null)}</td>
                <td className="py-1 text-right text-bear">{fmtPct(compareResult.short ? -compareResult.short.risk_pct : null)}</td>
              </tr>
              <tr>
                <td className="py-1 text-gray-400">R:R</td>
                <td className="py-1 text-right">{compareResult.long ? `1:${compareResult.long.risk_reward.toFixed(2)}` : "—"}</td>
                <td className="py-1 text-right">{compareResult.short ? `1:${compareResult.short.risk_reward.toFixed(2)}` : "—"}</td>
              </tr>
              <tr>
                <td className="py-1 text-gray-400">Factores a favor / en contra</td>
                <td className="py-1 text-right">{compareResult.long ? `${compareResult.long.bullish_factors}↑ / ${compareResult.long.bearish_factors}↓` : "—"}</td>
                <td className="py-1 text-right">{compareResult.short ? `${compareResult.short.bearish_factors}↑ / ${compareResult.short.bullish_factors}↓` : "—"}</td>
              </tr>
            </tbody>
          </table>
          <p className="text-xs text-gray-300 border-t border-border pt-2">
            <strong>{compareResult.summary}</strong>
          </p>
        </div>
      )}
    </div>
  );
}
