"""Fase 7: backtesting reproducible, paper trading, journal y autopsias."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BacktestRun, PaperAccount, PaperTrade, TradeAutopsy, TradeJournalEntry
from app.services import indicators, market_data

VALID_STRATEGIES = {"ema_crossover", "rsi", "breakout", "trend_following"}


def _number(value: object, digits: int = 6) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    result = indicators.compute_all_indicators(df.copy())
    result["high_20"] = result["high"].rolling(20).max().shift(1)
    result["low_20"] = result["low"].rolling(20).min().shift(1)
    return result


def _signal(row: pd.Series, strategy: str) -> str | None:
    if strategy == "ema_crossover":
        if pd.notna(row.get("ema_9")) and pd.notna(row.get("ema_21")):
            return "long" if row.ema_9 > row.ema_21 else "short"
    elif strategy == "rsi":
        if pd.notna(row.get("rsi_14")):
            if row.rsi_14 <= 35:
                return "long"
            if row.rsi_14 >= 65:
                return "short"
    elif strategy == "breakout":
        if pd.notna(row.get("high_20")) and row.close > row.high_20:
            return "long"
        if pd.notna(row.get("low_20")) and row.close < row.low_20:
            return "short"
    elif strategy == "trend_following":
        trend = row.get("trend")
        if trend in {"bullish", "bearish"}:
            return "long" if trend == "bullish" else "short"
    return None


def _close_trade(position: dict, exit_price: float, exit_ts, fee_pct: float, reason: str) -> dict:
    direction_multiplier = 1 if position["direction"] == "long" else -1
    gross_pnl = (exit_price - position["entry"]) * position["quantity"] * direction_multiplier
    fees = (position["entry"] * position["quantity"] + exit_price * position["quantity"]) * fee_pct / 100
    pnl = gross_pnl - fees
    risk = position["risk_amount"]
    return {
        **position,
        "exit": _number(exit_price),
        "exit_ts": exit_ts.isoformat(),
        "gross_pnl": _number(gross_pnl),
        "fees": _number(fees),
        "pnl": _number(pnl),
        "r_multiple": _number(pnl / risk if risk else 0),
        "exit_reason": reason,
    }


def run_backtest(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    strategy: str,
    initial_capital: float,
    risk_pct: float,
    fee_pct: float,
    slippage_pct: float,
    limit: int,
) -> dict:
    if strategy not in VALID_STRATEGIES:
        raise ValueError(f"Estrategia no soportada. Usa una de: {', '.join(sorted(VALID_STRATEGIES))}")
    if initial_capital <= 0 or not 0 < risk_pct <= 100 or fee_pct < 0 or slippage_pct < 0:
        raise ValueError("Capital, riesgo, comisión y slippage deben tener valores válidos.")

    df = market_data.load_candles_df(db, symbol, timeframe, limit=limit)
    if len(df) < 60:
        return {"status": "no_data", "message": "Se necesitan al menos 60 velas guardadas para backtesting."}

    enriched = _prepare(df)
    capital = float(initial_capital)
    position: dict | None = None
    trades: list[dict] = []
    equity_curve = [{"ts": enriched.iloc[0].ts.isoformat(), "equity": _number(capital, 2)}]

    for index in range(1, len(enriched)):
        row = enriched.iloc[index]
        if position is not None:
            stop_hit = row.low <= position["stop"] if position["direction"] == "long" else row.high >= position["stop"]
            target_hit = row.high >= position["target"] if position["direction"] == "long" else row.low <= position["target"]
            if stop_hit or target_hit:
                # Si una misma vela toca ambos niveles, el backtest elige el stop:
                # es la convención conservadora y evita optimismo intrabar.
                exit_price = position["stop"] if stop_hit else position["target"]
                closed = _close_trade(position, exit_price, row.ts, fee_pct, "stop" if stop_hit else "target")
                capital += closed["pnl"]
                trades.append(closed)
                position = None

        if position is None and index < len(enriched) - 1:
            signal = _signal(enriched.iloc[index - 1], strategy)
            atr = enriched.iloc[index - 1].get("atr_14")
            if signal and pd.notna(atr) and float(atr) > 0:
                raw_entry = float(row.open)
                entry = raw_entry * (1 + slippage_pct / 100 if signal == "long" else 1 - slippage_pct / 100)
                risk_distance = float(atr) * 2
                stop = entry - risk_distance if signal == "long" else entry + risk_distance
                target = entry + risk_distance * 2 if signal == "long" else entry - risk_distance * 2
                risk_amount = capital * risk_pct / 100
                quantity = risk_amount / risk_distance
                position = {
                    "direction": signal,
                    "entry": _number(entry),
                    "entry_ts": row.ts.isoformat(),
                    "stop": _number(stop),
                    "target": _number(target),
                    "quantity": _number(quantity),
                    "risk_amount": _number(risk_amount),
                    "strategy": strategy,
                }

        equity_curve.append({"ts": row.ts.isoformat(), "equity": _number(capital, 2)})

    if position is not None:
        last = enriched.iloc[-1]
        closed = _close_trade(position, float(last.close), last.ts, fee_pct, "end_of_data")
        capital += closed["pnl"]
        trades.append(closed)
        equity_curve[-1]["equity"] = _number(capital, 2)

    pnls = [trade["pnl"] for trade in trades]
    winners = [pnl for pnl in pnls if pnl > 0]
    losers = [pnl for pnl in pnls if pnl < 0]
    equity_values = [point["equity"] for point in equity_curve]
    peak = initial_capital
    max_drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, (peak - value) / peak * 100 if peak else 0)
    returns = pd.Series(equity_values).pct_change().dropna()
    sharpe = float(returns.mean() / returns.std() * (len(returns) ** 0.5)) if len(returns) > 1 and returns.std() else 0.0
    metrics = {
        "total_trades": len(trades),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate_pct": _number(len(winners) / len(trades) * 100 if trades else 0, 2),
        "profit_factor": _number(sum(winners) / abs(sum(losers)) if losers else (None if winners else 0), 3),
        "expectancy": _number(sum(pnls) / len(pnls) if pnls else 0, 2),
        "roi_pct": _number((capital - initial_capital) / initial_capital * 100, 2),
        "max_drawdown_pct": _number(max_drawdown, 2),
        "sharpe": _number(sharpe, 3),
        "net_pnl": _number(capital - initial_capital, 2),
        "largest_win": _number(max(pnls) if pnls else 0, 2),
        "largest_loss": _number(min(pnls) if pnls else 0, 2),
    }
    run = BacktestRun(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        started_at=enriched.iloc[0].ts,
        ended_at=enriched.iloc[-1].ts,
        initial_capital=initial_capital,
        config={"risk_pct": risk_pct, "fee_pct": fee_pct, "slippage_pct": slippage_pct, "limit": limit},
        metrics=metrics,
        trades=trades,
        equity_curve=equity_curve,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"status": "ok", "id": run.id, "symbol": symbol, "timeframe": timeframe, "strategy": strategy, "metrics": metrics, "trades": trades, "equity_curve": equity_curve}


def get_backtests(db: Session, symbol: str, limit: int = 20) -> list[dict]:
    rows = db.execute(select(BacktestRun).where(BacktestRun.symbol == symbol).order_by(BacktestRun.created_at.desc()).limit(limit)).scalars()
    return [{"id": row.id, "symbol": row.symbol, "timeframe": row.timeframe, "strategy": row.strategy, "started_at": row.started_at, "ended_at": row.ended_at, "initial_capital": row.initial_capital, "config": row.config, "metrics": row.metrics} for row in rows]


def create_account(db: Session, name: str, initial_capital: float) -> PaperAccount:
    if initial_capital <= 0:
        raise ValueError("El capital inicial debe ser mayor que 0.")
    account = PaperAccount(name=name, initial_capital=initial_capital, current_capital=initial_capital)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def account_view(db: Session, account_id: int) -> dict:
    account = db.get(PaperAccount, account_id)
    if account is None:
        raise ValueError("Cuenta paper no encontrada.")
    trades = db.execute(select(PaperTrade).where(PaperTrade.account_id == account_id).order_by(PaperTrade.opened_at.desc())).scalars().all()
    closed = [trade for trade in trades if trade.status == "closed"]
    wins = sum(1 for trade in closed if (trade.pnl or 0) > 0)
    return {"id": account.id, "name": account.name, "initial_capital": account.initial_capital, "current_capital": account.current_capital, "roi_pct": (account.current_capital - account.initial_capital) / account.initial_capital * 100, "trades": [_paper_trade_view(trade) for trade in trades], "closed_trades": len(closed), "win_rate_pct": wins / len(closed) * 100 if closed else 0}


def _paper_trade_view(trade: PaperTrade) -> dict:
    return {"id": trade.id, "account_id": trade.account_id, "symbol": trade.symbol, "direction": trade.direction, "strategy": trade.strategy, "entry": trade.entry, "exit_price": trade.exit_price, "stop": trade.stop, "target": trade.target, "quantity": trade.quantity, "fees_paid": trade.fees_paid, "pnl": trade.pnl, "status": trade.status, "opened_at": trade.opened_at, "closed_at": trade.closed_at, "notes": trade.notes}


def open_paper_trade(db: Session, **data) -> dict:
    account = db.get(PaperAccount, data["account_id"])
    direction = data["direction"].lower()
    if account is None:
        raise ValueError("Cuenta paper no encontrada.")
    if direction not in {"long", "short"} or data["entry"] <= 0 or data["quantity"] <= 0:
        raise ValueError("Dirección, entrada y cantidad no son válidas.")
    trade = PaperTrade(**{**data, "direction": direction})
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return _paper_trade_view(trade)


def close_paper_trade(db: Session, trade_id: int, exit_price: float, fee_pct: float, notes: str | None) -> dict:
    trade = db.get(PaperTrade, trade_id)
    if trade is None or trade.status != "open":
        raise ValueError("La operación paper no existe o ya está cerrada.")
    if exit_price <= 0:
        raise ValueError("El precio de salida debe ser mayor que 0.")
    gross = (exit_price - trade.entry) * trade.quantity * (1 if trade.direction == "long" else -1)
    fees = (trade.entry * trade.quantity + exit_price * trade.quantity) * fee_pct / 100
    trade.exit_price = exit_price
    trade.fees_paid = fees
    trade.pnl = gross - fees
    trade.status = "closed"
    trade.closed_at = datetime.now(timezone.utc)
    if notes:
        trade.notes = notes
    account = db.get(PaperAccount, trade.account_id)
    account.current_capital += trade.pnl
    db.commit()
    db.refresh(trade)
    return _paper_trade_view(trade)


def create_journal_entry(db: Session, **data) -> TradeJournalEntry:
    entry = TradeJournalEntry(**data)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def create_autopsy(db: Session, **data) -> TradeAutopsy:
    if db.get(TradeJournalEntry, data["journal_entry_id"]) is None:
        raise ValueError("Entrada de journal no encontrada.")
    autopsy = TradeAutopsy(**data)
    db.add(autopsy)
    db.commit()
    db.refresh(autopsy)
    return autopsy


def serialize_model(row) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}
