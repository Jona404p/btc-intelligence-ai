"""
ROI Calculator + Position Size Calculator (secciones 6 y 7 del spec).

Son funciones puras: no tocan la base de datos ni el exchange. Reciben
exactamente los números que el usuario ingresa (capital, entry, stop, exit,
leverage, fees) y devuelven todo lo que pide el spec, sin inventar nada.

IMPORTANTE (sección 6):
  - Se separa explícitamente el ROI del ACTIVO (% que se movió el precio)
    del ROI SOBRE EL CAPITAL (lo que realmente gana/pierde el usuario, ya
    aplicando leverage y tamaño de posición).
  - El leverage no es rentabilidad: solo amplifica el resultado (y el
    riesgo) sobre el capital, nunca sobre el ROI del activo.
"""

from __future__ import annotations

DEFAULT_TAKER_FEE_PCT = 0.04  # 0.04% por lado (Binance Futures taker fee, ajustable)


def position_size(
    capital: float,
    risk_pct: float,
    entry: float,
    stop: float,
    leverage: float = 1.0,
) -> dict:
    """
    Sección 7 - Position Size Calculator.

    Calcula el tamaño de posición tal que, si el precio llega al stop, la
    pérdida sea exactamente `risk_pct`% del capital (nunca más).
    """
    if capital <= 0 or entry <= 0 or stop <= 0:
        return {"status": "error", "message": "Capital, entry y stop deben ser mayores a 0."}
    if entry == stop:
        return {"status": "error", "message": "Entry y stop no pueden ser iguales (distancia de stop = 0)."}
    if risk_pct <= 0:
        return {"status": "error", "message": "Risk % debe ser mayor a 0."}

    stop_distance = abs(entry - stop)
    stop_distance_pct = stop_distance / entry * 100

    max_risk_usd = capital * (risk_pct / 100)
    # Tamaño de posición (en USD nocional) tal que max_risk_usd = position_size_usd * stop_distance_pct/100
    position_size_usd = max_risk_usd / (stop_distance_pct / 100)
    position_size_asset = position_size_usd / entry

    leverage = max(leverage, 0.0001)
    capital_required = position_size_usd / leverage

    return {
        "status": "ok",
        "capital": capital,
        "risk_pct": risk_pct,
        "entry": entry,
        "stop": stop,
        "leverage": leverage,
        "stop_distance": round(stop_distance, 2),
        "stop_distance_pct": round(stop_distance_pct, 4),
        "max_risk_usd": round(max_risk_usd, 2),
        "position_size_usd": round(position_size_usd, 2),
        "position_size_asset": round(position_size_asset, 8),
        "capital_required": round(capital_required, 2),
        "warning": (
            "El capital requerido supera el capital disponible: con este leverage y stop, "
            "no puedes abrir la posición completa manteniendo el riesgo pedido."
            if capital_required > capital
            else None
        ),
    }


def roi_calculator(
    capital: float,
    entry: float,
    exit_price: float,
    stop: float | None = None,
    leverage: float = 1.0,
    risk_pct: float | None = None,
    fee_pct: float = DEFAULT_TAKER_FEE_PCT,
    direction: str = "long",
) -> dict:
    """
    Sección 6 - ROI Calculator.

    Si se da `risk_pct` (y `stop`), el tamaño de posición se calcula
    automáticamente respetando ese riesgo (igual que el Position Size
    Calculator). Si no, se asume que todo el capital (x leverage) se usa
    como tamaño de posición nocional.
    """
    if capital <= 0 or entry <= 0 or exit_price <= 0:
        return {"status": "error", "message": "Capital, entry y exit deben ser mayores a 0."}

    direction = direction.lower()
    if direction not in ("long", "short"):
        return {"status": "error", "message": "direction debe ser 'long' o 'short'."}

    leverage = max(leverage, 0.0001)

    sizing_note = None
    if risk_pct and stop:
        sized = position_size(capital, risk_pct, entry, stop, leverage)
        if sized["status"] != "ok":
            return sized
        position_size_usd = sized["position_size_usd"]
        sizing_note = "Position size calculado automáticamente a partir del riesgo máximo indicado."
    else:
        position_size_usd = capital * leverage

    position_size_asset = position_size_usd / entry

    # ROI del ACTIVO: cuánto se movió el precio, independiente del capital/leverage.
    if direction == "long":
        asset_roi_pct = (exit_price - entry) / entry * 100
    else:
        asset_roi_pct = (entry - exit_price) / entry * 100

    gross_pnl_usd = position_size_usd * (asset_roi_pct / 100)

    # Fees estimadas: entrada + salida, cada una sobre el notional de la posición.
    fees_usd = position_size_usd * (fee_pct / 100) * 2
    net_pnl_usd = gross_pnl_usd - fees_usd

    capital_used = position_size_usd / leverage
    capital_roi_pct = (net_pnl_usd / capital) * 100 if capital > 0 else None

    result: dict = {
        "status": "ok",
        "direction": direction,
        "capital": capital,
        "entry": entry,
        "exit": exit_price,
        "leverage": leverage,
        "position_size_usd": round(position_size_usd, 2),
        "position_size_asset": round(position_size_asset, 8),
        "capital_used": round(capital_used, 2),
        "asset_roi_pct": round(asset_roi_pct, 4),
        "gross_pnl_usd": round(gross_pnl_usd, 2),
        "fees_usd": round(fees_usd, 2),
        "net_pnl_usd": round(net_pnl_usd, 2),
        "capital_roi_pct": round(capital_roi_pct, 4) if capital_roi_pct is not None else None,
        "sizing_note": sizing_note,
    }

    if stop:
        if direction == "long":
            risk_pct_calc = (entry - stop) / entry * 100
        else:
            risk_pct_calc = (stop - entry) / entry * 100
        max_loss_usd = position_size_usd * (abs(risk_pct_calc) / 100) + fees_usd
        result["risk_pct"] = round(abs(risk_pct_calc), 4)
        result["max_loss_usd"] = round(max_loss_usd, 2)
        reward_pct = abs(asset_roi_pct)
        risk_pct_abs = abs(risk_pct_calc)
        result["risk_reward"] = round(reward_pct / risk_pct_abs, 2) if risk_pct_abs > 0 else None

    result["note"] = (
        "ROI del activo (asset_roi_pct) mide cuánto se movió el precio. "
        "ROI sobre capital (capital_roi_pct) es lo que realmente ganas/pierdes sobre tu "
        "capital, ya con leverage y fees aplicados. No confundir ambos."
    )
    return result
