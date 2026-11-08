from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import news

router = APIRouter(prefix="/news", tags=["news"])


@router.post("/sync")
def sync_news(db: Session = Depends(get_db)):
    """Descarga noticias reales de los feeds RSS configurados y guarda las relevantes a BTC."""
    return news.sync_news(db)


@router.get("/latest")
def latest_news(limit: int = Query(default=20, le=100), db: Session = Depends(get_db)):
    rows = news.get_latest(db, limit=limit)
    if not rows:
        return {"status": "no_data", "message": "Ejecuta /news/sync primero.", "news": []}
    return {
        "status": "ok",
        "news": [
            {
                "id": r.id,
                "ts": r.ts,
                "title": r.title,
                "source": r.source,
                "url": r.url,
                "summary": r.summary,
                "sentiment": r.sentiment,
                "relevance": r.relevance,
                "potential_impact": r.potential_impact,
                "affected_asset": r.affected_asset,
            }
            for r in rows
        ],
    }


@router.get("/sentiment-breakdown")
def news_sentiment_breakdown(limit: int = Query(default=40, le=200), db: Session = Depends(get_db)):
    return news.sentiment_breakdown(db, limit=limit)


@router.post("/analyze/{news_id}")
def analyze_news_impact(news_id: int, db: Session = Depends(get_db)):
    """'Analyze impact on BTC' - la IA evalúa SOLO la noticia guardada indicada, sin inventar nada más."""
    result = news.analyze_impact(db, news_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Noticia no encontrada.")
    return result
