"use client";

import { useEffect, useRef, useState } from "react";
import { Candle } from "./api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws");

export interface LiveTick {
  price: number;
  changePct: number;
}

interface UseMarketSocketResult {
  liveTick: LiveTick | null;
  liveCandle: Candle | null;
  /** Se actualiza (timestamp) cada vez que una vela del timeframe activo CIERRA. */
  candleClosedAt: number | null;
  connected: boolean;
}

/**
 * Conexión WebSocket en vivo al backend (/market/ws). Reemplaza el polling
 * REST para el precio y la vela en formación: los mensajes llegan push, en
 * cuanto hay un trade nuevo en el exchange, así que el precio y el gráfico
 * se sienten "en vivo" en vez de refrescar cada N segundos.
 *
 * Se reconecta solo si la conexión se cae (red, backend reiniciando, etc.).
 */
export function useMarketSocket(symbol: string, timeframe: string): UseMarketSocketResult {
  const [liveTick, setLiveTick] = useState<LiveTick | null>(null);
  const [liveCandle, setLiveCandle] = useState<Candle | null>(null);
  const [candleClosedAt, setCandleClosedAt] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let retryTimeout: ReturnType<typeof setTimeout>;
    let retryDelay = 1000;

    // El precio/vela en vivo dependen del símbolo Y del timeframe activo
    // (la vela en formación es distinta para 5m que para 1d), así que al
    // cambiar de timeframe reseteamos lo que teníamos en pantalla.
    setLiveTick(null);
    setLiveCandle(null);
    setCandleClosedAt(null);

    function connect() {
      if (cancelled) return;
      const url = `${WS_URL}/market/ws?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(
        timeframe
      )}`;
      const socket = new WebSocket(url);
      wsRef.current = socket;

      socket.onopen = () => {
        retryDelay = 1000;
        setConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "ticker") {
            setLiveTick({ price: msg.price, changePct: msg.change_pct });
          } else if (msg.type === "kline") {
            const c = msg.candle;
            setLiveCandle({
              ts: new Date(c.ts * 1000).toISOString(),
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
              volume: c.volume,
            });
            if (msg.is_final) {
              setCandleClosedAt(Date.now());
            }
          }
        } catch {
          // Mensaje no parseable: lo ignoramos, no vale la pena romper la conexión.
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          retryTimeout = setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 15000);
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(retryTimeout);
      wsRef.current?.close();
    };
  }, [symbol, timeframe]);

  return { liveTick, liveCandle, candleClosedAt, connected };
}
