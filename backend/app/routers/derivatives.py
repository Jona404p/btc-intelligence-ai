from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import derivatives

router = APIRouter(prefix="/derivatives", tags=["derivatives"])


@router.post("/sync")
def sync_derivatives(symbol: str = Query(default=None), db: Session = Depends(get_db)):
    """Descarga el estado actual de derivados (OI, funding, L/S ratio) y detecta anomalías."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    return derivatives.sync_and_analyze(db, symbol=symbol)


@router.get("/latest")
def latest_derivatives(symbol: str = Query(default=None), db: Session = Depends(get_db)):
    symbol = symbol or settings.DEFAULT_SYMBOL
    row = derivatives.get_latest(db, symbol)
    if not row:
        return {"symbol": symbol, "status": "no_data", "message": "Ejecuta /derivatives/sync primero."}
    return {
        "symbol": symbol,
        "status": "ok",
        "ts": row.ts,
        "open_interest": row.open_interest,
        "open_interest_usd": row.open_interest_usd,
        "funding_rate": row.funding_rate,
        "predicted_funding": row.predicted_funding,
        "long_short_ratio": row.long_short_ratio,
        "top_trader_ls_ratio": row.top_trader_ls_ratio,
        "mark_price": row.mark_price,
        "index_price": row.index_price,
        "basis": row.basis,
        "basis_pct": row.basis_pct,
    }


@router.get("/history")
def derivatives_history(
    symbol: str = Query(default=None), limit: int = Query(default=200, le=1000), db: Session = Depends(get_db)
):
    symbol = symbol or settings.DEFAULT_SYMBOL
    rows = derivatives.get_history(db, symbol, limit=limit)
    return {
        "symbol": symbol,
        "history": [
            {
                "ts": r.ts,
                "open_interest": r.open_interest,
                "funding_rate": r.funding_rate,
                "long_short_ratio": r.long_short_ratio,
                "basis_pct": r.basis_pct,
            }
            for r in rows
        ],
    }
