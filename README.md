# BTC Intelligence AI — Fase 1 + Fase 2 + Fase 3 + Fase 4 + Fase 5

**Fase 1:** Market Data + Database (TimescaleDB) + Technical Analysis + Chart + Ollama + Dashboard
**Fase 2:** Multi-Timeframe Analysis + Market Structure (BOS/CHOCH) + Derivatives Dashboard
**Fase 3:** News Intelligence + Macro Dashboard + Sentiment (Fear & Greed)
**Fase 4:** Knowledge Center + RAG (Qdrant + embeddings locales vía Ollama)
**Fase 5:** Historical Similarity Engine + Anomaly Detector (precio/volumen + alertas combinadas)

Esta es la plataforma de inteligencia y análisis de trading para BTC/USDT. Incluye:

**Fase 1:**
- Backend en **FastAPI** que descarga velas reales de Binance (vía `ccxt`), calcula indicadores
  técnicos (EMA, SMA, RSI, MACD, ATR, Bollinger Bands, VWAP), detecta soportes/resistencias y
  clasifica el régimen de mercado.
- Base de datos **PostgreSQL + TimescaleDB** con hypertables para series temporales.
- Integración con **Ollama** (LLM local) para generar un "AI Market Bias" con evidencia y nivel
  de confianza — sin inventar datos ni garantizar resultados.
- Frontend en **Next.js + TypeScript** con un dashboard: gráfico de velas (TradingView
  Lightweight Charts), tarjeta de Market Overview, y un chat básico para preguntarle a la IA.

**Fase 2 (nuevo):**
- **Market Structure Engine**: detecta swing highs/lows, tendencia estructural, y eventos
  **BOS** (Break of Structure) y **CHOCH** (Change of Character), marcados directamente en el
  gráfico de velas.
- **Multi-Timeframe Analysis**: analiza 5m/15m/1h/4h/1d simultáneamente y calcula un consenso
  de tendencia ("X/Y timeframes bullish").
- **Derivatives Dashboard**: Open Interest, Funding Rate, Long/Short Ratio, Basis (mark vs
  index price), obtenidos de Binance Futures vía `ccxt`.
- **Detección de anomalías en derivados**: funding extremo, long/short ratio extremo (posible
  long/short squeeze), basis anómalo, spikes de Open Interest — todo persistido en la tabla
  `signals` para auditoría histórica.
- El **AI Market Bias** ahora recibe también contexto de estructura de mercado y derivados,
  no solo indicadores técnicos.

**Fase 3 (nuevo):**
- **News Intelligence**: recolecta noticias reales desde feeds RSS de CoinDesk, Cointelegraph
  y Decrypt (sin API key), filtra las relevantes a BTC, y las clasifica como bullish/bearish/
  neutral con una heurística de palabras clave transparente y ajustable
  (`backend/app/services/news.py`). Cada noticia se puede analizar individualmente con
  **"Analyze impact on BTC"**, que le pasa a Ollama únicamente el titular+resumen real (no
  puede inventar nada fuera de eso).
- **Macro Dashboard**: DXY, S&P 500, NASDAQ, VIX, US10Y y Gold vía Yahoo Finance (`yfinance`,
  sin API key). Clasifica el entorno como **RISK-ON / NEUTRAL / RISK-OFF** con una heurística
  documentada y ajustable.
- **Sentiment**: combina el **Fear & Greed Index** real (API pública de `alternative.me`) con
  la distribución bullish/bearish/neutral de las noticias recolectadas, para un veredicto
  `overall_sentiment` (BULLISH/NEUTRAL/BEARISH). Reddit, X y Google Trends quedan documentados
  como fuentes pendientes (requieren credenciales/scraping no disponibles localmente) — no se
  simulan.
- El **AI Market Bias** ahora también recibe contexto de noticias, entorno macro y sentimiento
  al construir el Market Overview.
- **Fix de CORS/500**: se agregó un manejador global de excepciones en `main.py`. Antes, una
  excepción no controlada en cualquier endpoint (p. ej. `/ai/ask`) escapaba por fuera de
  `CORSMiddleware`, y el navegador solo mostraba *"CORS Missing Allow Origin"* en vez del
  error real. Ahora cualquier excepción no controlada se resuelve dentro del stack de
  middlewares correcto, así que siempre lleva las cabeceras CORS y el detalle real del error.

