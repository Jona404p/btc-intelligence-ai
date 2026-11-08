"""
Wrapper delgado sobre el cliente de Qdrant (vector DB local, Fase 4).

Responsabilidades:
  - asegurar que la colección exista con el tamaño de vector correcto.
  - upsert de chunks (id, vector, payload con metadatos para filtrar/mostrar).
  - búsqueda semántica (top-k), opcionalmente filtrada por categoría.
  - borrado de todos los puntos asociados a un documento (al eliminarlo).

No se inventa nada aquí: si Qdrant no está disponible, las funciones lanzan
la excepción original para que el router la traduzca en un HTTP 503 claro.
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.QDRANT_URL)
    return _client


def is_available() -> bool:
    try:
        get_client().get_collections()
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_collection(vector_size: int) -> None:
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if settings.QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )


def upsert_chunk(
    point_id: str,
    vector: list[float],
    document_id: int,
    document_title: str,
    category: str,
    chunk_index: int,
) -> None:
    ensure_collection(len(vector))
    client = get_client()
    client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=[
            qmodels.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "document_id": document_id,
                    "document_title": document_title,
                    "category": category,
                    "chunk_index": chunk_index,
                },
            )
        ],
    )


def search(
    vector: list[float],
    top_k: int = 5,
    category: str | None = None,
    score_threshold: float | None = None,
):
    client = get_client()
    query_filter = None
    if category:
        query_filter = qmodels.Filter(
            must=[qmodels.FieldCondition(key="category", match=qmodels.MatchValue(value=category))]
        )
    return client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=vector,
        limit=top_k,
        query_filter=query_filter,
        score_threshold=score_threshold,
        with_payload=True,
    )


def delete_document_points(document_id: int) -> None:
    client = get_client()
    try:
        client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id", match=qmodels.MatchValue(value=document_id)
                        )
                    ]
                )
            ),
        )
    except Exception:  # noqa: BLE001
        # Si la colección no existe todavía, no hay nada que borrar.
        pass
