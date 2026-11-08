-- ============================================================
-- BTC INTELLIGENCE AI - FASE 5
-- Historical Similarity Engine + Market Memory + Anomaly Detection
--
-- La tabla `signals` (creada en 002_phase2.sql) ya se reutiliza para las
-- nuevas anomalías de precio/volumen y para las alertas combinadas
-- multi-categoría; no requiere cambios de esquema, solo nuevos valores de
-- `category` ('price', 'volume', 'combined') y `signal_type`.
-- ============================================================

-- ---------------------------------------------------------------
-- historical_setups: resultados persistidos del motor de similitud
-- histórica (sección 21 del spec). Cada fila = una consulta resuelta.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historical_setups (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    anchor_ts           TIMESTAMPTZ NOT NULL,
    current_features    JSONB NOT NULL,
    matches             JSONB NOT NULL,
    num_matches         BIGINT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_historical_setups_symbol_tf_ts
    ON historical_setups (symbol, timeframe, ts DESC);
