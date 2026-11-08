from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import macro

router = APIRouter(prefix="/macro", tags=["macro"])


@router.post("/sync")
def sync_macro(db: Session = Depends(get_db)):
    """Descarga datos macro reales (DXY, S&P500, NASDAQ, VIX, US10Y, Gold) vía Yahoo Finance."""
    return macro.sync_macro(db)


@router.get("/latest")
def latest_macro(db: Session = Depends(get_db)):
    latest = macro.get_latest(db)
    if not latest:
        return {"status": "no_data", "message": "Ejecuta /macro/sync primero."}
    risk_env = macro.classify_risk_environment(latest)
    return {
        "status": "ok",
        "indicators": {
            k: {"ts": v.ts, "value": v.value, "change_pct": v.change_pct} for k, v in latest.items()
        },
        "risk_environment": risk_env,
    }


@router.get("/history")
def macro_history(
    indicator: str = Query(..., description="DXY, SPX, NDX, VIX, US10Y o GOLD"),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    rows = macro.get_history(db, indicator, limit=limit)
    return {
        "indicator": indicator,
        "history": [{"ts": r.ts, "value": r.value, "change_pct": r.change_pct} for r in rows],
    }
