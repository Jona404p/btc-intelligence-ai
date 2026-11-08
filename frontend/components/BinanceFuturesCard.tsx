"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BinanceAccount,
  BinanceOpenOrder,
  BinancePosition,
  BinanceStatus,
  BinanceAIProposal,
  cancelBinanceOrder,
  closeBinancePosition,
  getBinanceAccount,
  getBinanceOpenOrders,
  getBinancePositions,
  getBinanceStatus,
  getBinanceTicker,
  sendBinanceBracketOrder,
  sendBinanceOrder,
} from "@/lib/api";

const inputClass = "w-full rounded-lg border border-border bg-panel-muted px-3 py-2 text-sm text-foreground outline-none focus:border-neutral";
const valueOf = (value: string) => Number(value) || 0;
const futuresSymbol = "BTC/USDT:USDT";
const baseAsset = futuresSymbol.split("/")[0];
// El ticker ahora es público (sin API keys, sin peso de cuenta), así que se
// puede refrescar seguido sin costo. Cuenta/posiciones/órdenes SÍ son
// privadas y cuentan contra el rate-limit real de la API key, por eso se
// refrescan con menos frecuencia.
const tickerRefreshIntervalMs = 5000;
const accountRefreshIntervalMs = 15000;

function Field({ label, suffix, children }: { label: string; suffix?: string; children: React.ReactNode }) {
  return <label className="block space-y-1 text-xs text-muted"><span>{label}</span><div className="relative">{children}{suffix && <span className="pointer-events-none absolute right-3 top-2.5 text-xs text-muted">{suffix}</span>}</div></label>;
}

