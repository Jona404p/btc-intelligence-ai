"use client";

import { useEffect, useState } from "react";
import { askAI, ChatConversation, ChatMessage, createChatConversation, deleteChatConversation, getChatConversations, getChatMessages } from "@/lib/api";

export default function AIChatCard() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [useKnowledge, setUseKnowledge] = useState(true);
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadConversation(id: number) {
    setLoadingHistory(true);
    try {
      setConversationId(id);
      setMessages(await getChatMessages(id));
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "No se pudo cargar la conversación.");
    } finally {
      setLoadingHistory(false);
    }
  }

  async function refreshConversations(selectLatest = false) {
    const items = await getChatConversations();
    setConversations(items);
    if (selectLatest && items[0]) await loadConversation(items[0].id);
    if (selectLatest && !items[0]) setLoadingHistory(false);
  }

  useEffect(() => {
    refreshConversations(true).catch((exception) => {
      setError(exception instanceof Error ? exception.message : "No se pudo cargar el historial.");
      setLoadingHistory(false);
    });
  }, []);

  async function newConversation() {
    try {
      const conversation = await createChatConversation();
      setConversations((current) => [conversation, ...current]);
      setConversationId(conversation.id);
      setMessages([]);
      setQuestion("");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "No se pudo crear la conversación.");
    }
  }

  async function removeConversation(id: number) {
    try {
      await deleteChatConversation(id);
      const remaining = conversations.filter((conversation) => conversation.id !== id);
      setConversations(remaining);
      if (conversationId === id) {
        setConversationId(remaining[0]?.id ?? null);
        setMessages(remaining[0] ? await getChatMessages(remaining[0].id) : []);
      }
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "No se pudo eliminar la conversación.");
    }
  }

  async function handleAsk() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    const optimisticMessage: ChatMessage = {
      id: -Date.now(),
      conversation_id: conversationId ?? 0,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimisticMessage]);
    const sentQuestion = question;
    setQuestion("");
    try {
      const response = await askAI(
        sentQuestion,
        "BTC/USDT",
        "1h",
        conversationId ?? undefined,
        useKnowledge
      ) as { conversation_id?: number };
      const id = response.conversation_id ?? conversationId;
      if (id) {
        setConversationId(id);
        setMessages(await getChatMessages(id));
      }
      await refreshConversations();
    } catch (exception) {
      setMessages((current) => current.filter((message) => message.id !== optimisticMessage.id));
      setError(exception instanceof Error ? exception.message : "Error consultando a la IA.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="card space-y-3">
        <div className="flex items-center justify-between gap-2"><div><p className="text-xs uppercase tracking-[0.16em] text-neutral">Historial</p><h3 className="font-semibold text-sm">Conversaciones</h3></div><button className="rounded-lg border border-border-strong px-2 py-1 text-xs font-semibold" onClick={newConversation}>+</button></div>
        <div className="max-h-80 space-y-1 overflow-y-auto">{conversations.length === 0 && <p className="text-xs text-muted">No hay conversaciones guardadas.</p>}{conversations.map((conversation) => <div key={conversation.id} className={`flex items-center gap-1 rounded-lg ${conversation.id === conversationId ? "bg-neutral text-white" : "text-muted hover:bg-panel-muted hover:text-foreground"}`}><button className="min-w-0 flex-1 truncate px-3 py-2 text-left text-xs" onClick={() => loadConversation(conversation.id)}>{conversation.title}</button><button className="px-2 py-1 text-xs opacity-70 hover:text-bear" title="Eliminar conversación" aria-label={`Eliminar ${conversation.title}`} onClick={() => void removeConversation(conversation.id)}>×</button></div>)}</div>
      </aside>
      <section className="card flex min-h-[520px] flex-col gap-3">
      <div className="flex items-center gap-3 border-b border-border pb-3"><div className="h-16 w-20 shrink-0 overflow-hidden rounded-xl border border-neutral/40 bg-black"><img src="/pancrasito.png" alt="PanCrasito, gatito analista de Bitcoin" className="h-full w-full object-cover" /></div><div><p className="text-xs uppercase tracking-[0.18em] text-neutral">PanCrasito</p><h3 className="text-lg font-semibold">El gatito de Jonathan</h3><p className="text-xs text-muted">Curioso, listo, buena onda y realista con BTC y el riesgo.</p></div></div>
      <div className="flex-1 space-y-3 overflow-y-auto">{loadingHistory && <p className="text-sm text-muted">PanCrasito está revisando el historial...</p>}{!loadingHistory && messages.length === 0 && <div className="flex flex-col items-center rounded-xl border border-dashed border-border p-6 text-center"><img src="/pancrasito.png" alt="PanCrasito" className="mb-3 h-28 w-40 object-cover" /><p className="text-sm font-semibold">Hola, soy PanCrasito</p><p className="mt-1 text-sm text-muted">Pregúntame por BTC, riesgo, mercado o cualquier idea que quieras explorar.</p></div>}{messages.map((message) => <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`flex max-w-[90%] items-start gap-2 ${message.role === "user" ? "flex-row-reverse" : ""}`}>{message.role === "assistant" && <img src="/pancrasito.png" alt="PanCrasito" className="h-8 w-10 shrink-0 rounded-lg border border-neutral/30 object-cover" />}<div className={`rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${message.role === "user" ? "bg-neutral text-white" : "bg-panel-muted text-foreground"}`}>{message.content}<span className="mt-1 block text-[10px] opacity-60">{message.model || message.role}</span></div></div></div>)}{loading && <p className="text-xs text-muted">PanCrasito está pensando...</p>}</div>
      <div className="flex gap-2 border-t border-border pt-3">
        <input
          className="flex-1 rounded-lg border border-border bg-panel-muted px-3 py-2 text-sm"
          placeholder="Escribe tu pregunta..."
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && void handleAsk()}
          disabled={loading}
        />
        <button onClick={() => void handleAsk()} disabled={loading || !question.trim()} className="rounded-lg bg-neutral px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "..." : "Enviar"}</button>
      </div>
      <label className="flex items-start gap-2 text-xs text-muted">
        <input
          type="checkbox"
          checked={useKnowledge}
          onChange={(event) => setUseKnowledge(event.target.checked)}
          disabled={loading}
          className="mt-0.5 accent-violet-500"
        />
        <span>
          Usar conocimiento de <code>knowledge_library/</code> (RAG). Sincroniza la biblioteca
          en Knowledge Center; se recuperan solo fragmentos relevantes y la IA cita sus documentos.
        </span>
      </label>
      {error && <p className="text-bear text-xs">{error}</p>}
      </section>
    </div>
  );
}
