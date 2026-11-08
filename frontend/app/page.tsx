"use client";

import { useEffect, useState, useCallback } from "react";
import PriceChart from "@/components/PriceChart";
import MarketOverviewCard from "@/components/MarketOverviewCard";
import AIChatCard from "@/components/AIChatCard";
import MultiTimeframeCard from "@/components/MultiTimeframeCard";
import DerivativesCard from "@/components/DerivativesCard";
import NewsCard from "@/components/NewsCard";
import MacroCard from "@/components/MacroCard";
import SentimentCard from "@/components/SentimentCard";
import KnowledgeCenterCard from "@/components/KnowledgeCenterCard";
import HistoricalSimilarityCard from "@/components/HistoricalSimilarityCard";
import AnomalyAlertsCard from "@/components/AnomalyAlertsCard";
import TradeFinderCard from "@/components/TradeFinderCard";
import CalculatorsCard from "@/components/CalculatorsCard";
import Phase7Lab from "@/components/Phase7Lab";
import BinanceFuturesCard from "@/components/BinanceFuturesCard";
import BinanceAICard from "@/components/BinanceAICard";
import Tabs, { TabDef } from "@/components/Tabs";
import { useMarketSocket } from "@/lib/useMarketSocket";
import {
  getOverview,
  getCandles,
  getStructure,
  getMultiTimeframe,
  getDerivatives,
  getNews,
  getMacro,
  getSentiment,
  syncAll,
  Candle,
  BinanceAIProposal,
  MarketOverview,
  MarketStructure,
  MultiTimeframeResult,
  DerivativesSnapshot,
  NewsResponse,
  MacroSnapshot,
  SentimentSnapshot,
} from "@/lib/api";

const TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"];

function biasColor(bias?: string) {
  if (!bias) return "#5b6472";
  const b = bias.toLowerCase();
  if (b.includes("bull") || b.includes("alcist")) return "#16c784";
  if (b.includes("bear") || b.includes("bajist")) return "#ea3943";
  return "#f0b90b";
}

