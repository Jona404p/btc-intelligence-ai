import type { MultiTimeframeResult } from "@/lib/api";

function trendColor(trend?: string) {
  if (!trend) return "text-gray-400";
  if (trend === "bullish") return "text-bull";
  if (trend === "bearish") return "text-bear";
  return "text-neutral";
}

function consensusColor(consensus: string) {
  if (consensus === "bullish") return "text-bull";
  if (consensus === "bearish") return "text-bear";
  if (consensus === "mixed") return "text-neutral";
  return "text-gray-500";
}

export default function MultiTimeframeCard({ data }: { data: MultiTimeframeResult }) {
  const order = ["5m", "15m", "1h", "4h", "1d", "1w"];
  const entries = Object.entries(data.timeframes).sort(
    ([a], [b]) => order.indexOf(a) - order.indexOf(b)
  );

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm text-gray-300">Multi-Timeframe Consensus</h3>
        <span className={`text-sm font-bold uppercase ${consensusColor(data.summary.consensus)}`}>
          {data.summary.consensus}
        </span>
      </div>

      <div className="space-y-1">
        {entries.map(([tf, info]) => (
          <div key={tf} className="flex items-center justify-between text-sm border-b border-border/50 pb-1">
            <span className="text-gray-400 w-10">{tf}</span>
            {info.status === "ok" ? (
              <>
                <span className={`font-semibold uppercase ${trendColor(info.trend)}`}>{info.trend}</span>
                <span className="text-xs text-gray-500">RSI {info.rsi_14 ?? "—"}</span>
                <span className={`text-xs ${trendColor(info.structure_trend)}`}>
                  Struct: {info.structure_trend ?? "—"}
                </span>
              </>
            ) : (
              <span className="text-xs text-gray-600">sin datos</span>
            )}
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-500 pt-1">
        {data.summary.bullish_count}/{data.summary.total_analyzed} timeframes bullish ·{" "}
        {data.summary.bearish_count}/{data.summary.total_analyzed} bearish
      </p>
    </div>
  );
}
