import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.routers import (
    market,
    ai,
    derivatives as derivatives_router,
    news as news_router,
    macro as macro_router,
    sentiment as sentiment_router,
    knowledge as knowledge_router,
    historical as historical_router,
    anomalies as anomalies_router,
    trades as trades_router,
    phase7 as phase7_router,
    binance as binance_router,
    sync as sync_router,
)
from app.services import (
    market_data,
    derivatives,
    news,
    macro,
    sentiment,
    library_scanner,
    anomaly_detector,
    trade_finder,
)

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BTC Intelligence AI",
    description="Market Intelligence & AI Trading Research platform - Fase 1-7",
    version="0.7.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(ai.router)
app.include_router(derivatives_router.router)
app.include_router(news_router.router)
app.include_router(macro_router.router)
app.include_router(sentiment_router.router)
app.include_router(knowledge_router.router)
app.include_router(historical_router.router)
app.include_router(anomalies_router.router)
app.include_router(trades_router.router)
app.include_router(phase7_router.router)
app.include_router(binance_router.router)
app.include_router(sync_router.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Manejador global de excepciones no controladas.

    IMPORTANTE (fix del bug de CORS reportado en /ai/ask):
    Si una excepción se escapa sin manejar, Starlette la resuelve en
    `ServerErrorMiddleware`, que está POR FUERA de `CORSMiddleware` en el stack
    de middlewares. El resultado es un 500 que nunca pasa por CORSMiddleware,
    así que el navegador nunca recibe la cabecera `Access-Control-Allow-Origin`
    y muestra "CORS Missing Allow Origin" en vez del error real.

    Registrar un exception_handler aquí hace que FastAPI resuelva la excepción
    DENTRO de ExceptionMiddleware (que sí está envuelto por CORSMiddleware), por
    lo que la respuesta de error sí lleva las cabeceras CORS correctas.
    """
    logger.exception("Excepción no controlada en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor. Revisa los logs del backend para más detalle.",
            "path": str(request.url.path),
        },
    )

scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_startup():
    # Crea las tablas ORM que no dependan de hypertables ya creadas por init_db/001_init.sql
    Base.metadata.create_all(bind=engine)
    Path(settings.DOCUMENTS_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    library_scanner.ensure_library_folders()

    def scheduled_sync():
        db = SessionLocal()
        try:
            market_data.sync_symbol(db)
        except Exception:  # noqa: BLE001
            logger.exception("Error en la sincronización automática de mercado")
        finally:
            db.close()

    def scheduled_derivatives_sync():
        db = SessionLocal()
        try:
            derivatives.sync_and_analyze(db)
        except Exception:  # noqa: BLE001
            logger.exception("Error en la sincronización automática de derivados")
        finally:
            db.close()

    def scheduled_news_sync():
        db = SessionLocal()
        try:
            news.sync_news(db)
        except Exception:  # noqa: BLE001
            logger.exception("Error en la sincronización automática de noticias")
        finally:
            db.close()

    def scheduled_macro_sync():
        db = SessionLocal()
        try:
            macro.sync_macro(db)
        except Exception:  # noqa: BLE001
            logger.exception("Error en la sincronización automática de macro")
        finally:
            db.close()

    def scheduled_sentiment_sync():
        db = SessionLocal()
        try:
            sentiment.sync_sentiment(db)
        except Exception:  # noqa: BLE001
            logger.exception("Error en la sincronización automática de sentimiento")
        finally:
            db.close()

    def scheduled_library_scan():
        db = SessionLocal()
        try:
            library_scanner.scan_library(db)
        except Exception:  # noqa: BLE001
            logger.exception("Error escaneando la biblioteca local de conocimiento")
        finally:
            db.close()

    def scheduled_anomaly_scan():
        db = SessionLocal()
        try:
            anomaly_detector.scan(db)
        except Exception:  # noqa: BLE001
            logger.exception("Error en el escaneo automático de anomalías")
        finally:
            db.close()

    def scheduled_trade_scan():
        db = SessionLocal()
        try:
            # Escaneo automático "de fondo" con filtros permisivos (min_confidence=0)
            # para que /trades/opportunities siempre tenga algo reciente que mostrar,
            # sin forzar al usuario a lanzar /trades/find manualmente primero.
            trade_finder.find_opportunities(
                db,
                trade_type="BOTH",
                min_roi_pct=0,
                min_risk_reward=0,
                min_confidence=0,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Error en el escaneo automático de oportunidades (Trade Finder)")
        finally:
            db.close()

    # Sincroniza velas cada 60 segundos (ajustable). Fase 1: solo BTC/USDT.
    scheduler.add_job(scheduled_sync, "interval", seconds=60, id="market_sync", replace_existing=True)
    # Sincroniza derivados (OI, funding, L/S ratio) cada 5 minutos - Fase 2.
    scheduler.add_job(
        scheduled_derivatives_sync, "interval", seconds=300, id="derivatives_sync", replace_existing=True
    )
    # Fase 3: noticias cada 10 min, macro cada 15 min, sentimiento (FNG + noticias) cada 15 min.
    scheduler.add_job(scheduled_news_sync, "interval", seconds=600, id="news_sync", replace_existing=True)
    scheduler.add_job(scheduled_macro_sync, "interval", seconds=900, id="macro_sync", replace_existing=True)
    scheduler.add_job(
        scheduled_sentiment_sync, "interval", seconds=900, id="sentiment_sync", replace_existing=True
    )
    # Fase 4b: escanea la carpeta local de biblioteca cada N minutos y
    # auto-indexa lo que encuentre nuevo o modificado.
    scheduler.add_job(
        scheduled_library_scan,
        "interval",
        minutes=settings.LIBRARY_SCAN_INTERVAL_MINUTES,
        id="library_scan",
        replace_existing=True,
    )
    # Fase 5: escanea anomalías de precio/volumen (y las combina con señales
    # recientes de otros módulos) cada 5 minutos sobre el timeframe rápido.
    scheduler.add_job(
        scheduled_anomaly_scan, "interval", seconds=300, id="anomaly_scan", replace_existing=True
    )
    # Fase 6: recalcula el Opportunity Scanner cada 5 minutos sobre el timeframe
    # por defecto (1h), y lo persiste en trade_opportunities para el ranking.
    scheduler.add_job(
        scheduled_trade_scan, "interval", seconds=300, id="trade_scan", replace_existing=True
    )
    scheduler.start()
    logger.info("BTC Intelligence AI backend iniciado. Scheduler de sincronización activo.")


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown(wait=False)


@app.get("/")
def root():
    return {
        "app": "BTC Intelligence AI",
        "phase": 7,
        "status": "ok",
        "endpoints": [
            "/market/sync",
            "/market/candles",
            "/market/ws (WebSocket, precio y vela en vivo)",
            "/market/indicators",
            "/market/levels",
            "/market/overview",
            "/market/structure",
            "/market/multi-timeframe",
            "/derivatives/sync",
            "/derivatives/latest",
            "/derivatives/history",
            "/news/sync",
            "/news/latest",
            "/news/analyze",
            "/macro/sync",
            "/macro/latest",
            "/macro/history",
            "/sentiment/sync",
            "/sentiment/latest",
            "/sentiment/history",
            "/ai/ask",
            "/knowledge/upload",
            "/knowledge/documents",
            "/knowledge/categories",
            "/knowledge/scan-library",
            "/knowledge/ask",
            "/historical/similar",
            "/historical/history",
            "/anomalies/scan",
            "/anomalies/latest",
            "/trades/find",
            "/trades/opportunities",
            "/trades/compare",
            "/trades/roi-calculator",
            "/trades/position-size",
            "/phase7/backtests",
            "/phase7/paper/accounts",
            "/phase7/paper/trades",
            "/phase7/journal",
            "/phase7/autopsies",
            "/binance/status",
            "/binance/ai/analyze",
            "/binance/account",
            "/binance/positions",
            "/binance/orders",
            "/sync/all",
            "/docs",
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}
