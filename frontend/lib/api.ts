const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Candle {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketOverview {
  symbol: string;
  status: string;
  price?: number;
  change_pct?: number;
  volatility_pct?: number;
  market_regime?: string;
  technical_bias?: string;
  ai_bias?: string;
  ai_confidence?: number;
  ai_explanation?: string;
  ai_invalidation?: string;
  support_levels?: number[];
  resistance_levels?: number[];
  message?: string;
}

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export function getOverview(symbol = "BTC/USDT", timeframe = "1h", useAi = true) {
  const params = new URLSearchParams({ symbol, timeframe, use_ai: String(useAi) });
  return fetchJSON<MarketOverview>(`/market/overview?${params.toString()}`);
}

export function getCandles(symbol = "BTC/USDT", timeframe = "1h", limit = 300) {
  const params = new URLSearchParams({ symbol, timeframe, limit: String(limit) });
  return fetchJSON<{ symbol: string; timeframe: string; candles: Candle[] }>(
    `/market/candles?${params.toString()}`
  );
}

export function syncMarket(symbol = "BTC/USDT") {
  const params = new URLSearchParams({ symbol });
  return fetchJSON(`/market/sync?${params.toString()}`, { method: "POST" });
}

export interface SyncStepResult {
  status: "ok" | "error";
  data?: unknown;
  error?: string;
}

export interface SyncAllResult {
  status: "ok" | "partial";
  symbol: string;
  failed_steps: string[];
  results: Record<string, SyncStepResult>;
  started_at: string;
  finished_at: string;
}

export function syncAll(symbol = "BTC/USDT", limit = 500) {
  const params = new URLSearchParams({ symbol, limit: String(limit) });
  return fetchJSON<SyncAllResult>(`/sync/all?${params.toString()}`, { method: "POST" });
}

export interface ChatConversation {
  id: number;
  title: string;
  symbol: string;
  timeframe: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  model?: string;
  created_at: string;
}

export function askAI(
  question: string,
  symbol = "BTC/USDT",
  timeframe = "1h",
  conversation_id?: number,
  use_knowledge = false
) {
  return fetchJSON(`/ai/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, timeframe, question, conversation_id, use_knowledge }),
  });
}

export function getChatConversations() {
  return fetchJSON<ChatConversation[]>("/ai/conversations");
}

export function createChatConversation(title = "Nueva conversación", symbol = "BTC/USDT", timeframe = "1h") {
  return fetchJSON<ChatConversation>("/ai/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, symbol, timeframe }),
  });
}

export function getChatMessages(conversationId: number) {
  return fetchJSON<ChatMessage[]>(`/ai/conversations/${conversationId}`);
}

export function deleteChatConversation(conversationId: number) {
  return fetchJSON<{ status: string; conversation_id: number }>(`/ai/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

// ---------------- Fase 2 ----------------

export interface StructureEvent {
  ts: string;
  price: number;
  event_type: "BOS" | "CHOCH";
  direction: "bullish" | "bearish";
  broken_level: number;
  note: string;
}

export interface MarketStructure {
  symbol: string;
  timeframe: string;
  status: string;
  current_trend?: string;
  events?: StructureEvent[];
  key_levels?: { last_swing_high?: number; last_swing_low?: number };
  message?: string;
}

export interface TimeframeAnalysis {
  timeframe: string;
  status: string;
  price?: number;
  trend?: string;
  rsi_14?: number;
  structure_trend?: string;
  message?: string;
}

export interface MultiTimeframeResult {
  symbol: string;
  timeframes: Record<string, TimeframeAnalysis>;
  summary: {
    bullish_count: number;
    bearish_count: number;
    neutral_count: number;
    total_analyzed: number;
    consensus: string;
  };
}

export interface DerivativesSnapshot {
  symbol: string;
  status: string;
  ts?: string;
  open_interest?: number;
  open_interest_usd?: number;
  funding_rate?: number;
  predicted_funding?: number;
  long_short_ratio?: number;
  top_trader_ls_ratio?: number;
  mark_price?: number;
  index_price?: number;
  basis?: number;
  basis_pct?: number;
  message?: string;
}

export function getStructure(symbol = "BTC/USDT", timeframe = "1h") {
  const params = new URLSearchParams({ symbol, timeframe });
  return fetchJSON<MarketStructure>(`/market/structure?${params.toString()}`);
}

export function getMultiTimeframe(symbol = "BTC/USDT") {
  const params = new URLSearchParams({ symbol });
  return fetchJSON<MultiTimeframeResult>(`/market/multi-timeframe?${params.toString()}`);
}

export function getDerivatives(symbol = "BTC/USDT") {
  const params = new URLSearchParams({ symbol });
  return fetchJSON<DerivativesSnapshot>(`/derivatives/latest?${params.toString()}`);
}

export function syncDerivatives(symbol = "BTC/USDT") {
  const params = new URLSearchParams({ symbol });
  return fetchJSON(`/derivatives/sync?${params.toString()}`, { method: "POST" });
}

// ---------------- Fase 7: Backtesting + Paper Trading ----------------

export interface BacktestResult {
  status: string;
  id?: number;
  symbol?: string;
  timeframe?: string;
  strategy?: string;
  metrics?: Record<string, number>;
  trades?: Array<Record<string, unknown>>;
  equity_curve?: Array<{ ts: string; equity: number }>;
  message?: string;
}

export interface PaperTrade {
  id: number;
  symbol: string;
  direction: string;
  entry: number;
  exit_price?: number;
  quantity: number;
  pnl?: number;
  status: string;
  opened_at: string;
  closed_at?: string;
}

export interface PaperAccount {
  id: number;
  name: string;
  initial_capital: number;
  current_capital: number;
  roi_pct: number;
  closed_trades: number;
  win_rate_pct: number;
  trades: PaperTrade[];
}

export function runBacktest(payload: Record<string, unknown>) {
  return fetchJSON<BacktestResult>("/phase7/backtests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function createPaperAccount(name: string, initial_capital: number) {
  return fetchJSON<PaperAccount>("/phase7/paper/accounts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, initial_capital }),
  });
}

export function getPaperAccount(accountId: number) {
  return fetchJSON<PaperAccount>(`/phase7/paper/accounts/${accountId}`);
}

export function openPaperTrade(payload: Record<string, unknown>) {
  return fetchJSON<PaperTrade>("/phase7/paper/trades", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function closePaperTrade(tradeId: number, exit_price: number) {
  return fetchJSON<PaperTrade>(`/phase7/paper/trades/${tradeId}/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ exit_price }),
  });
}

export function createJournalEntry(payload: Record<string, unknown>) {
  return fetchJSON<Record<string, unknown>>("/phase7/journal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function createTradeAutopsy(payload: Record<string, unknown>) {
  return fetchJSON<Record<string, unknown>>("/phase7/autopsies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface BinanceStatus {
  exchange: string;
  market_type: string;
  configured: boolean;
  testnet: boolean;
  live_trading_enabled: boolean;
  allowed_symbols: string[];
  max_order_notional_usdt: number;
  message: string;
}

export interface BinanceAccount {
  asset: string;
  total?: number;
  free?: number;
  used?: number;
  testnet: boolean;
}

export interface BinancePosition {
  symbol: string;
  side?: string;
  contracts?: number;
  entry_price?: number;
  mark_price?: number;
  unrealized_pnl?: number;
  leverage?: number;
  liquidation_price?: number;
}

export interface BinanceOpenOrder {
  id: string;
  symbol: string;
  type: string;
  side: string;
  amount: number;
  remaining?: number;
  price?: number;
  status?: string;
  reduce_only?: boolean;
}

export function getBinanceStatus() {
  return fetchJSON<BinanceStatus>("/binance/status");
}

export function getBinanceAccount() {
  return fetchJSON<BinanceAccount>("/binance/account");
}

export function getBinancePositions() {
  return fetchJSON<{ positions: BinancePosition[] }>("/binance/positions");
}

export function getBinanceTicker(symbol = "BTC/USDT:USDT") {
  return fetchJSON<{ symbol: string; last?: number; bid?: number; ask?: number; percentage?: number }>(`/binance/ticker?symbol=${encodeURIComponent(symbol)}`);
}

export function getBinanceOpenOrders(symbol = "BTC/USDT:USDT") {
  return fetchJSON<{ orders: BinanceOpenOrder[] }>(`/binance/orders/open?symbol=${encodeURIComponent(symbol)}`);
}

export function sendBinanceOrder(payload: Record<string, unknown>) {
  return fetchJSON<Record<string, unknown>>("/binance/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface BinanceBracketOrderResult {
  entry: {
    id?: string;
    symbol?: string;
    type?: string;
    side?: string;
    amount?: number;
    price?: number;
    average?: number;
    status?: string;
    reduce_only?: boolean;
    testnet?: boolean;
  };
  protection: Array<{ kind: string; id?: string; stop_price: number; status?: string }>;
  protection_errors: string[];
}

export function sendBinanceBracketOrder(payload: Record<string, unknown>) {
  return fetchJSON<BinanceBracketOrderResult>("/binance/orders/bracket", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface BinanceAIProposal {
  direction: "LONG" | "SHORT";
  entry: number;
  stop_loss: number;
  take_profit: number;
  risk_pct: number;
  reward_risk: number;
  margin_roi_pct: number;
  suggested_amount: number;
  risk_usdt?: number;
  leverage: number;
  setup: string;
  activation: string;
  invalidation: string;
  evidence: string[];
  warnings: string[];
}

export interface BinanceKnowledgeSource {
  document_id: number;
  document_title: string;
  category: string;
  chunk_index: number;
  content: string;
  score: number;
}

export interface BinanceAIAnalysis {
  verdict: "LONG" | "SHORT" | "NO_TRADE";
  confidence: number;
  summary: string;
  proposals: BinanceAIProposal[];
  evidence: Array<{ kind: string; text: string; source: string }>;
  disclaimer: string;
  account_available_usdt?: number;
  account_connected?: boolean;
  open_positions_count?: number;
  multi_timeframe_consensus?: string | null;
  knowledge_sources_count?: number;
  knowledge_sources: BinanceKnowledgeSource[];
  generated_at?: string;
  data_scope?: { symbol: string; timeframe: string; testnet: boolean };
}

export function analyzeBinanceWithAI(payload: Record<string, unknown>) {
  return fetchJSON<BinanceAIAnalysis>("/binance/ai/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function cancelBinanceOrder(order_id: string, symbol = "BTC/USDT:USDT", confirm_live = false) {
  return fetchJSON<Record<string, unknown>>("/binance/orders/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order_id, symbol, confirm_live }),
  });
}

export function closeBinancePosition(symbol = "BTC/USDT:USDT", amount?: number, confirm_live = false) {
  return fetchJSON<Record<string, unknown>>("/binance/positions/close", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, amount, confirm_live }),
  });
}

// ---------------- Fase 3 ----------------

export interface NewsItem {
  id: number;
  ts: string;
  title: string;
  source: string;
  url: string;
  summary?: string;
  sentiment?: "bullish" | "bearish" | "neutral";
  relevance?: number;
  potential_impact?: "low" | "medium" | "high";
  affected_asset: string;
}

export interface NewsResponse {
  status: string;
  news: NewsItem[];
  message?: string;
}

export interface MacroIndicator {
  ts?: string;
  value?: number;
  change_pct?: number;
}

export interface MacroSnapshot {
  status: string;
  indicators?: Record<string, MacroIndicator>;
  risk_environment?: { regime: string; score: number; factors: string[] };
  message?: string;
}

export interface SentimentSnapshot {
  symbol: string;
  status: string;
  ts?: string;
  fng_value?: number;
  fng_classification?: string;
  news_bullish_pct?: number;
  news_bearish_pct?: number;
  news_neutral_pct?: number;
  news_sample_size?: number;
  overall_sentiment?: string;
  message?: string;
}

export function getNews(limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  return fetchJSON<NewsResponse>(`/news/latest?${params.toString()}`);
}

export function syncNews() {
  return fetchJSON(`/news/sync`, { method: "POST" });
}

export function analyzeNewsImpact(newsId: number) {
  return fetchJSON(`/news/analyze/${newsId}`, { method: "POST" });
}

export function getMacro() {
  return fetchJSON<MacroSnapshot>(`/macro/latest`);
}

export function syncMacro() {
  return fetchJSON(`/macro/sync`, { method: "POST" });
}

export function getSentiment(symbol = "BTC/USDT") {
  const params = new URLSearchParams({ symbol });
  return fetchJSON<SentimentSnapshot>(`/sentiment/latest?${params.toString()}`);
}

export function syncSentiment(symbol = "BTC/USDT") {
  const params = new URLSearchParams({ symbol });
  return fetchJSON(`/sentiment/sync?${params.toString()}`, { method: "POST" });
}

// ---------------- Fase 4: Knowledge Center + RAG ----------------

export const KNOWLEDGE_CATEGORIES = [
  "technical_analysis",
  "candlesticks",
  "price_action",
  "psychology",
  "risk_management",
  "crypto",
  "quantitative_trading",
  "behavioral_finance",
  "other",
] as const;

export type KnowledgeCategory = (typeof KNOWLEDGE_CATEGORIES)[number];

export interface KnowledgeDocument {
  id: number;
  title: string;
  category: string;
  filename: string;
  file_type: string;
  status: "processing" | "ready" | "error";
  error_message?: string | null;
  num_chunks: number;
  char_count?: number | null;
  uploaded_at: string;
  source: "upload" | "library";
}

export interface KnowledgeSource {
  document_id: number;
  document_title: string;
  category?: string;
  chunk_index: number;
  content: string;
  score: number;
}

export interface KnowledgeAskResponse {
  question: string;
  answer: string;
  sources: KnowledgeSource[];
  model: string;
  ts: string;
}

export function getKnowledgeDocuments(category?: string) {
  const params = category ? `?${new URLSearchParams({ category }).toString()}` : "";
  return fetchJSON<KnowledgeDocument[]>(`/knowledge/documents${params}`);
}

export async function uploadKnowledgeDocument(file: File, category: string, title?: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  if (title) form.append("title", title);

  const res = await fetch(`${API_URL}/knowledge/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<KnowledgeDocument>;
}

export function deleteKnowledgeDocument(id: number) {
  return fetchJSON(`/knowledge/documents/${id}`, { method: "DELETE" });
}

export function scanKnowledgeLibrary() {
  return fetchJSON<{ status: string; message: string }>(`/knowledge/scan-library`, {
    method: "POST",
  });
}

export function askKnowledge(question: string, category?: string) {
  return fetchJSON<KnowledgeAskResponse>(`/knowledge/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, category: category || null }),
  });
}

// ---------------- Fase 5: Historical Similarity + Anomaly Detection ----------------

export interface HistoricalMatch {
  rank: number;
  ts: string;
  similarity_pct: number;
  features_at_match: Record<string, number>;
  outcome: {
    forward_window_candles: number;
    forward_return_pct: number;
    max_gain_pct: number;
    max_loss_pct: number;
  };
}

export interface HistoricalSimilarityResult {
  status: "ok" | "insufficient_data";
  symbol: string;
  timeframe: string;
  message?: string;
  lookback_window?: number;
  forward_window?: number;
  anchor_ts?: string;
  current_features?: Record<string, number>;
  matches?: HistoricalMatch[];
  summary?: {
    num_matches: number;
    bullish_outcomes: number;
    bearish_outcomes: number;
    avg_forward_return_pct: number | null;
  };
  disclaimer?: string;
}

export function getSimilarSetups(
  symbol = "BTC/USDT",
  timeframe = "1h",
  lookbackWindow = 20,
  forwardWindow = 10,
  topK = 5
) {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    lookback_window: String(lookbackWindow),
    forward_window: String(forwardWindow),
    top_k: String(topK),
  });
  return fetchJSON<HistoricalSimilarityResult>(`/historical/similar?${params.toString()}`);
}

export interface AnomalySignal {
  ts: string;
  category: string;
  signal_type: string;
  severity: "info" | "warning" | "critical";
  direction: string | null;
  message: string;
}

export interface CombinedAlert {
  signal_type: string;
  severity: string;
  direction: string | null;
  message: string;
  based_on: string[];
}

export interface AnomalyScanResult {
  symbol: string;
  timeframe: string;
  ts: string;
  new_anomalies: AnomalySignal[];
  combined_alerts: CombinedAlert[];
  recent_signals_considered: number;
}

export function scanAnomalies(symbol = "BTC/USDT", timeframe = "5m") {
  const params = new URLSearchParams({ symbol, timeframe });
  return fetchJSON<AnomalyScanResult>(`/anomalies/scan?${params.toString()}`, { method: "POST" });
}

export function getLatestAnomalies(symbol = "BTC/USDT", limit = 50) {
  const params = new URLSearchParams({ symbol, limit: String(limit) });
  return fetchJSON<{ symbol: string; signals: AnomalySignal[] }>(
    `/anomalies/latest?${params.toString()}`
  );
}

// ---------------- Fase 6: Trade Finder + ROI/Position Calculators ----------------

export const STRATEGIES = [
  "trend_following",
  "breakout",
  "pullback",
  "mean_reversion",
  "momentum",
  "support_resistance",
  "price_action",
  "scalping",
  "swing_trading",
] as const;

export interface ScoreCategory {
  subscore: number | null;
  max: number;
  vote: "bullish" | "bearish" | "neutral" | null;
  note: string;
}

export interface ScenarioBranch {
  type: string;
  conditions: string;
  entry?: number;
  target?: number;
  invalidation?: number;
  roi_pct?: number;
  risk_pct?: number;
  risk_reward?: number;
}

export interface TradeOpportunity {
  direction: "long" | "short";
  strategy?: string | null;
  timeframe: string;
  symbol: string;
  entry: number;
  stop: number;
  target: number;
  risk_pct: number;
  potential_roi_pct: number;
  risk_reward: number;
  trade_score: number;
  grade: string;
  confidence: number;
  confluence: "HIGH" | "MEDIUM" | "LOW" | "insufficient_data";
  bullish_factors: number;
  bearish_factors: number;
  categories_available: number;
  categories_total: number;
  score_breakdown: Record<string, ScoreCategory>;
  market_regime: string;
  scenario: { primary: ScenarioBranch; alternative: ScenarioBranch; range: ScenarioBranch };
  invalidation_note: string;
  capital: number;
  max_risk_pct: number;
  position_size_usd: number | null;
  position_size_asset: number | null;
  potential_profit_usd: number | null;
  max_loss_usd: number | null;
  passed_filters: boolean;
  status: "potential" | "conditional" | "rejected";
}

export interface TradeFinderResult {
  status: "ok" | "insufficient_data";
  symbol: string;
  timeframe: string;
  message?: string;
  price?: number;
  market_regime?: string;
  filters?: Record<string, any>;
  opportunities?: TradeOpportunity[];
  best_match?: TradeOpportunity | null;
  num_candidates?: number;
  num_passed_filters?: number;
  disclaimer?: string;
}

export interface TradeFinderFilters {
  symbol?: string;
  timeframe?: string;
  trade_type?: "LONG" | "SHORT" | "BOTH";
  capital?: number;
  max_risk_pct?: number;
  min_roi_pct?: number;
  min_risk_reward?: number;
  min_confidence?: number;
  strategy?: string | null;
}

export function findTradeOpportunities(filters: TradeFinderFilters) {
  return fetchJSON<TradeFinderResult>(`/trades/find`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filters),
  });
}

export function compareLongVsShort(symbol = "BTC/USDT", timeframe = "1h") {
  return fetchJSON<TradeFinderResult & { long: TradeOpportunity | null; short: TradeOpportunity | null; winner: string | null; summary: string }>(
    `/trades/compare`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, timeframe }),
    }
  );
}

export interface ROICalculatorResult {
  status: "ok" | "error";
  message?: string;
  direction?: string;
  capital?: number;
  entry?: number;
  exit?: number;
  leverage?: number;
  position_size_usd?: number;
  position_size_asset?: number;
  capital_used?: number;
  asset_roi_pct?: number;
  gross_pnl_usd?: number;
  fees_usd?: number;
  net_pnl_usd?: number;
  capital_roi_pct?: number | null;
  risk_pct?: number;
  max_loss_usd?: number;
  risk_reward?: number | null;
  sizing_note?: string | null;
  note?: string;
}

export function calculateROI(params: {
  capital: number;
  entry: number;
  exit_price: number;
  stop?: number | null;
  leverage?: number;
  risk_pct?: number | null;
  fee_pct?: number | null;
  direction?: "long" | "short";
}) {
  return fetchJSON<ROICalculatorResult>(`/trades/roi-calculator`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export interface PositionSizeResult {
  status: "ok" | "error";
  message?: string;
  capital?: number;
  risk_pct?: number;
  entry?: number;
  stop?: number;
  leverage?: number;
  stop_distance?: number;
  stop_distance_pct?: number;
  max_risk_usd?: number;
  position_size_usd?: number;
  position_size_asset?: number;
  capital_required?: number;
  warning?: string | null;
}

export function calculatePositionSize(params: {
  capital: number;
  risk_pct: number;
  entry: number;
  stop: number;
  leverage?: number;
}) {
  return fetchJSON<PositionSizeResult>(`/trades/position-size`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}
