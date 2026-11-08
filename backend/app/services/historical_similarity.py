"""
Historical Similarity Engine (Fase 5 - sección 21 del spec).

Idea: describir el "setup" actual con un vector de features simple y
explicable (retorno reciente, RSI, cambio de volumen, volatilidad), y
buscar en el propio historial de velas ya guardado momentos que se
parezcan. Para cada match se muestra qué ocurrió después (retorno futuro,
máxima ganancia y máxima pérdida en una ventana fija de velas), para que
el usuario compare escenarios - NUNCA como una predicción garantizada.

IMPORTANTE (regla 37 del spec):
  - No se inventan datos: si no hay suficiente historial guardado (hace
    falta al menos `lookback_window + forward_window` velas antes de
    cualquier candidato), simplemente no se generan matches y se informa
    "datos insuficientes".
  - La similitud es una heurística transparente (distancia euclidiana
    normalizada), no un modelo de probabilidad. Se documenta cada feature
    usada para que el usuario pueda auditar el resultado.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.models import HistoricalSetup
from app.services import indicators, market_data

# Features usadas para describir un "setup". Todas son calculables a partir
# de OHLCV crudo, así que no dependemos de indicadores persistidos aparte.
FEATURE_NAMES = [
    "return_pct",       # retorno acumulado en la ventana de lookback
    "rsi_14",           # nivel de sobrecompra/sobreventa al cierre de la ventana
    "volume_change_pct",  # cambio de volumen promedio vs la ventana anterior
    "volatility_pct",   # ATR% (volatilidad relativa al precio)
    "macd_hist_norm",   # momentum normalizado (MACD histogram / precio)
]

MIN_HISTORY_MULTIPLIER = 1  # margen extra de velas requerido más allá de lookback+forward


def _build_feature_frame(df: pd.DataFrame, lookback_window: int) -> pd.DataFrame:
    """
    Calcula, para cada vela `i` del DataFrame, el vector de features que
    describe la ventana [i - lookback_window, i]. Devuelve un DataFrame
    indexado igual que `df`, con NaN en las filas donde no hay suficiente
    historia previa para calcular todas las features.
    """
    close = df["close"]
    volume = df["volume"]

    return_pct = close.pct_change(periods=lookback_window) * 100

    rsi_series = indicators.rsi(close, period=14)

    vol_recent = volume.rolling(window=lookback_window, min_periods=lookback_window).mean()
    vol_prior = vol_recent.shift(lookback_window)
    volume_change_pct = (vol_recent - vol_prior) / vol_prior.replace(0, np.nan) * 100

    atr_series = indicators.atr(df, period=14)
    volatility_pct = atr_series / close * 100

    _, _, macd_hist = indicators.macd(close)
    macd_hist_norm = macd_hist / close * 100

    features = pd.DataFrame(
        {
            "ts": df["ts"],
            "close": close,
            "return_pct": return_pct,
            "rsi_14": rsi_series,
            "volume_change_pct": volume_change_pct,
            "volatility_pct": volatility_pct,
            "macd_hist_norm": macd_hist_norm,
        }
    )
    return features


def _standardize(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Estandariza columnas (z-score) usando solo los candidatos válidos, para que
    ninguna feature domine la distancia por tener una escala más grande (p.ej. RSI
    0-100 vs return_pct de un par de puntos porcentuales)."""
    mean = np.nanmean(matrix, axis=0)
    std = np.nanstd(matrix, axis=0)
    std[std == 0] = 1.0
    standardized = (matrix - mean) / std
    return standardized, mean, std


