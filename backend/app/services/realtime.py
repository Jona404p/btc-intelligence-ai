"""
Streaming en tiempo real para el tab de Mercado (Fase 5).

No usamos polling REST para el precio en vivo: nos conectamos al WebSocket
público de Binance (gratis, sin API key) y reenviamos los mensajes ya
traducidos a nuestros clientes conectados por WebSocket en /market/ws.

Dos streams combinados:
  - <symbol>@ticker -> precio actual + % de cambio 24h (varias veces por segundo)
  - <symbol>@kline_<tf> -> la vela en formación del timeframe activo, se
    actualiza en cada trade y trae un flag "is_final" cuando la vela cierra.

Si el exchange configurado (EXCHANGE_ID) no es Binance, igual usamos el
WebSocket público de Binance para el precio en vivo (es el más líquido y
gratuito); los datos históricos de velas siguen viniendo del exchange
configurado vía ccxt, como hasta ahora. Si en el futuro se quiere soportar
otro exchange para el streaming, este es el único lugar a tocar.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream"

# Timeframes que Binance acepta tal cual en el nombre del stream de kline.
SUPPORTED_KLINE_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}


def to_binance_symbol(symbol: str) -> str:
    """'BTC/USDT' -> 'btcusdt' (formato que usa Binance en sus streams)."""
    return symbol.replace("/", "").replace("-", "").lower()


def to_binance_interval(timeframe: str) -> str:
    return timeframe if timeframe in SUPPORTED_KLINE_INTERVALS else "1m"


def stream_url(symbol: str, timeframe: str) -> str:
    sym = to_binance_symbol(symbol)
    interval = to_binance_interval(timeframe)
    streams = f"{sym}@ticker/{sym}@kline_{interval}"
    return f"{BINANCE_WS_BASE}?streams={streams}"


def translate_message(raw: str) -> dict | None:
    """
    Traduce un mensaje del stream combinado de Binance a nuestro formato:
      {"type": "ticker", "price": float, "change_pct": float}
      {"type": "kline", "candle": {...}, "is_final": bool}
    Devuelve None si el mensaje no es relevante (lo ignoramos).
    """
    try:
        outer = json.loads(raw)
        data = outer.get("data", outer)
        event_type = data.get("e")

        if event_type == "24hrTicker":
            return {
                "type": "ticker",
                "price": float(data["c"]),
                "change_pct": float(data["P"]),
            }

        if event_type == "kline":
            k = data["k"]
            return {
                "type": "kline",
                "is_final": bool(k["x"]),
                "candle": {
                    "ts": k["t"] / 1000,  # epoch seconds (inicio de la vela)
                    "open": float(k["o"]),
                    "high": float(k["h"]),
                    "low": float(k["l"]),
                    "close": float(k["c"]),
                    "volume": float(k["v"]),
                },
            }
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.debug("Mensaje de stream ignorado (%s): %s", exc, raw[:200])
    return None
