"use client";

import { useState } from "react";
import {
  BacktestResult,
  PaperAccount,
  closePaperTrade,
  createJournalEntry,
  createTradeAutopsy,
  createPaperAccount,
  getPaperAccount,
  openPaperTrade,
  runBacktest,
} from "@/lib/api";

const inputClass = "w-full rounded-lg border border-border bg-panel-muted px-3 py-2 text-sm text-foreground";
const strategies = ["ema_crossover", "rsi", "breakout", "trend_following"];

function Metric({ label, value }: { label: string; value: string | number | undefined }) {
  return (
    <div className="rounded-lg border border-border bg-panel-muted p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value ?? "-"}</p>
    </div>
  );
}

export default function Phase7Lab() {
  const [strategy, setStrategy] = useState("ema_crossover");
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [accountName, setAccountName] = useState("BTC Paper Account");
  const [capital, setCapital] = useState("10000");
  const [entry, setEntry] = useState("");
  const [quantity, setQuantity] = useState("0.001");
  const [direction, setDirection] = useState("long");
  const [closePrices, setClosePrices] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [journalId, setJournalId] = useState("");
  const [journalReason, setJournalReason] = useState("");
  const [autopsyLessons, setAutopsyLessons] = useState("");

  async function handleBacktest() {
    setBusy(true);
    setMessage(null);
    try {
      setBacktest(await runBacktest({ strategy, timeframe: "1h", initial_capital: Number(capital), limit: 300 }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo ejecutar el backtest.");
    } finally {
      setBusy(false);
    }
  }

  async function handleJournal() {
    if (!journalReason.trim()) return;
    setBusy(true);
    try {
      const entryRecord = await createJournalEntry({ direction, reason: journalReason, symbol: "BTC/USDT", result: "open" });
      setJournalId(String(entryRecord.id));
      setJournalReason("");
      setMessage(`Entrada de journal #${entryRecord.id} guardada.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo guardar el journal.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAutopsy() {
    if (!journalId || !autopsyLessons.trim()) return;
    setBusy(true);
    try {
      await createTradeAutopsy({ journal_entry_id: Number(journalId), lessons: autopsyLessons, indicators_worked: [], indicators_failed: [] });
      setAutopsyLessons("");
      setMessage(`Autopsia de la entrada #${journalId} guardada.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo guardar la autopsia.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateAccount() {
    setBusy(true);
    setMessage(null);
    try {
      setAccount(await createPaperAccount(accountName, Number(capital)));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo crear la cuenta paper.");
    } finally {
      setBusy(false);
    }
  }

  async function handleOpenTrade() {
    if (!account || !entry) return;
    setBusy(true);
    try {
      await openPaperTrade({ account_id: account.id, symbol: "BTC/USDT", direction, entry: Number(entry), quantity: Number(quantity) });
      setAccount(await getPaperAccount(account.id));
      setMessage("Operación virtual abierta.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo abrir la operación.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCloseTrade(tradeId: number) {
    const exitPrice = closePrices[tradeId];
    if (!account || !exitPrice) return;
    setBusy(true);
    try {
      await closePaperTrade(tradeId, Number(exitPrice));
      setAccount(await getPaperAccount(account.id));
      setMessage("Operación virtual cerrada y contabilizada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo cerrar la operación.");
    } finally {
      setBusy(false);
    }
  }

  const metrics = backtest?.metrics;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <section className="card space-y-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-neutral">Fase 7 / Backtest Lab</p>
            <h2 className="mt-1 text-xl font-semibold">Prueba una estrategia sin mirar al futuro</h2>
            <p className="mt-1 text-sm text-muted">La entrada se ejecuta en la apertura de la vela siguiente. Si una vela toca stop y target, se cuenta el stop.</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs text-muted">Estrategia<select className={inputClass} value={strategy} onChange={(event) => setStrategy(event.target.value)}>{strategies.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label className="text-xs text-muted">Capital<input className={inputClass} type="number" value={capital} onChange={(event) => setCapital(event.target.value)} /></label>
          </div>
          <button className="w-full rounded-lg bg-neutral px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" onClick={handleBacktest} disabled={busy}> {busy ? "Ejecutando..." : "Ejecutar backtest 1H"}</button>
          {backtest?.status === "ok" && metrics && <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Metric label="Trades" value={metrics.total_trades} /><Metric label="Win rate" value={`${metrics.win_rate_pct}%`} /><Metric label="ROI" value={`${metrics.roi_pct}%`} /><Metric label="Max DD" value={`${metrics.max_drawdown_pct}%`} /><Metric label="Profit factor" value={metrics.profit_factor} /><Metric label="Expectancy" value={metrics.expectancy} /><Metric label="Sharpe" value={metrics.sharpe} /><Metric label="Net PnL" value={`$${metrics.net_pnl}`} /></div>}
        </section>

        <section className="card space-y-4">
          <div><p className="text-xs uppercase tracking-[0.18em] text-neutral">Paper trading</p><h2 className="mt-1 text-xl font-semibold">Practica el proceso, no el dinero real</h2><p className="mt-1 text-sm text-muted">Estas operaciones son virtuales y no tienen conexión con órdenes del exchange.</p></div>
          {!account ? <div className="space-y-3"><label className="text-xs text-muted">Nombre de cuenta<input className={inputClass} value={accountName} onChange={(event) => setAccountName(event.target.value)} /></label><button className="w-full rounded-lg border border-border-strong px-4 py-2 text-sm font-semibold hover:border-neutral" onClick={handleCreateAccount} disabled={busy}>Crear cuenta virtual de ${Number(capital || 0).toLocaleString()}</button></div> : <>
            <div className="grid grid-cols-3 gap-2"><Metric label="Capital" value={`$${account.current_capital.toFixed(2)}`} /><Metric label="ROI" value={`${account.roi_pct.toFixed(2)}%`} /><Metric label="Win rate" value={`${account.win_rate_pct.toFixed(1)}%`} /></div>
            <div className="grid grid-cols-3 gap-2"><select className={inputClass} value={direction} onChange={(event) => setDirection(event.target.value)}><option value="long">LONG</option><option value="short">SHORT</option></select><input className={inputClass} type="number" placeholder="Entrada" value={entry} onChange={(event) => setEntry(event.target.value)} /><input className={inputClass} type="number" placeholder="Cantidad" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></div>
            <button className="w-full rounded-lg bg-neutral px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" onClick={handleOpenTrade} disabled={busy || !entry}>Abrir operación virtual</button>
            <div className="space-y-2">{account.trades.map((trade) => <div className="rounded-lg border border-border p-3 text-sm" key={trade.id}><div className="flex items-center justify-between"><span className="font-semibold">{trade.direction.toUpperCase()} #{trade.id}</span><span className={trade.pnl && trade.pnl >= 0 ? "text-bull" : "text-bear"}>{trade.status === "open" ? "OPEN" : `$${trade.pnl?.toFixed(2)}`}</span></div>{trade.status === "open" && <div className="mt-2 flex gap-2"><input className={inputClass} type="number" placeholder="Precio salida" value={closePrices[trade.id] || ""} onChange={(event) => setClosePrices((current) => ({ ...current, [trade.id]: event.target.value }))} /><button className="rounded-lg border border-border-strong px-3 text-xs" onClick={() => handleCloseTrade(trade.id)}>Cerrar</button></div>}</div>)}</div>
          </>}
        </section>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <section className="card space-y-3">
          <div><p className="text-xs uppercase tracking-[0.18em] text-neutral">Trade Journal</p><h2 className="mt-1 text-lg font-semibold">Registra la hipótesis antes del resultado</h2></div>
          <textarea className={`${inputClass} min-h-24`} placeholder="Qué viste, qué invalidaría la idea y por qué decidiste operar..." value={journalReason} onChange={(event) => setJournalReason(event.target.value)} />
          <button className="rounded-lg border border-border-strong px-4 py-2 text-sm font-semibold hover:border-neutral disabled:opacity-50" onClick={handleJournal} disabled={busy || !journalReason.trim()}>Guardar journal</button>
          {journalId && <p className="text-xs text-muted">Última entrada: #{journalId}</p>}
        </section>
        <section className="card space-y-3">
          <div><p className="text-xs uppercase tracking-[0.18em] text-neutral">Trade Autopsy</p><h2 className="mt-1 text-lg font-semibold">Convierte el resultado en aprendizaje</h2></div>
          <input className={inputClass} type="number" placeholder="ID de entrada del journal" value={journalId} onChange={(event) => setJournalId(event.target.value)} />
          <textarea className={`${inputClass} min-h-24`} placeholder="Qué funcionó, qué falló y qué cambiarías..." value={autopsyLessons} onChange={(event) => setAutopsyLessons(event.target.value)} />
          <button className="rounded-lg border border-border-strong px-4 py-2 text-sm font-semibold hover:border-neutral disabled:opacity-50" onClick={handleAutopsy} disabled={busy || !journalId || !autopsyLessons.trim()}>Guardar autopsia</button>
        </section>
      </div>
      {message && <p className="rounded-lg border border-border bg-panel-muted px-3 py-2 text-sm text-muted">{message}</p>}
    </div>
  );
}
