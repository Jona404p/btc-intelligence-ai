"use client";

import { useState } from "react";
import type { SentimentSnapshot } from "@/lib/api";
import { syncSentiment } from "@/lib/api";

function fngColor(classification?: string) {
  if (!classification) return "text-gray-400";
  const c = classification.toLowerCase();
  if (c.includes("extreme greed")) return "text-bull";
  if (c.includes("greed")) return "text-bull";
  if (c.includes("extreme fear")) return "text-bear";
  if (c.includes("fear")) return "text-bear";
  return "text-neutral";
}

function overallColor(sentiment?: string) {
  if (sentiment === "BULLISH") return "text-bull";
  if (sentiment === "BEARISH") return "text-bear";
  return "text-neutral";
}

export default function SentimentCard({
  data,
  onRefresh,
}: {
  data: SentimentSnapshot;
  onRefresh: () => void;
}) {
  const [syncing, setSyncing] = useState(false);

  async function handleSync() {
    setSyncing(true);
    try {
      await syncSentiment(data.symbol);
      onRefresh();
    } finally {
      setSyncing(false);
    }
  }

  if (data.status !== "ok") {
    return (
      <div className="card space-y-2">
        <h3 className="font-semibold text-sm text-gray-300">Sentiment</h3>
        <p className="text-gray-500 text-sm">{data.message || "Sin datos aún."}</p>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="bg-panel border border-border px-3 py-1 rounded text-xs hover:border-neutral disabled:opacity-50"
        >
          {syncing ? "Sincronizando..." : "Sync Sentiment"}
        </button>
      </div>
    );
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm text-gray-300">Sentiment</h3>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="text-xs text-gray-400 hover:text-neutral disabled:opacity-50"
        >
          {syncing ? "..." : "🔄 refresh"}
        </button>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <span className="text-gray-400 block text-xs">Fear & Greed Index</span>
          <span className={`font-semibold ${fngColor(data.fng_classification)}`}>
            {data.fng_value !== undefined ? data.fng_value : "—"} · {data.fng_classification || "—"}
          </span>
        </div>
        <div className="text-right">
          <span className="text-gray-400 block text-xs">Overall</span>
          <span className={`font-semibold ${overallColor(data.overall_sentiment)}`}>
            {data.overall_sentiment || "—"}
          </span>
        </div>
      </div>

      {data.news_sample_size ? (
        <div className="space-y-1">
          <span className="text-gray-400 block text-xs">
            News sentiment ({data.news_sample_size} artículos)
          </span>
          <div className="flex h-2 rounded overflow-hidden border border-border">
            <div className="bg-bull" style={{ width: `${data.news_bullish_pct || 0}%` }} />
            <div className="bg-neutral" style={{ width: `${data.news_neutral_pct || 0}%` }} />
            <div className="bg-bear" style={{ width: `${data.news_bearish_pct || 0}%` }} />
          </div>
          <div className="flex justify-between text-[10px] text-gray-500">
            <span>🟢 {data.news_bullish_pct ?? 0}%</span>
            <span>🟡 {data.news_neutral_pct ?? 0}%</span>
            <span>🔴 {data.news_bearish_pct ?? 0}%</span>
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-500">Sin noticias suficientes para calcular distribución.</p>
      )}

      {data.ts && (
        <p className="text-[11px] text-gray-500 pt-1 border-t border-border">
          Última actualización: {new Date(data.ts).toLocaleString()}
        </p>
      )}
    </div>
  );
}
