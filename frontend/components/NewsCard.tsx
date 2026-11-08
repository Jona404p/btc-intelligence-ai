"use client";

import { useState } from "react";
import type { NewsResponse } from "@/lib/api";
import { syncNews, analyzeNewsImpact } from "@/lib/api";

function sentimentColor(sentiment?: string) {
  if (sentiment === "bullish") return "text-bull border-bull";
  if (sentiment === "bearish") return "text-bear border-bear";
  return "text-gray-400 border-border";
}

function sentimentBadge(sentiment?: string) {
  if (sentiment === "bullish") return "🟢";
  if (sentiment === "bearish") return "🔴";
  return "🟡";
}

export default function NewsCard({ data, onRefresh }: { data: NewsResponse; onRefresh: () => void }) {
  const [syncing, setSyncing] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<Record<number, string>>({});

  async function handleSync() {
    setSyncing(true);
    try {
      await syncNews();
      onRefresh();
    } finally {
      setSyncing(false);
    }
  }

  async function handleAnalyze(id: number) {
    setAnalyzingId(id);
    try {
      const result: any = await analyzeNewsImpact(id);
      setAnalysis((prev) => ({ ...prev, [id]: result.analysis || result.message || "Sin respuesta." }));
    } catch (e: any) {
      setAnalysis((prev) => ({ ...prev, [id]: e.message || "Error analizando impacto." }));
    } finally {
      setAnalyzingId(null);
    }
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm text-gray-300">News Intelligence</h3>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="text-xs text-gray-400 hover:text-neutral disabled:opacity-50"
        >
          {syncing ? "..." : "🔄 refresh"}
        </button>
      </div>

      {(!data.news || data.news.length === 0) && (
        <p className="text-gray-500 text-sm">{data.message || "Sin noticias aún."}</p>
      )}

      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
        {data.news?.map((item) => (
          <div key={item.id} className={`border-l-2 pl-2 py-1 ${sentimentColor(item.sentiment)}`}>
            <div className="flex items-start justify-between gap-2">
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-gray-200 hover:underline leading-snug"
              >
                {sentimentBadge(item.sentiment)} {item.title}
              </a>
            </div>
            <div className="flex items-center justify-between mt-1">
              <span className="text-[10px] text-gray-500">
                {item.source} · {new Date(item.ts).toLocaleString()}
              </span>
              <button
                onClick={() => handleAnalyze(item.id)}
                disabled={analyzingId === item.id}
                className="text-[10px] text-gray-400 hover:text-neutral disabled:opacity-50"
              >
                {analyzingId === item.id ? "analizando..." : "Analyze impact"}
              </button>
            </div>
            {analysis[item.id] && (
              <p className="text-[11px] text-gray-400 mt-1 bg-bg/50 p-1.5 rounded">{analysis[item.id]}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
