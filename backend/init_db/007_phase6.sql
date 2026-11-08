-- ============================================================
-- BTC INTELLIGENCE AI - FASE 6
-- Trade Finder + ROI Calculator + Position Sizing + Opportunity Ranking
-- (secciones 3, 4, 6, 7, 10, 11, 34, 35 del spec)
-- ============================================================
--
-- ROI Calculator y Position Size Calculator (secciones 6/7) son puramente
-- funciones sobre inputs del usuario: no requieren tabla propia. Lo único
-- que se persiste es el resultado del Opportunity Scanner (Trade Finder),
-- para poder auditar qué encontró el motor y reutilizarlo después en el
-- Trade Journal / Trade Autopsy (fase 7).

CREATE TABLE IF NOT EXISTS trade_opportunities (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    direction           TEXT NOT NULL,               -- long / short
    strategy            TEXT,
    status              TEXT NOT NULL,                -- potential / conditional / rejected
    entry               DOUBLE PRECISION NOT NULL,
    stop                DOUBLE PRECISION NOT NULL,
    target              DOUBLE PRECISION NOT NULL,
    risk_pct            DOUBLE PRECISION NOT NULL,
    potential_roi_pct   DOUBLE PRECISION NOT NULL,
    risk_reward         DOUBLE PRECISION NOT NULL,
    trade_score         DOUBLE PRECISION NOT NULL,
    grade               TEXT NOT NULL,
    confidence          DOUBLE PRECISION NOT NULL,
    confluence          TEXT NOT NULL,
    market_regime       TEXT,
    passed_filters      BOOLEAN NOT NULL DEFAULT TRUE,
    score_breakdown     JSONB NOT NULL,
    factors             JSONB NOT NULL,
    scenario            JSONB,
    invalidation_note   TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_opportunities_symbol_ts
    ON trade_opportunities (symbol, ts DESC);
CREATE INDEX IF NOT EXISTS idx_trade_opportunities_direction
    ON trade_opportunities (symbol, direction, ts DESC);
