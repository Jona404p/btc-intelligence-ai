from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import anomaly_detector

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.post("/scan")
def scan_anomalies(
    symbol: str = Query(default=None),
    timeframe: str = Query(default="5m"),
    db: Session = Depends(get_db),
):
    """
    Corre la detección de anomalías de precio/volumen sobre el timeframe dado
    y arma alertas combinadas con señales recientes de otros módulos
    (derivados, etc.) - sección 23 del spec.
    """
    symbol = symbol or settings.DEFAULT_SYMBOL
    return anomaly_detector.scan(db, symbol=symbol, timeframe=timeframe)


@router.get("/latest")
def latest_anomalies(
    symbol: str = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """Últimas señales/anomalías persistidas de todas las categorías (technical, derivatives, price, volume...)."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    return {"symbol": symbol, "signals": anomaly_detector.get_latest(db, symbol, limit)}
