"""
Extracción de texto y chunking para el Knowledge Center (Fase 4).

Formatos soportados: PDF (.pdf), texto plano (.txt) y Markdown (.md).
No se usa OCR ni se inventa contenido: si un PDF no tiene texto extraíble
(por ejemplo, un escaneo de imágenes), se reporta con char_count=0 y el
documento queda en estado "error" para que el usuario lo sepa.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from app.config import settings


def hash_file(file_path: str) -> str:
    """sha256 del contenido del archivo, para deduplicar/detectar cambios."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}

# Categorías del Knowledge Center. La clave es también el nombre de carpeta
# esperado dentro de la biblioteca local (knowledge_library/<clave>/...).
# Único lugar donde se define esta lista: el router y el escáner de
# biblioteca la importan de aquí para no duplicarla.
KNOWLEDGE_CATEGORIES: dict[str, str] = {
    "technical_analysis": "Análisis técnico: indicadores, medias móviles, osciladores, teoría de Dow, Elliott, Wyckoff.",
    "candlesticks": "Patrones de velas japonesas y price patterns clásicos (doji, engulfing, martillo, etc.).",
    "price_action": "Price action puro: estructura de mercado, soportes/resistencias, order blocks, liquidez.",
    "psychology": "Psicología del trading: disciplina, sesgos cognitivos, gestión emocional, journaling.",
    "risk_management": "Gestión de riesgo y money management: tamaño de posición, R:R, stop loss, drawdown.",
    "crypto": "Contenido específico de cripto/BTC: on-chain, tokenomics, ciclos de mercado, halving.",
    "quantitative_trading": "Trading cuantitativo/algorítmico: backtesting, estadística, sistemas, machine learning aplicado.",
    "behavioral_finance": "Finanzas conductuales y economía: sesgos de mercado, ciclos macro, historia financiera.",
    "other": "Cualquier documento que no encaje claramente en las categorías anteriores.",
}

VALID_CATEGORIES = set(KNOWLEDGE_CATEGORIES.keys())


def infer_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".md":
        return "md"
    return "txt"


def extract_text(file_path: str, file_type: str) -> str:
    """Extrae texto plano de un archivo ya guardado en disco."""
    if file_type == "pdf":
        reader = PdfReader(file_path)
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(text)
        return "\n\n".join(pages_text).strip()

    # txt / md: texto plano, con manejo tolerante de encoding.
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """
    Chunking simple por caracteres con solapamiento, respetando saltos de
    párrafo cuando es posible para no cortar frases a la mitad de forma tosca.
    """
    chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
    overlap = overlap or settings.RAG_CHUNK_OVERLAP
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
            continue

        if current:
            chunks.append(current)
            # Solapamiento: arrastra la cola del chunk anterior al siguiente.
            current = current[-overlap:] if overlap > 0 else ""

        if len(para) > chunk_size:
            # Párrafo demasiado largo por sí solo: se corta en bloques fijos.
            start = 0
            while start < len(para):
                end = start + chunk_size
                piece = para[start:end]
                if current:
                    chunks.append(f"{current}\n\n{piece}" if current != piece else piece)
                    current = piece[-overlap:] if overlap > 0 else ""
                else:
                    chunks.append(piece)
                start = end
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        chunks.append(current)

    return [c.strip() for c in chunks if c.strip()]
