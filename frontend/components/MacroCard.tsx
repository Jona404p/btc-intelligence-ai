"use client";

import { useState } from "react";
import type { MacroSnapshot } from "@/lib/api";
import { syncMacro } from "@/lib/api";

const LABELS: Record<string, string> = {
  DXY: "DXY",
  SPX: "S&P 500",
  NDX: "NASDAQ",
  VIX: "VIX",
  US10Y: "US 10Y",
  GOLD: "Gold",
};

function changeColor(pct?: number) {
  if (pct === undefined || pct === null) return "text-gray-400";
  if (pct > 0) return "text-bull";
  if (pct < 0) return "text-bear";
  return "text-gray-200";
}

function regimeColor(regime?: string) {
  if (regime === "RISK-ON") return "text-bull";
  if (regime === "RISK-OFF") return "text-bear";
  return "text-neutral";
}

export default function MacroCard({ data, onRefresh }: { data: MacroSnapshot; onRefresh: () => void }) {
  const [syncing, setSyncing] = useState(false);

  async function handleSync() {
    setSyncing(true);
    try {
      await syncMacro();
      onRefresh();
    } finally {
      setSyncing(false);
    }
  }

  if (data.status !== "ok") {
    return (
      <div className="card space-y-2">
        <h3 className="font-semibold text-sm text-gray-300">Macro Dashboard</h3>
        <p className="text-gray-500 text-sm">{data.message || "Sin datos aún."}</p>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="bg-panel border border-border px-3 py-1 rounded text-xs hover:border-neutral disabled:opacity-50"
        >
          {syncing ? "Sincronizando..." : "Sync Macro"}
        </button>
      </div>
    );
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm text-gray-300">Macro Dashboard</h3>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="text-xs text-gray-400 hover:text-neutral disabled:opacity-50"
        >
          {syncing ? "..." : "🔄 refresh"}
        </button>
      </div>

      {data.risk_environment && (
        <div className={`text-sm font-semibold ${regimeColor(data.risk_environment.regime)}`}>
          {data.risk_environment.regime}
          <span className="text-gray-500 font-normal text-xs ml-2">
            (score {data.risk_environment.score})
          </span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 text-sm">
        {Object.entries(data.indicators || {}).map(([key, ind]) => (
          <div key={key}>
            <span className="text-gray-400 block text-xs">{LABELS[key] || key}</span>
            <span>
              {ind.value !== undefined ? ind.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}
            </span>{" "}
            {ind.change_pct !== undefined && ind.change_pct !== null && (
              <span className={`text-xs ${changeColor(ind.change_pct)}`}>
                ({ind.change_pct > 0 ? "+" : ""}
                {ind.change_pct.toFixed(2)}%)
              </span>
            )}
          </div>
        ))}
      </div>

      {data.risk_environment?.factors && data.risk_environment.factors.length > 0 && (
        <p className="text-[11px] text-gray-500 pt-1 border-t border-border">
          {data.risk_environment.factors.join(" · ")}
        </p>
      )}
    </div>
  );
}