**Fase 4 (nuevo):**
- **Knowledge Center**: subida de documentos (PDF/TXT/MD — libros, papers, notas de research)
  clasificados por categoría (Technical Analysis, Price Action, Psychology, Risk Management,
  Crypto, Quantitative Trading, Behavioral Finance, etc). Cada documento se trocea en chunks
  con solapamiento (`backend/app/services/documents.py`), se embebe localmente con Ollama
  (`nomic-embed-text` vía `/api/embeddings`) y se indexa en **Qdrant** (vector DB local).
  La ingesta corre en background: el documento queda en estado `processing` y pasa a `ready`
  o `error` (por ejemplo si un PDF escaneado no tiene texto extraíble — nunca se inventa
  contenido).
- **RAG (`/knowledge/ask`)**: el usuario pregunta en lenguaje natural; el sistema embebe la
  pregunta, recupera los `top_k` fragmentos más relevantes de Qdrant (opcionalmente filtrando
  por categoría) y se los pasa a Ollama como **única fuente permitida**. El modelo debe citar
  el documento de origen y decir explícitamente si los fragmentos no bastan para responder —
  nunca inventa fuentes ni datos fuera de lo recuperado (sección 24/37 del spec).
- **Biblioteca en el chat de PanCrasito**: activa «Usar conocimiento de `knowledge_library/`»
  para recuperar fragmentos relevantes y combinarlos con el contexto técnico actual; la
  respuesta incluye los títulos de sus fuentes. Sincroniza primero la biblioteca desde Knowledge
  Center y espera a que los documentos estén en estado `ready`. Esto no reentrena ni modifica el
  modelo: indexa los documentos localmente en Qdrant y consulta los fragmentos pertinentes por
  similitud para no enviar libros completos al contexto de cada pregunta.
- El texto de cada chunk se guarda también en Postgres (`document_chunks`) para poder mostrar
  al usuario, en el frontend, la fuente exacta usada por la IA (expandible por fragmento, con
  su score de similitud).
- Nueva tarjeta **Knowledge Center** en el dashboard: subir documentos, ver su estado de
  indexación, eliminarlos, y un chat de preguntas/respuestas con las fuentes citadas.

**Fase 5 (nuevo):**
- **Historical Similarity Engine (`/historical/similar`)**: describe el setup actual (retorno
  reciente, RSI, cambio de volumen, volatilidad ATR%, momentum MACD normalizado) con un vector
  de features simple y transparente, y busca en el propio historial de velas ya guardado
  (`market_candles`) los `top_k` momentos más parecidos. Para cada match muestra qué ocurrió
  después (retorno futuro, máxima ganancia y máxima pérdida en una ventana fija de velas). Todo
  el cálculo corre sobre datos reales ya sincronizados — si no hay suficiente historial, el
  endpoint responde `"status": "insufficient_data"` en vez de inventar un resultado. Cada
  consulta resuelta se persiste en `historical_setups` para auditoría (sección 21/37 del spec).
- **Anomaly Detector (`/anomalies/scan`, `/anomalies/latest`)**: calcula z-scores de precio
  (retorno de las últimas 3 velas vs su propia distribución reciente) y de volumen (vs su media
  móvil), sobre el timeframe rápido (5m por defecto, corre automáticamente cada 5 minutos).
  Además correlaciona estas anomalías con las ya detectadas en Derivados (funding extremo,
  long/short ratio extremo, spikes de Open Interest) para generar **alertas combinadas** del
  estilo "posible short squeeze" cuando varias señales independientes coinciden en una ventana
  corta de tiempo — exactamente el ejemplo de la sección 23 del spec. Todo queda persistido en
  la tabla `signals` ya existente (nuevas categorías `price`/`volume`/`combined`), visible desde
  la nueva pestaña **"Memoria & Alertas"** del dashboard.

> ⚠️ Esta plataforma NO ejecuta operaciones reales. Es una herramienta de análisis y
> evaluación de riesgo, no un sistema de señales garantizadas. La similitud histórica y las
> anomalías detectadas son heurísticas explicables, no predicciones ni probabilidades validadas
> estadísticamente.

