# Biblioteca de Conocimiento — BTC Intelligence AI

Esta carpeta vive en TU PC (no dentro del contenedor Docker). El backend la
monta como volumen (ver `docker-compose.yml`) y la escanea automáticamente:

- Al arrancar el backend.
- Cada `LIBRARY_SCAN_INTERVAL_MINUTES` (por defecto 10 minutos).
- Cuando llames manualmente a `POST /knowledge/scan-library`.

## Cómo usarla

1. Copia tus PDFs, TXT o MD dentro de la subcarpeta de categoría que
   corresponda (puedes crear subcarpetas dentro de cada categoría para
   organizarte mejor, ej. `technical_analysis/elliott_wave/`).
2. En el dashboard, abre **Conocimiento (RAG)** y pulsa **Sincronizar biblioteca local**.
   También puedes esperar al siguiente escaneo automático o dispararlo por API:
   ```bash
   curl -X POST http://localhost:8000/knowledge/scan-library
   ```
3. Revisa el estado en `GET /knowledge/documents?source=library` o desde el
   Knowledge Center en la web (verás el estado processing -> ready).
4. Activa **Usar conocimiento de `knowledge_library/`** en el chat principal para
   combinar los extractos recuperados con el análisis actual. También puedes preguntar
   desde `/knowledge/ask` o el chat del Knowledge Center para obtener respuestas basadas
   únicamente en documentos, con las fuentes consultadas visibles.

## Formatos soportados
`.pdf`, `.txt`, `.md`

## Notas importantes
- Si modificas el contenido de un archivo ya indexado, el escáner detecta el
  cambio (por hash) y lo re-indexa automáticamente.
- Si BORRAS un archivo de esta carpeta, el documento indexado NO se borra
  solo (por seguridad); bórralo a mano desde la UI o con
  `DELETE /knowledge/documents/{id}` si ya no lo quieres.
- No hace falta reiniciar Docker para agregar archivos nuevos: solo cópialos
  y espera el próximo escaneo (o dispáralo manualmente).
- Los documentos no se usan para reentrenar el modelo. Se indexan en Qdrant y, por pregunta,
  se recuperan solo los fragmentos semánticamente relevantes; los demás siguen almacenados
  para futuras consultas. Esto permite conservar bibliotecas extensas sin desbordar el contexto
  que el modelo puede leer en una sola respuesta.
