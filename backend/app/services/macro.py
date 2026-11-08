"""
Macro Dashboard (Fase 3, sección 19 del spec).

Descarga datos REALES de mercados macro vía Yahoo Finance (`yfinance`), sin
necesidad de API key. Si un ticker falla (rate-limit, símbolo no disponible),
se omite y se registra el error — nunca se inventa un valor.

Clasifica el entorno como RISK-ON / NEUTRAL / RISK-OFF con una heurística
simple y documentada, basada en cuántos indicadores se mueven "a favor" de
activos de riesgo (equities arriba, VIX abajo, DXY abajo) vs en contra.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MacroData

logger = logging.getLogger(__name__)

# symbol_local -> ticker de Yahoo Finance
TICKERS = {
    "DXY": "DX-Y.NYB",
    "SPX": "^GSPC",
    "NDX": "^IXIC",
    "VIX": "^VIX",
    "US10Y": "^TNX",   # rendimiento a 10 años * 10 (convención de Yahoo)
    "GOLD": "GC=F",
}


def fetch_macro_snapshot() -> dict:
    """
    Descarga el último precio y variación diaria de cada ticker.
    Cada indicador se intenta de forma independiente: un fallo no bloquea al resto.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance no está instalado. Agrega 'yfinance' a requirements.txt.")
        return {"ts": datetime.now(timezone.utc), "indicators": {}, "errors": {"_all": "yfinance not installed"}}

    ts = datetime.now(timezone.utc)
    indicators: dict[str, dict] = {}
    errors: dict[str, str] = {}

    for local_symbol, yf_ticker in TICKERS.items():
        try:
            ticker = yf.Ticker(yf_ticker)
            hist = ticker.history(period="5d", interval="1d")
            if hist.empty or len(hist) < 1:
                errors[local_symbol] = "sin datos históricos disponibles"
                continue
            last_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_close
            change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close else None
            indicators[local_symbol] = {"value": last_close, "change_pct": change_pct}
        except Exception as exc:  # noqa: BLE001
            errors[local_symbol] = str(exc)

    return {"ts": ts, "indicators": indicators, "errors": errors}


def save_snapshot(db: Session, snapshot: dict) -> list[MacroData]:
    rows = []
    for indicator, data in snapshot["indicators"].items():
        row = MacroData(
            ts=snapshot["ts"],
            indicator=indicator,
            value=data.get("value"),
            change_pct=data.get("change_pct"),
        )
        db.add(row)
        rows.append(row)
    if rows:
        db.commit()
    return rows


def get_latest(db: Session) -> dict[str, MacroData]:
    """Último registro guardado por cada indicador."""
    result: dict[str, MacroData] = {}
    for indicator in TICKERS.keys():
        stmt = (
            select(MacroData)
            .where(MacroData.indicator == indicator)
            .order_by(MacroData.ts.desc())
            .limit(1)
        )
        row = db.execute(stmt).scalars().first()
        if row:
            result[indicator] = row
    return result


def get_history(db: Session, indicator: str, limit: int = 200) -> list[MacroData]:
    stmt = (
        select(MacroData)
        .where(MacroData.indicator == indicator)
        .order_by(MacroData.ts.desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()
    return rows


def classify_risk_environment(latest: dict[str, MacroData]) -> dict:
    """
    Heurística RISK-ON / NEUTRAL / RISK-OFF (documentada y ajustable):
      +1 risk-on si SPX o NDX suben, VIX baja, DXY baja.
      -1 risk-off en el caso contrario.
    """
    score = 0
    factors = []

    spx = latest.get("SPX")
    if spx and spx.change_pct is not None:
        if spx.change_pct > 0.3:
            score += 1
            factors.append("S&P 500 al alza")
        elif spx.change_pct < -0.3:
            score -= 1
            factors.append("S&P 500 a la baja")

    ndx = latest.get("NDX")
    if ndx and ndx.change_pct is not None:
        if ndx.change_pct > 0.3:
            score += 1
            factors.append("NASDAQ al alza")
        elif ndx.change_pct < -0.3:
            score -= 1
            factors.append("NASDAQ a la baja")

    vix = latest.get("VIX")
    if vix and vix.change_pct is not None:
        if vix.change_pct < -3:
            score += 1
            factors.append("VIX cayendo (menor miedo)")
        elif vix.change_pct > 5:
            score -= 1
            factors.append("VIX subiendo (más miedo)")

    dxy = latest.get("DXY")
    if dxy and dxy.change_pct is not None:
        if dxy.change_pct < -0.2:
            score += 1
            factors.append("DXY debilitándose")
        elif dxy.change_pct > 0.2:
            score -= 1
            factors.append("DXY fortaleciéndose")

    if score >= 2:
        regime = "RISK-ON"
    elif score <= -2:
        regime = "RISK-OFF"
    else:
        regime = "NEUTRAL"

    return {"regime": regime, "score": score, "factors": factors}


def sync_macro(db: Session) -> dict:
    snapshot = fetch_macro_snapshot()
    save_snapshot(db, snapshot)
    latest = get_latest(db)
    risk_env = classify_risk_environment(latest)
    return {
        "ts": snapshot["ts"],
        "indicators": snapshot["indicators"],
        "errors": snapshot.get("errors", {}),
        "risk_environment": risk_env,
    }
