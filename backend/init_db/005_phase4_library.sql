-- ============================================================
-- BTC INTELLIGENCE AI - FASE 4b
-- Knowledge Center: Biblioteca local (carpeta en disco) además del upload manual
-- ============================================================
--
-- Ahora un documento puede llegar por dos caminos:
--   - "upload": subido a mano desde la web (como antes).
--   - "library": encontrado por el escáner en la carpeta local montada
--     (knowledge_library/<categoria>/...), sin pasar por el navegador.
--
-- file_hash permite detectar archivos ya indexados (no reprocesar) y
-- detectar cuándo el contenido de un archivo cambió (re-indexar).

ALTER TABLE documents ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'upload';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents (source);
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents (file_hash);
