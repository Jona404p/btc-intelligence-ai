"""
Escáner de la Biblioteca Local (Fase 4b).

Idea: en vez de subir archivos uno por uno desde la web, el usuario tiene una
carpeta en su PC (montada dentro del contenedor backend, ver docker-compose.yml)
con una subcarpeta por categoría:

    knowledge_library/
        technical_analysis/
        candlesticks/
        price_action/
        psychology/
        risk_management/
        crypto/
        quantitative_trading/
        behavioral_finance/
        other/

El usuario simplemente copia PDFs/TXT/MD dentro de la carpeta de la categoría
que corresponda. Este módulo recorre esa carpeta (recursivo, admite
subcarpetas dentro de cada categoría para organizarse mejor) y:

  1. Detecta archivos nuevos -> los registra como Document(source="library")
     y dispara el pipeline de ingesta normal (texto -> chunks -> embeddings).
  2. Detecta archivos ya indexados cuyo contenido cambió (hash distinto)
     -> borra el documento viejo (y sus vectores en Qdrant) y re-indexa.
  3. Ignora archivos ya indexados sin cambios.

No borra documentos si el archivo se elimina de la carpeta (para evitar
pérdidas accidentales); eso se sigue haciendo a mano desde la UI.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document
from app.services import documents as documents_service
from app.services import rag

logger = logging.getLogger(__name__)


def ensure_library_folders() -> None:
    """Crea la carpeta raíz + una subcarpeta por categoría si no existen."""
    root = Path(settings.LIBRARY_PATH)
    for category in documents_service.KNOWLEDGE_CATEGORIES:
        (root / category).mkdir(parents=True, exist_ok=True)


def _category_for_path(file_path: Path, root: Path) -> str:
    try:
        relative = file_path.relative_to(root)
    except ValueError:
        return "other"
    top_folder = relative.parts[0] if relative.parts else "other"
    return top_folder if top_folder in documents_service.KNOWLEDGE_CATEGORIES else "other"


def scan_library(db: Session) -> dict:
    """
    Recorre LIBRARY_PATH, indexa archivos nuevos/modificados.
    Devuelve un resumen: {"new": n, "updated": n, "skipped": n, "errors": n}
    """
    root = Path(settings.LIBRARY_PATH)
    root.mkdir(parents=True, exist_ok=True)
    ensure_library_folders()

    summary = {"new": 0, "updated": 0, "skipped": 0, "errors": 0}

    # Índice de documentos de biblioteca ya conocidos, por ruta de archivo.
    existing_by_path: dict[str, Document] = {
        doc.file_path: doc
        for doc in db.execute(select(Document).where(Document.source == "library")).scalars().all()
    }

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in documents_service.SUPPORTED_EXTENSIONS:
            continue

        path_str = str(file_path)
        try:
            file_hash = documents_service.hash_file(path_str)
        except OSError as exc:
            logger.warning("No se pudo leer %s: %s", path_str, exc)
            summary["errors"] += 1
            continue

        category = _category_for_path(file_path, root)
        existing = existing_by_path.get(path_str)

        if existing is not None:
            if existing.file_hash == file_hash:
                summary["skipped"] += 1
                continue
            # El archivo cambió de contenido: se re-indexa desde cero.
            logger.info("Archivo modificado, re-indexando: %s", path_str)
            rag.delete_document(db, existing)
            summary["updated"] += 1
        else:
            summary["new"] += 1

        document = Document(
            title=file_path.stem,
            category=category,
            filename=file_path.name,
            file_path=path_str,
            file_type=documents_service.infer_file_type(file_path.name),
            status="processing",
            source="library",
            file_hash=file_hash,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            rag.ingest_document(db, document)
        except Exception:  # noqa: BLE001
            logger.exception("Error indexando %s desde la biblioteca", path_str)
            summary["errors"] += 1

    logger.info("Escaneo de biblioteca completo: %s", summary)
    return summary
