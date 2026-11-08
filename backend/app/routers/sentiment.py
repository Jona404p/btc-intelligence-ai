from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import sentiment

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.post("/sync")
def sync_sentiment(symbol: str = Query(default=None), db: Session = Depends(get_db)):
    """Refresca Fear & Greed Index real + distribución bullish/bearish/neutral de noticias."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    return sentiment.sync_sentiment(db, symbol=symbol)


@router.get("/latest")
def latest_sentiment(symbol: str = Query(default=None), db: Session = Depends(get_db)):
    symbol = symbol or settings.DEFAULT_SYMBOL
    row = sentiment.get_latest(db, symbol)
    if not row:
        return {"symbol": symbol, "status": "no_data", "message": "Ejecuta /sentiment/sync primero."}
    return {
        "symbol": symbol,
        "status": "ok",
        "ts": row.ts,
        "fng_value": row.fng_value,
        "fng_classification": row.fng_classification,
        "news_bullish_pct": row.news_bullish_pct,
        "news_bearish_pct": row.news_bearish_pct,
        "news_neutral_pct": row.news_neutral_pct,
        "news_sample_size": row.news_sample_size,
        "overall_sentiment": row.overall_sentiment,
    }


@router.get("/history")
def sentiment_history(
    symbol: str = Query(default=None), limit: int = Query(default=200, le=1000), db: Session = Depends(get_db)
):
    symbol = symbol or settings.DEFAULT_SYMBOL
    rows = sentiment.get_history(db, symbol, limit=limit)
    return {
        "symbol": symbol,
        "history": [
            {
                "ts": r.ts,
                "fng_value": r.fng_value,
                "fng_classification": r.fng_classification,
                "overall_sentiment": r.overall_sentiment,
            }
            for r in rows
        ],
    }
