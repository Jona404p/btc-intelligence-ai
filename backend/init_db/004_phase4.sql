-- ============================================================
-- BTC INTELLIGENCE AI - FASE 4
-- Knowledge Center + RAG (Retrieval-Augmented Generation)
-- ============================================================
--
-- Los embeddings vectoriales viven en Qdrant (servicio aparte); aquí solo
-- guardamos el texto original de cada chunk (para poder mostrar la fuente
-- exacta usada por la IA) y los metadatos del documento.

-- ---------------------------------------------------------------
-- documents: un registro por archivo subido al Knowledge Center.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'other',
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_type       TEXT NOT NULL,               -- pdf / txt / md
    status          TEXT NOT NULL DEFAULT 'processing',  -- processing / ready / error
    error_message   TEXT,
    num_chunks      BIGINT NOT NULL DEFAULT 0,
    char_count      BIGINT,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_category ON documents (category);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);

-- ---------------------------------------------------------------
-- document_chunks: texto original de cada fragmento indexado en Qdrant.
-- El embedding en sí NO se guarda aquí; solo el texto + el id del punto
-- en Qdrant, para poder mostrar al usuario exactamente qué fuente usó
-- la IA (sección 24 del spec: "Mostrar las fuentes utilizadas por la IA").
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_chunks (
    id                BIGSERIAL PRIMARY KEY,
    document_id       BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index       BIGINT NOT NULL,
    content           TEXT NOT NULL,
    qdrant_point_id   TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks (document_id);