function PriceTicker({
  overview,
  liveTick,
  connected,
}: {
  overview: MarketOverview | null;
  liveTick: { price: number; changePct: number } | null;
  connected: boolean;
}) {
  const price = liveTick?.price ?? overview?.price;
  const change = liveTick?.changePct ?? overview?.change_pct;
  if (price === undefined) return null;
  const positive = (change ?? 0) >= 0;
  return (
    <div className="flex items-baseline gap-3 pl-4 ml-1 border-l border-border">
      <span className="text-lg font-semibold tabular-nums">
        ${price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
      </span>
      {change !== undefined && (
        <span className={`text-sm tabular-nums ${positive ? "text-bull" : "text-bear"}`}>
          {positive ? "+" : ""}
          {change.toFixed(2)}%
        </span>
      )}
      <span
        className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-bull" : "bg-gray-600"}`}
        title={connected ? "En vivo" : "Reconectando..."}
      />
    </div>
  );
}

export default function Home() {
  const [timeframe, setTimeframe] = useState("1h");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [structure, setStructure] = useState<MarketStructure | null>(null);
  const [multiTf, setMultiTf] = useState<MultiTimeframeResult | null>(null);
  const [deriv, setDeriv] = useState<DerivativesSnapshot | null>(null);
  const [newsData, setNewsData] = useState<NewsResponse | null>(null);
  const [macroData, setMacroData] = useState<MacroSnapshot | null>(null);
  const [sentimentData, setSentimentData] = useState<SentimentSnapshot | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("market");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [binanceProposal, setBinanceProposal] = useState<BinanceAIProposal | null>(null);

  useEffect(() => {
    const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
    setTheme(prefersLight ? "light" : "dark");
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("light", theme === "light");
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const { liveTick, liveCandle, candleClosedAt, connected } = useMarketSocket("BTC/USDT", timeframe);

  // Datos ligados al timeframe seleccionado (velas, overview con IA,
  // estructura). Estos son los únicos que necesitan refrescarse cuando el
  // usuario cambia de timeframe o cuando cierra una vela.
  const loadChartData = useCallback(async () => {
    try {
      const [ov, cd, st] = await Promise.all([
        getOverview("BTC/USDT", timeframe),
        getCandles("BTC/USDT", timeframe, 300),
        getStructure("BTC/USDT", timeframe),
      ]);
      setOverview(ov);
      setCandles(cd.candles);
      setStructure(st);
      setErrorMsg(null);
    } catch (e: any) {
      setErrorMsg(e.message || "Error cargando datos del backend.");
    }
  }, [timeframe]);

  // Datos independientes del timeframe (multi-timeframe, derivados, noticias,
  // macro, sentimiento). Antes se pedían junto con lo anterior en un único
  // Promise.all, así que cambiar de timeframe (o el poll de 45s) disparaba
  // estas 5 llamadas también, aunque su resultado no depende del timeframe
  // ni cambia de una pestaña a otra. Separarlas evita ese trabajo repetido.
  const loadGlobalData = useCallback(async () => {
    try {
      const [mtf, dv, nw, mc, sn] = await Promise.all([
        getMultiTimeframe("BTC/USDT"),
        getDerivatives("BTC/USDT"),
        getNews(20),
        getMacro(),
        getSentiment("BTC/USDT"),
      ]);
      setMultiTf(mtf);
      setDeriv(dv);
      setNewsData(nw);
      setMacroData(mc);
      setSentimentData(sn);
    } catch (e: any) {
      setErrorMsg((prev) => prev ?? e.message ?? "Error cargando datos de contexto del backend.");
    }
  }, []);

  // Conveniencia para acciones que sí deben refrescar todo de una (p. ej.
  // después de un sync manual).
  const loadData = useCallback(async () => {
    await Promise.all([loadChartData(), loadGlobalData()]);
  }, [loadChartData, loadGlobalData]);

  useEffect(() => {
    loadChartData();
    // El precio y la vela en formación ya llegan en vivo por WebSocket
    // (useMarketSocket); este poll REST es solo un respaldo para lo que el
    // WS no cubre (estructura, overview con IA) y para que las velas
    // cerradas queden guardadas en la base de datos.
    const interval = setInterval(loadChartData, 45000);
    return () => clearInterval(interval);
  }, [loadChartData]);

  // Los datos de contexto (multi-timeframe, derivados, noticias, macro,
  // sentimiento) se cargan una vez al montar y luego se refrescan a un ritmo
  // más lento, solo mientras el usuario está en una pestaña que realmente
  // los muestra. En "Conocimiento" y "Asistente IA" no hace falta seguir
  // pidiéndolos en segundo plano.
  useEffect(() => {
    const tabsThatNeedGlobalData = ["market", "derivatives", "news-sentiment", "macro"];
    if (!tabsThatNeedGlobalData.includes(activeTab)) return;

    loadGlobalData();
    const interval = setInterval(loadGlobalData, 60000);
    return () => clearInterval(interval);
  }, [activeTab, loadGlobalData]);

  // Refresco "rápido" del overview (ATR%, régimen, bias técnico), SIN pasar
  // por la IA (use_ai=false): son cálculos deterministas sobre las velas ya
  // guardadas, así que son baratos y se pueden pedir cada pocos segundos sin
  // golpear a Ollama. El precio/cambio visibles ya vienen del WebSocket; esto
  // solo mantiene frescos el resto de los campos de la tarjeta de overview.
  const fastRefreshOverview = useCallback(async () => {
    try {
      const fast = await getOverview("BTC/USDT", timeframe, false);
      setOverview((prev) => {
        if (fast.status !== "ok") return prev ?? fast;
        if (!prev || prev.status !== "ok") return fast;
        // Conserva el veredicto de IA (más caro, se refresca en el ciclo lento).
        return {
          ...fast,
          ai_bias: prev.ai_bias,
          ai_confidence: prev.ai_confidence,
          ai_explanation: prev.ai_explanation,
          ai_invalidation: prev.ai_invalidation,
        };
      });
    } catch {
      // Refresco en segundo plano: si falla, simplemente lo reintentamos en el próximo tick.
    }
  }, [timeframe]);

  useEffect(() => {
    // El overview solo se ve en la pestaña "Mercado"; no tiene sentido seguir
    // refrescándolo cada 8s en segundo plano si el usuario está en otra pestaña.
    if (activeTab !== "market") return;
    const interval = setInterval(fastRefreshOverview, 8000);
    return () => clearInterval(interval);
  }, [fastRefreshOverview, activeTab]);

  // En cuanto cierra una vela (llega por WebSocket), refrescamos de inmediato
  // en vez de esperar al próximo tick de 8s: es el momento exacto en que
  // régimen/ATR%/bias técnico realmente pueden cambiar.
  useEffect(() => {
    if (candleClosedAt !== null) {
      fastRefreshOverview();
    }
  }, [candleClosedAt, fastRefreshOverview]);

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await syncAll("BTC/USDT");
      await loadData();
      if (result.status === "partial") {
        setErrorMsg(`Sincronización parcial. Fallaron: ${result.failed_steps.join(", ")}.`);
      } else {
        setErrorMsg(null);
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Error sincronizando datos de mercado.");
    } finally {
      setSyncing(false);
    }
  }

  const tabs: TabDef[] = [
    {
      id: "market",
      label: "Mercado",
      dotColor: biasColor(overview?.ai_bias || overview?.technical_bias),
      content: (
        <div className="space-y-4">
          <div className="flex gap-2">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  tf === timeframe
                    ? "bg-neutral text-white border-neutral shadow-sm"
                    : "bg-panel border-border text-muted hover:text-foreground hover:border-neutral/50"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 card">
              {candles.length > 0 ? (
                <PriceChart
                  candles={candles}
                  liveCandle={liveCandle}
                  timeframe={timeframe}
                  supportLevels={overview?.support_levels}
                  resistanceLevels={overview?.resistance_levels}
                  structureEvents={structure?.events}
                />
              ) : (
                <p className="text-gray-500 text-sm p-8 text-center">
                  No hay velas cargadas. Haz click en &quot;Sync Market Data&quot; para descargar datos
                  reales desde el exchange.
                </p>
              )}
            </div>

            <div className="space-y-4">
              {overview && <MarketOverviewCard data={overview} liveTick={liveTick} connected={connected} />}
              {multiTf && <MultiTimeframeCard data={multiTf} />}
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "derivatives",
      label: "Derivados",
      content: (
        <div className="max-w-2xl">{deriv ? <DerivativesCard data={deriv} onRefresh={loadData} /> : null}</div>
      ),
    },
    {
      id: "news-sentiment",
      label: "Noticias & Sentimiento",
      content: (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          {sentimentData && <SentimentCard data={sentimentData} onRefresh={loadData} />}
          {newsData && <NewsCard data={newsData} onRefresh={loadData} />}
        </div>
      ),
    },
    {
      id: "macro",
      label: "Macro",
      content: <div className="max-w-2xl">{macroData ? <MacroCard data={macroData} onRefresh={loadData} /> : null}</div>,
    },
    {
      id: "knowledge",
      label: "Conocimiento (RAG)",
      content: (
        <div className="max-w-2xl">
          <KnowledgeCenterCard />
        </div>
      ),
    },
    {
      id: "memory-alerts",
      label: "Memoria & Alertas",
      content: (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          <HistoricalSimilarityCard symbol="BTC/USDT" />
          <AnomalyAlertsCard symbol="BTC/USDT" />
        </div>
      ),
    },
    {
      id: "trade-finder",
      label: "Trade Finder",
      content: (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-start">
          <div className="xl:col-span-2">
            <TradeFinderCard symbol="BTC/USDT" />
          </div>
          <CalculatorsCard />
        </div>
      ),
    },
    {
      id: "assistant",
      label: "PanCrasito",
      content: (
        <div className="max-w-2xl">
          <AIChatCard />
        </div>
      ),
    },
    {
      id: "phase7",
      label: "Fase 7 Lab",
      content: <Phase7Lab />,
    },
    {
      id: "binance-futures",
      label: "Binance Futures",
      content: (
        <div className="space-y-4">
          <div className="border-l-2 border-bear pl-4">
            <p className="text-xs uppercase tracking-[0.18em] text-bear">Cuenta de exchange</p>
            <h2 className="mt-1 text-xl font-semibold">Operaciones Binance Futures</h2>
            <p className="mt-1 text-sm text-muted">
              Balance, posiciones y órdenes USDT-M. Comprueba siempre si estás en Testnet o producción antes de operar.
            </p>
          </div>
          <BinanceAICard onApplyProposal={setBinanceProposal} />
          <BinanceFuturesCard proposal={binanceProposal} />
        </div>
      ),
    },
  ];

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-8 space-y-6 max-w-[1480px] mx-auto">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
        <div className="flex items-center gap-4 sm:gap-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-neutral text-lg font-bold text-white shadow-lg shadow-violet-500/20">B</div>
            <div>
              <h1 className="text-lg font-bold tracking-tight sm:text-xl">BTC Intelligence AI</h1>
              <p className="text-muted text-xs sm:text-sm">Market intelligence &amp; AI trading research</p>
            </div>
          </div>
          <PriceTicker overview={overview} liveTick={liveTick} connected={connected} />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={`Cambiar a modo ${theme === "dark" ? "claro" : "oscuro"}`}
            className="bg-panel border border-border px-3 py-2 rounded-lg text-sm text-muted hover:text-foreground hover:border-border-strong transition-colors"
          >
            {theme === "dark" ? "Modo claro" : "Modo oscuro"}
          </button>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="bg-neutral text-white px-4 py-2 rounded-lg text-sm font-medium shadow-lg shadow-violet-500/15 hover:brightness-110 disabled:opacity-50 transition-all"
          >
            {syncing ? "Sincronizando todo..." : "Sincronizar todo"}
          </button>
        </div>
      </header>

      {errorMsg && (
        <div className="card border-bear text-bear text-sm">
          {errorMsg} — Verifica que el backend esté corriendo en http://localhost:8000 y que hayas
          hecho click en &quot;Sync Market Data&quot;.
        </div>
      )}

      <Tabs tabs={tabs} defaultTab="market" onTabChange={setActiveTab} />
    </main>
  );
}
