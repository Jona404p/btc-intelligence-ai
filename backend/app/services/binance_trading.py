"""Conexión privada y ejecución controlada para Binance USD-M Futures.

Las credenciales solo se leen desde variables de entorno. Este módulo nunca las
incluye en respuestas ni logs. El modo live está bloqueado por defecto.

Optimización: antes se creaba un cliente ccxt (y se recargaban los mercados)
en CADA llamada -- status, cuenta, ticker, posiciones, cada orden -- lo que
significaba handshakes/HTTP setup y load_markets() repetidos innecesariamente
varias veces por segundo (el panel refresca cada 5s). Ahora se cachea una
única instancia por proceso (autenticada y pública) y los mercados se cargan
una sola vez, invalidando el caché solo si cambia la config de red (testnet).
"""

from __future__ import annotations

import time

import ccxt

from app.config import settings

# --- Caché de clientes ccxt (evita reconstruir el cliente y recargar
#     mercados en cada llamada; ccxt.Exchange es seguro de reutilizar). ---
_private_exchange: ccxt.Exchange | None = None
_public_exchange: ccxt.Exchange | None = None
_markets_loaded_at: float = 0.0
_MARKETS_TTL_SECONDS = 3600.0  # los símbolos/precisión de Binance no cambian en minutos


def futures_symbol(symbol: str) -> str:
    if ":" in symbol:
        return symbol
    base, quote = symbol.split("/")
    return f"{base}/{quote}:{quote}"


