"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, IPriceLine } from "lightweight-charts";
import type { Candle, StructureEvent } from "@/lib/api";

interface Props {
  candles: Candle[];
  liveCandle?: Candle | null;
  timeframe?: string;
  supportLevels?: number[];
  resistanceLevels?: number[];
  structureEvents?: StructureEvent[];
}

type ChartCandle = { time: any; open: number; high: number; low: number; close: number };

function normalizeCandles(items: Candle[]): ChartCandle[] {
  const byTime = new Map<number, Candle>();
  for (const candle of items) {
    const time = Math.floor(new Date(candle.ts).getTime() / 1000);
    if (Number.isFinite(time)) byTime.set(time, candle);
  }
  return [...byTime.entries()]
    .sort(([left], [right]) => left - right)
    .map(([time, candle]) => ({ time: time as any, open: candle.open, high: candle.high, low: candle.low, close: candle.close }));
}

function markerData(events: StructureEvent[]) {
  const byTime = new Map<number, { time: any; position: "belowBar" | "aboveBar"; color: string; shape: "arrowUp" | "arrowDown"; text: string }>();
  for (const event of events) {
    const time = Math.floor(new Date(event.ts).getTime() / 1000);
    if (!Number.isFinite(time)) continue;
    byTime.set(time, {
      time: time as any,
      position: event.direction === "bullish" ? "belowBar" : "aboveBar",
      color: event.direction === "bullish" ? "#16c784" : "#ea3943",
      shape: event.direction === "bullish" ? "arrowUp" : "arrowDown",
      text: event.event_type,
    });
  }
  return [...byTime.values()].sort((left, right) => (left.time as number) - (right.time as number));
}

export default function PriceChart({
  candles,
  liveCandle,
  timeframe,
  supportLevels = [],
  resistanceLevels = [],
  structureEvents = [],
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lastFittedTimeframe = useRef<string | undefined>(undefined);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  // Huella de los últimos datos pintados, para no repetir setData/createPriceLine
  // cuando el poll de refresco trae exactamente lo mismo que ya está en pantalla
  // (p. ej. mientras no cierra una vela nueva).
  const lastPaintedSignature = useRef<string>("");
  const lastSeriesTime = useRef<number | null>(null);
  const lastMarkersSignature = useRef<string>("");

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#12161c" },
        textColor: "#c8ccd1",
      },
      grid: {
        vertLines: { color: "#1f2530" },
        horzLines: { color: "#1f2530" },
      },
      width: Math.max(containerRef.current.clientWidth, 320),
      height: 420,
      timeScale: { timeVisible: true, secondsVisible: false },
    });

    const series = chart.addCandlestickSeries({
      upColor: "#16c784",
      downColor: "#ea3943",
      borderVisible: false,
      wickUpColor: "#16c784",
      wickDownColor: "#ea3943",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: Math.max(containerRef.current.clientWidth, 320) });
      }
    };
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(containerRef.current);

    return () => {
      window.removeEventListener("resize", handleResize);
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || candles.length === 0) return;

    // Firma barata de los datos a pintar: si no cambió nada respecto al
    // último render (mismo número de velas, misma última vela, mismos
    // niveles), nos ahorramos volver a llamar setData/createPriceLine.
    // Esto evita trabajo redundante en cada poll de 45s cuando todavía no
    // cerró una vela nueva (el precio en vivo ya lo maneja el efecto de
    // liveCandle, por separado, sin pasar por aquí).
    const first = candles[0];
    const last = candles[candles.length - 1];
    const signature = JSON.stringify([
      candles.length,
      first.ts,
      first.open,
      last.ts,
      last.open,
      last.high,
      last.low,
      last.close,
      supportLevels.join(","),
      resistanceLevels.join(","),
    ]);
    if (signature === lastPaintedSignature.current) {
      return;
    }
    lastPaintedSignature.current = signature;

    const data = normalizeCandles(candles);
    if (data.length === 0) return;
    seriesRef.current.setData(data);
    lastSeriesTime.current = data[data.length - 1].time as number;

    // Limpiamos las líneas de soporte/resistencia anteriores antes de
    // agregar las nuevas: sin esto, cada refresco (cada 45s) iba dejando
    // líneas viejas sin borrar, acumulándose para siempre y degradando el
    // render con el tiempo.
    priceLinesRef.current.forEach((line) => seriesRef.current?.removePriceLine(line));
    priceLinesRef.current = [];

    supportLevels.forEach((price) => {
      const line = seriesRef.current?.createPriceLine({
        price,
        color: "#16c784",
        lineWidth: 1,
        lineStyle: 2,
        title: "Support",
      });
      if (line) priceLinesRef.current.push(line);
    });
    resistanceLevels.forEach((price) => {
      const line = seriesRef.current?.createPriceLine({
        price,
        color: "#ea3943",
        lineWidth: 1,
        lineStyle: 2,
        title: "Resistance",
      });
      if (line) priceLinesRef.current.push(line);
    });

    // Solo re-encuadramos la vista cuando cambia el timeframe (o en la carga
    // inicial). Si hiciéramos fitContent() en cada refresco periódico, cada
    // actualización "en vivo" le resetearía el zoom/pan al usuario.
    if (lastFittedTimeframe.current !== timeframe) {
      chartRef.current?.timeScale().fitContent();
      lastFittedTimeframe.current = timeframe;
    }
  }, [candles, supportLevels, resistanceLevels, timeframe]);

  // Vela en formación en vivo (llega por WebSocket, sin polling). Usamos
  // series.update() en vez de setData(): actualiza solo la última vela (o
  // agrega una nueva si el tiempo avanzó) sin tocar el resto del gráfico ni
  // el zoom/scroll del usuario.
  useEffect(() => {
    if (!seriesRef.current || !liveCandle) return;
    const time = Math.floor(new Date(liveCandle.ts).getTime() / 1000);
    if (!Number.isFinite(time)) return;
    // Binance/REST can briefly deliver an older event after a refresh. The
    // chart library rejects updates older than its last data point.
    if (lastSeriesTime.current !== null && time < lastSeriesTime.current) return;
    seriesRef.current.update({
      time: time as any,
      open: liveCandle.open,
      high: liveCandle.high,
      low: liveCandle.low,
      close: liveCandle.close,
    });
    lastSeriesTime.current = time;
  }, [liveCandle]);

  useEffect(() => {
    if (!seriesRef.current) return;

    const markers = markerData(structureEvents);
    const signature = JSON.stringify(markers);
    if (signature === lastMarkersSignature.current) return;
    lastMarkersSignature.current = signature;
    seriesRef.current.setMarkers(markers);
  }, [structureEvents]);

  return <div ref={containerRef} className="w-full" />;
}
