from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import sync_all

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/all")
def sync_everything(
    symbol: str = Query(default=None),
    limit: int = Query(default=500, ge=50, le=1500),
    db: Session = Depends(get_db),
):
    """Actualiza todas las fuentes utilizadas por las pestañas del dashboard."""
    return sync_all.sync_all(db, symbol=symbol or settings.DEFAULT_SYMBOL, limit=limit)
