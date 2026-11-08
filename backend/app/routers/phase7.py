from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PaperAccount, PaperTrade, TradeAutopsy, TradeJournalEntry
from app.schemas import (
    AutopsyRequest,
    BacktestRequest,
    ClosePaperTradeRequest,
    JournalEntryRequest,
    PaperAccountRequest,
    PaperTradeRequest,
)
from app.services import phase7

router = APIRouter(prefix="/phase7", tags=["phase7"])


def _bad_request(exc: ValueError):
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/backtests")
def run_backtest(payload: BacktestRequest, db: Session = Depends(get_db)):
    try:
        return phase7.run_backtest(db, **payload.model_dump())
    except ValueError as exc:
        _bad_request(exc)


@router.get("/backtests")
def list_backtests(symbol: str = "BTC/USDT", limit: int = Query(default=20, le=100), db: Session = Depends(get_db)):
    return {"symbol": symbol, "backtests": phase7.get_backtests(db, symbol, limit)}


@router.post("/paper/accounts")
def create_paper_account(payload: PaperAccountRequest, db: Session = Depends(get_db)):
    try:
        return phase7.account_view(db, phase7.create_account(db, **payload.model_dump()).id)
    except ValueError as exc:
        _bad_request(exc)


@router.get("/paper/accounts/{account_id}")
def get_paper_account(account_id: int, db: Session = Depends(get_db)):
    try:
        return phase7.account_view(db, account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/paper/trades")
def open_trade(payload: PaperTradeRequest, db: Session = Depends(get_db)):
    try:
        return phase7.open_paper_trade(db, **payload.model_dump())
    except ValueError as exc:
        _bad_request(exc)


@router.post("/paper/trades/{trade_id}/close")
def close_trade(trade_id: int, payload: ClosePaperTradeRequest, db: Session = Depends(get_db)):
    try:
        return phase7.close_paper_trade(db, trade_id, **payload.model_dump())
    except ValueError as exc:
        _bad_request(exc)


@router.get("/journal")
def list_journal(limit: int = Query(default=50, le=200), db: Session = Depends(get_db)):
    rows = db.execute(select(TradeJournalEntry).order_by(TradeJournalEntry.created_at.desc()).limit(limit)).scalars()
    return {"entries": [phase7.serialize_model(row) for row in rows]}


@router.post("/journal")
def create_journal(payload: JournalEntryRequest, db: Session = Depends(get_db)):
    return phase7.serialize_model(phase7.create_journal_entry(db, **payload.model_dump()))


@router.get("/autopsies")
def list_autopsies(limit: int = Query(default=50, le=200), db: Session = Depends(get_db)):
    rows = db.execute(select(TradeAutopsy).order_by(TradeAutopsy.created_at.desc()).limit(limit)).scalars()
    return {"autopsies": [phase7.serialize_model(row) for row in rows]}


@router.post("/autopsies")
def create_autopsy(payload: AutopsyRequest, db: Session = Depends(get_db)):
    try:
        return phase7.serialize_model(phase7.create_autopsy(db, **payload.model_dump()))
    except ValueError as exc:
        _bad_request(exc)
