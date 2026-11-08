"""
Trade Finder / Opportunity Scanner (Fase 6).

Cubre, sobre datos reales ya sincronizados en la base de datos:

  - Sección 10 - TRADE SCORE: puntaje 0-100 transparente y desglosado por
    categoría. Cada categoría usa SOLO datos que el sistema ya tiene
    disponibles (técnico, estructura, volumen, derivados, macro, noticias,
    sentimiento, similitud histórica). No incluye "on-chain" porque ese
    dashboard todavía no está implementado (sección 17 pendiente) - jamás
    se inventa un subscore para un dato que no existe.
  - Sección 11 - CONFLUENCE ENGINE: cuenta cuántas categorías votan a favor
    y en contra de la dirección evaluada.
  - Sección 12 - SCENARIO ENGINE: además del escenario principal (LONG o
    SHORT), siempre se agrega el escenario alternativo (la dirección
    opuesta) y qué lo activaría.
  - Secciones 3/4 - TRADE FINDER / OPPORTUNITY SCANNER: genera candidatos
    LONG y/o SHORT usando ATR + soportes/resistencias reales, y los filtra
    según los criterios del usuario (riesgo, ROI mínimo, R:R mínimo,
    confianza mínima, timeframe, estrategia).
  - Sección 34/35 - RANKING: ordena por Risk/Reward, riesgo, confluencia,
    calidad de setup y solo al final por ROI potencial. Nunca se recomienda
    la operación con mayor ROI sin más.

REGLA DE ORO (sección 37): si un módulo no tiene datos disponibles, su
categoría se marca explícitamente como "sin datos" con subscore None y no
cuenta ni a favor ni en contra en el Confluence Engine.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.models import TradeOpportunity
from app.services import (
    calculators,
    derivatives as derivatives_service,
    historical_similarity,
    indicators,
    macro as macro_service,
    market_data,
    market_structure,
    news as news_service,
    sentiment as sentiment_service,
)

logger = logging.getLogger(__name__)

# Pesos del Trade Score (suman 100). Documentados y ajustables a propósito
# (sección 10: "el score debe ser transparente y configurable").
SCORE_WEIGHTS = {
    "technical": 20,
    "market_structure": 15,
    "volume": 10,
    "derivatives": 15,
    "macro": 15,
    "news": 10,
    "sentiment": 10,
    "historical_similarity": 5,
}

VALID_STRATEGIES = [
    "trend_following",
    "breakout",
    "pullback",
    "mean_reversion",
    "momentum",
    "support_resistance",
    "price_action",
    "scalping",
    "swing_trading",
]


def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "A-"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _cat(subscore: float | None, weight: int, vote: str | None, note: str) -> dict:
    return {"subscore": subscore, "max": weight, "vote": vote, "note": note}


# ---------------------------------------------------------------------
# Subscores por categoría
# ---------------------------------------------------------------------


def _technical_category(last_row: dict, direction: str) -> dict:
    weight = SCORE_WEIGHTS["technical"]
    trend = last_row.get("trend", "neutral")
    rsi = last_row.get("rsi_14")
    macd_hist = last_row.get("macd_hist")

    trend_pts = 0.0
    if trend == direction:
        trend_pts = weight * 0.6
    elif trend == "neutral":
        trend_pts = weight * 0.3

    momentum_pts = 0.0
    if macd_hist is not None and macd_hist == macd_hist:  # not NaN
        matches = (macd_hist > 0 and direction == "bullish") or (macd_hist < 0 and direction == "bearish")
        momentum_pts = weight * 0.2 if matches else 0.0

    rsi_pts = 0.0
    if rsi is not None and rsi == rsi:
        if direction == "bullish":
            rsi_pts = weight * 0.2 if 45 <= rsi <= 75 else (weight * 0.1 if rsi < 45 else 0.0)
        else:
            rsi_pts = weight * 0.2 if 25 <= rsi <= 55 else (weight * 0.1 if rsi > 55 else 0.0)

    subscore = round(trend_pts + momentum_pts + rsi_pts, 1)
    vote = "bullish" if trend == "bullish" else "bearish" if trend == "bearish" else "neutral"
    note = f"Tendencia EMA: {trend}, RSI14: {round(rsi, 1) if rsi == rsi else 'N/A'}"
    return _cat(subscore, weight, vote, note)


def _structure_category(structure: dict, direction: str) -> dict:
    weight = SCORE_WEIGHTS["market_structure"]
    if not structure or structure.get("status") == "no_data":
        return _cat(None, weight, None, "Sin suficientes velas para analizar estructura.")

    trend = structure.get("current_trend")
    events = structure.get("events") or []
    last_event = events[-1] if events else None

    trend_pts = 0.0
    if trend == direction:
        trend_pts = weight * 0.65
    elif trend == "range" or trend is None:
        trend_pts = weight * 0.3

    event_pts = 0.0
    if last_event and last_event.get("direction") == direction:
        event_pts = weight * 0.35

    subscore = round(trend_pts + event_pts, 1)
    vote = "bullish" if trend == "bullish" else "bearish" if trend == "bearish" else "neutral"
    note = f"Estructura: {trend or 'N/A'}" + (
        f", último evento {last_event['event_type']} {last_event['direction']}" if last_event else ""
    )
    return _cat(subscore, weight, vote, note)


def _volume_category(df: pd.DataFrame, direction: str) -> dict:
    weight = SCORE_WEIGHTS["volume"]
    if len(df) < 21:
        return _cat(None, weight, None, "Sin suficiente historial de volumen.")

    recent = df["volume"].iloc[-1]
    avg = df["volume"].tail(20).mean()
    if avg == 0:
        return _cat(None, weight, None, "Volumen promedio es 0.")

    ratio = recent / avg
    if ratio >= 1.2:
        subscore, vote = weight, direction
        note = f"Volumen actual {ratio:.2f}x su media de 20 velas (confirma el movimiento)."
    elif ratio >= 0.8:
        subscore, vote = weight * 0.5, "neutral"
        note = f"Volumen dentro de lo normal ({ratio:.2f}x su media)."
    else:
        subscore, vote = weight * 0.2, "neutral"
        note = f"Volumen débil ({ratio:.2f}x su media): el movimiento no está bien confirmado."

    return _cat(round(subscore, 1), weight, vote, note)


def _derivatives_category(deriv, direction: str) -> dict:
    weight = SCORE_WEIGHTS["derivatives"]
    if deriv is None:
        return _cat(None, weight, None, "Sin datos de derivados sincronizados (ejecuta /derivatives/sync).")

    funding = deriv.funding_rate
    ls_ratio = deriv.long_short_ratio
    pts = weight * 0.5  # baseline neutral
    notes = []

    if funding is not None:
        extreme = derivatives_service.FUNDING_EXTREME_THRESHOLD
        if direction == "bullish":
            if funding <= -extreme:
                pts += weight * 0.25
                notes.append("funding muy negativo favorece long (shorts pagan a longs)")
            elif funding >= extreme:
                pts -= weight * 0.25
                notes.append("funding muy positivo penaliza long (sobreapalancamiento largo)")
        else:
            if funding >= extreme:
                pts += weight * 0.25
                notes.append("funding muy positivo favorece short (longs pagan a shorts)")
            elif funding <= -extreme:
                pts -= weight * 0.25
                notes.append("funding muy negativo penaliza short (sobreapalancamiento corto)")

    if ls_ratio is not None:
        if direction == "bullish":
            if ls_ratio <= derivatives_service.LS_RATIO_EXTREME_LOW:
                pts += weight * 0.25
                notes.append("L/S ratio muy bajo: contrarian bullish (riesgo de short squeeze)")
            elif ls_ratio >= derivatives_service.LS_RATIO_EXTREME_HIGH:
                pts -= weight * 0.25
                notes.append("L/S ratio muy alto: posicionamiento retail ya muy largo")
        else:
            if ls_ratio >= derivatives_service.LS_RATIO_EXTREME_HIGH:
                pts += weight * 0.25
                notes.append("L/S ratio muy alto: contrarian bearish (riesgo de long squeeze)")
            elif ls_ratio <= derivatives_service.LS_RATIO_EXTREME_LOW:
                pts -= weight * 0.25
                notes.append("L/S ratio muy bajo: posicionamiento retail ya muy corto")

    pts = max(0.0, min(weight, pts))
    vote = "bullish" if pts > weight * 0.5 else "bearish" if pts < weight * 0.5 else "neutral"
    note = "; ".join(notes) if notes else "Funding y L/S ratio sin señal extrema."
    return _cat(round(pts, 1), weight, vote, note)


def _macro_category(macro_ctx: dict | None, direction: str) -> dict:
    weight = SCORE_WEIGHTS["macro"]
    if not macro_ctx:
        return _cat(None, weight, None, "Sin datos macro sincronizados (ejecuta /macro/sync).")

    regime = macro_ctx.get("regime")
    if (regime == "RISK-ON" and direction == "bullish") or (regime == "RISK-OFF" and direction == "bearish"):
        subscore, vote = weight, direction
    elif regime == "NEUTRAL":
        subscore, vote = weight * 0.5, "neutral"
    else:
        subscore, vote = weight * 0.15, "bearish" if direction == "bullish" else "bullish"

    note = f"Entorno macro: {regime} ({', '.join(macro_ctx.get('factors', [])) or 'sin factores destacados'})"
    return _cat(round(subscore, 1), weight, vote, note)


def _news_category(news_ctx: dict | None, direction: str) -> dict:
    weight = SCORE_WEIGHTS["news"]
    if not news_ctx or not news_ctx.get("sample_size"):
        return _cat(None, weight, None, "Sin noticias recientes sincronizadas (ejecuta /news/sync).")

    bullish_pct = news_ctx.get("bullish_pct") or 0
    bearish_pct = news_ctx.get("bearish_pct") or 0

    if direction == "bullish":
        subscore = weight * min(1.0, bullish_pct / 60)
    else:
        subscore = weight * min(1.0, bearish_pct / 60)

    if bullish_pct > bearish_pct:
        vote = "bullish"
    elif bearish_pct > bullish_pct:
        vote = "bearish"
    else:
        vote = "neutral"

    note = f"Noticias recientes: {bullish_pct}% bullish / {bearish_pct}% bearish (n={news_ctx['sample_size']})"
    return _cat(round(subscore, 1), weight, vote, note)


def _sentiment_category(sentiment_row, direction: str) -> dict:
    weight = SCORE_WEIGHTS["sentiment"]
    if sentiment_row is None:
        return _cat(None, weight, None, "Sin datos de sentimiento sincronizados (ejecuta /sentiment/sync).")

    overall = sentiment_row.overall_sentiment
    fng = sentiment_row.fng_value

    pts = weight * 0.5
    notes = [f"Sentimiento general: {overall or 'N/A'}"]

    if overall:
        overall_norm = "bullish" if "BULLISH" in overall.upper() else "bearish" if "BEARISH" in overall.upper() else "neutral"
        if overall_norm == direction:
            pts += weight * 0.3
        elif overall_norm != "neutral":
            pts -= weight * 0.3

    # Contrarian: codicia extrema es riesgo para longs nuevos, pánico extremo es riesgo para shorts nuevos.
    if fng is not None:
        if fng >= 85 and direction == "bullish":
            pts -= weight * 0.2
            notes.append(f"FNG en {fng:.0f} (codicia extrema): riesgo de reversión para longs nuevos")
        elif fng <= 15 and direction == "bearish":
            pts -= weight * 0.2
            notes.append(f"FNG en {fng:.0f} (miedo extremo): riesgo de reversión para shorts nuevos")

    pts = max(0.0, min(weight, pts))
    vote = "bullish" if pts > weight * 0.5 else "bearish" if pts < weight * 0.5 else "neutral"
    return _cat(round(pts, 1), weight, vote, "; ".join(notes))


def _historical_category(db: Session, symbol: str, timeframe: str, direction: str) -> dict:
    weight = SCORE_WEIGHTS["historical_similarity"]
    try:
        result = historical_similarity.find_similar_setups(
            db, symbol=symbol, timeframe=timeframe, lookback_window=20, forward_window=10, top_k=5
        )
    except Exception:  # noqa: BLE001
        logger.exception("Fallo calculando similitud histórica para el trade finder")
        return _cat(None, weight, None, "No se pudo calcular similitud histórica.")

    if result.get("status") != "ok" or not result.get("summary", {}).get("num_matches"):
        return _cat(None, weight, None, result.get("message", "Sin matches históricos suficientes."))

    summary = result["summary"]
    bullish_outcomes = summary["bullish_outcomes"]
    bearish_outcomes = summary["bearish_outcomes"]
    total = bullish_outcomes + bearish_outcomes
    if total == 0:
        return _cat(None, weight, None, "Setups históricos encontrados sin desenlace claro.")

    favorable = bullish_outcomes if direction == "bullish" else bearish_outcomes
    ratio = favorable / total
    subscore = round(weight * ratio, 1)
    vote = "bullish" if bullish_outcomes > bearish_outcomes else "bearish" if bearish_outcomes > bullish_outcomes else "neutral"
    note = (
        f"{total} setups históricos similares: {bullish_outcomes} con desenlace alcista, "
        f"{bearish_outcomes} con desenlace bajista. Retorno futuro promedio: "
        f"{summary.get('avg_forward_return_pct')}%. No es una predicción."
    )
    return _cat(subscore, weight, vote, note)


def compute_trade_score(
    db: Session,
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    last_row: dict,
    structure: dict,
    direction: str,
) -> dict:
    """
    Sección 10 (Trade Score) + Sección 11 (Confluence Engine) combinados:
    calcula el desglose por categoría, el total, el grade, y cuántas
    categorías votan a favor / en contra de `direction` ("bullish"/"bearish").
    """
    deriv = derivatives_service.get_latest(db, symbol)
    news_ctx = news_service.sentiment_breakdown(db)
    if not news_ctx.get("sample_size"):
        news_ctx = None
    macro_latest = macro_service.get_latest(db)
    macro_ctx = macro_service.classify_risk_environment(macro_latest) if macro_latest else None
    sentiment_row = sentiment_service.get_latest(db, symbol)

    breakdown = {
        "technical": _technical_category(last_row, direction),
        "market_structure": _structure_category(structure, direction),
        "volume": _volume_category(df, direction),
        "derivatives": _derivatives_category(deriv, direction),
        "macro": _macro_category(macro_ctx, direction),
        "news": _news_category(news_ctx, direction),
        "sentiment": _sentiment_category(sentiment_row, direction),
        "historical_similarity": _historical_category(db, symbol, timeframe, direction),
    }

    available = {k: v for k, v in breakdown.items() if v["subscore"] is not None}
    total_score = sum(v["subscore"] for v in available.values())
    total_max = sum(v["max"] for v in available.values())
    # Normalizado a 100 sobre las categorías realmente disponibles, para no
    # penalizar al usuario simplemente porque aún no sincronizó un módulo.
    normalized_score = round((total_score / total_max) * 100, 1) if total_max > 0 else 0.0

    bullish_votes = sum(1 for v in available.values() if v["vote"] == "bullish")
    bearish_votes = sum(1 for v in available.values() if v["vote"] == "bearish")
    neutral_votes = sum(1 for v in available.values() if v["vote"] == "neutral")

    favorable_votes = bullish_votes if direction == "bullish" else bearish_votes
    opposing_votes = bearish_votes if direction == "bullish" else bullish_votes
    total_votes = len(available)

    if total_votes == 0:
        confluence = "insufficient_data"
    elif opposing_votes == 0 and favorable_votes >= total_votes * 0.6:
        confluence = "HIGH"
    elif favorable_votes > opposing_votes:
        confluence = "MEDIUM"
    else:
        confluence = "LOW"

    return {
        "score": normalized_score,
        "grade": _grade_from_score(normalized_score),
        "breakdown": breakdown,
        "confluence": confluence,
        "bullish_factors": bullish_votes,
        "bearish_factors": bearish_votes,
        "neutral_factors": neutral_votes,
        "categories_available": total_votes,
        "categories_total": len(breakdown),
    }


# ---------------------------------------------------------------------
# Construcción de entry / stop / target (secciones 3, 4, 12)
# ---------------------------------------------------------------------


def _build_setup(
    price: float,
    atr: float,
    support: list[dict],
    resistance: list[dict],
    direction: str,
    risk_reward_min: float,
) -> dict | None:
    if atr <= 0 or atr != atr:
        return None

    if direction == "bullish":
        supports_below = [s["price"] for s in support if s["price"] < price]
        stop = (max(supports_below) - atr * 0.15) if supports_below else (price - atr * 1.5)
        stop = min(stop, price - atr * 0.3)  # nunca un stop absurdamente pegado al precio
        stop_distance = price - stop
        if stop_distance <= 0:
            return None
        resistances_above = [r["price"] for r in resistance if r["price"] > price]
        min_target = price + stop_distance * risk_reward_min
        target = max(resistances_above) if resistances_above and max(resistances_above) > min_target else min_target
        entry = price
    else:
        resistances_above = [r["price"] for r in resistance if r["price"] > price]
        stop = (min(resistances_above) + atr * 0.15) if resistances_above else (price + atr * 1.5)
        stop = max(stop, price + atr * 0.3)
        stop_distance = stop - price
        if stop_distance <= 0:
            return None
        supports_below = [s["price"] for s in support if s["price"] < price]
        min_target = price - stop_distance * risk_reward_min
        target = min(supports_below) if supports_below and min(supports_below) < min_target else min_target
        entry = price

    if direction == "bullish":
        risk_pct = (entry - stop) / entry * 100
        reward_pct = (target - entry) / entry * 100
    else:
        risk_pct = (stop - entry) / entry * 100
        reward_pct = (entry - target) / entry * 100

    if risk_pct <= 0 or reward_pct <= 0:
        return None

    return {
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_pct": round(risk_pct, 4),
        "potential_roi_pct": round(reward_pct, 4),
        "risk_reward": round(reward_pct / risk_pct, 2),
    }


def _build_scenario(direction: str, setup: dict, market_regime: str) -> dict:
    """Sección 12 - Scenario Engine: escenario principal + alternativo + rango."""
    opposite = "bearish" if direction == "bullish" else "bullish"
    return {
        "primary": {
            "type": direction.upper(),
            "conditions": f"El precio respeta el nivel de invalidación de {setup['stop']} y avanza hacia {setup['target']}.",
            "entry": setup["entry"],
            "target": setup["target"],
            "invalidation": setup["stop"],
            "roi_pct": setup["potential_roi_pct"],
            "risk_pct": setup["risk_pct"],
            "risk_reward": setup["risk_reward"],
        },
        "alternative": {
            "type": opposite.upper(),
            "conditions": (
                f"Si el precio pierde {setup['stop']} (invalidación del escenario {direction.upper()}), "
                f"el sesgo cambia a {opposite.upper()}."
            ),
        },
        "range": {
            "type": "RANGE",
            "conditions": (
                f"Si el precio oscila entre {setup['stop']} y {setup['target']} sin romper ninguno de los dos "
                "niveles con convicción, el mercado permanece en consolidación (régimen actual: "
                f"{market_regime})."
            ),
        },
    }


def _status_from_confidence(confidence: float, passed_filters: bool) -> str:
    if not passed_filters:
        return "rejected"
    if confidence >= 70:
        return "potential"
    if confidence >= 50:
        return "conditional"
    return "rejected"


def evaluate_direction(
    db: Session,
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    last_row: dict,
    structure: dict,
    support: list[dict],
    resistance: list[dict],
    market_regime: str,
    direction: str,
    strategy: str | None,
    risk_reward_min: float,
) -> dict | None:
    """Construye y puntúa UNA oportunidad (LONG o SHORT) para el precio actual."""
    price = float(last_row["close"])
    atr = float(last_row.get("atr_14") or 0)

    setup = _build_setup(price, atr, support, resistance, direction, risk_reward_min)
    if setup is None:
        return None

    scoring = compute_trade_score(db, symbol, timeframe, df, last_row, structure, direction)
    scenario = _build_scenario(direction, setup, market_regime)

    return {
        "direction": "long" if direction == "bullish" else "short",
        "strategy": strategy,
        "timeframe": timeframe,
        "symbol": symbol,
        **setup,
        "trade_score": scoring["score"],
        "grade": scoring["grade"],
        "confidence": scoring["score"],  # el score normalizado hace de proxy de confianza (0-100)
        "confluence": scoring["confluence"],
        "bullish_factors": scoring["bullish_factors"],
        "bearish_factors": scoring["bearish_factors"],
        "categories_available": scoring["categories_available"],
        "categories_total": scoring["categories_total"],
        "score_breakdown": scoring["breakdown"],
        "market_regime": market_regime,
        "scenario": scenario,
        "invalidation_note": scenario["primary"]["conditions"],
    }


# ---------------------------------------------------------------------
# Trade Finder principal (secciones 3, 4, 34, 35)
# ---------------------------------------------------------------------

RANK_KEY = (
    lambda o: (
        -o["risk_reward"],
        o["risk_pct"],
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "insufficient_data": 3}.get(o["confluence"], 3),
        -o["trade_score"],
        -o["potential_roi_pct"],
    )
)


def find_opportunities(
    db: Session,
    symbol: str | None = None,
    timeframe: str = "1h",
    trade_type: str = "BOTH",  # LONG / SHORT / BOTH
    capital: float = 100.0,
    max_risk_pct: float = 1.0,
    min_roi_pct: float = 2.0,
    min_risk_reward: float = 2.0,
    min_confidence: float = 60.0,
    strategy: str | None = None,
    persist: bool = True,
) -> dict:
    """
    Sección 3/4 - Trade Finder / Opportunity Scanner.

    Genera candidatos LONG y/o SHORT sobre el precio actual, los puntúa con
    el Trade Score + Confluence Engine, y devuelve los que cumplen los
    filtros del usuario, ordenados según la sección 34 (Risk/Reward > riesgo
    > confluencia > calidad > ROI), NUNCA solo por ROI.
    """
    symbol = symbol or settings.DEFAULT_SYMBOL
    trade_type = trade_type.upper()
    if trade_type not in ("LONG", "SHORT", "BOTH"):
        trade_type = "BOTH"

    if strategy and strategy not in VALID_STRATEGIES:
        strategy = None

    df = market_data.load_candles_df(db, symbol, timeframe, limit=500)
    if df.empty or len(df) < 60:
        return {
            "status": "insufficient_data",
            "symbol": symbol,
            "timeframe": timeframe,
            "message": (
                "No hay suficientes velas guardadas para este símbolo/timeframe. "
                "Ejecuta /market/sync primero."
            ),
        }

    ind_df = indicators.compute_all_indicators(df)
    last_row = ind_df.iloc[-1].to_dict()
    support, resistance = indicators.find_support_resistance(df)
    market_regime = indicators.classify_market_regime(df)
    structure = market_structure.analyze_market_structure(df)

    directions_to_try = []
    if trade_type in ("LONG", "BOTH"):
        directions_to_try.append("bullish")
    if trade_type in ("SHORT", "BOTH"):
        directions_to_try.append("bearish")

    candidates = []
    for direction in directions_to_try:
        candidate = evaluate_direction(
            db, symbol, timeframe, df, last_row, structure, support, resistance,
            market_regime, direction, strategy, min_risk_reward,
        )
        if candidate:
            candidates.append(candidate)

    results = []
    for c in candidates:
        # Tamaño de posición / ROI en USD respetando el riesgo máximo pedido (secciones 6/7).
        sizing = calculators.position_size(capital, max_risk_pct, c["entry"], c["stop"])
        roi_usd = None
        if sizing.get("status") == "ok":
            position_size_usd = sizing["position_size_usd"]
            roi_usd = round(position_size_usd * (c["potential_roi_pct"] / 100), 2)
            max_loss_usd = sizing["max_risk_usd"]
        else:
            max_loss_usd = None

        passed_filters = (
            c["potential_roi_pct"] >= min_roi_pct
            and c["risk_reward"] >= min_risk_reward
            and c["trade_score"] >= min_confidence
        )

        status = _status_from_confidence(c["trade_score"], passed_filters)

        opportunity = {
            **c,
            "capital": capital,
            "max_risk_pct": max_risk_pct,
            "position_size_usd": sizing.get("position_size_usd") if sizing.get("status") == "ok" else None,
            "position_size_asset": sizing.get("position_size_asset") if sizing.get("status") == "ok" else None,
            "potential_profit_usd": roi_usd,
            "max_loss_usd": max_loss_usd,
            "passed_filters": passed_filters,
            "status": status,
        }
        results.append(opportunity)

    results.sort(key=RANK_KEY)

    if persist:
        now = datetime.now(timezone.utc)
        for o in results:
            db.add(
                TradeOpportunity(
                    symbol=symbol,
                    timeframe=timeframe,
                    ts=now,
                    direction=o["direction"],
                    strategy=o["strategy"],
                    status=o["status"],
                    entry=o["entry"],
                    stop=o["stop"],
                    target=o["target"],
                    risk_pct=o["risk_pct"],
                    potential_roi_pct=o["potential_roi_pct"],
                    risk_reward=o["risk_reward"],
                    trade_score=o["trade_score"],
                    grade=o["grade"],
                    confidence=o["confidence"],
                    confluence=o["confluence"],
                    market_regime=o["market_regime"],
                    passed_filters=o["passed_filters"],
                    score_breakdown=o["score_breakdown"],
                    factors={
                        "bullish_factors": o["bullish_factors"],
                        "bearish_factors": o["bearish_factors"],
                        "categories_available": o["categories_available"],
                        "categories_total": o["categories_total"],
                    },
                    scenario=o["scenario"],
                    invalidation_note=o["invalidation_note"],
                )
            )
        db.commit()

    passing = [o for o in results if o["passed_filters"]]

    return {
        "status": "ok",
        "symbol": symbol,
        "timeframe": timeframe,
        "price": float(last_row["close"]),
        "market_regime": market_regime,
        "filters": {
            "trade_type": trade_type,
            "capital": capital,
            "max_risk_pct": max_risk_pct,
            "min_roi_pct": min_roi_pct,
            "min_risk_reward": min_risk_reward,
            "min_confidence": min_confidence,
            "strategy": strategy,
        },
        "opportunities": results,
        "best_match": passing[0] if passing else None,
        "num_candidates": len(results),
        "num_passed_filters": len(passing),
        "disclaimer": (
            "Esto NO es una señal garantizada ni una recomendación financiera. Los niveles se "
            "calculan a partir de ATR y soportes/resistencias reales; el Trade Score es una "
            "heurística transparente, no una probabilidad estadística de ganar."
        ),
    }


def get_recent_opportunities(db: Session, symbol: str, timeframe: str | None = None, limit: int = 50) -> list[dict]:
    """Sección 35 - últimas oportunidades ya calculadas y persistidas (para el ranking sin recalcular)."""
    from sqlalchemy import select

    stmt = select(TradeOpportunity).where(TradeOpportunity.symbol == symbol)
    if timeframe:
        stmt = stmt.where(TradeOpportunity.timeframe == timeframe)
    stmt = stmt.order_by(TradeOpportunity.ts.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": r.id,
            "ts": r.ts,
            "timeframe": r.timeframe,
            "direction": r.direction,
            "strategy": r.strategy,
            "status": r.status,
            "entry": r.entry,
            "stop": r.stop,
            "target": r.target,
            "risk_pct": r.risk_pct,
            "potential_roi_pct": r.potential_roi_pct,
            "risk_reward": r.risk_reward,
            "trade_score": r.trade_score,
            "grade": r.grade,
            "confidence": r.confidence,
            "confluence": r.confluence,
            "market_regime": r.market_regime,
            "passed_filters": r.passed_filters,
        }
        for r in rows
    ]


def compare_long_vs_short(db: Session, symbol: str | None = None, timeframe: str = "1h") -> dict:
    """Sección 9 - Long vs Short Comparison: corre ambas direcciones y las pone lado a lado."""
    result = find_opportunities(
        db, symbol=symbol, timeframe=timeframe, trade_type="BOTH",
        min_roi_pct=0, min_risk_reward=0, min_confidence=0, persist=False,
    )
    if result["status"] != "ok":
        return result

    by_direction = {o["direction"]: o for o in result["opportunities"]}
    long_o = by_direction.get("long")
    short_o = by_direction.get("short")

    winner = None
    if long_o and short_o:
        winner = "long" if long_o["trade_score"] >= short_o["trade_score"] else "short"
    elif long_o:
        winner = "long"
    elif short_o:
        winner = "short"

    return {
        "status": "ok",
        "symbol": result["symbol"],
        "timeframe": result["timeframe"],
        "price": result["price"],
        "long": long_o,
        "short": short_o,
        "winner": winner,
        "summary": (
            f"{winner.upper()} tiene mayor confluencia/score actualmente."
            if winner
            else "No se pudo construir un setup válido en ninguna dirección con los datos actuales."
        ),
    }
