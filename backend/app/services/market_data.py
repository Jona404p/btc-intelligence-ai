"""
Servicio de datos de mercado.

Responsable de:
  - Conectarse a un exchange real (por defecto Binance) vía ccxt.
  - Descargar velas OHLCV para BTC/USDT en distintos timeframes.
  - Persistir esas velas en TimescaleDB (tabla market_candles).
  - Exponer utilidades para leer velas ya guardadas como DataFrame de pandas.

IMPORTANTE: este módulo NUNCA inventa datos. Si el exchange no responde,
se propaga el error en lugar de generar datos sintéticos.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import ccxt
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarketCandle

logger = logging.getLogger(__name__)

# Caché muy corta (TTL en segundos) de las velas ya cargadas desde la DB.
#
# El frontend dispara varios endpoints en paralelo que leen exactamente las
# mismas velas (p. ej. /market/candles y /market/structure piden ambos las
# últimas 300 velas del mismo symbol+timeframe dentro del mismo Promise.all).
# Sin caché, eso son N round-trips idénticos a la base de datos por cada
# refresco. Un TTL de un par de segundos es más que suficiente: las velas
# cerradas no cambian dentro de ese margen, y la vela en formación ya llega
# en vivo por WebSocket (no depende de este endpoint).
_CANDLES_CACHE_TTL_SECONDS = 2.0
_candles_cache: dict[tuple[str, str, int], tuple[float, pd.DataFrame]] = {}


def invalidate_candles_cache(symbol: str | None = None, timeframe: str | None = None) -> None:
    """Limpia la caché de velas (usado tras sincronizar datos nuevos del exchange)."""
    if symbol is None and timeframe is None:
        _candles_cache.clear()
        return
    for key in [k for k in _candles_cache if (symbol is None or k[0] == symbol) and (timeframe is None or k[1] == timeframe)]:
        _candles_cache.pop(key, None)


def get_exchange() -> ccxt.Exchange:
    """Crea un cliente público para datos de mercado, sin usar credenciales privadas."""
    exchange_class = getattr(ccxt, settings.EXCHANGE_ID)
    exchange = exchange_class(
        {
            "enableRateLimit": True,
        }
    )
    return exchange


def fetch_ohlcv(
    symbol: str = None,
    timeframe: str = "1h",
    limit: int = 500,
    since_ms: int | None = None,
) -> list[list]:
    """Descarga velas OHLCV crudas desde el exchange. Devuelve la lista tal cual ccxt la entrega."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    exchange = get_exchange()
    return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit, since=since_ms)


def upsert_candles(db: Session, symbol: str, timeframe: str, raw_candles: list[list]) -> int:
    """Guarda velas en la base de datos. Usa UPSERT para evitar duplicados si se re-descarga un rango."""
    if not raw_candles:
        return 0

    rows = []
    for c in raw_candles:
        ts_ms, o, h, l, close, vol = c
        rows.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "ts": datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                "open": o,
                "high": h,
                "low": l,
                "close": close,
                "volume": vol,
                "source": settings.EXCHANGE_ID,
            }
        )

    stmt = pg_insert(MarketCandle).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "timeframe", "ts"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
        },
    )
    db.execute(stmt)
    db.commit()
    invalidate_candles_cache(symbol, timeframe)
    return len(rows)


def sync_symbol(db: Session, symbol: str = None, timeframes: list[str] | None = None, limit: int = 500) -> dict:
    """Sincroniza (descarga + guarda) las últimas velas para un símbolo en varios timeframes."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    timeframes = timeframes or settings.timeframes

    results = {}
    for tf in timeframes:
        try:
            raw = fetch_ohlcv(symbol=symbol, timeframe=tf, limit=limit)
            saved = upsert_candles(db, symbol, tf, raw)
            results[tf] = {"status": "ok", "candles_saved": saved}
            logger.info("Synced %s %s: %s candles", symbol, tf, saved)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed syncing %s %s", symbol, tf)
            results[tf] = {"status": "error", "error": str(exc)}
    return results


def load_candles_df(db: Session, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """Carga las últimas N velas de la base de datos como DataFrame ordenado ascendentemente por tiempo.

    Usa una caché corta en memoria (ver _CANDLES_CACHE_TTL_SECONDS) para evitar
    volver a pegarle a la DB cuando varios endpoints piden el mismo
    symbol+timeframe+limit dentro de la misma ventana de refresco.
    """
    cache_key = (symbol, timeframe, limit)
    cached = _candles_cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and (now - cached[0]) < _CANDLES_CACHE_TTL_SECONDS:
        return cached[1].copy()

    df = _load_candles_df_uncached(db, symbol, timeframe, limit)
    _candles_cache[cache_key] = (now, df)
    return df.copy()


def _load_candles_df_uncached(db: Session, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    stmt = (
        select(MarketCandle)
        .where(MarketCandle.symbol == symbol, MarketCandle.timeframe == timeframe)
        .order_by(MarketCandle.ts.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    if not rows:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    data = [
        {
            "ts": r.ts,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
        }
        for r in rows
    ]
    df = pd.DataFrame(data).sort_values("ts").reset_index(drop=True)
    return df


def get_latest_price(db: Session, symbol: str, timeframe: str = "5m") -> float | None:
    df = load_candles_df(db, symbol, timeframe, limit=1)
    if df.empty:
        return None
    return float(df.iloc[-1]["close"])