---

## 1. Requisitos

- Docker y Docker Compose instalados.
- ~8 GB de RAM libres (para correr un modelo pequeño de Ollama, p.ej. `llama3.1:8b`).
- Conexión a internet (para descargar velas reales de Binance y el modelo de Ollama).

## 2. Levantar el entorno

```bash
cd btc-intelligence-ai
cp backend/.env.example backend/.env   # ya viene creado, pero revisa/ajusta si quieres
docker compose up --build
```

Esto levanta:

| Servicio     | Puerto | Descripción                          |
|--------------|--------|---------------------------------------|
| timescaledb  | 5433   | Base de datos (5432 dentro de Docker) |
| qdrant       | 6333   | Vector DB (se usará en Fase 4 - RAG)  |
| ollama       | 11434  | LLM local                             |
| backend      | 8000   | API FastAPI                           |
| frontend     | 3000   | Dashboard Next.js                     |

## 3. Descargar un modelo en Ollama (una sola vez)

```bash
docker exec -it btc_ollama ollama pull llama3.1
docker exec -it btc_ollama ollama pull gemma2:2b
```

El proyecto usa dos modelos con responsabilidades distintas:

- `OLLAMA_MODEL=llama3.1`: Binance AI Analyst, RAG, análisis técnico, propuestas y riesgo.
- `OLLAMA_CHAT_MODEL=gemma2:2b`: conversación casual y saludos rápidos.

Si cambias los modelos, actualiza las variables correspondientes en `backend/.env` y recrea el
backend. No cambies `OLLAMA_MODEL` a Gemma si quieres conservar la calidad del análisis financiero.

Para el **Knowledge Center / RAG (Fase 4)** además necesitas un modelo de embeddings:

```bash
docker exec -it btc_ollama ollama pull nomic-embed-text
```

(o el que prefieras, actualizando `OLLAMA_EMBED_MODEL` en `backend/.env`).

## 4. Sincronizar datos de mercado

El backend sincroniza automáticamente cada 60 segundos, pero para la primera carga (con más
historial) puedes forzarlo manualmente:

```bash
curl -X POST "http://localhost:8000/market/sync?symbol=BTC/USDT&limit=500"
```

O simplemente haz click en **"🔄 Sync Market Data"** dentro del dashboard.

## 5. Abrir el dashboard

Ve a **http://localhost:3000**

Verás:

- El gráfico de velas de BTC/USDT con soportes y resistencias marcados.
- La tarjeta de Market Overview: precio, cambio 24h, volatilidad, régimen de mercado, y el
  **AI Market Bias** (bullish/bearish/neutral) con su nivel de confianza y explicación.
- Un chat simple para preguntas como *"¿Existe una oportunidad LONG ahora?"*.

## 6. Explorar la API directamente

FastAPI expone documentación interactiva en **http://localhost:8000/docs**

Endpoints de Fase 1:

- `POST /market/sync` — descarga y guarda velas reales.
- `POST /sync/all` — sincroniza de una vez mercado, derivados, noticias, macro, sentimiento,
  biblioteca local, anomalías y oportunidades. Si una fuente falla, las demás continúan y la
  respuesta indica `failed_steps`.
- `GET /market/candles` — velas OHLCV guardadas.
- `GET /market/indicators` — indicadores técnicos calculados.
- `GET /market/levels` — soportes y resistencias detectados.
- `GET /market/overview` — resumen completo + AI Market Bias.
- `POST /ai/ask` — pregunta libre a la IA con contexto técnico real inyectado.

Endpoints de Fase 2:

- `GET /market/structure` — swings, tendencia estructural, eventos BOS/CHOCH.
- `GET /market/multi-timeframe` — consenso de tendencia entre 5m/15m/1h/4h/1d.
- `POST /derivatives/sync` — descarga OI, funding rate y L/S ratio, y corre detección de anomalías.
- `GET /derivatives/latest` — último snapshot de derivados guardado.
- `GET /derivatives/history` — histórico de derivados (para graficar funding/OI en el tiempo).

