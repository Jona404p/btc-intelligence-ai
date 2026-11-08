"""
News Intelligence (Fase 3, sección 18 del spec).

Recolecta noticias REALES desde feeds RSS públicos de medios cripto reconocidos
(CoinDesk, Cointelegraph). Nunca se inventan noticias ni fuentes: si un feed
falla, simplemente se omite y se registra el error.

Cada noticia se clasifica con una heurística de palabras clave, transparente y
ajustable (ver BULLISH_KEYWORDS / BEARISH_KEYWORDS). Esto NO es un modelo de
NLP sofisticado — es una primera aproximación explicable. La sección de
"Analyze impact on BTC" delega en Ollama, inyectando el titular+resumen real
como único contexto (no puede inventar impacto que no se le haya dado).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services import ollama_client

logger = logging.getLogger(__name__)

# Fuentes RSS reales. Se puede ampliar esta lista sin tocar el resto del código.
RSS_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
}

BULLISH_KEYWORDS = [
    "etf approval", "etf inflow", "institutional adoption", "buys bitcoin",
    "adds bitcoin", "rally", "surge", "all-time high", "ath", "bullish",
    "upgrade", "halving", "accumulation", "inflow", "adoption", "approves",
    "record high", "breakout", "outperform",
]
BEARISH_KEYWORDS = [
    "hack", "exploit", "lawsuit", "sec sues", "ban", "crash", "selloff",
    "sell-off", "bearish", "outflow", "liquidation", "collapse", "fraud",
    "investigation", "delist", "crackdown", "insolvency", "bankruptcy",
    "plunge", "dump",
]


def _classify_sentiment(text: str) -> tuple[str, str]:
    """Devuelve (sentiment, matched_reason) a partir de coincidencias de palabras clave."""
    lowered = text.lower()
    bull_hits = [kw for kw in BULLISH_KEYWORDS if kw in lowered]
    bear_hits = [kw for kw in BEARISH_KEYWORDS if kw in lowered]

    if bull_hits and not bear_hits:
        return "bullish", bull_hits[0]
    if bear_hits and not bull_hits:
        return "bearish", bear_hits[0]
    if bull_hits and bear_hits:
        # Señales mixtas: gana la que tenga más coincidencias.
        return ("bullish" if len(bull_hits) > len(bear_hits) else "bearish"), "mixed"
    return "neutral", "no_keywords_matched"


def _is_btc_relevant(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in ("bitcoin", "btc", " crypto", "cryptocurrency"))


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_rss(xml_text: str) -> list[dict]:
    """Parser mínimo de RSS 2.0 usando la librería estándar (sin dependencias extra)."""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("No se pudo parsear RSS: %s", exc)
        return items

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = _strip_html(item.findtext("description") or "")
        pub_date_raw = item.findtext("pubDate")
        try:
            from email.utils import parsedate_to_datetime
            pub_date = parsedate_to_datetime(pub_date_raw) if pub_date_raw else datetime.now(timezone.utc)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            pub_date = datetime.now(timezone.utc)

        if title and link:
            items.append({"title": title, "url": link, "summary": description[:500], "ts": pub_date})
    return items


def fetch_news() -> list[dict]:
    """Descarga noticias reales de todos los feeds configurados. Fuentes fallidas se omiten."""
    all_items: list[dict] = []
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            resp = httpx.get(feed_url, timeout=10.0, headers={"User-Agent": "btc-intelligence-ai/0.1"})
            resp.raise_for_status()
            parsed = _parse_rss(resp.text)
            for entry in parsed:
                entry["source"] = source_name
                all_items.append(entry)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fallo obteniendo feed de %s: %s", source_name, exc)
    return all_items


def save_news(db: Session, items: list[dict]) -> int:
    """Guarda noticias relevantes a BTC, evitando duplicados por URL (constraint UNIQUE)."""
    saved = 0
    for entry in items:
        full_text = f"{entry['title']} {entry.get('summary', '')}"
        if not _is_btc_relevant(full_text):
            continue

        exists = db.execute(select(NewsItem).where(NewsItem.url == entry["url"])).scalars().first()
        if exists:
            continue

        sentiment, _reason = _classify_sentiment(full_text)
        relevance = 1.0 if "bitcoin" in full_text.lower() or "btc" in full_text.lower() else 0.5
        impact = "high" if sentiment != "neutral" and relevance >= 1.0 else "medium" if sentiment != "neutral" else "low"

        row = NewsItem(
            ts=entry["ts"],
            title=entry["title"],
            source=entry["source"],
            url=entry["url"],
            summary=entry.get("summary"),
            sentiment=sentiment,
            relevance=relevance,
            potential_impact=impact,
            affected_asset="BTC",
        )
        db.add(row)
        saved += 1

    if saved:
        db.commit()
    return saved


def sync_news(db: Session) -> dict:
    items = fetch_news()
    saved = save_news(db, items)
    return {"fetched": len(items), "saved_new": saved}


def get_latest(db: Session, limit: int = 20) -> list[NewsItem]:
    stmt = select(NewsItem).order_by(NewsItem.ts.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def sentiment_breakdown(db: Session, limit: int = 40) -> dict:
    """Calcula % bullish/bearish/neutral sobre las últimas `limit` noticias guardadas."""
    rows = get_latest(db, limit=limit)
    total = len(rows)
    if total == 0:
        return {"bullish_pct": None, "bearish_pct": None, "neutral_pct": None, "sample_size": 0}

    bullish = sum(1 for r in rows if r.sentiment == "bullish")
    bearish = sum(1 for r in rows if r.sentiment == "bearish")
    neutral = total - bullish - bearish

    return {
        "bullish_pct": round(bullish / total * 100, 1),
        "bearish_pct": round(bearish / total * 100, 1),
        "neutral_pct": round(neutral / total * 100, 1),
        "sample_size": total,
    }


def analyze_impact(db: Session, news_id: int) -> dict:
    """
    "Analyze impact on BTC" (sección 18 del spec): le pasa a Ollama SOLO el
    titular + resumen real de una noticia guardada, y le pide evaluar impacto
    potencial. La IA no puede inventar detalles fuera de lo que se le da.
    """
    row = db.get(NewsItem, news_id)
    if not row:
        return {"status": "not_found", "news_id": news_id}

    if not ollama_client.is_available():
        return {
            "status": "ai_unavailable",
            "news_id": news_id,
            "message": "Ollama no está disponible. El registro de la noticia y su clasificación heurística siguen siendo válidos.",
        }

    prompt = (
        "Analiza el posible impacto de esta noticia real sobre BTC/USDT. "
        "NO inventes detalles que no estén en el titular o resumen. Si la noticia no "
        "tiene relación clara con BTC, dilo explícitamente.\n\n"
        f"Titular: {row.title}\n"
        f"Fuente: {row.source}\n"
        f"Resumen: {row.summary or '(sin resumen disponible)'}\n"
        f"Clasificación heurística previa: {row.sentiment}\n\n"
        "Responde en máximo 4 líneas: sesgo (bullish/bearish/neutral), impacto potencial "
        "(bajo/medio/alto) y por qué."
    )
    try:
        response_text = ollama_client.generate(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fallo analizando impacto de noticia con Ollama")
        return {"status": "error", "news_id": news_id, "message": str(exc)}

    return {"status": "ok", "news_id": news_id, "title": row.title, "url": row.url, "analysis": response_text}
