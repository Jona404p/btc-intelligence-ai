"use client";

import { useState } from "react";
import { calculateROI, calculatePositionSize, ROICalculatorResult, PositionSizeResult } from "@/lib/api";

function fmtUsd(n?: number | null) {
  if (n === undefined || n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtPct(n?: number | null) {
  if (n === undefined || n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export default function CalculatorsCard() {
  const [tab, setTab] = useState<"roi" | "size">("roi");

  // ROI calculator state
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [capital, setCapital] = useState(100);
  const [entry, setEntry] = useState(103400);
  const [exitPrice, setExitPrice] = useState(105500);
  const [stop, setStop] = useState<number | "">(102700);
  const [leverage, setLeverage] = useState(1);
  const [roiResult, setRoiResult] = useState<ROICalculatorResult | null>(null);
  const [roiLoading, setRoiLoading] = useState(false);

  // Position size calculator state
  const [psCapital, setPsCapital] = useState(1000);
  const [psRisk, setPsRisk] = useState(1);
  const [psEntry, setPsEntry] = useState(103400);
  const [psStop, setPsStop] = useState(102900);
  const [psLeverage, setPsLeverage] = useState(1);
  const [psResult, setPsResult] = useState<PositionSizeResult | null>(null);
  const [psLoading, setPsLoading] = useState(false);

  async function handleRoi() {
    setRoiLoading(true);
    try {
      const res = await calculateROI({
        capital,
        entry,
        exit_price: exitPrice,
        stop: stop === "" ? null : stop,
        leverage,
        direction,
      });
      setRoiResult(res);
    } finally {
      setRoiLoading(false);
    }
  }

  async function handlePositionSize() {
    setPsLoading(true);
    try {
      const res = await calculatePositionSize({
        capital: psCapital,
        risk_pct: psRisk,
        entry: psEntry,
        stop: psStop,
        leverage: psLeverage,
      });
      setPsResult(res);
    } finally {
      setPsLoading(false);
    }
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="font-semibold text-sm text-gray-300 flex-1">🧮 Calculadoras</h3>
        <button
          onClick={() => setTab("roi")}
          className={`text-xs px-3 py-1 rounded border ${tab === "roi" ? "bg-neutral text-black border-neutral" : "border-border text-gray-400"}`}
        >
          ROI
        </button>
        <button
          onClick={() => setTab("size")}
          className={`text-xs px-3 py-1 rounded border ${tab === "size" ? "bg-neutral text-black border-neutral" : "border-border text-gray-400"}`}
        >
          Position Size
        </button>
      </div>

      {tab === "roi" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <label className="space-y-1">
              <span className="text-gray-500 block">Dirección</span>
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value as any)}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
              >
                <option value="long">LONG</option>
                <option value="short">SHORT</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Capital ($)</span>
              <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Leverage (x)</span>
              <input type="number" step="0.5" value={leverage} onChange={(e) => setLeverage(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Entry</span>
              <input type="number" value={entry} onChange={(e) => setEntry(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Exit</span>
              <input type="number" value={exitPrice} onChange={(e) => setExitPrice(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Stop (opcional)</span>
              <input
                type="number"
                value={stop}
                onChange={(e) => setStop(e.target.value === "" ? "" : Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200"
              />
            </label>
          </div>

          <button
            onClick={handleRoi}
            disabled={roiLoading}
            className="bg-neutral text-black font-medium px-4 py-2 rounded text-sm hover:opacity-90 disabled:opacity-50"
          >
            {roiLoading ? "Calculando..." : "Calcular ROI"}
          </button>

          {roiResult?.status === "error" && <p className="text-bear text-xs">{roiResult.message}</p>}

          {roiResult?.status === "ok" && (
            <div className="space-y-2 border-t border-border pt-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div><span className="text-gray-500 block">ROI del activo</span><span className={roiResult.asset_roi_pct! >= 0 ? "text-bull font-medium" : "text-bear font-medium"}>{fmtPct(roiResult.asset_roi_pct)}</span></div>
                <div><span className="text-gray-500 block">ROI sobre capital</span><span className={(roiResult.capital_roi_pct ?? 0) >= 0 ? "text-bull font-medium" : "text-bear font-medium"}>{fmtPct(roiResult.capital_roi_pct)}</span></div>
                <div><span className="text-gray-500 block">PnL neto</span><span className={roiResult.net_pnl_usd! >= 0 ? "text-bull font-medium" : "text-bear font-medium"}>{fmtUsd(roiResult.net_pnl_usd)}</span></div>
                <div><span className="text-gray-500 block">Fees estimadas</span><span className="text-gray-300 font-medium">{fmtUsd(roiResult.fees_usd)}</span></div>
                <div><span className="text-gray-500 block">Tamaño posición</span><span className="text-gray-300 font-medium">{fmtUsd(roiResult.position_size_usd)}</span></div>
                <div><span className="text-gray-500 block">Capital usado</span><span className="text-gray-300 font-medium">{fmtUsd(roiResult.capital_used)}</span></div>
                {roiResult.risk_pct !== undefined && (
                  <>
                    <div><span className="text-gray-500 block">Riesgo</span><span className="text-bear font-medium">-{roiResult.risk_pct.toFixed(2)}%</span></div>
                    <div><span className="text-gray-500 block">R:R</span><span className="text-gray-300 font-medium">{roiResult.risk_reward ? `1:${roiResult.risk_reward.toFixed(2)}` : "—"}</span></div>
                  </>
                )}
              </div>
              <p className="text-[11px] text-gray-500">{roiResult.note}</p>
            </div>
          )}
        </div>
      )}

      {tab === "size" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <label className="space-y-1">
              <span className="text-gray-500 block">Capital ($)</span>
              <input type="number" value={psCapital} onChange={(e) => setPsCapital(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Riesgo (%)</span>
              <input type="number" step="0.1" value={psRisk} onChange={(e) => setPsRisk(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Leverage (x)</span>
              <input type="number" step="0.5" value={psLeverage} onChange={(e) => setPsLeverage(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Entry</span>
              <input type="number" value={psEntry} onChange={(e) => setPsEntry(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
            <label className="space-y-1">
              <span className="text-gray-500 block">Stop</span>
              <input type="number" value={psStop} onChange={(e) => setPsStop(Number(e.target.value))}
                className="bg-panel border border-border rounded px-2 py-1 w-full text-gray-200" />
            </label>
          </div>

          <button
            onClick={handlePositionSize}
            disabled={psLoading}
            className="bg-neutral text-black font-medium px-4 py-2 rounded text-sm hover:opacity-90 disabled:opacity-50"
          >
            {psLoading ? "Calculando..." : "Calcular Position Size"}
          </button>

          {psResult?.status === "error" && <p className="text-bear text-xs">{psResult.message}</p>}

          {psResult?.status === "ok" && (
            <div className="space-y-2 border-t border-border pt-3">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                <div><span className="text-gray-500 block">Stop distance</span><span className="text-gray-300 font-medium">{psResult.stop_distance_pct?.toFixed(3)}%</span></div>
                <div><span className="text-gray-500 block">Riesgo máximo</span><span className="text-bear font-medium">{fmtUsd(psResult.max_risk_usd ? -psResult.max_risk_usd : null)}</span></div>
                <div><span className="text-gray-500 block">Position Size</span><span className="text-gray-300 font-medium">{fmtUsd(psResult.position_size_usd)}</span></div>
                <div><span className="text-gray-500 block">Tamaño en BTC</span><span className="text-gray-300 font-medium">{psResult.position_size_asset}</span></div>
                <div><span className="text-gray-500 block">Capital requerido</span><span className="text-gray-300 font-medium">{fmtUsd(psResult.capital_required)}</span></div>
              </div>
              {psResult.warning && <p className="text-[11px] text-neutral">{psResult.warning}</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