> Nota: `/derivatives/sync` requiere que el símbolo tenga mercado de futuros perpetuos en
> Binance (BTC/USDT lo tiene). El scheduler interno ya lo sincroniza automáticamente cada
> 5 minutos, así que normalmente no necesitas llamarlo manualmente salvo para forzar un refresh.

Endpoints de Fase 3:

- `POST /news/sync` — descarga noticias reales de los feeds RSS configurados.
- `GET /news/latest` — últimas noticias guardadas, con su clasificación de sentimiento.
- `GET /news/sentiment-breakdown` — % bullish/bearish/neutral sobre las últimas noticias.
- `POST /news/analyze/{news_id}` — "Analyze impact on BTC" de una noticia puntual (usa Ollama).
- `POST /macro/sync` — descarga datos macro reales (Yahoo Finance).
- `GET /macro/latest` — último snapshot macro + clasificación RISK-ON/NEUTRAL/RISK-OFF.
- `GET /macro/history?indicator=DXY` — histórico de un indicador (DXY, SPX, NDX, VIX, US10Y, GOLD).
- `POST /sentiment/sync` — refresca Fear & Greed Index + distribución de noticias.
- `GET /sentiment/latest` — último snapshot de sentimiento combinado.
- `GET /sentiment/history` — histórico de sentimiento.

> Nota: `/macro/sync` y `/sentiment/sync` no requieren API keys (Yahoo Finance y alternative.me
> son públicas). El scheduler interno sincroniza noticias cada 10 min, y macro/sentimiento cada
> 15 min.

Endpoints de Fase 4:

- `POST /knowledge/upload` — sube un documento (multipart/form-data: `file`, `category`,
  `title` opcional). Devuelve el documento con `status="processing"`; la indexación corre en
  background.
- `GET /knowledge/documents` — lista documentos subidos (opcionalmente filtrado por
  `?category=`), con su estado (`processing` / `ready` / `error`) y número de chunks.
- `DELETE /knowledge/documents/{id}` — elimina el documento, sus chunks en Postgres y sus
  vectores en Qdrant.
- `POST /knowledge/ask` — pregunta en RAG: `{ "question": "...", "category": null, "top_k": 5 }`.
  Devuelve la respuesta de la IA junto con las fuentes (`document_title`, `chunk_index`,
  `content`, `score`) usadas para generarla.
- `POST /ai/ask` acepta `use_knowledge: true` para incluir fragmentos relevantes de documentos
  indexados en la respuesta de PanCrasito; su valor predeterminado es `false` para clientes API
  anteriores.

> Nota: RAG requiere que Qdrant y Ollama estén corriendo, y que el modelo de
> embeddings (`nomic-embed-text` por defecto) esté descargado. Si no hay documentos indexados
> listos (o ninguno coincide con la consulta/filtro), el Knowledge Center lo dice explícitamente;
> en el chat principal se responde sin citas de la biblioteca.

Endpoints de Fase 5:

- `GET /historical/similar?symbol=BTC/USDT&timeframe=1h&lookback_window=20&forward_window=10&top_k=5`
  — busca los setups históricos más parecidos al actual y qué ocurrió después de cada uno.
  Devuelve `"status": "insufficient_data"` si no hay suficientes velas guardadas.
- `GET /historical/history?symbol=BTC/USDT` — últimas consultas de similitud ya resueltas
  (sin recalcular), para auditoría rápida.
- `POST /anomalies/scan?symbol=BTC/USDT&timeframe=5m` — corre la detección de anomalías de
  precio/volumen y arma alertas combinadas con señales recientes de otros módulos (p. ej.
  derivados). Se ejecuta también automáticamente cada 5 minutos vía el scheduler interno.
- `GET /anomalies/latest?symbol=BTC/USDT` — últimas señales/anomalías persistidas, de todas
  las categorías (`technical`, `derivatives`, `price`, `volume`, ...).

> Nota: el Anomaly Detector necesita al menos ~55 velas guardadas del timeframe rápido (5m por
> defecto) para calcular z-scores con una base histórica razonable; si no las tiene, simplemente
> no reporta anomalías (no inventa umbrales).

