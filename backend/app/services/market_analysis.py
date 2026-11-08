from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarketSnapshot
from app.services import (
    market_data,
    indicators,
    ollama_client,
    market_structure,
    derivatives,
    news as news_service,
    macro as macro_service,
    sentiment as sentiment_service,
)

logger = logging.getLogger(__name__)


def _build_ai_prompt(
    symbol: str,
    timeframe: str,
    last_row: dict,
    regime: str,
    support: list,
    resistance: list,
    structure: dict | None = None,
    deriv: dict | None = None,
    news_ctx: dict | None = None,
    macro_ctx: dict | None = None,
    sentiment_ctx: dict | None = None,
) -> str:
    context = {
        "symbol": symbol,
        "timeframe": timeframe,
        "price": last_row.get("close"),
        "trend": last_row.get("trend"),
        "rsi_14": round(last_row.get("rsi_14"), 2) if last_row.get("rsi_14") is not None else None,
        "macd_hist": last_row.get("macd_hist"),
        "ema_9": last_row.get("ema_9"),
        "ema_21": last_row.get("ema_21"),
        "ema_50": last_row.get("ema_50"),
        "ema_200": last_row.get("ema_200"),
        "atr_14": last_row.get("atr_14"),
        "market_regime": regime,
        "support_levels": [s["price"] for s in support],
        "resistance_levels": [r["price"] for r in resistance],
    }

    if structure:
        context["market_structure_trend"] = structure.get("current_trend")
        last_event = structure.get("events", [])[-1] if structure.get("events") else None
        context["last_structure_event"] = (
            {"type": last_event["event_type"], "direction": last_event["direction"], "price": last_event["price"]}
            if last_event
            else None
        )
        context["key_levels"] = structure.get("key_levels")

    if deriv:
        context["funding_rate"] = deriv.get("funding_rate")
        context["long_short_ratio"] = deriv.get("long_short_ratio")
        context["open_interest"] = deriv.get("open_interest")
        context["basis_pct"] = deriv.get("basis_pct")

    if news_ctx:
        context["recent_news_sentiment"] = news_ctx
    if macro_ctx:
        context["macro_risk_environment"] = macro_ctx
    if sentiment_ctx:
        context["market_sentiment"] = sentiment_ctx

    return (
        "Analiza el siguiente contexto técnico de BTC/USDT y da un veredicto de sesgo de mercado "
        "(BULLISH, BEARISH o NEUTRAL), una confianza de 0 a 100, y una explicación breve (máx 4 líneas) "
        "de por qué, mencionando qué lo invalidaría.\n\n"
        f"DATOS:\n{json.dumps(context, indent=2, default=str)}\n\n"
        "Responde en este formato exacto:\n"
        "BIAS: <BULLISH|BEARISH|NEUTRAL>\n"
        "CONFIDENCE: <0-100>\n"
        "EXPLANATION: <texto>\n"
        "INVALIDATION: <texto>"
    )


def _parse_ai_response(text: str) -> dict:
    bias, confidence, explanation, invalidation = None, None, text, None
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("BIAS:"):
            bias = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("CONFIDENCE:"):
            raw = line.split(":", 1)[1].strip().replace("%", "")
            try:
                confidence = float(raw)
            except ValueError:
                confidence = None
        elif line.upper().startswith("EXPLANATION:"):
            explanation = line.split(":", 1)[1].strip()
        elif line.upper().startswith("INVALIDATION:"):
            invalidation = line.split(":", 1)[1].strip()

    return {
        "bias": bias or "NEUTRAL",
        "confidence": confidence,
        "explanation": explanation,
        "invalidation": invalidation,
    }


