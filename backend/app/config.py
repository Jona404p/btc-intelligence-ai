from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = (
        "postgresql+psycopg://btc_user:btc_password@localhost:5432/btc_intelligence"
    )

    EXCHANGE_ID: str = "binance"
    EXCHANGE_API_KEY: str = ""
    EXCHANGE_API_SECRET: str = ""
    BINANCE_MARKET_TYPE: str = "USDT-M"
    BINANCE_TESTNET: bool = True
    BINANCE_LIVE_TRADING: bool = False
    BINANCE_MAX_ORDER_NOTIONAL_USDT: float = 100.0
    BINANCE_ALLOWED_SYMBOLS: str = "BTC/USDT:USDT"
    DEFAULT_SYMBOL: str = "BTC/USDT"
    DEFAULT_TIMEFRAMES: str = "5m,15m,1h,4h,1d"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_CHAT_MODEL: str = "gemma2:2b"
    AI_CREATOR_NAME: str = "Jonathan Paniagua Vazquez"
    # Modelo de embeddings local vía Ollama (Fase 4 - Knowledge Center / RAG).
    # Descargar con: docker exec -it btc_ollama ollama pull nomic-embed-text
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- Fase 4: Knowledge Center + RAG ---
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "btc_knowledge"
    RAG_CHUNK_SIZE: int = 1200          # caracteres por chunk
    RAG_CHUNK_OVERLAP: int = 150        # caracteres de solapamiento entre chunks
    RAG_TOP_K: int = 5                  # chunks recuperados por consulta
    RAG_MIN_SCORE: float = 0.35         # score mínimo de similitud cosine
    BINANCE_KNOWLEDGE_MIN_SCORE: float = 0.55
    DOCUMENTS_STORAGE_PATH: str = "/app/storage/documents"

    # --- Fase 4b: Biblioteca local (carpeta en el PC del usuario) ---
    # Se monta como volumen en docker-compose.yml (host: ./knowledge_library).
    LIBRARY_PATH: str = "/app/storage/library"
    LIBRARY_SCAN_INTERVAL_MINUTES: int = 10

    @property
    def timeframes(self) -> list[str]:
        return [tf.strip() for tf in self.DEFAULT_TIMEFRAMES.split(",") if tf.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def binance_allowed_symbols_list(self) -> list[str]:
        return [symbol.strip() for symbol in self.BINANCE_ALLOWED_SYMBOLS.split(",") if symbol.strip()]


settings = Settings()
