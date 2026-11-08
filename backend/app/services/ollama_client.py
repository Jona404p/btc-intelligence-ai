"""
Cliente mínimo para Ollama (LLM local) vía su API HTTP (/api/generate).

Reglas de la IA (ver seccion 37 del spec):
  - No inventar datos ni fuentes.
  - No garantizar ganancias.
  - Si los datos son insuficientes, debe poder decir "Datos insuficientes".
Estas reglas se imponen mediante el system prompt.
"""

from __future__ import annotations

import httpx

from app.config import settings

SYSTEM_PROMPT = f"""Eres PanCrasito, un gatito analista de mercado especializado en BTC/USDT.

IDENTIDAD DEL SISTEMA:
- Fuiste creado por {settings.AI_CREATOR_NAME}, tu papá y creador. Le tienes mucho cariño y respeto.
- Si te preguntan quién te creó, quién es tu creador, autor o desarrollador, responde claramente: "Fui creado por {settings.AI_CREATOR_NAME}."
- No confundas esta identidad con una fuente, precio, noticia o dato de mercado.

PERSONALIDAD:
- Sé curioso, inteligente, claro y buena onda, pero también realista y humilde.
- Puedes mostrar cariño por tu papá Jonathan cuando sea natural, sin adularlo de forma repetitiva.
- Explica tu razonamiento con claridad y reconoce tus límites.

REGLAS ESTRICTAS:
- NUNCA inventes datos, precios, noticias o fuentes que no se te hayan proporcionado.
- NUNCA garantices ganancias ni afirmes certeza sobre el futuro.
- Basa tu análisis ÚNICAMENTE en los datos técnicos proporcionados en el prompt.
- Si los datos son insuficientes o contradictorios, dilo explícitamente ("Datos insuficientes" o "Señales contradictorias").
- Usa lenguaje de probabilidad/condicionalidad ("condiciones favorables para...", "esto sugiere...") en vez de afirmaciones absolutas.
- Siempre menciona qué invalidaría tu análisis.
- Responde en español, de forma concisa y estructurada.
"""


def generate(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    timeout: float = 180.0,
    num_predict: int = 256,
    response_format: str | None = None,
) -> str:
    """Llama al endpoint /api/generate de Ollama y devuelve el texto de respuesta completo (no streaming)."""
    model = model or settings.OLLAMA_MODEL
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system or SYSTEM_PROMPT,
        "stream": False,
        "options": {"num_predict": num_predict},
    }
    if response_format:
        payload["format"] = response_format
    with httpx.Client(base_url=settings.OLLAMA_BASE_URL, timeout=timeout) as client:
        resp = client.post("/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()


def is_available() -> bool:
    """Chequea si el servidor Ollama está accesible."""
    try:
        with httpx.Client(base_url=settings.OLLAMA_BASE_URL, timeout=3.0) as client:
            resp = client.get("/api/tags")
            return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def embed(text: str, model: str | None = None, timeout: float = 60.0) -> list[float]:
    """
    Genera un embedding local vía Ollama (/api/embeddings) para el texto dado.

    Se usa tanto para indexar chunks del Knowledge Center (Fase 4) como para
    embeber la pregunta del usuario antes de buscar en Qdrant. Requiere un
    modelo de embeddings descargado en Ollama (por defecto `nomic-embed-text`):

        docker exec -it btc_ollama ollama pull nomic-embed-text
    """
    model = model or settings.OLLAMA_EMBED_MODEL
    payload = {"model": model, "prompt": text}
    with httpx.Client(base_url=settings.OLLAMA_BASE_URL, timeout=timeout) as client:
        resp = client.post("/api/embeddings", json=payload)
        resp.raise_for_status()
        data = resp.json()
        embedding = data.get("embedding")
        if not embedding:
            raise ValueError("Ollama no devolvió un embedding válido.")
        return embedding
