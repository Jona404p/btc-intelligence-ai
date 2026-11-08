"use client";

import { useState } from "react";
import type { DerivativesSnapshot } from "@/lib/api";
import { syncDerivatives } from "@/lib/api";

function fmt(n?: number, decimals = 2) {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

function fundingColor(rate?: number) {
  if (rate === undefined || rate === null) return "text-gray-400";
  if (rate > 0.0003) return "text-bear";
  if (rate < -0.0003) return "text-bull";
  return "text-gray-200";
}

function lsRatioColor(ratio?: number) {
  if (ratio === undefined || ratio === null) return "text-gray-400";
  if (ratio >= 2.2) return "text-bear";
  if (ratio <= 0.55) return "text-bull";
  return "text-gray-200";
}

export default function DerivativesCard({
  data,
  onRefresh,
}: {
  data: DerivativesSnapshot;
  onRefresh: () => void;
}) {
  const [syncing, setSyncing] = useState(false);

  async function handleSync() {
    setSyncing(true);
    try {
      await syncDerivatives(data.symbol);
      onRefresh();
    } finally {
      setSyncing(false);
    }
  }

  if (data.status !== "ok") {
    return (
      <div className="card space-y-2">
        <h3 className="font-semibold text-sm text-gray-300">Derivatives Dashboard</h3>
        <p className="text-gray-500 text-sm">{data.message || "Sin datos aún."}</p>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="bg-panel border border-border px-3 py-1 rounded text-xs hover:border-neutral disabled:opacity-50"
        >
          {syncing ? "Sincronizando..." : "Sync Derivatives"}
        </button>
      </div>
    );
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm text-gray-300">Derivatives Dashboard</h3>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="text-xs text-gray-400 hover:text-neutral disabled:opacity-50"
        >
          {syncing ? "..." : "🔄 refresh"}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-400 block text-xs">Funding Rate</span>
          <span className={`font-semibold ${fundingColor(data.funding_rate)}`}>
            {data.funding_rate !== undefined && data.funding_rate !== null
              ? `${(data.funding_rate * 100).toFixed(4)}%`
              : "—"}
          </span>
        </div>
        <div>
          <span className="text-gray-400 block text-xs">Long/Short Ratio</span>
          <span className={`font-semibold ${lsRatioColor(data.long_short_ratio)}`}>
            {fmt(data.long_short_ratio)}
          </span>
        </div>
        <div>
          <span className="text-gray-400 block text-xs">Open Interest</span>
          <span>{fmt(data.open_interest, 0)}</span>
        </div>
        <div>
          <span className="text-gray-400 block text-xs">Basis</span>
          <span>{data.basis_pct !== undefined ? `${fmt(data.basis_pct, 3)}%` : "—"}</span>
        </div>
        <div>
          <span className="text-gray-400 block text-xs">Mark Price</span>
          <span>${fmt(data.mark_price)}</span>
        </div>
        <div>
          <span className="text-gray-400 block text-xs">Index Price</span>
          <span>${fmt(data.index_price)}</span>
        </div>
      </div>

      {data.ts && (
        <p className="text-[11px] text-gray-500 pt-1 border-t border-border">
          Última actualización: {new Date(data.ts).toLocaleString()}
        </p>
      )}
    </div>
  );
}
