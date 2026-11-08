"""
Motor de Market Structure (estructura de mercado tipo price action / smart money concepts).

Conceptos implementados:
  - Swing highs / swing lows (pivotes) usando una ventana de N velas a cada lado.
  - Estructura de tendencia: secuencia de HH/HL (uptrend) o LH/LL (downtrend).
  - BOS (Break of Structure): el precio rompe el último swing en la dirección de la
    tendencia vigente -> confirma continuación de tendencia.
  - CHOCH (Change of Character): el precio rompe un swing en la dirección OPUESTA a la
    tendencia vigente -> primera señal de posible cambio de tendencia.

Esto es una heurística de price action, no una verdad matemática absoluta. Se etiqueta
todo con el precio y timestamp exactos que lo generaron para que sea auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SwingPoint:
    index: int
    ts: pd.Timestamp
    price: float
    kind: str  # "high" | "low"


@dataclass
class StructureEvent:
    ts: pd.Timestamp
    price: float
    event_type: str      # "BOS" | "CHOCH"
    direction: str        # "bullish" | "bearish"
    broken_level: float
    note: str


def find_swing_points(df: pd.DataFrame, window: int = 3) -> list[SwingPoint]:
    """Detecta swing highs y swing lows: un punto es swing si es el extremo local en +-window velas."""
    swings: list[SwingPoint] = []
    highs, lows = df["high"], df["low"]
    n = len(df)

    for i in range(window, n - window):
        local_high = highs[i - window : i + window + 1]
        local_low = lows[i - window : i + window + 1]

        if highs[i] == local_high.max() and (local_high == highs[i]).sum() == 1:
            swings.append(SwingPoint(index=i, ts=df["ts"].iloc[i], price=float(highs[i]), kind="high"))
        if lows[i] == local_low.min() and (local_low == lows[i]).sum() == 1:
            swings.append(SwingPoint(index=i, ts=df["ts"].iloc[i], price=float(lows[i]), kind="low"))

    swings.sort(key=lambda s: s.index)
    return swings


def _alternate_swings(swings: list[SwingPoint]) -> list[SwingPoint]:
    """Se queda solo con la alternancia high/low/high/low, descartando swings redundantes
    del mismo tipo consecutivo (se queda con el más extremo)."""
    if not swings:
        return []

    cleaned: list[SwingPoint] = [swings[0]]
    for s in swings[1:]:
        last = cleaned[-1]
        if s.kind == last.kind:
            if s.kind == "high" and s.price > last.price:
                cleaned[-1] = s
            elif s.kind == "low" and s.price < last.price:
                cleaned[-1] = s
            # si no es más extremo, se descarta
        else:
            cleaned.append(s)
    return cleaned


def analyze_market_structure(df: pd.DataFrame, window: int = 3) -> dict:
    """
    Analiza la estructura de mercado completa de un DataFrame de velas (ordenado ascendente).

    Devuelve:
      - swings: lista de swing points detectados (alternados)
      - current_trend: "bullish" | "bearish" | "undefined"
      - events: lista de eventos BOS/CHOCH detectados en orden cronológico
      - key_levels: último swing high y swing low relevantes (para invalidación)
    """
    if len(df) < window * 4:
        return {
            "swings": [],
            "current_trend": "undefined",
            "events": [],
            "key_levels": {},
            "message": "Datos insuficientes para análisis de estructura.",
        }

    raw_swings = find_swing_points(df, window=window)
    swings = _alternate_swings(raw_swings)

    if len(swings) < 4:
        return {
            "swings": [_swing_to_dict(s) for s in swings],
            "current_trend": "undefined",
            "events": [],
            "key_levels": {},
            "message": "Aún no hay suficientes swings alternados para determinar estructura.",
        }

    events: list[StructureEvent] = []
    trend = "undefined"

    # Determinamos tendencia inicial comparando los primeros dos highs y dos lows disponibles
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if len(highs) >= 2 and len(lows) >= 2:
        if highs[1].price > highs[0].price and lows[1].price > lows[0].price:
            trend = "bullish"
        elif highs[1].price < highs[0].price and lows[1].price < lows[0].price:
            trend = "bearish"

    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None

    for s in swings:
        if s.kind == "high":
            if last_high is not None:
                if s.price > last_high.price:
                    # Higher high
                    if trend == "bearish":
                        events.append(
                            StructureEvent(
                                ts=s.ts, price=s.price, event_type="CHOCH", direction="bullish",
                                broken_level=last_high.price,
                                note=f"Ruptura alcista de swing high previo (${last_high.price:,.2f}); posible cambio de carácter.",
                            )
                        )
                        trend = "bullish"
                    elif trend == "bullish":
                        events.append(
                            StructureEvent(
                                ts=s.ts, price=s.price, event_type="BOS", direction="bullish",
                                broken_level=last_high.price,
                                note=f"Continuación alcista: rompe swing high previo (${last_high.price:,.2f}).",
                            )
                        )
            last_high = s
        else:
            if last_low is not None:
                if s.price < last_low.price:
                    # Lower low
                    if trend == "bullish":
                        events.append(
                            StructureEvent(
                                ts=s.ts, price=s.price, event_type="CHOCH", direction="bearish",
                                broken_level=last_low.price,
                                note=f"Ruptura bajista de swing low previo (${last_low.price:,.2f}); posible cambio de carácter.",
                            )
                        )
                        trend = "bearish"
                    elif trend == "bearish":
                        events.append(
                            StructureEvent(
                                ts=s.ts, price=s.price, event_type="BOS", direction="bearish",
                                broken_level=last_low.price,
                                note=f"Continuación bajista: rompe swing low previo (${last_low.price:,.2f}).",
                            )
                        )
            last_low = s

    key_levels = {
        "last_swing_high": last_high.price if last_high else None,
        "last_swing_low": last_low.price if last_low else None,
    }

    return {
        "swings": [_swing_to_dict(s) for s in swings],
        "current_trend": trend,
        "events": [_event_to_dict(e) for e in events],
        "key_levels": key_levels,
        "message": None,
    }


def _swing_to_dict(s: SwingPoint) -> dict:
    return {"ts": s.ts, "price": s.price, "kind": s.kind}


def _event_to_dict(e: StructureEvent) -> dict:
    return {
        "ts": e.ts,
        "price": e.price,
        "event_type": e.event_type,
        "direction": e.direction,
        "broken_level": e.broken_level,
        "note": e.note,
    }