def get_private_exchange() -> ccxt.Exchange:
    """Cliente autenticado, cacheado a nivel de proceso."""
    global _private_exchange
    if not settings.EXCHANGE_API_KEY or not settings.EXCHANGE_API_SECRET:
        raise ValueError("Faltan EXCHANGE_API_KEY y EXCHANGE_API_SECRET en backend/.env.")
    if _private_exchange is None:
        exchange = ccxt.binanceusdm(
            {
                "apiKey": settings.EXCHANGE_API_KEY,
                "secret": settings.EXCHANGE_API_SECRET,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        exchange.set_sandbox_mode(settings.BINANCE_TESTNET)
        _private_exchange = exchange
    return _private_exchange


def get_public_futures_exchange() -> ccxt.Exchange:
    """Cliente PÚBLICO de futuros (sin API key). Sirve para precio/orderbook
    de solo lectura sin gastar rate-limit ni requerir credenciales, algo
    fundamental para que el Analista IA funcione aunque el usuario todavía
    no haya configurado sus claves de Binance."""
    global _public_exchange
    if _public_exchange is None:
        exchange = ccxt.binanceusdm({"enableRateLimit": True})
        exchange.set_sandbox_mode(settings.BINANCE_TESTNET)
        _public_exchange = exchange
    return _public_exchange


def _ensure_markets_loaded(exchange: ccxt.Exchange) -> None:
    global _markets_loaded_at
    now = time.monotonic()
    if not exchange.markets or (now - _markets_loaded_at) > _MARKETS_TTL_SECONDS:
        exchange.load_markets()
        _markets_loaded_at = now


def reset_exchange_cache() -> None:
    """Fuerza recrear los clientes ccxt (por ejemplo, si cambia testnet/claves en caliente)."""
    global _private_exchange, _public_exchange, _markets_loaded_at
    _private_exchange = None
    _public_exchange = None
    _markets_loaded_at = 0.0


def public_ticker(symbol: str) -> dict:
    """Ticker de solo lectura vía el cliente PÚBLICO (no requiere API keys).

    Se usa para el Analista IA y para cualquier vista de "precio actual" que
    no necesite ejecutar órdenes, así el panel no consume peso de rate-limit
    de la cuenta ni obliga a configurar claves solo para ver precio.
    """
    normalized = _check_symbol(symbol)
    exchange = get_public_futures_exchange()
    item = exchange.fetch_ticker(normalized)
    return {
        "symbol": normalized,
        "last": item.get("last"),
        "bid": item.get("bid"),
        "ask": item.get("ask"),
        "percentage": item.get("percentage"),
        "timestamp": item.get("timestamp"),
    }


def _check_symbol(symbol: str) -> str:
    normalized = futures_symbol(symbol)
    if normalized not in settings.binance_allowed_symbols_list:
        raise ValueError(f"Símbolo no permitido. Permitidos: {', '.join(settings.binance_allowed_symbols_list)}")
    return normalized


def connection_status() -> dict:
    configured = bool(settings.EXCHANGE_API_KEY and settings.EXCHANGE_API_SECRET)
    return {
        "exchange": "binance",
        "market_type": settings.BINANCE_MARKET_TYPE,
        "configured": configured,
        "testnet": settings.BINANCE_TESTNET,
        "live_trading_enabled": settings.BINANCE_LIVE_TRADING,
        "allowed_symbols": settings.binance_allowed_symbols_list,
        "max_order_notional_usdt": settings.BINANCE_MAX_ORDER_NOTIONAL_USDT,
        "message": "Las órdenes reales están bloqueadas por configuración." if not settings.BINANCE_LIVE_TRADING else "Órdenes live habilitadas: operar con precaución.",
    }


def account_summary() -> dict:
    exchange = get_private_exchange()
    balance = exchange.fetch_balance()
    usdt = balance.get("USDT", {})
    return {
        "exchange": "binance",
        "market_type": settings.BINANCE_MARKET_TYPE,
        "testnet": settings.BINANCE_TESTNET,
        "asset": "USDT",
        "total": usdt.get("total"),
        "free": usdt.get("free"),
        "used": usdt.get("used"),
    }


def positions() -> list[dict]:
    exchange = get_private_exchange()
    raw_positions = exchange.fetch_positions(settings.binance_allowed_symbols_list)
    return [
        {
            "symbol": item.get("symbol"),
            "side": item.get("side"),
            "contracts": item.get("contracts"),
            "entry_price": item.get("entryPrice"),
            "mark_price": item.get("markPrice"),
            "unrealized_pnl": item.get("unrealizedPnl"),
            "leverage": item.get("leverage"),
            "liquidation_price": item.get("liquidationPrice"),
        }
        for item in raw_positions
        if item.get("contracts")
    ]


def ticker(symbol: str) -> dict:
    normalized = _check_symbol(symbol)
    item = get_private_exchange().fetch_ticker(normalized)
    return {
        "symbol": normalized,
        "last": item.get("last"),
        "bid": item.get("bid"),
        "ask": item.get("ask"),
        "percentage": item.get("percentage"),
        "timestamp": item.get("timestamp"),
    }


def open_orders(symbol: str | None = None) -> list[dict]:
    exchange = get_private_exchange()
    normalized = _check_symbol(symbol) if symbol else None
    orders = exchange.fetch_open_orders(normalized)
    return [
        {
            "id": order.get("id"),
            "symbol": order.get("symbol"),
            "type": order.get("type"),
            "side": order.get("side"),
            "amount": order.get("amount"),
            "remaining": order.get("remaining"),
            "price": order.get("price"),
            "status": order.get("status"),
            "reduce_only": order.get("info", {}).get("reduceOnly", False),
        }
        for order in orders
    ]


def _orders_allowed(confirm_live: bool) -> None:
    if not settings.BINANCE_LIVE_TRADING and not settings.BINANCE_TESTNET:
        raise PermissionError("Órdenes bloqueadas: BINANCE_LIVE_TRADING=false.")
    if not confirm_live:
        raise PermissionError("La operación requiere confirm_live=true para evitar envíos accidentales.")


def create_order(
    *,
    symbol: str,
    side: str,
    amount: float,
    order_type: str,
    price: float | None,
    leverage: int,
    time_in_force: str,
    reduce_only: bool,
    confirm_live: bool,
) -> dict:
    normalized = _check_symbol(symbol)
    side = side.lower()
    order_type = order_type.lower()
    if side not in {"buy", "sell"}:
        raise ValueError("side debe ser buy o sell.")
    if order_type not in {"market", "limit"}:
        raise ValueError("order_type debe ser market o limit.")
    if time_in_force not in {"GTC", "IOC", "FOK"}:
        raise ValueError("time_in_force debe ser GTC, IOC o FOK.")
    if amount <= 0 or leverage < 1 or leverage > 20:
        raise ValueError("amount debe ser positivo y leverage debe estar entre 1 y 20.")
    if order_type == "limit" and (price is None or price <= 0):
        raise ValueError("Las órdenes limit requieren un price positivo.")
    _orders_allowed(confirm_live)

    exchange = get_private_exchange()
    _ensure_markets_loaded(exchange)
    if reduce_only:
        matching_side = "long" if side == "sell" else "short"
        matching_position = next(
            (
                item
                for item in exchange.fetch_positions([normalized])
                if item.get("side") == matching_side and float(item.get("contracts") or 0) > 0
            ),
            None,
        )
        position_amount = float(matching_position.get("contracts") or 0) if matching_position else 0
        if position_amount <= 0:
            raise ValueError(
                f"No existe una posición {matching_side.upper()} abierta para reducir. "
                "Desactiva Reduce-only para abrir una posición."
            )
        if amount > position_amount:
            raise ValueError(
                f"La cantidad reduce-only ({amount}) supera la posición disponible ({position_amount})."
            )
    reference_price = price
    if reference_price is None:
        reference_price = exchange.fetch_ticker(normalized).get("last")
    notional = float(amount) * float(reference_price or 0)
    if notional > settings.BINANCE_MAX_ORDER_NOTIONAL_USDT:
        raise PermissionError(
            f"Notional ${notional:.2f} supera el límite configurado de ${settings.BINANCE_MAX_ORDER_NOTIONAL_USDT:.2f}."
        )

    exchange.set_leverage(leverage, normalized)
    params = {"reduceOnly": reduce_only}
    if order_type == "limit":
        params["timeInForce"] = time_in_force
    order = exchange.create_order(normalized, order_type, side, amount, price, params)
    return {
        "id": order.get("id"),
        "symbol": order.get("symbol"),
        "type": order.get("type"),
        "side": order.get("side"),
        "amount": order.get("amount"),
        "price": order.get("price"),
        "average": order.get("average"),
        "status": order.get("status"),
        "reduce_only": reduce_only,
        "testnet": settings.BINANCE_TESTNET,
    }


def cancel_order(*, symbol: str, order_id: str, confirm_live: bool) -> dict:
    normalized = _check_symbol(symbol)
    _orders_allowed(confirm_live)
    order = get_private_exchange().cancel_order(order_id, normalized)
    return {"id": order.get("id"), "symbol": order.get("symbol"), "status": order.get("status"), "cancelled": True}


def create_bracket_order(
    *,
    symbol: str,
    side: str,
    amount: float,
    order_type: str,
    price: float | None,
    leverage: int,
    time_in_force: str,
    confirm_live: bool,
    stop_loss: float | None,
    take_profit: float | None,
) -> dict:
    """Abre una posición y, si se piden, adjunta órdenes reduce-only de
    protección (STOP_MARKET para stop-loss y TAKE_PROFIT_MARKET para take
    profit) usando closePosition=true -- así cubren TODA la posición y no
    quedan huérfanas si luego se cambia el tamaño manualmente.

    Antes el panel solo calculaba TP/SL en pantalla como referencia; el
    usuario tenía que crear esas órdenes a mano después. Aquí sí se envían
    a Binance, en el mismo flujo, y cualquier fallo en el bracket queda
    reportado (no oculto) sin revertir la entrada, porque cancelar una
    entrada ya ejecutada podría dejar exposición sin darse cuenta.
    """
    entry = create_order(
        symbol=symbol,
        side=side,
        amount=amount,
        order_type=order_type,
        price=price,
        leverage=leverage,
        time_in_force=time_in_force,
        reduce_only=False,
        confirm_live=confirm_live,
    )
    normalized = futures_symbol(symbol)
    exit_side = "sell" if side.lower() == "buy" else "buy"
    exchange = get_private_exchange()
    protection: list[dict] = []
    errors: list[str] = []

    def _place(kind: str, stop_price: float) -> None:
        try:
            order = exchange.create_order(
                normalized,
                kind,
                exit_side,
                amount,
                None,
                {"stopPrice": stop_price, "closePosition": True, "workingType": "MARK_PRICE"},
            )
            protection.append(
                {
                    "kind": kind,
                    "id": order.get("id"),
                    "stop_price": stop_price,
                    "status": order.get("status"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{kind} no se pudo colocar: {exc}")

    if stop_loss and stop_loss > 0:
        _place("STOP_MARKET", stop_loss)
    if take_profit and take_profit > 0:
        _place("TAKE_PROFIT_MARKET", take_profit)

    return {"entry": entry, "protection": protection, "protection_errors": errors}


def close_position(*, symbol: str, amount: float | None, confirm_live: bool) -> dict:
    normalized = _check_symbol(symbol)
    _orders_allowed(confirm_live)
    exchange = get_private_exchange()
    current = next((item for item in exchange.fetch_positions([normalized]) if item.get("contracts")), None)
    if current is None:
        raise ValueError("No hay una posición abierta para ese símbolo.")
    contracts = float(amount or current.get("contracts") or 0)
    if contracts <= 0:
        raise ValueError("La cantidad a cerrar debe ser mayor que 0.")
    side = "sell" if current.get("side") == "long" else "buy"
    order = exchange.create_order(normalized, "market", side, contracts, None, {"reduceOnly": True})
    return {"id": order.get("id"), "symbol": order.get("symbol"), "side": order.get("side"), "amount": order.get("amount"), "reduce_only": True, "testnet": settings.BINANCE_TESTNET}
