"""
Anomaly Detector (Fase 5 - sección 23 del spec).

Detecta anomalías de precio y volumen usando z-scores sobre el propio
historial de velas (sin necesitar datos externos), y las combina con las
anomalías ya detectadas en otros módulos (derivados: funding, OI,
long/short ratio - ver `services/derivatives.py`) que quedaron persistidas
en la tabla `signals`.

Cuando varias anomalías independientes coinciden en una ventana corta de
tiempo (p.ej. spike de precio + spike de volumen + funding extremo), se
genera además una alerta "combinada" tipo "posible short squeeze" - la
misma idea que la sección 23 del spec ilustra con su ejemplo.

Reglas (sección 37 del spec): nunca se inventan datos ni se garantiza que
una anomalía se traduzca en un movimiento futuro; solo se describe lo que
ya ocurrió, con el umbral usado, para que sea auditable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Signal
from app.services import market_data

# --- Umbrales (documentados, ajustables) ---
PRICE_ZSCORE_THRESHOLD = 2.5      # movimiento de precio "anómalo" en la ventana corta
VOLUME_ZSCORE_THRESHOLD = 2.5     # volumen "anómalo" vs su propio promedio móvil
SHORT_WINDOW_CANDLES = 3          # ventana "corta" para medir el movimiento súbito
ROLLING_WINDOW_CANDLES = 50       # ventana usada para calcular media/desviación típica
COMBINED_ALERT_WINDOW_MINUTES = 30  # qué tan cerca en el tiempo deben ocurrir las señales


def detect_price_volume_anomalies(
    db: Session, symbol: str | None = None, timeframe: str = "5m"
) -> list[dict]:
    """
    Calcula z-scores de:
      - retorno de las últimas SHORT_WINDOW_CANDLES velas, contra la
        distribución de retornos de ese mismo tamaño de ventana en las
        últimas ROLLING_WINDOW_CANDLES velas.
      - volumen de la última vela, contra la media/desviación de volumen
        de las últimas ROLLING_WINDOW_CANDLES velas.

    Persiste cada anomalía detectada como Signal (category='price' o 'volume').
    """
    symbol = symbol or settings.DEFAULT_SYMBOL
    df = market_data.load_candles_df(
        db, symbol, timeframe, limit=ROLLING_WINDOW_CANDLES + SHORT_WINDOW_CANDLES + 5
    )

    min_required = ROLLING_WINDOW_CANDLES + SHORT_WINDOW_CANDLES
    if len(df) < min_required:
        return []

    anomalies: list[dict] = []
    ts_now = df.iloc[-1]["ts"]
    if hasattr(ts_now, "to_pydatetime"):
        ts_now = ts_now.to_pydatetime()

    # --- Anomalía de precio ---
    rolling_returns = df["close"].pct_change(periods=SHORT_WINDOW_CANDLES) * 100
    rolling_returns_hist = rolling_returns.iloc[-ROLLING_WINDOW_CANDLES:-1].dropna()
    current_return = rolling_returns.iloc[-1]

    if len(rolling_returns_hist) >= 10 and not np.isnan(current_return):
        mean_r = rolling_returns_hist.mean()
        std_r = rolling_returns_hist.std() or 1e-9
        z_price = (current_return - mean_r) / std_r

        if abs(z_price) >= PRICE_ZSCORE_THRESHOLD:
            direction = "bullish" if z_price > 0 else "bearish"
            anomalies.append(
                {
                    "signal_type": "price_anomaly",
                    "category": "price",
                    "severity": "warning",
                    "direction": direction,
                    "message": (
                        f"Movimiento de precio inusual: {current_return:+.2f}% en las últimas "
                        f"{SHORT_WINDOW_CANDLES} velas de {timeframe} (z-score {z_price:+.2f}, "
                        f"umbral ±{PRICE_ZSCORE_THRESHOLD})."
                    ),
                    "payload": {
                        "return_pct": round(float(current_return), 2),
                        "z_score": round(float(z_price), 2),
                        "window_candles": SHORT_WINDOW_CANDLES,
                        "timeframe": timeframe,
                    },
                }
            )

    # --- Anomalía de volumen ---
    vol_hist = df["volume"].iloc[-ROLLING_WINDOW_CANDLES:-1]
    current_vol = df["volume"].iloc[-1]
    mean_v = vol_hist.mean()
    std_v = vol_hist.std() or 1e-9
    z_vol = (current_vol - mean_v) / std_v

    if z_vol >= VOLUME_ZSCORE_THRESHOLD:
        vol_change_pct = (current_vol - mean_v) / mean_v * 100 if mean_v else None
        anomalies.append(
            {
                "signal_type": "volume_anomaly",
                "category": "volume",
                "severity": "info",
                "direction": None,
                "message": (
                    f"Volumen inusualmente alto en {timeframe}: "
                    f"{vol_change_pct:+.0f}% sobre el promedio móvil (z-score {z_vol:+.2f})."
                    if vol_change_pct is not None
                    else f"Volumen inusualmente alto en {timeframe} (z-score {z_vol:+.2f})."
                ),
                "payload": {
                    "volume": round(float(current_vol), 2),
                    "z_score": round(float(z_vol), 2),
                    "timeframe": timeframe,
                },
            }
        )

    for a in anomalies:
        db.add(
            Signal(
                symbol=symbol,
                ts=ts_now,
                category=a["category"],
                signal_type=a["signal_type"],
                severity=a["severity"],
                direction=a.get("direction"),
                message=a["message"],
                payload=a["payload"],
            )
        )
    if anomalies:
        db.commit()

    return anomalies


def get_recent_signals(db: Session, symbol: str, minutes: int = COMBINED_ALERT_WINDOW_MINUTES) -> list[Signal]:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    stmt = (
        select(Signal)
        .where(Signal.symbol == symbol, Signal.ts >= since)
        .order_by(Signal.ts.desc())
    )
    return list(db.execute(stmt).scalars().all())


def build_combined_alerts(recent_signals: list[Signal]) -> list[dict]:
    """
    Busca patrones conocidos entre señales recientes de distintas categorías
    (sección 23 del spec: p.ej. price + volume + OI apuntando a un squeeze).
    Esto es una capa de correlación simple sobre señales YA detectadas -
    no inventa ninguna señal nueva.
    """
    by_type = {s.signal_type: s for s in recent_signals}
    combined: list[dict] = []

    has_price_up = any(
        s.signal_type == "price_anomaly" and s.direction == "bullish" for s in recent_signals
    )
    has_price_down = any(
        s.signal_type == "price_anomaly" and s.direction == "bearish" for s in recent_signals
    )
    has_volume_spike = "volume_anomaly" in by_type
    has_short_squeeze_setup = "funding_extreme_negative" in by_type or "long_short_ratio_extreme_low" in by_type
    has_long_squeeze_setup = "funding_extreme_positive" in by_type or "long_short_ratio_extreme_high" in by_type
    has_oi_spike = "open_interest_spike" in by_type

    if has_price_up and has_volume_spike and has_short_squeeze_setup:
        combined.append(
            {
                "signal_type": "potential_short_squeeze",
                "severity": "warning",
                "direction": "bullish",
                "message": (
                    "Subida de precio + spike de volumen + funding/long-short ratio ya sesgado "
                    "corto: patrón compatible con un potencial short squeeze."
                ),
                "based_on": [s.signal_type for s in recent_signals if s.signal_type in by_type],
            }
        )
    if has_price_down and has_volume_spike and has_long_squeeze_setup:
        combined.append(
            {
                "signal_type": "potential_long_squeeze",
                "severity": "warning",
                "direction": "bearish",
                "message": (
                    "Caída de precio + spike de volumen + funding/long-short ratio ya sesgado "
                    "largo: patrón compatible con un potencial long squeeze."
                ),
                "based_on": [s.signal_type for s in recent_signals if s.signal_type in by_type],
            }
        )
    if has_oi_spike and has_volume_spike and (has_price_up or has_price_down):
        combined.append(
            {
                "signal_type": "high_conviction_move",
                "severity": "info",
                "direction": "bullish" if has_price_up else "bearish",
                "message": (
                    "Movimiento de precio acompañado de spike de volumen Y de Open Interest: "
                    "sugiere posiciones nuevas entrando (no solo cierre de posiciones existentes)."
                ),
                "based_on": [s.signal_type for s in recent_signals if s.signal_type in by_type],
            }
        )

    return combined


def scan(db: Session, symbol: str | None = None, timeframe: str = "5m") -> dict:
    """Corre la detección de precio/volumen y arma las alertas combinadas con lo ya visto."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    new_anomalies = detect_price_volume_anomalies(db, symbol, timeframe)
    recent = get_recent_signals(db, symbol)
    combined = build_combined_alerts(recent)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "ts": datetime.now(timezone.utc),
        "new_anomalies": new_anomalies,
        "combined_alerts": combined,
        "recent_signals_considered": len(recent),
    }


def get_latest(db: Session, symbol: str, limit: int = 50) -> list[dict]:
    """Devuelve las últimas señales/anomalías persistidas para mostrar en el dashboard."""
    stmt = (
        select(Signal)
        .where(Signal.symbol == symbol)
        .order_by(Signal.ts.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "ts": r.ts,
            "category": r.category,
            "signal_type": r.signal_type,
            "severity": r.severity,
            "direction": r.direction,
            "message": r.message,
        }
        for r in rows
    ]