def build_market_overview(db: Session, symbol: str = None, timeframe: str = "1h", use_ai: bool = True) -> dict:
    """
    Construye el Market Overview completo:
      1. Carga velas ya sincronizadas de la DB.
      2. Calcula indicadores técnicos.
      3. Detecta soportes/resistencias y régimen de mercado.
      4. (Opcional) Consulta a Ollama para el AI bias.
      5. Persiste un market_snapshot con todo lo anterior.
    """
    symbol = symbol or settings.DEFAULT_SYMBOL

    df = market_data.load_candles_df(db, symbol, timeframe, limit=500)
    if df.empty:
        return {
            "symbol": symbol,
            "status": "no_data",
            "message": (
                "No hay velas guardadas todavia para este símbolo/timeframe. "
                "Ejecuta primero /market/sync para descargar datos reales."
            ),
        }

    ind_df = indicators.compute_all_indicators(df)
    last_row = ind_df.iloc[-1].to_dict()

    support, resistance = indicators.find_support_resistance(df)
    regime = indicators.classify_market_regime(df)
    volatility_pct = indicators.compute_volatility_pct(df)

    # market_structure / derivatives / news / macro / sentiment solo se usan
    # para armar el prompt de la IA (ver _build_ai_prompt). El refresco
    # "rápido" (use_ai=False, pedido cada pocos segundos por el frontend para
    # refrescar régimen/ATR%/bias técnico) NO los necesita, así que nos
    # ahorramos ese trabajo (varias queries a la DB + recorrido de swings)
    # en el camino caliente. Esto es lo que más pesaba en cada refresco.
    structure: dict = {}
    deriv_ctx = None
    news_ctx = None
    macro_ctx = None
    sentiment_ctx = None

    if use_ai:
        structure = market_structure.analyze_market_structure(df)
        latest_derivatives = derivatives.get_latest(db, symbol)
        deriv_ctx = (
            {
                "funding_rate": latest_derivatives.funding_rate,
                "long_short_ratio": latest_derivatives.long_short_ratio,
                "open_interest": latest_derivatives.open_interest,
                "basis_pct": latest_derivatives.basis_pct,
            }
            if latest_derivatives
            else None
        )

        # Fase 3: contexto de news/macro/sentiment (best-effort - nunca bloquea el overview).
        try:
            news_ctx = news_service.sentiment_breakdown(db)
            if not news_ctx.get("sample_size"):
                news_ctx = None
        except Exception:  # noqa: BLE001
            logger.exception("Fallo obteniendo contexto de noticias para el overview")

        try:
            latest_macro = macro_service.get_latest(db)
            if latest_macro:
                macro_ctx = macro_service.classify_risk_environment(latest_macro)
        except Exception:  # noqa: BLE001
            logger.exception("Fallo obteniendo contexto macro para el overview")

        try:
            latest_sentiment = sentiment_service.get_latest(db, symbol)
            if latest_sentiment:
                sentiment_ctx = {
                    "fng_value": latest_sentiment.fng_value,
                    "fng_classification": latest_sentiment.fng_classification,
                    "overall_sentiment": latest_sentiment.overall_sentiment,
                }
        except Exception:  # noqa: BLE001
            logger.exception("Fallo obteniendo contexto de sentimiento para el overview")

    prev_close = df["close"].iloc[-2] if len(df) > 1 else df["close"].iloc[-1]
    change_pct = (last_row["close"] - prev_close) / prev_close * 100 if prev_close else None

    technical_bias = last_row.get("trend", "neutral")

    ai_bias, ai_confidence, ai_explanation, ai_invalidation = None, None, None, None
    if use_ai and ollama_client.is_available():
        try:
            prompt = _build_ai_prompt(
                symbol, timeframe, last_row, regime, support, resistance,
                structure=structure, deriv=deriv_ctx,
                news_ctx=news_ctx, macro_ctx=macro_ctx, sentiment_ctx=sentiment_ctx,
            )
            raw_response = ollama_client.generate(prompt)
            parsed = _parse_ai_response(raw_response)
            ai_bias = parsed["bias"]
            ai_confidence = parsed["confidence"]
            ai_explanation = parsed["explanation"]
            ai_invalidation = parsed["invalidation"]
        except Exception:  # noqa: BLE001
            logger.exception("Fallo consultando a Ollama, se omite AI bias.")
    elif use_ai:
        ai_explanation = "Ollama no está disponible en este momento (verifica que el contenedor esté corriendo)."

    # Persistimos un market_snapshot solo en el camino "completo" (use_ai=True,
    # ~cada 45s en el frontend). El refresco rápido (use_ai=False, cada pocos
    # segundos) es puramente de lectura para la UI: nada vuelve a leer esta
    # tabla más adelante, así que escribir una fila nueva en cada uno de esos
    # refrescos solo agregaba una escritura a DB desperdiciada y hacía crecer
    # market_snapshots sin ningún beneficio.
    now_ts = datetime.now(timezone.utc)
    snapshot_price = float(last_row["close"])

    if use_ai:
        snapshot = MarketSnapshot(
            symbol=symbol,
            ts=now_ts,
            price=snapshot_price,
            change_24h_pct=change_pct,
            volume_24h=float(df["volume"].tail(24).sum()) if len(df) >= 24 else float(df["volume"].sum()),
            volatility_pct=volatility_pct,
            market_regime=regime,
            technical_bias=technical_bias,
            ai_bias=ai_bias,
            ai_confidence=ai_confidence,
            support_levels=[s["price"] for s in support],
            resistance_levels=[r["price"] for r in resistance],
            raw_payload={"explanation": ai_explanation, "invalidation": ai_invalidation},
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        now_ts = snapshot.ts

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "status": "ok",
        "price": snapshot_price,
        "change_pct": change_pct,
        "volatility_pct": volatility_pct,
        "market_regime": regime,
        "technical_bias": technical_bias,
        "ai_bias": ai_bias,
        "ai_confidence": ai_confidence,
        "ai_explanation": ai_explanation,
        "ai_invalidation": ai_invalidation,
        "support_levels": [s["price"] for s in support],
        "resistance_levels": [r["price"] for r in resistance],
        "market_structure": {
            "trend": structure.get("current_trend"),
            "last_event": structure.get("events", [])[-1] if structure.get("events") else None,
            "key_levels": structure.get("key_levels"),
        },
        "derivatives": deriv_ctx,
        "news_sentiment": news_ctx,
        "macro": macro_ctx,
        "sentiment": sentiment_ctx,
        "latest_indicators": {
            k: (None if v != v else v)  # convierte NaN a None
            for k, v in last_row.items()
            if k not in ("ts", "open", "high", "low", "close", "volume")
        },
        "ts": now_ts,
    }
