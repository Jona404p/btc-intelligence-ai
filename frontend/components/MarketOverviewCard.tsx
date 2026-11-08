import type { MarketOverview } from "@/lib/api";

function biasColor(bias?: string) {
  if (!bias) return "text-neutral";
  const b = bias.toLowerCase();
  if (b.includes("bull")) return "text-bull";
  if (b.includes("bear")) return "text-bear";
  return "text-neutral";
}

function fmt(n?: number, decimals = 2) {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

export default function MarketOverviewCard({
  data,
  liveTick,
  connected,
}: {
  data: MarketOverview;
  liveTick?: { price: number; changePct: number } | null;
  connected?: boolean;
}) {
  if (data.status !== "ok") {
    return (
      <div className="card">
        <p className="text-neutral">{data.message || "Sin datos aún."}</p>
      </div>
    );
  }

  // El precio y el % de cambio se muestran en vivo (WebSocket, tick a tick);
  // el resto (ATR%, régimen, bias técnico) se recalcula desde el backend
  // cada pocos segundos sin pasar por la IA, para que se sienta "en vivo"
  // sin golpear a Ollama en cada refresh.
  const displayPrice = liveTick?.price ?? data.price;
  const displayChangePct = liveTick?.changePct ?? data.change_pct;

  return (
    <div className="card space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          {data.symbol}
          <span
            className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-bull" : "bg-gray-600"}`}
            title={connected ? "Precio en vivo" : "Reconectando..."}
          />
        </h2>
        <span className={`text-2xl font-bold ${biasColor(data.technical_bias)}`}>
          ${fmt(displayPrice)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-400">Cambio: </span>
          <span className={(displayChangePct || 0) >= 0 ? "text-bull" : "text-bear"}>
            {fmt(displayChangePct)}%
          </span>
        </div>
        <div>
          <span className="text-gray-400">Volatilidad (ATR%): </span>
          <span>{fmt(data.volatility_pct)}%</span>
        </div>
        <div>
          <span className="text-gray-400">Régimen: </span>
          <span className="uppercase">{data.market_regime}</span>
        </div>
        <div>
          <span className="text-gray-400">Bias técnico: </span>
          <span className={biasColor(data.technical_bias)}>{data.technical_bias}</span>
        </div>
      </div>

      <div className="border-t border-border pt-3">
        <div className="flex items-center justify-between">
          <span className="text-gray-400 text-sm">AI Market Bias</span>
          {data.ai_confidence !== undefined && data.ai_confidence !== null && (
            <span className="text-xs text-gray-400">Confianza: {fmt(data.ai_confidence, 0)}/100</span>
          )}
        </div>
        <p className={`text-lg font-bold ${biasColor(data.ai_bias)}`}>{data.ai_bias || "N/A"}</p>
        {data.ai_explanation && <p className="text-sm text-gray-300 mt-1">{data.ai_explanation}</p>}
        {data.ai_invalidation && (
          <p className="text-xs text-gray-500 mt-1">Invalidación: {data.ai_invalidation}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-border">
        <div>
          <p className="text-gray-400 mb-1">Soportes</p>
          {(data.support_levels || []).map((p) => (
            <p key={p} className="text-bull">${fmt(p)}</p>
          ))}
        </div>
        <div>
          <p className="text-gray-400 mb-1">Resistencias</p>
          {(data.resistance_levels || []).map((p) => (
            <p key={p} className="text-bear">${fmt(p)}</p>
          ))}
        </div>
      </div>

      <p className="text-[11px] text-gray-500 pt-2 border-t border-border">
        Esto no es asesoramiento financiero ni garantía de resultados. Información con fines de
        análisis y evaluación de riesgo.
      </p>
    </div>
  );
}
