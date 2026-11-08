"""Sincronización coordinada de todas las fuentes que alimentan el dashboard."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.services import (
    anomaly_detector,
    derivatives,
    library_scanner,
    macro,
    market_data,
    news,
    sentiment,
    trade_finder,
)

logger = logging.getLogger(__name__)


def _run_step(results: dict, name: str, callback) -> None:
    try:
        results[name] = {"status": "ok", "data": callback()}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Error en sincronización global: %s", name)
        results[name] = {"status": "error", "error": str(exc)}


def sync_all(db: Session, symbol: str | None = None, limit: int = 500) -> dict:
    """Actualiza todas las fuentes del dashboard sin abortar por un módulo fallido."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    results: dict = {
        "status": "ok",
        "symbol": symbol,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    _run_step(results, "market", lambda: market_data.sync_symbol(db, symbol=symbol, limit=limit))
    _run_step(results, "derivatives", lambda: derivatives.sync_and_analyze(db, symbol=symbol))
    _run_step(results, "news", lambda: news.sync_news(db))
    _run_step(results, "macro", lambda: macro.sync_macro(db))
    _run_step(results, "sentiment", lambda: sentiment.sync_sentiment(db, symbol=symbol))
    _run_step(results, "knowledge_library", lambda: library_scanner.scan_library(db))
    _run_step(results, "anomalies", lambda: anomaly_detector.scan(db, symbol=symbol))
    _run_step(
        results,
        "opportunities",
        lambda: trade_finder.find_opportunities(
            db,
            symbol=symbol,
            trade_type="BOTH",
            min_roi_pct=0,
            min_risk_reward=0,
            min_confidence=0,
        ),
    )

    failed = [name for name, result in results.items() if isinstance(result, dict) and result.get("status") == "error"]
    results["status"] = "partial" if failed else "ok"
    results["failed_steps"] = failed
    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    return results
