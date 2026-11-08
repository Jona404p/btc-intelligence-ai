from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas import (
    CompareTradeRequest,
    PositionSizeRequest,
    ROICalculatorRequest,
    TradeFinderRequest,
)
from app.services import calculators, trade_finder

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("/find")
def find_opportunities(payload: TradeFinderRequest, db: Session = Depends(get_db)):
    """
    Trade Finder / Opportunity Scanner (secciones 3, 4, 34, 35 del spec).

    Devuelve las oportunidades LONG y/o SHORT construidas sobre el precio
    actual, puntuadas con el Trade Score + Confluence Engine, ordenadas por
    Risk/Reward > riesgo > confluencia > calidad > ROI (nunca solo por ROI).
    """
    return trade_finder.find_opportunities(
        db,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        trade_type=payload.trade_type,
        capital=payload.capital,
        max_risk_pct=payload.max_risk_pct,
        min_roi_pct=payload.min_roi_pct,
        min_risk_reward=payload.min_risk_reward,
        min_confidence=payload.min_confidence,
        strategy=payload.strategy,
    )


@router.get("/opportunities")
def get_opportunities(
    symbol: str = Query(default=None),
    timeframe: str = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """Sección 35 - Oportunidades ya calculadas y persistidas, para el ranking sin recalcular."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    return {
        "symbol": symbol,
        "opportunities": trade_finder.get_recent_opportunities(db, symbol, timeframe, limit),
    }


@router.post("/compare")
def compare_long_vs_short(payload: CompareTradeRequest, db: Session = Depends(get_db)):
    """Sección 9 - Long vs Short Comparison."""
    return trade_finder.compare_long_vs_short(db, symbol=payload.symbol, timeframe=payload.timeframe)


@router.post("/roi-calculator")
def roi_calculator(payload: ROICalculatorRequest):
    """Sección 6 - ROI Calculator (función pura, sin tocar la base de datos)."""
    kwargs = {
        "capital": payload.capital,
        "entry": payload.entry,
        "exit_price": payload.exit_price,
        "stop": payload.stop,
        "leverage": payload.leverage,
        "risk_pct": payload.risk_pct,
        "direction": payload.direction,
    }
    if payload.fee_pct is not None:
        kwargs["fee_pct"] = payload.fee_pct
    return calculators.roi_calculator(**kwargs)


@router.post("/position-size")
def position_size_calculator(payload: PositionSizeRequest):
    """Sección 7 - Position Size Calculator (función pura, sin tocar la base de datos)."""
    return calculators.position_size(
        capital=payload.capital,
        risk_pct=payload.risk_pct,
        entry=payload.entry,
        stop=payload.stop,
        leverage=payload.leverage,
    )