## 7. Fase 7: Backtesting, Paper Trading y Journal

La pestaña **Fase 7 Lab** del dashboard permite ejecutar estrategias sobre velas históricas,
crear una cuenta virtual, abrir/cerrar operaciones simuladas y guardar la hipótesis de cada
trade junto con su autopsia posterior. El backtester ejecuta las señales en la apertura de la
vela siguiente, aplica comisión y slippage, y usa una convención conservadora cuando una vela
toca stop y target en el mismo intervalo. No ejecuta órdenes reales.

Endpoints principales:

- `POST /phase7/backtests` — ejecuta y persiste un backtest (`ema_crossover`, `rsi`, `breakout` o `trend_following`).
- `GET /phase7/backtests` — historial de ejecuciones y métricas.
- `POST /phase7/paper/accounts` — crea una cuenta virtual.
- `POST /phase7/paper/trades` y `POST /phase7/paper/trades/{id}/close` — abre/cierra operaciones paper.
- `POST /phase7/journal` — guarda la tesis, contexto y resultado de una operación.
- `POST /phase7/autopsies` — registra qué funcionó, qué falló y las lecciones aprendidas.

La migración correspondiente es `backend/init_db/008_phase7.sql`. En una base ya creada se puede
aplicar con `docker exec -i btc_timescaledb psql -U btc_user -d btc_intelligence < backend/init_db/008_phase7.sql`.

## 8. Binance Futures USDT-M (conexión opcional)

La aplicación puede consultar balance/posiciones y, solo después de una activación explícita,
enviar órdenes a Binance USDT-M. Las claves se leen desde `backend/.env`, nunca desde el
frontend ni desde el repositorio. Crea primero claves separadas para Futures Testnet en Binance,
con permiso de Futures y **sin permiso de retiros**, y configura:

```env
EXCHANGE_API_KEY=...
EXCHANGE_API_SECRET=...
BINANCE_TESTNET=true
BINANCE_LIVE_TRADING=false
BINANCE_MAX_ORDER_NOTIONAL_USDT=100
BINANCE_ALLOWED_SYMBOLS=BTC/USDT:USDT
```

Endpoints:

- `GET /binance/status` — estado de configuración, red y límites sin mostrar secretos.
- `GET /binance/account` — balance USDT privado.
- `GET /binance/positions` — posiciones USDT-M abiertas.
- `POST /binance/ai/analyze` — requiere fragmentos documentales relevantes (similitud mínima
  configurable con `BINANCE_KNOWLEDGE_MIN_SCORE`, por defecto `0.55`) y al menos una fuente
  sustantiva de `risk_management`. Las propuestas deben citar un documento y su categoría; si
  falta ese respaldo o falla la generación, devuelve `NO_TRADE` sin propuestas. La respuesta
  muestra los fragmentos realmente usados en `knowledge_sources`.
- `POST /binance/orders` — orden market/limit protegida por límites y confirmación explícita.

Para producción, valida primero Testnet y cambia conjuntamente `BINANCE_TESTNET=false` y
`BINANCE_LIVE_TRADING=true`. El endpoint exige además `confirm_live=true`, limita el símbolo,
apalancamiento máximo de 20x y notional máximo configurado. No se recomienda habilitarlo sin
probar antes el flujo completo con la cuenta virtual.

El analista de Binance Futures usa la biblioteca como fundamento principal de sus reglas de
entrada, invalidación y riesgo; los datos vivos sirven para evaluar si esas reglas se cumplen.
Agrega material educativo sustantivo (no solo los README de instrucciones) a
`knowledge_library/risk_management/` y a las categorías técnicas pertinentes, sincroniza la
biblioteca y revisa las fuentes desplegadas junto al análisis. Mientras falte contenido relevante
de gestión de riesgo, la decisión permanece en `NO_TRADE`.

## 9. Reglas de la IA (aplicadas desde Fase 1)

El `system prompt` de Ollama (ver `backend/app/services/ollama_client.py`) obliga al modelo a:

- No inventar datos, precios ni fuentes.
- No garantizar ganancias ni certeza sobre el futuro.
- Usar lenguaje condicional ("condiciones favorables para...").
- Explicar qué invalidaría su análisis.
- Decir explícitamente "datos insuficientes" cuando corresponda.

