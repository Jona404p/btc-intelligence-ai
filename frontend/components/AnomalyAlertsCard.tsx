"use client";

import { useState } from "react";
import type { AnomalySignal, CombinedAlert } from "@/lib/api";
import { scanAnomalies, getLatestAnomalies } from "@/lib/api";

function severityColor(sev: string) {
  if (sev === "critical") return "border-bear text-bear";
  if (sev === "warning") return "border-yellow-600 text-yellow-500";
  return "border-border text-gray-300";
}

function directionColor(dir: string | null) {
  if (dir === "bullish") return "text-bull";
  if (dir === "bearish") return "text-bear";
  return "text-gray-400";
}

export default function AnomalyAlertsCard({
  symbol = "BTC/USDT",
  initialSignals,
}: {
  symbol?: string;
  initialSignals?: AnomalySignal[];
}) {
  const [signals, setSignals] = useState<AnomalySignal[]>(initialSignals || []);
  const [combined, setCombined] = useState<CombinedAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleScan() {
    setLoading(true);
    setError(null);
    try {
      const scan = await scanAnomalies(symbol);
      setCombined(scan.combined_alerts);
      const latest = await getLatestAnomalies(symbol, 50);
      setSignals(latest.signals);
    } catch (e: any) {
      setError(e.message || "Error escaneando anomalías.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm text-gray-300">Anomaly Detector</h3>
        <button
          onClick={handleScan}
          disabled={loading}
          className="bg-panel border border-border px-3 py-1 rounded text-xs hover:border-neutral disabled:opacity-50"
        >
          {loading ? "Escaneando..." : "🔍 Escanear ahora"}
        </button>
      </div>

      {error && <p className="text-bear text-xs">{error}</p>}

      {combined.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-400">Alertas combinadas (multi-señal)</p>
          {combined.map((c, i) => (
            <div key={i} className={`border rounded p-2 text-xs space-y-1 ${severityColor(c.severity)}`}>
              <div className="flex justify-between">
                <span className="font-medium">{c.signal_type.replace(/_/g, " ")}</span>
                <span className={directionColor(c.direction)}>{c.direction || ""}</span>
              </div>
              <p className="text-gray-300">{c.message}</p>
              <p className="text-[10px] text-gray-500">Basado en: {c.based_on.join(", ")}</p>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-1">
        <p className="text-xs text-gray-400">Últimas señales</p>
        {signals.length === 0 && (
          <p className="text-gray-500 text-sm">Sin señales aún. Ejecuta un escaneo.</p>
        )}
        <div className="max-h-64 overflow-y-auto space-y-1">
          {signals.map((s, i) => (
            <div key={i} className="flex items-start justify-between text-xs border-b border-border/50 py-1">
              <div className="flex-1">
                <span className="text-gray-500">[{s.category}]</span>{" "}
                <span className="text-gray-300">{s.message}</span>
              </div>
              <span className="text-[10px] text-gray-500 whitespace-nowrap pl-2">
                {new Date(s.ts).toLocaleTimeString()}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
