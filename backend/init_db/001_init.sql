-- ============================================================
-- BTC INTELLIGENCE AI - FASE 1
-- Schema inicial: market_candles, indicators, market_snapshots, ai_reports
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ---------------------------------------------------------------
-- market_candles: OHLCV crudo por símbolo / timeframe
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_candles (
    id          BIGSERIAL,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      DOUBLE PRECISION NOT NULL,
    source      TEXT NOT NULL DEFAULT 'binance',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, timeframe, ts)
);

SELECT create_hypertable('market_candles', 'ts', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_ts
    ON market_candles (symbol, timeframe, ts DESC);

-- ---------------------------------------------------------------
-- indicators: valores de indicadores técnicos calculados por vela
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indicators (
    id          BIGSERIAL,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    ema_9       DOUBLE PRECISION,
    ema_21      DOUBLE PRECISION,
    ema_50      DOUBLE PRECISION,
    ema_200     DOUBLE PRECISION,
    sma_20      DOUBLE PRECISION,
    sma_50      DOUBLE PRECISION,
    rsi_14      DOUBLE PRECISION,
    macd        DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    macd_hist   DOUBLE PRECISION,
    atr_14      DOUBLE PRECISION,
    bb_upper    DOUBLE PRECISION,
    bb_middle   DOUBLE PRECISION,
    bb_lower    DOUBLE PRECISION,
    vwap        DOUBLE PRECISION,
    trend       TEXT,               -- bullish / bearish / neutral
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, timeframe, ts)
);

SELECT create_hypertable('indicators', 'ts', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_indicators_symbol_tf_ts
    ON indicators (symbol, timeframe, ts DESC);

-- ---------------------------------------------------------------
-- market_structure: soportes, resistencias, BOS/CHOCH detectados
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_structure (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    level_type  TEXT NOT NULL,      -- support / resistance / bos / choch / liquidity
    price       DOUBLE PRECISION NOT NULL,
    strength    DOUBLE PRECISION,   -- 0-1, basado en toques / volumen
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_structure_symbol_tf_ts
    ON market_structure (symbol, timeframe, ts DESC);

-- ---------------------------------------------------------------
-- market_snapshots: foto consolidada del mercado en un momento dado
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_snapshots (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    price               DOUBLE PRECISION NOT NULL,
    change_24h_pct      DOUBLE PRECISION,
    volume_24h          DOUBLE PRECISION,
    volatility_pct      DOUBLE PRECISION,
    market_regime       TEXT,       -- trending_bull / trending_bear / range / high_vol / low_vol...
    technical_bias      TEXT,       -- bullish / bearish / neutral
    ai_bias             TEXT,
    ai_confidence       DOUBLE PRECISION,
    support_levels      JSONB,
    resistance_levels   JSONB,
    raw_payload         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_ts
    ON market_snapshots (symbol, ts DESC);

-- ---------------------------------------------------------------
-- ai_reports: reportes generados por el LLM local (Ollama)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_reports (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    model           TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    response        TEXT NOT NULL,
    bias            TEXT,
    confidence      DOUBLE PRECISION,
    snapshot_id     BIGINT REFERENCES market_snapshots(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_reports_symbol_ts
    ON ai_reports (symbol, ts DESC);