def find_similar_setups(
    db: Session,
    symbol: str | None = None,
    timeframe: str = "1h",
    lookback_window: int = 20,
    forward_window: int = 10,
    top_k: int = 5,
    candle_limit: int = 1500,
) -> dict:
    """
    Busca los `top_k` momentos históricos más parecidos al setup actual.

    Devuelve siempre un dict con `status`:
      - "ok": hay matches (puede haber 0 si nada superó el mínimo de similitud).
      - "insufficient_data": no hay suficientes velas guardadas para este
        symbol/timeframe. El usuario debe correr /market/sync primero.
    """
    symbol = symbol or settings.DEFAULT_SYMBOL
    df = market_data.load_candles_df(db, symbol, timeframe, limit=candle_limit)

    min_required = lookback_window + forward_window + 30  # margen para que EMA/RSI/ATR converjan
    if len(df) < min_required:
        return {
            "status": "insufficient_data",
            "symbol": symbol,
            "timeframe": timeframe,
            "message": (
                f"Se necesitan al menos {min_required} velas guardadas para "
                f"{symbol} {timeframe} (hay {len(df)}). Ejecuta /market/sync con un "
                "límite mayor."
            ),
        }

    feat_df = _build_feature_frame(df, lookback_window)

    # El "ancla" (setup actual) es la última fila completa.
    anchor = feat_df.iloc[-1]
    if anchor[FEATURE_NAMES].isna().any():
        return {
            "status": "insufficient_data",
            "symbol": symbol,
            "timeframe": timeframe,
            "message": "No se pudieron calcular todas las features para la vela más reciente (datos insuficientes).",
        }

    # Candidatos: todo punto que tenga features completas Y suficiente historia
    # futura (forward_window velas) para poder decir "qué pasó después". Se
    # excluye la ventana final (la que se solapa con el propio ancla) para no
    # comparar el setup consigo mismo.
    last_valid_idx = len(feat_df) - 1 - forward_window
    candidate_idx = [
        i
        for i in range(lookback_window, last_valid_idx + 1)
        if not feat_df.iloc[i][FEATURE_NAMES].isna().any()
    ]
    # Excluir la propia ventana de anclaje (últimas lookback_window velas).
    candidate_idx = [i for i in candidate_idx if i < len(feat_df) - lookback_window]

    if not candidate_idx:
        return {
            "status": "insufficient_data",
            "symbol": symbol,
            "timeframe": timeframe,
            "message": "No hay suficiente historial previo con features completas para comparar.",
        }

    all_vectors = feat_df.iloc[candidate_idx][FEATURE_NAMES].to_numpy(dtype=float)
    anchor_vector = anchor[FEATURE_NAMES].to_numpy(dtype=float)

    combined = np.vstack([all_vectors, anchor_vector])
    standardized, _, _ = _standardize(combined)
    candidates_std = standardized[:-1]
    anchor_std = standardized[-1]

    distances = np.linalg.norm(candidates_std - anchor_std, axis=1)
    # Similitud en escala 0-100 (100 = idéntico). Distancia 0 -> 100%;
    # se normaliza contra la distancia máxima observada entre candidatos
    # para que el score sea relativo a este propio dataset, no arbitrario.
    max_dist = distances.max() if distances.max() > 0 else 1.0
    similarity_pct = 100 * (1 - distances / max_dist)

    order = np.argsort(distances)[:top_k]

    matches = []
    for rank, pos in enumerate(order, start=1):
        i = candidate_idx[pos]
        row = feat_df.iloc[i]
        entry_close = row["close"]
        exit_close = feat_df.iloc[i + forward_window]["close"]
        window_closes = feat_df.iloc[i : i + forward_window + 1]["close"]

        forward_return_pct = (exit_close - entry_close) / entry_close * 100
        max_gain_pct = (window_closes.max() - entry_close) / entry_close * 100
        max_loss_pct = (window_closes.min() - entry_close) / entry_close * 100

        matches.append(
            {
                "rank": rank,
                "ts": row["ts"].isoformat() if hasattr(row["ts"], "isoformat") else str(row["ts"]),
                "similarity_pct": round(float(similarity_pct[pos]), 1),
                "features_at_match": {k: round(float(row[k]), 2) for k in FEATURE_NAMES},
                "outcome": {
                    "forward_window_candles": forward_window,
                    "forward_return_pct": round(float(forward_return_pct), 2),
                    "max_gain_pct": round(float(max_gain_pct), 2),
                    "max_loss_pct": round(float(max_loss_pct), 2),
                },
            }
        )

    outcomes = [m["outcome"]["forward_return_pct"] for m in matches]
    bullish_count = sum(1 for o in outcomes if o > 0)
    bearish_count = sum(1 for o in outcomes if o < 0)

    result = {
        "status": "ok",
        "symbol": symbol,
        "timeframe": timeframe,
        "lookback_window": lookback_window,
        "forward_window": forward_window,
        "anchor_ts": anchor["ts"].isoformat() if hasattr(anchor["ts"], "isoformat") else str(anchor["ts"]),
        "current_features": {k: round(float(anchor[k]), 2) for k in FEATURE_NAMES},
        "matches": matches,
        "summary": {
            "num_matches": len(matches),
            "bullish_outcomes": bullish_count,
            "bearish_outcomes": bearish_count,
            "avg_forward_return_pct": round(float(np.mean(outcomes)), 2) if outcomes else None,
        },
        "disclaimer": (
            "Similitud calculada sobre datos históricos reales de este mismo símbolo/timeframe. "
            "No es una predicción ni una probabilidad estadística validada; úsalo solo como "
            "contexto adicional."
        ),
    }

    # Persistir para auditoría (sección 21 + 37 del spec: mostrar evidencia).
    row = HistoricalSetup(
        symbol=symbol,
        timeframe=timeframe,
        ts=datetime.now(timezone.utc),
        anchor_ts=anchor["ts"],
        current_features=result["current_features"],
        matches=matches,
        num_matches=len(matches),
    )
    db.add(row)
    db.commit()

    return result


def get_history(db: Session, symbol: str, timeframe: str | None = None, limit: int = 20) -> list[dict]:
    """Últimas consultas de similitud ya resueltas y persistidas (para auditoría rápida sin recalcular)."""
    from sqlalchemy import select

    stmt = select(HistoricalSetup).where(HistoricalSetup.symbol == symbol)
    if timeframe:
        stmt = stmt.where(HistoricalSetup.timeframe == timeframe)
    stmt = stmt.order_by(HistoricalSetup.ts.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "ts": r.ts,
            "timeframe": r.timeframe,
            "anchor_ts": r.anchor_ts,
            "num_matches": r.num_matches,
            "current_features": r.current_features,
        }
        for r in rows
    ]
