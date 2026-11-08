-- ============================================================
-- BTC INTELLIGENCE AI - FASE 2
-- Derivatives dashboard + refuerzo de Market Structure (BOS/CHOCH)
-- ============================================================

-- ---------------------------------------------------------------
-- derivatives: snapshot periódico de métricas de futuros perpetuos
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS derivatives (
    id                  BIGSERIAL,
    symbol              TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL,
    open_interest       DOUBLE PRECISION,
    open_interest_usd   DOUBLE PRECISION,
    funding_rate        DOUBLE PRECISION,
    predicted_funding    DOUBLE PRECISION,
    long_short_ratio    DOUBLE PRECISION,
    top_trader_ls_ratio DOUBLE PRECISION,
    mark_price          DOUBLE PRECISION,
    index_price         DOUBLE PRECISION,
    basis               DOUBLE PRECISION,     -- mark_price - index_price
    basis_pct           DOUBLE PRECISION,
    source              TEXT NOT NULL DEFAULT 'binance_futures',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, ts)
);

SELECT create_hypertable('derivatives', 'ts', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_derivatives_symbol_ts
    ON derivatives (symbol, ts DESC);

-- ---------------------------------------------------------------
-- liquidations: eventos de liquidación agregados (cuando disponibles)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS liquidations (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    side        TEXT NOT NULL,          -- long / short
    price       DOUBLE PRECISION,
    quantity    DOUBLE PRECISION,
    quantity_usd DOUBLE PRECISION,
    source      TEXT NOT NULL DEFAULT 'binance_futures',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_liquidations_symbol_ts
    ON liquidations (symbol, ts DESC);

-- ---------------------------------------------------------------
-- signals: señales/anomalías detectadas por los distintos módulos
-- (usada desde Fase 2 para anomalías de derivados; se ampliará en fases futuras)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signals (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    category    TEXT NOT NULL,      -- technical / derivatives / onchain / news / macro / sentiment
    signal_type TEXT NOT NULL,      -- e.g. long_squeeze, funding_extreme, bos, choch
    severity    TEXT NOT NULL DEFAULT 'info',  -- info / warning / critical
    direction   TEXT,               -- bullish / bearish / neutral
    message     TEXT NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_ts
    ON signals (symbol, ts DESC);
