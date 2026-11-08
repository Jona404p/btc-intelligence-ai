"""
Sentiment (Fase 3, sección 20 del spec).

Combina dos fuentes REALES, sin inventar nada:
  1. Fear & Greed Index de alternative.me (API pública, sin key) — cubre
     Fear/Greed/Extreme Fear/Extreme Greed tal como pide el spec.
  2. Distribución bullish/bearish/neutral de las noticias ya recolectadas
     por el módulo de News Intelligence.

Google Trends y X/Reddit requieren credenciales/scraping no disponibles en
este entorno local; se documentan como fuentes pendientes en vez de simularlas.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Sentiment
from app.services import news as news_service

logger = logging.getLogger(__name__)

FNG_API_URL = "https://api.alternative.me/fng/?limit=1&format=json"


def fetch_fear_greed() -> dict | None:
    """Fear & Greed Index real, fuente pública alternative.me. Devuelve None si falla."""
    try:
        resp = httpx.get(FNG_API_URL, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        entry = data["data"][0]
        return {
            "value": float(entry["value"]),
            "classification": entry["value_classification"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallo obteniendo Fear & Greed Index: %s", exc)
        return None


def _overall_sentiment(fng: dict | None, news_breakdown: dict) -> str:
    """
    Combina FNG + noticias en un veredicto simple. Documentado: no es un
    promedio matemático riguroso, es una heurística de confluencia.
    """
    votes = []
    if fng is not None:
        if fng["value"] >= 60:
            votes.append("bullish")
        elif fng["value"] <= 40:
            votes.append("bearish")
        else:
            votes.append("neutral")

    bull_pct = news_breakdown.get("bullish_pct")
    bear_pct = news_breakdown.get("bearish_pct")
    if bull_pct is not None and bear_pct is not None:
        if bull_pct - bear_pct >= 15:
            votes.append("bullish")
        elif bear_pct - bull_pct >= 15:
            votes.append("bearish")
        else:
            votes.append("neutral")

    if not votes:
        return "NEUTRAL"
    bullish_votes = votes.count("bullish")
    bearish_votes = votes.count("bearish")
    if bullish_votes > bearish_votes:
        return "BULLISH"
    if bearish_votes > bullish_votes:
        return "BEARISH"
    return "NEUTRAL"


def sync_sentiment(db: Session, symbol: str = None) -> dict:
    symbol = symbol or settings.DEFAULT_SYMBOL
    fng = fetch_fear_greed()
    news_breakdown = news_service.sentiment_breakdown(db)
    overall = _overall_sentiment(fng, news_breakdown)

    row = Sentiment(
        symbol=symbol,
        ts=datetime.now(timezone.utc),
        fng_value=fng["value"] if fng else None,
        fng_classification=fng["classification"] if fng else None,
        news_bullish_pct=news_breakdown.get("bullish_pct"),
        news_bearish_pct=news_breakdown.get("bearish_pct"),
        news_neutral_pct=news_breakdown.get("neutral_pct"),
        news_sample_size=news_breakdown.get("sample_size"),
        overall_sentiment=overall,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "symbol": symbol,
        "ts": row.ts,
        "fear_greed": fng,
        "news_breakdown": news_breakdown,
        "overall_sentiment": overall,
        "note": (
            "Fuentes activas: alternative.me (Fear & Greed) + noticias RSS clasificadas. "
            "Reddit, X y Google Trends requieren credenciales adicionales y no están "
            "activas todavía."
        ),
    }


def get_latest(db: Session, symbol: str = None) -> Sentiment | None:
    symbol = symbol or settings.DEFAULT_SYMBOL
    stmt = select(Sentiment).where(Sentiment.symbol == symbol).order_by(Sentiment.ts.desc()).limit(1)
    return db.execute(stmt).scalars().first()


def get_history(db: Session, symbol: str = None, limit: int = 200) -> list[Sentiment]:
    symbol = symbol or settings.DEFAULT_SYMBOL
    stmt = (
        select(Sentiment)
        .where(Sentiment.symbol == symbol)
        .order_by(Sentiment.ts.desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()
    return rows
