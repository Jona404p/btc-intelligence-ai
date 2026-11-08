"use client";

import { useState } from "react";
import type { HistoricalSimilarityResult } from "@/lib/api";
import { getSimilarSetups } from "@/lib/api";

function fmtPct(n?: number | null) {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function outcomeColor(pct: number) {
  if (pct > 0) return "text-bull";
  if (pct < 0) return "text-bear";
  return "text-gray-300";
}

const FEATURE_LABELS: Record<string, string> = {
  return_pct: "Retorno (ventana)",
  rsi_14: "RSI 14",
  volume_change_pct: "Cambio de volumen",
  volatility_pct: "Volatilidad (ATR%)",
  macd_hist_norm: "Momentum (MACD)",
};

export default function HistoricalSimilarityCard({ symbol = "BTC/USDT" }: { symbol?: string }) {
  const [timeframe, setTimeframe] = useState("1h");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HistoricalSimilarityResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch() {
    setLoading(true);
    setError(null);
    try {
      const res = await getSimilarSetups(symbol, timeframe);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Error buscando setups históricos similares.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm text-gray-300">Historical Similarity Engine</h3>
        <div className="flex gap-2 items-center">
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-panel border border-border rounded text-xs px-2 py-1 text-gray-300"
          >
            {["5m", "15m", "1h", "4h", "1d"].map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="bg-panel border border-border px-3 py-1 rounded text-xs hover:border-neutral disabled:opacity-50"
          >
            {loading ? "Buscando..." : "Buscar similares"}
          </button>
        </div>
      </div>

      {error && <p className="text-bear text-xs">{error}</p>}

      {!result && !loading && (
        <p className="text-gray-500 text-sm">
          Compara el setup actual contra el historial guardado de este mismo símbolo/timeframe.
        </p>
      )}

      {result?.status === "insufficient_data" && (
        <p className="text-gray-500 text-sm">{result.message}</p>
      )}

      {result?.status === "ok" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
            {Object.entries(result.current_features || {}).map(([k, v]) => (
              <div key={k}>
                <span className="text-gray-400 block">{FEATURE_LABELS[k] || k}</span>
                <span className="text-gray-200 font-medium">{v}</span>
              </div>
            ))}
          </div>

          {result.summary && (
            <p className="text-xs text-gray-400 border-t border-border pt-2">
              {result.summary.num_matches} matches encontrados — {result.summary.bullish_outcomes}{" "}
              con desenlace alcista, {result.summary.bearish_outcomes} con desenlace bajista.
              Retorno futuro promedio:{" "}
              <span className={outcomeColor(result.summary.avg_forward_return_pct || 0)}>
                {fmtPct(result.summary.avg_forward_return_pct)}
              </span>
            </p>
          )}

          <div className="space-y-2">
            {result.matches?.map((m) => (
              <div key={m.rank} className="border border-border rounded p-2 text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-gray-300">
                    #{m.rank} · {new Date(m.ts).toLocaleString()}
                  </span>
                  <span className="text-neutral font-medium">{m.similarity_pct}% similar</span>
                </div>
                <div className="flex gap-3">
                  <span className={outcomeColor(m.outcome.forward_return_pct)}>
                    Retorno +{m.outcome.forward_window_candles} velas: {fmtPct(m.outcome.forward_return_pct)}
                  </span>
                  <span className="text-bull">Máx. ganancia: {fmtPct(m.outcome.max_gain_pct)}</span>
                  <span className="text-bear">Máx. pérdida: {fmtPct(m.outcome.max_loss_pct)}</span>
                </div>
              </div>
            ))}
          </div>

          <p className="text-[11px] text-gray-500 border-t border-border pt-2">
            {result.disclaimer}
          </p>
        </div>
      )}
    </div>
  );
}
