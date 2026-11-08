import asyncio
import logging

import websockets
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import market_data, indicators, market_analysis, market_structure, multi_timeframe, realtime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])


@router.websocket("/ws")
async def market_ws(
    websocket: WebSocket,
    symbol: str = Query(default=None),
    timeframe: str = Query(default="1m"),
):
    """
    Precio y vela en formación EN VIVO, sin polling.

    El frontend abre esta conexión una vez por (symbol, timeframe) y recibe
    mensajes push cada vez que hay un trade nuevo en Binance:
      {"type": "ticker", "price": ..., "change_pct": ...}
      {"type": "kline", "is_final": bool, "candle": {...}}
    """
    await websocket.accept()
    symbol = symbol or settings.DEFAULT_SYMBOL
    upstream_url = realtime.stream_url(symbol, timeframe)

    async def forward_upstream() -> None:
        while True:
            try:
                async with websockets.connect(upstream_url, ping_interval=15, ping_timeout=10) as upstream:
                    logger.info("Conectado al stream en vivo de %s (%s)", symbol, timeframe)
                    async for raw in upstream:
                        payload = realtime.translate_message(raw)
                        if payload:
                            await websocket.send_json(payload)
            except (websockets.ConnectionClosed, OSError) as exc:
                logger.warning("Stream en vivo de %s caído (%s), reintentando en 3s...", symbol, exc)
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                raise

    forward_task = asyncio.create_task(forward_upstream())
    try:
        # Mantiene la conexión viva; no esperamos nada del cliente, pero hay
        # que seguir "recibiendo" para detectar cuando el navegador cierra.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()


@router.post("/sync")
def sync_market(
    symbol: str = Query(default=None),
    timeframes: str = Query(default=None, description="Comma separated, e.g. 1h,4h"),
    limit: int = Query(default=500, le=1500),
    db: Session = Depends(get_db),
):
    """Descarga velas reales del exchange y las guarda en la base de datos."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    tf_list = [t.strip() for t in timeframes.split(",")] if timeframes else None
    results = market_data.sync_symbol(db, symbol=symbol, timeframes=tf_list, limit=limit)
    return {"symbol": symbol, "results": results}


@router.get("/candles")
def get_candles(
    symbol: str = Query(default=None),
    timeframe: str = Query(default="1h"),
    limit: int = Query(default=300, le=1500),
    db: Session = Depends(get_db),
):
    symbol = symbol or settings.DEFAULT_SYMBOL
    df = market_data.load_candles_df(db, symbol, timeframe, limit=limit)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": df.to_dict(orient="records"),
    }


@router.get("/indicators")
def get_indicators(
    symbol: str = Query(default=None),
    timeframe: str = Query(default="1h"),
    limit: int = Query(default=300, le=1500),
    db: Session = Depends(get_db),
):
    symbol = symbol or settings.DEFAULT_SYMBOL
    df = market_data.load_candles_df(db, symbol, timeframe, limit=limit)
    if df.empty:
        return {"symbol": symbol, "timeframe": timeframe, "indicators": [], "message": "no data, sync first"}

    ind_df = indicators.compute_all_indicators(df)
    ind_df = ind_df.replace({float("nan"): None})
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "indicators": ind_df.to_dict(orient="records"),
    }


@router.get("/levels")
def get_levels(
    symbol: str = Query(default=None),
    timeframe: str = Query(default="1h"),
    db: Session = Depends(get_db),
):
    symbol = symbol or settings.DEFAULT_SYMBOL
    df = market_data.load_candles_df(db, symbol, timeframe, limit=300)
    support, resistance = indicators.find_support_resistance(df)
    return {"symbol": symbol, "timeframe": timeframe, "support": support, "resistance": resistance}


@router.get("/overview")
def get_overview(
    symbol: str = Query(default=None),
    timeframe: str = Query(default="1h"),
    use_ai: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    symbol = symbol or settings.DEFAULT_SYMBOL
    return market_analysis.build_market_overview(db, symbol=symbol, timeframe=timeframe, use_ai=use_ai)


@router.get("/structure")
def get_structure(
    symbol: str = Query(default=None),
    timeframe: str = Query(default="1h"),
    window: int = Query(default=3, ge=2, le=10),
    limit: int = Query(default=300, le=1500),
    db: Session = Depends(get_db),
):
    """Análisis de Market Structure: swings, tendencia estructural y eventos BOS/CHOCH."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    df = market_data.load_candles_df(db, symbol, timeframe, limit=limit)
    if df.empty:
        return {"symbol": symbol, "timeframe": timeframe, "status": "no_data"}

    result = market_structure.analyze_market_structure(df, window=window)
    return {"symbol": symbol, "timeframe": timeframe, "status": "ok", **result}


@router.get("/multi-timeframe")
def get_multi_timeframe(
    symbol: str = Query(default=None),
    timeframes: str = Query(default=None, description="Comma separated, e.g. 15m,1h,4h,1d"),
    db: Session = Depends(get_db),
):
    """Consenso de tendencia a través de múltiples timeframes."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    tf_list = [t.strip() for t in timeframes.split(",")] if timeframes else None
    return multi_timeframe.multi_timeframe_consensus(db, symbol=symbol, timeframes=tf_list)
