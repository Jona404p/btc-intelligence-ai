from datetime import datetime
from pydantic import BaseModel


class Candle(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    class Config:
        from_attributes = True


class IndicatorSnapshot(BaseModel):
    ts: datetime
    ema_9: float | None = None
    ema_21: float | None = None
    ema_50: float | None = None
    ema_200: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    atr_14: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    vwap: float | None = None
    trend: str | None = None

    class Config:
        from_attributes = True


class SupportResistanceLevel(BaseModel):
    price: float
    strength: float | None = None
    level_type: str


class MarketOverview(BaseModel):
    symbol: str
    price: float
    change_24h_pct: float | None = None
    volume_24h: float | None = None
    volatility_pct: float | None = None
    market_regime: str | None = None
    technical_bias: str | None = None
    ai_bias: str | None = None
    ai_confidence: float | None = None
    support_levels: list[float] = []
    resistance_levels: list[float] = []
    latest_indicators: IndicatorSnapshot | None = None
    ts: datetime


class AIReportRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    question: str | None = None
    conversation_id: int | None = None
    use_knowledge: bool = False


class AIReportResponse(BaseModel):
    symbol: str
    model: str
    bias: str | None = None
    confidence: float | None = None
    response: str
    ts: datetime
    conversation_id: int | None = None


class ChatConversationOut(BaseModel):
    id: int
    title: str
    symbol: str
    timeframe: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatConversationCreate(BaseModel):
    title: str = "Nueva conversación"
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"


class ChatMessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    model: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------- Fase 4: Knowledge Center + RAG ----------------


class DocumentOut(BaseModel):
    id: int
    title: str
    category: str
    filename: str
    file_type: str
    status: str
    error_message: str | None = None
    num_chunks: int
    char_count: int | None = None
    uploaded_at: datetime
    source: str = "upload"

    class Config:
        from_attributes = True


class KnowledgeAskRequest(BaseModel):
    question: str
    category: str | None = None  # filtra la búsqueda a una categoría (opcional)
    top_k: int | None = None


class KnowledgeSource(BaseModel):
    document_id: int
    document_title: str
    category: str | None = None
    chunk_index: int
    content: str
    score: float


class KnowledgeAskResponse(BaseModel):
    question: str
    answer: str
    sources: list[KnowledgeSource]
    model: str
    ts: datetime


# ---------------- Fase 6: Trade Finder + ROI/Position Calculators ----------------


class TradeFinderRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    trade_type: str = "BOTH"  # LONG / SHORT / BOTH
    capital: float = 100.0
    max_risk_pct: float = 1.0
    min_roi_pct: float = 2.0
    min_risk_reward: float = 2.0
    min_confidence: float = 60.0
    strategy: str | None = None


class ROICalculatorRequest(BaseModel):
    capital: float
    entry: float
    exit_price: float
    stop: float | None = None
    leverage: float = 1.0
    risk_pct: float | None = None
    fee_pct: float | None = None
    direction: str = "long"


class PositionSizeRequest(BaseModel):
    capital: float
    risk_pct: float
    entry: float
    stop: float
    leverage: float = 1.0


class CompareTradeRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"


# ---------------- Fase 7: Backtesting + Paper Trading + Journal ----------------


class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    strategy: str = "ema_crossover"
    initial_capital: float = 10000.0
    risk_pct: float = 1.0
    fee_pct: float = 0.1
    slippage_pct: float = 0.05
    limit: int = 1000


class PaperAccountRequest(BaseModel):
    name: str = "BTC Paper Account"
    initial_capital: float = 10000.0


class PaperTradeRequest(BaseModel):
    account_id: int
    symbol: str = "BTC/USDT"
    direction: str
    entry: float
    quantity: float
    stop: float | None = None
    target: float | None = None
    strategy: str | None = None
    notes: str | None = None


class ClosePaperTradeRequest(BaseModel):
    exit_price: float
    fee_pct: float = 0.1
    notes: str | None = None


class JournalEntryRequest(BaseModel):
    paper_trade_id: int | None = None
    symbol: str = "BTC/USDT"
    direction: str
    strategy: str | None = None
    entry: float | None = None
    exit_price: float | None = None
    stop: float | None = None
    target: float | None = None
    market_regime: str | None = None
    ai_score: float | None = None
    confidence: float | None = None
    reason: str
    result: str | None = None
    roi_pct: float | None = None
    r_multiple: float | None = None
    notes: str | None = None


class AutopsyRequest(BaseModel):
    journal_entry_id: int
    why_won: str | None = None
    why_lost: str | None = None
    indicators_worked: list[str] = []
    indicators_failed: list[str] = []
    regime_correct: bool | None = None
    excessive_leverage: bool = False
    error_type: str | None = None
    lessons: str


# ---------------- Binance Futures: conexión controlada ----------------


class FuturesOrderRequest(BaseModel):
    symbol: str = "BTC/USDT:USDT"
    side: str
    amount: float
    order_type: str = "market"
    price: float | None = None
    leverage: int = 1
    time_in_force: str = "GTC"
    reduce_only: bool = False
    confirm_live: bool = False


class FuturesBracketOrderRequest(BaseModel):
    """Igual que FuturesOrderRequest, pero adjunta stop-loss/take-profit reales
    (reduce-only, closePosition=true) en el mismo flujo de creación."""

    symbol: str = "BTC/USDT:USDT"
    side: str
    amount: float
    order_type: str = "market"
    price: float | None = None
    leverage: int = 1
    time_in_force: str = "GTC"
    confirm_live: bool = False
    stop_loss: float | None = None
    take_profit: float | None = None


class FuturesCancelOrderRequest(BaseModel):
    symbol: str = "BTC/USDT:USDT"
    order_id: str
    confirm_live: bool = False


class FuturesClosePositionRequest(BaseModel):
    symbol: str = "BTC/USDT:USDT"
    amount: float | None = None
    confirm_live: bool = False


class BinanceAIRequest(BaseModel):
    symbol: str = "BTC/USDT:USDT"
    timeframe: str = "1h"
    risk_pct: float = 1.0
    objective: str = "Buscar escenarios LONG, SHORT o NO TRADE con riesgo controlado."
