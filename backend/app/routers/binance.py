import ccxt
from fastapi import APIRouter, HTTPException

from app.schemas import (
    BinanceAIRequest,
    FuturesBracketOrderRequest,
    FuturesCancelOrderRequest,
    FuturesClosePositionRequest,
    FuturesOrderRequest,
)
from app.services import binance_ai, binance_trading
from app.database import get_db
from fastapi import Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/binance", tags=["binance-futures"])


def _translate_error(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ccxt.AuthenticationError):
        raise HTTPException(status_code=502, detail="Binance rechazó las credenciales o sus permisos.") from exc
    if isinstance(exc, ccxt.ExchangeError):
        raise HTTPException(status_code=502, detail=f"Binance rechazó la solicitud: {exc}") from exc
    raise HTTPException(status_code=502, detail="No se pudo completar la solicitud privada a Binance.") from exc


@router.get("/status")
def status():
    return binance_trading.connection_status()


@router.post("/ai/analyze")
def ai_analyze(payload: BinanceAIRequest, db: Session = Depends(get_db)):
    try:
        return binance_ai.analyze(db, **payload.model_dump())
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)


@router.get("/account")
def account():
    try:
        return binance_trading.account_summary()
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)


@router.get("/positions")
def get_positions():
    try:
        return {"positions": binance_trading.positions()}
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)


@router.get("/ticker")
def get_ticker(symbol: str = "BTC/USDT:USDT"):
    # Ticker público: no necesita API keys ni gasta peso de la cuenta.
    # El panel lo llama cada pocos segundos solo para pintar precio/bid/ask,
    # así que no tiene sentido que dependiera de credenciales privadas.
    try:
        return binance_trading.public_ticker(symbol)
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)


@router.get("/orders/open")
def get_open_orders(symbol: str | None = None):
    try:
        return {"orders": binance_trading.open_orders(symbol)}
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)


@router.post("/orders")
def order(payload: FuturesOrderRequest):
    try:
        return binance_trading.create_order(**payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)


@router.post("/orders/bracket")
def bracket_order(payload: FuturesBracketOrderRequest):
    """Abre la posición y adjunta stop-loss/take-profit reales en Binance
    (antes el panel solo mostraba TP/SL estimados; el usuario tenía que
    crear esas órdenes de protección a mano después de entrar)."""
    try:
        return binance_trading.create_bracket_order(**payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)


@router.post("/orders/cancel")
def cancel_order(payload: FuturesCancelOrderRequest):
    try:
        return binance_trading.cancel_order(**payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)


@router.post("/positions/close")
def close_position(payload: FuturesClosePositionRequest):
    try:
        return binance_trading.close_position(**payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        _translate_error(exc)
