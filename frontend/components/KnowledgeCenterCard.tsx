"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  KNOWLEDGE_CATEGORIES,
  KnowledgeDocument,
  KnowledgeAskResponse,
  getKnowledgeDocuments,
  uploadKnowledgeDocument,
  deleteKnowledgeDocument,
  scanKnowledgeLibrary,
  askKnowledge,
} from "@/lib/api";

function statusBadge(status: string) {
  if (status === "ready") return "🟢";
  if (status === "processing") return "🟡";
  return "🔴";
}

function categoryLabel(category: string) {
  return category.replace(/_/g, " ");
}

export default function KnowledgeCenterCard() {
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [category, setCategory] = useState<string>("other");
  const [uploading, setUploading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [question, setQuestion] = useState("");
  const [askCategory, setAskCategory] = useState<string>("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<KnowledgeAskResponse | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      const rows = await getKnowledgeDocuments();
      setDocs(rows);
    } catch (e: any) {
      setErrorMsg(e.message || "Error cargando documentos.");
    }
  }, []);

  useEffect(() => {
    loadDocs();
    // Poll mientras haya documentos "processing", para reflejar cuando queden listos.
    const interval = setInterval(loadDocs, 5000);
    return () => clearInterval(interval);
  }, [loadDocs]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setErrorMsg(null);
    try {
      await uploadKnowledgeDocument(file, category);
      await loadDocs();
    } catch (err: any) {
      setErrorMsg(err.message || "Error subiendo el documento.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleScanLibrary() {
    setScanning(true);
    setErrorMsg(null);
    try {
      await scanKnowledgeLibrary();
      // El escaneo corre en background en el servidor; refrescamos varias
      // veces para ir viendo cómo aparecen/terminan los documentos nuevos.
      setTimeout(loadDocs, 2000);
      setTimeout(loadDocs, 8000);
    } catch (err: any) {
      setErrorMsg(err.message || "Error escaneando la biblioteca local.");
    } finally {
      setScanning(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteKnowledgeDocument(id);
      await loadDocs();
    } catch (err: any) {
      setErrorMsg(err.message || "Error eliminando el documento.");
    }
  }

  async function handleAsk() {
    if (!question.trim()) return;
    setAsking(true);
    setErrorMsg(null);
    try {
      const result = await askKnowledge(question.trim(), askCategory || undefined);
      setAnswer(result);
    } catch (err: any) {
      setErrorMsg(err.message || "Error consultando el Knowledge Center.");
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm text-gray-300">Knowledge Center (RAG)</h3>
        <span className="text-[10px] text-gray-500">Fase 4</span>
      </div>

      {errorMsg && <p className="text-xs text-bear">{errorMsg}</p>}

      {/* Upload */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-bg border border-border rounded px-2 py-1 text-xs text-gray-300 flex-1"
          >
            {KNOWLEDGE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {categoryLabel(c)}
              </option>
            ))}
          </select>
          <label className="text-xs bg-panel border border-border px-3 py-1.5 rounded hover:border-neutral cursor-pointer whitespace-nowrap">
            {uploading ? "Subiendo..." : "📄 Subir doc"}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              disabled={uploading}
              onChange={handleUpload}
            />
          </label>
        </div>
        <p className="text-[10px] text-gray-500">PDF, TXT o MD. Se trocea, se embebe (Ollama) y se indexa en Qdrant.</p>

        <button
          onClick={handleScanLibrary}
          disabled={scanning}
          className="w-full text-xs bg-panel border border-border px-3 py-1.5 rounded hover:border-neutral disabled:opacity-50"
        >
          {scanning ? "Sincronizando..." : "📚 Sincronizar biblioteca local"}
        </button>
        <p className="text-[10px] text-gray-500">
          Escanea la carpeta <code>knowledge_library/</code> en tu PC y auto-indexa lo nuevo/modificado
          (también corre solo cada {"{"}LIBRARY_SCAN_INTERVAL_MINUTES{"}"} minutos).
          Solo los documentos en estado listo se usan en las respuestas de la IA.
        </p>
      </div>

      {/* Document list */}
      <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
        {docs.length === 0 && <p className="text-gray-500 text-xs">Sin documentos aún.</p>}
        {docs.map((d) => (
          <div
            key={d.id}
            className="flex items-center justify-between gap-2 border-l-2 border-border pl-2 py-1"
          >
            <div className="min-w-0">
              <p className="text-xs text-gray-200 truncate">
                {statusBadge(d.status)} {d.source === "library" ? "📚" : "📤"} {d.title}
              </p>
              <p className="text-[10px] text-gray-500">
                {categoryLabel(d.category)} · {d.num_chunks} chunks
                {d.status === "error" && d.error_message ? ` · ${d.error_message}` : ""}
              </p>
            </div>
            <button
              onClick={() => handleDelete(d.id)}
              className="text-[10px] text-gray-500 hover:text-bear shrink-0"
            >
              eliminar
            </button>
          </div>
        ))}
      </div>

      {/* Ask */}
      <div className="space-y-2 border-t border-border pt-3">
        <div className="flex items-center gap-2">
          <select
            value={askCategory}
            onChange={(e) => setAskCategory(e.target.value)}
            className="bg-bg border border-border rounded px-2 py-1 text-xs text-gray-300"
          >
            <option value="">Todas las categorías</option>
            {KNOWLEDGE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {categoryLabel(c)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            placeholder="Pregunta a tus libros/papers..."
            className="flex-1 bg-bg border border-border rounded px-2 py-1.5 text-xs text-gray-200"
          />
          <button
            onClick={handleAsk}
            disabled={asking}
            className="bg-panel border border-border px-3 py-1.5 rounded text-xs hover:border-neutral disabled:opacity-50"
          >
            {asking ? "..." : "Preguntar"}
          </button>
        </div>

        {answer && (
          <div className="space-y-2">
            <p className="text-xs text-gray-200 bg-bg/50 p-2 rounded whitespace-pre-wrap">
              {answer.answer}
            </p>
            {answer.sources.length > 0 && (
              <div className="space-y-1">
                <p className="text-[10px] text-gray-500">Fuentes utilizadas:</p>
                {answer.sources.map((s, i) => (
                  <details key={i} className="text-[10px] text-gray-400 border-l-2 border-border pl-2">
                    <summary className="cursor-pointer text-gray-300">
                      {s.document_title}{s.category ? ` (${categoryLabel(s.category)})` : ""} · fragmento {s.chunk_index} · score {s.score.toFixed(2)}
                    </summary>
                    <p className="mt-1 text-gray-500 whitespace-pre-wrap">{s.content}</p>
                  </details>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
