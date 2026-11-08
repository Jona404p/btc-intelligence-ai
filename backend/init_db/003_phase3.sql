-- ============================================================
-- BTC INTELLIGENCE AI - FASE 3
-- News Intelligence + Macro Dashboard + Sentiment
-- ============================================================

-- ---------------------------------------------------------------
-- news: noticias recolectadas de fuentes RSS reales, clasificadas
-- por sentimiento heurístico (bullish/bearish/neutral) y relevancia.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news (
    id                BIGSERIAL PRIMARY KEY,
    ts                TIMESTAMPTZ NOT NULL,
    title             TEXT NOT NULL,
    source            TEXT NOT NULL,
    url               TEXT NOT NULL UNIQUE,
    summary           TEXT,
    sentiment         TEXT,          -- bullish / bearish / neutral
    relevance         DOUBLE PRECISION,
    potential_impact  TEXT,          -- low / medium / high
    affected_asset    TEXT NOT NULL DEFAULT 'BTC',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_news_ts ON news (ts DESC);

-- ---------------------------------------------------------------
-- macro_data: series de indicadores macroeconómicos (DXY, S&P500,
-- NASDAQ, VIX, US10Y, Gold), obtenidos de fuentes reales (Yahoo Finance).
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS macro_data (
    id          BIGSERIAL,
    ts          TIMESTAMPTZ NOT NULL,
    indicator   TEXT NOT NULL,       -- DXY / SPX / NDX / VIX / US10Y / GOLD
    value       DOUBLE PRECISION,
    change_pct  DOUBLE PRECISION,
    source      TEXT NOT NULL DEFAULT 'yfinance',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (indicator, ts)
);

SELECT create_hypertable('macro_data', 'ts', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_macro_indicator_ts ON macro_data (indicator, ts DESC);

-- ---------------------------------------------------------------
-- sentiment: snapshot combinado de Fear & Greed Index (alternative.me)
-- + distribución bullish/bearish/neutral de las noticias recientes.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sentiment (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL,
    fng_value           DOUBLE PRECISION,
    fng_classification  TEXT,        -- Extreme Fear / Fear / Neutral / Greed / Extreme Greed
    news_bullish_pct    DOUBLE PRECISION,
    news_bearish_pct    DOUBLE PRECISION,
    news_neutral_pct    DOUBLE PRECISION,
    news_sample_size    BIGINT,
    overall_sentiment   TEXT,        -- BULLISH / NEUTRAL / BEARISH
    source              TEXT NOT NULL DEFAULT 'alternative.me+news',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sentiment_symbol_ts ON sentiment (symbol, ts DESC);
