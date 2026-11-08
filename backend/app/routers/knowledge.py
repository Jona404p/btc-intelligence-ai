import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import Document
from app.schemas import DocumentOut, KnowledgeAskRequest, KnowledgeAskResponse
from app.services import documents as documents_service
from app.services import library_scanner, rag

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Única fuente de verdad para las categorías: app/services/documents.py
# (también es la lista de carpetas esperadas en la biblioteca local).
VALID_CATEGORIES = documents_service.VALID_CATEGORIES


def _run_ingestion(document_id: int) -> None:
    """Corre en background (BackgroundTasks): necesita su propia sesión de DB."""
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            logger.error("Documento %s no encontrado para ingesta.", document_id)
            return
        rag.ingest_document(db, document)
    finally:
        db.close()


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    category: str = Form(default="other"),
    db: Session = Depends(get_db),
):
    """
    Sube un documento (PDF/TXT/MD) al Knowledge Center. La indexación
    (extracción + chunking + embeddings + Qdrant) corre en background;
    el documento queda con status="processing" y luego pasa a "ready" o "error".
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in documents_service.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado ({ext or 'desconocido'}). Usa PDF, TXT o MD.",
        )

    category = category if category in VALID_CATEGORIES else "other"

    storage_dir = Path(settings.DOCUMENTS_STORAGE_PATH) / category
    storage_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", file.filename or "documento")
    stored_filename = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = storage_dir / stored_filename

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    document = Document(
        title=title or (file.filename or stored_filename),
        category=category,
        filename=file.filename or stored_filename,
        file_path=str(file_path),
        file_type=documents_service.infer_file_type(file.filename or ""),
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(_run_ingestion, document.id)

    return document


@router.get("/categories")
def list_categories():
    """Categorías válidas + su descripción (son también los nombres de carpeta esperados en la biblioteca local)."""
    return documents_service.KNOWLEDGE_CATEGORIES


def _run_library_scan() -> None:
    db = SessionLocal()
    try:
        library_scanner.scan_library(db)
    finally:
        db.close()


@router.post("/scan-library")
def scan_library_endpoint(background_tasks: BackgroundTasks):
    """
    Dispara un escaneo de la carpeta local de biblioteca (LIBRARY_PATH,
    montada desde tu PC vía docker-compose). Corre en background porque
    puede tardar si hay muchos documentos nuevos; consulta el progreso con
    GET /knowledge/documents?source=library (o simplemente espera y refresca).
    """
    background_tasks.add_task(_run_library_scan)
    return {
        "status": "scanning",
        "message": (
            "Escaneo iniciado en segundo plano. Los documentos nuevos aparecerán "
            "en /knowledge/documents con status='processing' y luego 'ready'."
        ),
    }


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(category: str | None = None, source: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Document).order_by(Document.uploaded_at.desc())
    if category:
        query = query.filter(Document.category == category)
    if source:
        query = query.filter(Document.source == source)
    return query.all()


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    rag.delete_document(db, document)
    return {"status": "ok", "message": f"Documento {document_id} eliminado."}


@router.post("/ask", response_model=KnowledgeAskResponse)
def ask_knowledge(payload: KnowledgeAskRequest, db: Session = Depends(get_db)):
    """
    Pregunta libre contra el Knowledge Center (RAG). La IA responde solo con
    base en los fragmentos recuperados de Qdrant; nunca inventa fuentes.
    """
    try:
        result = rag.ask(db, payload.question, category=payload.category, top_k=payload.top_k)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return KnowledgeAskResponse(
        question=result["question"],
        answer=result["answer"],
        sources=result["sources"],
        model=result["model"],
        ts=datetime.now(timezone.utc),
    )
