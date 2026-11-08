from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import historical_similarity

router = APIRouter(prefix="/historical", tags=["historical"])


@router.get("/similar")
def similar_setups(
    symbol: str = Query(default=None),
    timeframe: str = Query(default="1h"),
    lookback_window: int = Query(default=20, ge=5, le=200),
    forward_window: int = Query(default=10, ge=3, le=100),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Busca setups históricos similares al momento actual y muestra qué ocurrió
    después de cada uno (sección 21 del spec). No es una predicción.
    """
    symbol = symbol or settings.DEFAULT_SYMBOL
    return historical_similarity.find_similar_setups(
        db,
        symbol=symbol,
        timeframe=timeframe,
        lookback_window=lookback_window,
        forward_window=forward_window,
        top_k=top_k,
    )


@router.get("/history")
def similarity_history(
    symbol: str = Query(default=None),
    timeframe: str = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """Consultas de similitud ya resueltas anteriormente (auditoría, sin recalcular)."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    return {
        "symbol": symbol,
        "history": historical_similarity.get_history(db, symbol, timeframe, limit),
    }