## 10. Próximas fases

- **Fase 6**: Trade Finder, ROI Calculator, Position Sizing, Opportunity Ranking.
- **Fase 7** (implementada): Backtesting, Paper Trading, Trade Journal, Trade Autopsy.
- **Fase 8**: Bull vs Bear AI + Senior Analyst (multi-agente).
- **Pendiente sin fase asignada todavía**: On-Chain Dashboard (sección 17 del spec — exchange
  inflows/outflows, MVRV, SOPR, NUPL — requiere una fuente de datos on-chain real; no
  implementado aún porque ninguna API pública gratuita cubre todas esas métricas para BTC).

---

## Estructura del proyecto

```
btc-intelligence-ai/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + scheduler de sync automático
│   │   ├── config.py          # Configuración vía variables de entorno
│   │   ├── database.py        # Conexión SQLAlchemy
│   │   ├── models.py          # Modelos ORM
│   │   ├── schemas.py         # Schemas Pydantic
│   │   ├── services/
│   │   │   ├── market_data.py       # Descarga y persistencia de velas (ccxt)
│   │   │   ├── indicators.py        # EMA/SMA/RSI/MACD/ATR/BB/VWAP/S-R/Regime
│   │   │   ├── market_structure.py  # Swings, BOS/CHOCH (Fase 2)
│   │   │   ├── multi_timeframe.py   # Consenso multi-timeframe (Fase 2)
│   │   │   ├── derivatives.py       # OI/Funding/L-S Ratio + anomalías (Fase 2)
│   │   │   ├── news.py              # RSS real + clasificación heurística (Fase 3)
│   │   │   ├── macro.py             # DXY/SPX/NDX/VIX/US10Y/Gold vía yfinance (Fase 3)
│   │   │   ├── sentiment.py         # Fear & Greed + distribución de noticias (Fase 3)
│   │   │   ├── documents.py         # Extracción de texto + chunking (Fase 4)
│   │   │   ├── vector_store.py      # Wrapper de Qdrant (Fase 4)
│   │   │   ├── rag.py               # Pipeline de ingesta + RAG ask (Fase 4)
│   │   │   ├── ollama_client.py     # Cliente HTTP para Ollama (chat + embeddings)
│   │   │   └── market_analysis.py   # Compone el Market Overview + AI bias
│   │   └── routers/
│   │       ├── market.py
│   │       ├── derivatives.py       # Fase 2
│   │       ├── news.py              # Fase 3
│   │       ├── macro.py             # Fase 3
│   │       ├── sentiment.py         # Fase 3
│   │       ├── knowledge.py         # Fase 4
│   │       └── ai.py
│   ├── init_db/
│   │   ├── 001_init.sql       # Schema Fase 1 + hypertables TimescaleDB
│   │   ├── 002_phase2.sql     # Tablas derivatives/liquidations/signals (Fase 2)
│   │   ├── 003_phase3.sql     # Tablas news/macro_data/sentiment (Fase 3)
│   │   └── 004_phase4.sql     # Tablas documents/document_chunks (Fase 4)
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx            # Dashboard principal
    │   └── globals.css
    ├── components/
    │   ├── PriceChart.tsx          # Gráfico de velas + marcadores BOS/CHOCH
    │   ├── MarketOverviewCard.tsx  # Tarjeta de overview + AI bias
    │   ├── MultiTimeframeCard.tsx  # Consenso multi-timeframe (Fase 2)
    │   ├── DerivativesCard.tsx     # Dashboard de derivados (Fase 2)
    │   ├── NewsCard.tsx            # News Intelligence (Fase 3)
    │   ├── MacroCard.tsx           # Macro Dashboard (Fase 3)
    │   ├── SentimentCard.tsx       # Fear & Greed + news sentiment (Fase 3)
    │   ├── KnowledgeCenterCard.tsx # Knowledge Center + RAG chat (Fase 4)
    │   └── AIChatCard.tsx          # Chat con la IA
    ├── lib/api.ts               # Cliente de la API del backend
    └── Dockerfile
```
# btc-intelligence-ai
