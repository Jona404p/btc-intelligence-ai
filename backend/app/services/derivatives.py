"""
Derivatives Dashboard - datos de futuros perpetuos (Binance USD-M Futures vía ccxt).

Métricas:
  - Open Interest (OI)
  - Funding Rate (actual y predicho)
  - Long/Short Account Ratio (global y top traders)
  - Mark price / Index price / Basis

Detección de anomalías (heurísticas simples, documentadas y explicables):
  - Funding extremo (positivo o negativo) -> posible sobreapalancamiento de un lado.
  - Long/Short ratio extremo -> posible long squeeze o short squeeze.
  - Basis anómalo -> posible dislocación entre mercado spot y futuros.

IMPORTANTE: si el exchange no expone un dato (por API, permisos o símbolo), se
devuelve None para ese campo. Nunca se rellena con valores inventados.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import ccxt
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import settings
from app.models import Derivatives, Signal

logger = logging.getLogger(__name__)


def _to_futures_symbol(symbol: str) -> str:
    """Convierte 'BTC/USDT' al formato de símbolo de futuros perpetuos de ccxt: 'BTC/USDT:USDT'."""
    if ":" in symbol:
        return symbol
    base, quote = symbol.split("/")
    return f"{base}/{quote}:{quote}"


def get_futures_exchange() -> ccxt.Exchange:
    """Instancia del exchange de futuros. Usamos binanceusdm (USD-M perpetuals) por defecto."""
    exchange_id = "binanceusdm" if settings.EXCHANGE_ID == "binance" else settings.EXCHANGE_ID
    exchange_class = getattr(ccxt, exchange_id)
    return exchange_class(
        {
            "enableRateLimit": True,
        }
    )


def fetch_derivatives_snapshot(symbol: str = None) -> dict:
    """
    Descarga el estado actual de derivados desde el exchange. Cada métrica se intenta
    de forma independiente: si una falla (no soportada, rate limit, etc.) las demás
    igual se devuelven, y el campo fallido queda en None con el error registrado.
    """
    symbol = symbol or settings.DEFAULT_SYMBOL
    fut_symbol = _to_futures_symbol(symbol)
    exchange = get_futures_exchange()

    result: dict = {
        "symbol": symbol,
        "ts": datetime.now(timezone.utc),
        "open_interest": None,
        "open_interest_usd": None,
        "funding_rate": None,
        "predicted_funding": None,
        "long_short_ratio": None,
        "top_trader_ls_ratio": None,
        "mark_price": None,
        "index_price": None,
        "basis": None,
        "basis_pct": None,
        "errors": {},
    }

    # --- Open Interest ---
    try:
        oi = exchange.fetch_open_interest(fut_symbol)
        result["open_interest"] = oi.get("openInterestAmount") or oi.get("openInterest")
        result["open_interest_usd"] = oi.get("openInterestValue")
    except Exception as exc:  # noqa: BLE001
        result["errors"]["open_interest"] = str(exc)

    # --- Funding Rate ---
    try:
        funding = exchange.fetch_funding_rate(fut_symbol)
        result["funding_rate"] = funding.get("fundingRate")
        result["mark_price"] = funding.get("markPrice")
        result["index_price"] = funding.get("indexPrice")
        result["predicted_funding"] = funding.get("nextFundingRate") or funding.get("fundingRate")
    except Exception as exc:  # noqa: BLE001
        result["errors"]["funding_rate"] = str(exc)

    # --- Long/Short Ratio (endpoint específico de Binance, vía llamada implícita) ---
    try:
        base_symbol = fut_symbol.split(":")[0].replace("/", "")
        raw = exchange.fapiPublicGetFuturesDataGlobalLongShortAccountRatio(
            {"symbol": base_symbol, "period": "1h", "limit": 1}
        )
        if raw:
            result["long_short_ratio"] = float(raw[-1]["longShortRatio"])
    except Exception as exc:  # noqa: BLE001
        result["errors"]["long_short_ratio"] = str(exc)

    try:
        base_symbol = fut_symbol.split(":")[0].replace("/", "")
        raw = exchange.fapiPublicGetFuturesDataTopLongShortAccountRatio(
            {"symbol": base_symbol, "period": "1h", "limit": 1}
        )
        if raw:
            result["top_trader_ls_ratio"] = float(raw[-1]["longShortRatio"])
    except Exception as exc:  # noqa: BLE001
        result["errors"]["top_trader_ls_ratio"] = str(exc)

    # --- Basis ---
    if result["mark_price"] and result["index_price"]:
        result["basis"] = result["mark_price"] - result["index_price"]
        result["basis_pct"] = (result["basis"] / result["index_price"]) * 100

    return result


def save_snapshot(db: Session, snapshot: dict) -> Derivatives:
    row = Derivatives(
        symbol=snapshot["symbol"],
        ts=snapshot["ts"],
        open_interest=snapshot.get("open_interest"),
        open_interest_usd=snapshot.get("open_interest_usd"),
        funding_rate=snapshot.get("funding_rate"),
        predicted_funding=snapshot.get("predicted_funding"),
        long_short_ratio=snapshot.get("long_short_ratio"),
        top_trader_ls_ratio=snapshot.get("top_trader_ls_ratio"),
        mark_price=snapshot.get("mark_price"),
        index_price=snapshot.get("index_price"),
        basis=snapshot.get("basis"),
        basis_pct=snapshot.get("basis_pct"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest(db: Session, symbol: str) -> Derivatives | None:
    stmt = (
        select(Derivatives)
        .where(Derivatives.symbol == symbol)
        .order_by(Derivatives.ts.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def get_history(db: Session, symbol: str, limit: int = 200) -> list[Derivatives]:
    stmt = (
        select(Derivatives)
        .where(Derivatives.symbol == symbol)
        .order_by(Derivatives.ts.desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()
    return rows


# --- Umbrales de anomalías (documentados, ajustables) ---
FUNDING_EXTREME_THRESHOLD = 0.0005      # 0.05% por periodo de 8h ~ anualizado alto
LS_RATIO_EXTREME_HIGH = 2.2             # muchos más longs que shorts
LS_RATIO_EXTREME_LOW = 0.55             # muchos más shorts que longs
BASIS_EXTREME_PCT = 0.5                 # 0.5% de basis es inusual en BTC perp


def interpret_current(funding_rate: float | None, long_short_ratio: float | None, basis_pct: float | None) -> list[str]:
    """Versión sin efectos secundarios (no escribe en DB) de la lectura de
    umbrales de `detect_anomalies`, pensada para consumidores de solo lectura
    como el Analista IA de Binance Futures: éste necesita saber SI el funding
    o el L/S ratio ya están en zona extrema, en vez de pasarle solo el número
    crudo y esperar que el LLM recuerde/aplique el umbral correcto él mismo.
    Devuelve mensajes cortos y ya interpretados, listos para el contexto."""
    notes: list[str] = []
    if funding_rate is not None:
        if funding_rate >= FUNDING_EXTREME_THRESHOLD:
            notes.append("Funding extremo positivo: longs pagan a shorts, riesgo de long squeeze (sesgo bajista).")
        elif funding_rate <= -FUNDING_EXTREME_THRESHOLD:
            notes.append("Funding extremo negativo: shorts pagan a longs, riesgo de short squeeze (sesgo alcista).")
    if long_short_ratio is not None:
        if long_short_ratio >= LS_RATIO_EXTREME_HIGH:
            notes.append("L/S ratio muy alto: posicionamiento retail sesgado a largos (contrarian bajista).")
        elif long_short_ratio <= LS_RATIO_EXTREME_LOW:
            notes.append("L/S ratio muy bajo: posicionamiento retail sesgado a cortos (contrarian alcista).")
    if basis_pct is not None and abs(basis_pct) >= BASIS_EXTREME_PCT:
        notes.append(f"Basis inusual entre mark e index price ({basis_pct:.2f}%).")
    return notes


def detect_anomalies(db: Session, symbol: str, current: dict, previous: Derivatives | None) -> list[dict]:
    """
    Compara el snapshot actual contra umbrales fijos y (si existe) contra el snapshot
    anterior, para detectar condiciones de squeeze / apalancamiento excesivo / basis anómalo.
    Cada anomalía detectada se persiste en la tabla `signals` para auditar el historial.
    """
    anomalies: list[dict] = []

    funding = current.get("funding_rate")
    if funding is not None:
        if funding >= FUNDING_EXTREME_THRESHOLD:
            anomalies.append(
                {
                    "signal_type": "funding_extreme_positive",
                    "severity": "warning",
                    "direction": "bearish",
                    "message": (
                        f"Funding rate muy positivo ({funding*100:.4f}%): longs pagan a shorts. "
                        "Sobreapalancamiento del lado largo; riesgo de long squeeze."
                    ),
                }
            )
        elif funding <= -FUNDING_EXTREME_THRESHOLD:
            anomalies.append(
                {
                    "signal_type": "funding_extreme_negative",
                    "severity": "warning",
                    "direction": "bullish",
                    "message": (
                        f"Funding rate muy negativo ({funding*100:.4f}%): shorts pagan a longs. "
                        "Sobreapalancamiento del lado corto; riesgo de short squeeze."
                    ),
                }
            )

    ls_ratio = current.get("long_short_ratio")
    if ls_ratio is not None:
        if ls_ratio >= LS_RATIO_EXTREME_HIGH:
            anomalies.append(
                {
                    "signal_type": "long_short_ratio_extreme_high",
                    "severity": "warning",
                    "direction": "bearish",
                    "message": (
                        f"Long/Short ratio muy alto ({ls_ratio:.2f}): posicionamiento retail "
                        "fuertemente sesgado a largos. Contrarian risk de long squeeze."
                    ),
                }
            )
        elif ls_ratio <= LS_RATIO_EXTREME_LOW:
            anomalies.append(
                {
                    "signal_type": "long_short_ratio_extreme_low",
                    "severity": "warning",
                    "direction": "bullish",
                    "message": (
                        f"Long/Short ratio muy bajo ({ls_ratio:.2f}): posicionamiento retail "
                        "fuertemente sesgado a cortos. Contrarian risk de short squeeze."
                    ),
                }
            )

    basis_pct = current.get("basis_pct")
    if basis_pct is not None and abs(basis_pct) >= BASIS_EXTREME_PCT:
        anomalies.append(
            {
                "signal_type": "basis_anomaly",
                "severity": "info",
                "direction": "bullish" if basis_pct > 0 else "bearish",
                "message": f"Basis inusual entre mark e index price ({basis_pct:.2f}%).",
            }
        )

    if previous is not None and previous.open_interest and current.get("open_interest"):
        oi_change_pct = (current["open_interest"] - previous.open_interest) / previous.open_interest * 100
        if abs(oi_change_pct) >= 5:
            anomalies.append(
                {
                    "signal_type": "open_interest_spike",
                    "severity": "info",
                    "direction": None,
                    "message": f"Cambio brusco de Open Interest: {oi_change_pct:+.2f}% desde el snapshot anterior.",
                }
            )

    # Persistir cada anomalía como Signal
    for a in anomalies:
        db.add(
            Signal(
                symbol=symbol,
                ts=current["ts"],
                category="derivatives",
                signal_type=a["signal_type"],
                severity=a["severity"],
                direction=a.get("direction"),
                message=a["message"],
                payload={k: v for k, v in current.items() if k != "errors"},
            )
        )
    if anomalies:
        db.commit()

    return anomalies


def sync_and_analyze(db: Session, symbol: str = None) -> dict:
    """Descarga el snapshot actual, lo guarda, y corre la detección de anomalías."""
    symbol = symbol or settings.DEFAULT_SYMBOL
    previous = get_latest(db, symbol)
    snapshot = fetch_derivatives_snapshot(symbol)
    save_snapshot(db, snapshot)
    anomalies = detect_anomalies(db, symbol, snapshot, previous)

    return {**snapshot, "anomalies": anomalies}