function Stat({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return <div className="rounded-lg border border-border bg-panel-muted p-3"><p className="text-[11px] uppercase tracking-wide text-muted">{label}</p><p className={`mt-1 font-semibold tabular-nums ${accent ? "text-neutral" : ""}`}>{value}</p></div>;
}

export default function BinanceFuturesCard({ proposal }: { proposal: BinanceAIProposal | null }) {
  const [status, setStatus] = useState<BinanceStatus | null>(null);
  const [account, setAccount] = useState<BinanceAccount | null>(null);
  const [positions, setPositions] = useState<BinancePosition[]>([]);
  const [openOrders, setOpenOrders] = useState<BinanceOpenOrder[]>([]);
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [bid, setBid] = useState<number | null>(null);
  const [ask, setAsk] = useState<number | null>(null);
  const [side, setSide] = useState("buy");
  const [orderType, setOrderType] = useState("market");
  const [amount, setAmount] = useState("0.001");
  const [allocationPercent, setAllocationPercent] = useState(0);
  const [price, setPrice] = useState("");
  const [takeProfitRoi, setTakeProfitRoi] = useState("2");
  const [stopLossRoi, setStopLossRoi] = useState("1");
  const [leverage, setLeverage] = useState("1");
  const [timeInForce, setTimeInForce] = useState("GTC");
  const [useBbo, setUseBbo] = useState(true);
  const [reduceOnly, setReduceOnly] = useState(false);
  const [attachProtection, setAttachProtection] = useState(true);
  const [confirm, setConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"info" | "success" | "error">("info");

  const referencePrice = useMemo(() => {
    if (useBbo && side === "buy" && ask) return ask;
    if (useBbo && side === "sell" && bid) return bid;
    return lastPrice;
  }, [ask, bid, lastPrice, side, useBbo]);
  const entryPrice = (useBbo ? referencePrice : valueOf(price) || referencePrice) || 0;
  const leverageValue = Math.max(1, valueOf(leverage));
  const roiDirection = side === "buy" ? 1 : -1;
  const takeProfitPrice = entryPrice ? entryPrice * (1 + roiDirection * valueOf(takeProfitRoi) / 100 / leverageValue) : 0;
  const stopLossPrice = entryPrice ? entryPrice * (1 - roiDirection * valueOf(stopLossRoi) / 100 / leverageValue) : 0;
  const cost = entryPrice * valueOf(amount) / leverageValue;
  const maxAmount = account?.free && entryPrice ? Math.min((account.free * leverageValue) / entryPrice, (status?.max_order_notional_usdt || Infinity) / entryPrice) : 0;
  const canTrade = Boolean(status?.configured && (status.testnet || status.live_trading_enabled));
  const canReduce = positions.some((position) => position.symbol === futuresSymbol && ((side === "sell" && position.side === "long") || (side === "buy" && position.side === "short")) && Number(position.contracts) > 0);
  const amountValue = valueOf(amount);
  const hasValidAmount = amountValue > 0 && amountValue <= maxAmount + Number.EPSILON;
  const hasValidLimitPrice = orderType !== "limit" || (!useBbo && valueOf(price) > 0);
  const canSubmit = canTrade && !loading && confirm && entryPrice > 0 && hasValidAmount && hasValidLimitPrice && (!reduceOnly || canReduce);

  useEffect(() => {
    if (!proposal) return;
    setSide(proposal.direction === "LONG" ? "buy" : "sell");
    setPrice(String(proposal.entry));
    setAmount(String(proposal.suggested_amount || maxAmount || ""));
    setLeverage(String(proposal.leverage || 1));
    setTakeProfitRoi(String(proposal.margin_roi_pct || 0));
    setStopLossRoi(String(proposal.risk_pct || 0));
    setUseBbo(false);
    setOrderType("limit");
    setAllocationPercent(0);
    setMessageTone("info");
    setMessage("Propuesta aplicada al ticket. Revisa precio, tamaño, TP/SL y confirma manualmente.");
  }, [proposal]);
  function setAllocation(value: number) {
    const normalized = Math.max(0, Math.min(100, value));
    setAllocationPercent(normalized);
    setAmount((maxAmount * normalized / 100).toFixed(8));
  }

  useEffect(() => {
    if (allocationPercent > 0 && maxAmount > 0) {
      setAmount((maxAmount * allocationPercent / 100).toFixed(8));
    }
  }, [allocationPercent, maxAmount]);

  // El precio (ticker) es público: se refresca siempre, tengas o no claves
  // configuradas, para que el panel muestre precio de mercado desde el
  // primer momento en vez de quedar en blanco hasta conectar Binance.
  async function refreshTicker(silent = false) {
    if (silent && loading) return;
    try {
      const ticker = await getBinanceTicker();
      setLastPrice(ticker.last ?? null);
      setBid(ticker.bid ?? null);
      setAsk(ticker.ask ?? null);
      if (!useBbo) setPrice((current) => current || String(ticker.last ?? ""));
    } catch (error) {
      if (!silent) {
        setMessageTone("error");
        setMessage(error instanceof Error ? error.message : "No se pudo consultar el precio de Binance.");
      }
    }
  }

  // Cuenta/posiciones/órdenes son privadas (requieren claves) y cuentan
  // contra el rate-limit real; se refrescan con menos frecuencia que el precio.
  async function refresh(silent = false) {
    if (silent && (loading || refreshing)) return;
    setRefreshing(true);
    try {
      const currentStatus = await getBinanceStatus();
      setStatus(currentStatus);
      if (currentStatus.configured) {
        const [currentAccount, currentPositions, currentOrders] = await Promise.all([
          getBinanceAccount(), getBinancePositions(), getBinanceOpenOrders(),
        ]);
        setAccount(currentAccount);
        setPositions(currentPositions.positions);
        setOpenOrders(currentOrders.orders);
      }
      await refreshTicker(silent);
    } catch (error) {
      setMessageTone("error");
      setMessage(error instanceof Error ? error.message : "No se pudo consultar Binance.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void refresh();
    const tickerInterval = setInterval(() => void refreshTicker(true), tickerRefreshIntervalMs);
    const accountInterval = setInterval(() => void refresh(true), accountRefreshIntervalMs);
    return () => {
      clearInterval(tickerInterval);
      clearInterval(accountInterval);
    };
  }, []);

  async function submitOrder() {
    if (!canSubmit) {
      setMessageTone("error");
      setMessage("Revisa dirección, precio, cantidad, saldo disponible y confirmación antes de enviar.");
      return;
    }
    setLoading(true);
    setMessageTone("info");
    setMessage(null);
    try {
      // Si se pide adjuntar protección y NO es reduce-only (reduce-only ya
      // está cerrando/reduciendo una posición existente, no tiene sentido
      // ponerle TP/SL a eso), usamos el endpoint bracket para que el TP/SL
      // calculado en pantalla se envíe de verdad a Binance como órdenes
      // reduce-only, en vez de quedarse solo como referencia visual.
      const shouldAttachProtection = attachProtection && !reduceOnly && takeProfitPrice > 0 && stopLossPrice > 0;
      const result = shouldAttachProtection
        ? await sendBinanceBracketOrder({
            symbol: futuresSymbol, side, amount: valueOf(amount), order_type: orderType,
            price: orderType === "limit" ? entryPrice : undefined, leverage: leverageValue,
            time_in_force: timeInForce, confirm_live: confirm,
            stop_loss: stopLossPrice, take_profit: takeProfitPrice,
          })
        : await sendBinanceOrder({
            symbol: futuresSymbol, side, amount: valueOf(amount), order_type: orderType,
            price: orderType === "limit" ? entryPrice : undefined, leverage: leverageValue,
            reduce_only: reduceOnly, time_in_force: timeInForce, confirm_live: confirm,
          });
      const entryStatus = shouldAttachProtection ? (result as { entry?: { status?: string } }).entry?.status : (result as { status?: string }).status;
      const protectionErrors = shouldAttachProtection ? (result as { protection_errors?: string[] }).protection_errors ?? [] : [];
      setMessageTone(protectionErrors.length > 0 ? "error" : "success");
      setMessage(
        `Orden aceptada (${entryStatus || "enviada"}) en ${status?.testnet ? "Testnet" : "producción"}.` +
          (shouldAttachProtection
            ? protectionErrors.length > 0
              ? ` TP/SL con problemas: ${protectionErrors.join(" · ")}`
              : " TP/SL adjuntados."
            : "") +
          " Actualizando saldo..."
      );
      await refresh();
    } catch (error) {
      setMessageTone("error");
      setMessage(error instanceof Error ? error.message : "Binance rechazó la orden.");
    } finally {
      setLoading(false);
    }
  }

  async function closePosition(symbol: string) {
    setLoading(true);
    setMessageTone("info");
    try { await closeBinancePosition(symbol, undefined, confirm); await refresh(); }
    catch (error) { setMessageTone("error"); setMessage(error instanceof Error ? error.message : "No se pudo cerrar la posición."); }
    finally { setLoading(false); }
  }

  async function cancelOrder(order: BinanceOpenOrder) {
    setLoading(true);
    setMessageTone("info");
    try { await cancelBinanceOrder(order.id, order.symbol, confirm); await refresh(); }
    catch (error) { setMessageTone("error"); setMessage(error instanceof Error ? error.message : "No se pudo cancelar la orden."); }
    finally { setLoading(false); }
  }

  return (
    <section className="card space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-[0.18em] text-neutral">Binance Futures · USDT-M</p><h2 className="mt-1 text-xl font-semibold">Panel de operaciones</h2><p className="mt-1 text-sm text-muted">Precios automáticos cada 5 segundos. TP/SL se expresan como ROI sobre el margen.</p></div><button className="rounded-lg border border-border-strong px-3 py-2 text-xs font-semibold" onClick={() => void refresh()} disabled={loading || refreshing}>{refreshing ? "Actualizando..." : "Actualizar"}</button></div>
      {status && <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Estado" value={status.configured ? "Conectada" : "Sin claves"} accent={status.configured} /><Stat label="Red" value={status.testnet ? "Testnet" : "Producción"} /><Stat label="Órdenes" value={status.live_trading_enabled || status.testnet ? "Disponibles" : "Bloqueadas"} /><Stat label="Máximo" value={`$${status.max_order_notional_usdt.toFixed(2)}`} /></div>}
      {account && <div className="grid grid-cols-3 gap-2"><Stat label="Disponible" value={`${Number(account.free || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })} USDT`} /><Stat label="Total" value={`${Number(account.total || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })} USDT`} /><Stat label="Último" value={lastPrice ? `${lastPrice.toLocaleString()} USDT` : "-"} accent /></div>}
      {status && !status.configured && <p className="rounded-lg border border-border bg-panel-muted p-3 text-sm text-muted">Configura las claves en <strong>backend/.env</strong>. Usa Testnet primero y nunca habilites permisos de retiro.</p>}
      {canTrade && <div className="space-y-4 rounded-xl border border-border-strong bg-panel-muted/40 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs uppercase tracking-[0.18em] text-neutral">Nueva orden</p><p className="text-sm text-muted">Avbl {Number(account?.free || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })} USDT</p></div><span className="rounded-full border border-border px-3 py-1 text-xs">{status?.testnet ? "TESTNET" : "LIVE"}</span></div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Field label="Dirección"><select className={inputClass} value={side} onChange={(event) => setSide(event.target.value)}><option value="buy">LONG / BUY</option><option value="sell">SHORT / SELL</option></select></Field><Field label="Tipo"><select className={inputClass} value={orderType} onChange={(event) => setOrderType(event.target.value)}><option value="market">Market</option><option value="limit">Limit</option></select></Field><Field label="Precio" suffix="USDT"><input className={`${inputClass} pr-14`} type="number" value={entryPrice || ""} onChange={(event) => setPrice(event.target.value)} disabled={useBbo} /></Field><Field label="TIF"><select className={inputClass} value={timeInForce} onChange={(event) => setTimeInForce(event.target.value)}><option>GTC</option><option>IOC</option><option>FOK</option></select></Field></div>
        <div className="flex flex-wrap gap-2 text-xs"><button className={`rounded-lg border px-3 py-2 ${useBbo ? "border-neutral text-neutral" : "border-border text-muted"}`} onClick={() => setUseBbo(!useBbo)}>BBO {useBbo ? "activo" : "manual"}</button><span className="rounded-lg border border-border px-3 py-2 text-muted">Último {lastPrice?.toLocaleString() || "-"}</span><span className="rounded-lg border border-border px-3 py-2 text-muted">Bid {bid?.toLocaleString() || "-"}</span><span className="rounded-lg border border-border px-3 py-2 text-muted">Ask {ask?.toLocaleString() || "-"}</span></div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Field label="Tamaño" suffix={baseAsset}><input className={`${inputClass} pr-12`} type="number" min="0" step="any" value={amount} onChange={(event) => { setAmount(event.target.value); setAllocationPercent(0); }} /></Field><Field label="Apalancamiento" suffix="x"><input className={`${inputClass} pr-8`} type="number" min="1" max="20" value={leverage} onChange={(event) => setLeverage(event.target.value)} /></Field><Field label="TP / ROI" suffix="%"><input className={`${inputClass} pr-8`} type="number" min="0" step="any" value={takeProfitRoi} onChange={(event) => setTakeProfitRoi(event.target.value)} /></Field><Field label="Stop Loss / ROI" suffix="%"><input className={`${inputClass} pr-8`} type="number" min="0" step="any" value={stopLossRoi} onChange={(event) => setStopLossRoi(event.target.value)} /></Field></div>
        <div className="space-y-2"><div className="flex justify-between text-xs text-muted"><span>Usar saldo disponible</span><strong>{allocationPercent}% · {amountValue.toFixed(8)} {baseAsset}</strong></div><input aria-label="Porcentaje de saldo a utilizar" className="w-full accent-[rgb(var(--brand))]" type="range" min="0" max="100" step="1" value={allocationPercent} onChange={(event) => setAllocation(Number(event.target.value))} /><div className="flex justify-between text-[11px] text-muted"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div><p className="text-[11px] text-muted">Máximo operativo: {maxAmount.toFixed(8)} {baseAsset} · El tamaño se recalcula al cambiar saldo, precio o apalancamiento.</p></div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="TP estimado" value={`${takeProfitPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })} USDT`} accent /><Stat label="SL estimado" value={`${stopLossPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })} USDT`} /><Stat label="Costo / margen" value={`${cost.toFixed(2)} USDT`} /><Stat label={`Máximo ${baseAsset}`} value={`${maxAmount.toFixed(4)} ${baseAsset}`} /></div>
        <div className="flex flex-wrap items-center gap-4 text-xs text-muted"><label className="flex items-center gap-2"><input type="checkbox" checked={reduceOnly} disabled={!canReduce} onChange={(event) => setReduceOnly(event.target.checked)} /> Reducir-Solo {!canReduce && "(sin posición compatible)"}</label><label className="flex items-center gap-2"><input type="checkbox" checked={attachProtection} disabled={reduceOnly} onChange={(event) => setAttachProtection(event.target.checked)} /> Adjuntar TP/SL reales a Binance</label><label className="flex items-center gap-2"><input type="checkbox" checked={confirm} onChange={(event) => setConfirm(event.target.checked)} /> Confirmo la operación en {status?.testnet ? "Testnet" : "producción"}</label></div><button className="w-full rounded-lg bg-neutral px-4 py-3 text-sm font-semibold text-white disabled:opacity-50" onClick={submitOrder} disabled={!canSubmit}>Enviar {side === "buy" ? "LONG / BUY" : "SHORT / SELL"}</button>
      </div>}
      {positions.length > 0 && <div className="space-y-2"><h3 className="text-sm font-semibold">Posiciones abiertas</h3>{positions.map((position) => <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-3 text-sm" key={`${position.symbol}-${position.side}`}><span>{position.symbol} · {position.side?.toUpperCase()} · {position.contracts} {position.symbol.split("/")[0]} · {position.leverage}x</span><span className={Number(position.unrealized_pnl) >= 0 ? "text-bull" : "text-bear"}>{position.unrealized_pnl ?? "-"} USDT</span><button className="rounded border border-bear px-2 py-1 text-xs text-bear" onClick={() => closePosition(position.symbol)}>Cerrar</button></div>)}</div>}
      {openOrders.length > 0 && <div className="space-y-2"><h3 className="text-sm font-semibold">Órdenes abiertas</h3>{openOrders.map((order) => <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-3 text-sm" key={order.id}><span>#{order.id} · {order.side.toUpperCase()} {order.type} · {order.amount} {order.symbol.split("/")[0]} @ {order.price ?? "market"}</span><button className="rounded border border-border-strong px-2 py-1 text-xs" onClick={() => cancelOrder(order)}>Cancelar</button></div>)}</div>}
      {message && <p className={`rounded-lg border p-3 text-sm ${messageTone === "error" ? "border-bear text-bear" : messageTone === "success" ? "border-bull text-bull" : "border-border text-muted"}`}>{message}</p>}
    </section>
  );
}
