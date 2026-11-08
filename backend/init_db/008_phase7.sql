-- ============================================================
-- BTC INTELLIGENCE AI - FASE 7
-- Backtesting + Paper Trading + Trade Journal + Trade Autopsy
-- ============================================================

CREATE TABLE IF NOT EXISTS backtests (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    strategy TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    initial_capital DOUBLE PRECISION NOT NULL,
    config JSONB NOT NULL,
    metrics JSONB NOT NULL,
    trades JSONB NOT NULL,
    equity_curve JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_backtests_symbol_created ON backtests (symbol, created_at DESC);

CREATE TABLE IF NOT EXISTS paper_accounts (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    initial_capital DOUBLE PRECISION NOT NULL,
    current_capital DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES paper_accounts(id),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    strategy TEXT,
    entry DOUBLE PRECISION NOT NULL,
    exit_price DOUBLE PRECISION,
    stop DOUBLE PRECISION,
    target DOUBLE PRECISION,
    quantity DOUBLE PRECISION NOT NULL,
    fees_paid DOUBLE PRECISION NOT NULL DEFAULT 0,
    pnl DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'open',
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_paper_trades_account_status ON paper_trades (account_id, status, opened_at DESC);

CREATE TABLE IF NOT EXISTS trade_journal (
    id BIGSERIAL PRIMARY KEY,
    paper_trade_id BIGINT REFERENCES paper_trades(id),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    strategy TEXT,
    entry DOUBLE PRECISION,
    exit_price DOUBLE PRECISION,
    stop DOUBLE PRECISION,
    target DOUBLE PRECISION,
    market_regime TEXT,
    ai_score DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    reason TEXT NOT NULL,
    result TEXT,
    roi_pct DOUBLE PRECISION,
    r_multiple DOUBLE PRECISION,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_trade_journal_created ON trade_journal (created_at DESC);

CREATE TABLE IF NOT EXISTS trade_autopsies (
    id BIGSERIAL PRIMARY KEY,
    journal_entry_id BIGINT NOT NULL REFERENCES trade_journal(id),
    why_won TEXT,
    why_lost TEXT,
    indicators_worked JSONB,
    indicators_failed JSONB,
    regime_correct BOOLEAN,
    excessive_leverage BOOLEAN NOT NULL DEFAULT FALSE,
    error_type TEXT,
    lessons TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_trade_autopsies_journal ON trade_autopsies (journal_entry_id, created_at DESC);
