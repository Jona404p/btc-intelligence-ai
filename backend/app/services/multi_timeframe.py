"""
Multi-Timeframe Analysis.

Calcula, para cada timeframe configurado, un resumen de tendencia/estructura y
produce un "consensus" agregando cuántos timeframes están bullish/bearish/neutral.

No pondera timeframes de forma arbitraria: simplemente cuenta, y dejamos que el
usuario (o capas superiores como el Confluence Engine en fases futuras) decida
qué peso darle a cada uno.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.services import market_data, indicators, market_structure


def analyze_timeframe(db: Session, symbol: str, timeframe: str, limit: int = 300) -> dict:
    df = market_data.load_candles_df(db, symbol, timeframe, limit=limit)
    if df.empty or len(df) < 30:
        return {
            "timeframe": timeframe,
            "status": "no_data",
            "trend": "unknown",
            "message": "Sin suficientes velas. Ejecuta /market/sync para este timeframe.",
        }

    ind_df = indicators.compute_all_indicators(df)
    last = ind_df.iloc[-1]

    structure = market_structure.analyze_market_structure(df)

    return {
        "timeframe": timeframe,
        "status": "ok",
        "price": float(last["close"]),
        "trend": last.get("trend", "neutral"),
        "rsi_14": None if last.get("rsi_14") != last.get("rsi_14") else round(float(last["rsi_14"]), 2),
        "macd_hist": None if last.get("macd_hist") != last.get("macd_hist") else float(last["macd_hist"]),
        "structure_trend": structure["current_trend"],
        "last_structure_event": structure["events"][-1] if structure["events"] else None,
        "candles_analyzed": len(df),
    }


def multi_timeframe_consensus(
    db: Session, symbol: str = None, timeframes: list[str] | None = None
) -> dict:
    symbol = symbol or settings.DEFAULT_SYMBOL
    timeframes = timeframes or settings.timeframes

    per_tf = {}
    for tf in timeframes:
        per_tf[tf] = analyze_timeframe(db, symbol, tf)

    valid = [v for v in per_tf.values() if v["status"] == "ok"]
    bullish = sum(1 for v in valid if v["trend"] == "bullish")
    bearish = sum(1 for v in valid if v["trend"] == "bearish")
    neutral = sum(1 for v in valid if v["trend"] == "neutral")

    total = len(valid)
    if total == 0:
        consensus = "insufficient_data"
    elif bullish >= total * 0.6:
        consensus = "bullish"
    elif bearish >= total * 0.6:
        consensus = "bearish"
    else:
        consensus = "mixed"

    return {
        "symbol": symbol,
        "timeframes": per_tf,
        "summary": {
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "total_analyzed": total,
            "consensus": consensus,
        },
    }
