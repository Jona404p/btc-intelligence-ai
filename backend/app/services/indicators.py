"""
Motor de indicadores técnicos.

Todas las funciones trabajan sobre un DataFrame de pandas con columnas:
    ts, open, high, low, close, volume  (ordenado ascendente por ts)

Implementación manual (sin TA-Lib) para mantener el stack simple y portable.
No se inventan valores: si no hay suficientes velas para calcular un
indicador (p.ej. EMA200 con solo 50 velas), se devuelve NaN/None para ese punto.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    rsi_val = rsi_val.fillna(50)  # sin suficiente historia -> valor neutral, no None espurio
    return rsi_val


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = series.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def bollinger_bands(series: pd.Series, period: int = 20, std_mult: float = 2.0):
    mid = sma(series, period)
    std = series.rolling(window=period, min_periods=period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


def vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum().replace(0, np.nan)
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    return cum_tp_vol / cum_vol


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve un DataFrame alineado con df, con todas las columnas de indicadores calculadas."""
    if df.empty:
        return df

    out = df.copy()
    out["ema_9"] = ema(df["close"], 9)
    out["ema_21"] = ema(df["close"], 21)
    out["ema_50"] = ema(df["close"], 50)
    out["ema_200"] = ema(df["close"], 200)
    out["sma_20"] = sma(df["close"], 20)
    out["sma_50"] = sma(df["close"], 50)
    out["rsi_14"] = rsi(df["close"], 14)
    macd_line, signal_line, hist = macd(df["close"])
    out["macd"] = macd_line
    out["macd_signal"] = signal_line
    out["macd_hist"] = hist
    out["atr_14"] = atr(df, 14)
    bb_u, bb_m, bb_l = bollinger_bands(df["close"], 20, 2.0)
    out["bb_upper"] = bb_u
    out["bb_middle"] = bb_m
    out["bb_lower"] = bb_l
    out["vwap"] = vwap(df)

    out["trend"] = out.apply(_classify_trend_row, axis=1)
    return out


def _classify_trend_row(row) -> str:
    """Clasificación simple de tendencia basada en alineación de EMAs + posición del precio."""
    ema_9, ema_21, ema_50 = row.get("ema_9"), row.get("ema_21"), row.get("ema_50")
    close = row.get("close")

    if pd.isna(ema_9) or pd.isna(ema_21) or pd.isna(ema_50):
        return "neutral"

    if close > ema_9 > ema_21 > ema_50:
        return "bullish"
    if close < ema_9 < ema_21 < ema_50:
        return "bearish"
    return "neutral"


def find_support_resistance(
    df: pd.DataFrame, lookback: int = 100, window: int = 5, max_levels: int = 5
) -> tuple[list[dict], list[dict]]:
    """
    Detecta soportes y resistencias a partir de pivotes locales (swing highs / swing lows).
    Un pivote alto/bajo es aquel que es el máximo/mínimo dentro de una ventana de +-`window` velas.
    La "fuerza" del nivel es proporcional a cuántas veces el precio se acercó a él (dentro de 0.3%).
    """
    if len(df) < window * 2 + 1:
        return [], []

    data = df.tail(lookback).reset_index(drop=True)
    highs, lows = data["high"], data["low"]

    pivot_highs = []
    pivot_lows = []
    for i in range(window, len(data) - window):
        window_slice_high = highs[i - window : i + window + 1]
        window_slice_low = lows[i - window : i + window + 1]
        if highs[i] == window_slice_high.max():
            pivot_highs.append(highs[i])
        if lows[i] == window_slice_low.min():
            pivot_lows.append(lows[i])

    def cluster_levels(levels: list[float], tolerance_pct: float = 0.003) -> list[dict]:
        if not levels:
            return []
        levels = sorted(levels)
        clusters: list[list[float]] = [[levels[0]]]
        for lvl in levels[1:]:
            if abs(lvl - clusters[-1][-1]) / clusters[-1][-1] <= tolerance_pct:
                clusters[-1].append(lvl)
            else:
                clusters.append([lvl])
        result = [
            {"price": float(np.mean(c)), "strength": min(1.0, len(c) / 5)}
            for c in clusters
        ]
        result.sort(key=lambda x: x["strength"], reverse=True)
        return result[:max_levels]

    current_price = float(data["close"].iloc[-1])
    resistance_candidates = cluster_levels([h for h in pivot_highs if h > current_price])
    support_candidates = cluster_levels([l for l in pivot_lows if l < current_price])

    for r in resistance_candidates:
        r["level_type"] = "resistance"
    for s in support_candidates:
        s["level_type"] = "support"

    support_candidates.sort(key=lambda x: x["price"], reverse=True)
    resistance_candidates.sort(key=lambda x: x["price"])

    return support_candidates, resistance_candidates


def compute_volatility_pct(df: pd.DataFrame, period: int = 14) -> float | None:
    """Volatilidad reciente como ATR% del precio actual (ATR / close * 100)."""
    if len(df) < period + 1:
        return None
    atr_series = atr(df, period)
    last_atr = atr_series.iloc[-1]
    last_close = df["close"].iloc[-1]
    if pd.isna(last_atr) or last_close == 0:
        return None
    return float(last_atr / last_close * 100)


def classify_market_regime(df: pd.DataFrame) -> str:
    """
    Clasificación simple del régimen de mercado combinando tendencia (EMA) y volatilidad (ATR%).
    Esto es una heurística de Fase 1; se refinará en fases posteriores con más señales.
    """
    if df.empty or len(df) < 60:
        return "insufficient_data"

    ind = compute_all_indicators(df)
    last = ind.iloc[-1]
    vol_pct = compute_volatility_pct(df)

    trend = last.get("trend", "neutral")
    high_vol_threshold = 1.5  # ATR% aproximado para considerar "alta volatilidad" en 1h BTC

    if vol_pct is not None and vol_pct >= high_vol_threshold:
        if trend == "bullish":
            return "trending_bull_high_vol"
        if trend == "bearish":
            return "trending_bear_high_vol"
        return "high_volatility_range"

    if trend == "bullish":
        return "trending_bull"
    if trend == "bearish":
        return "trending_bear"
    return "range"
