"use client";

import { FormEvent, useMemo, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function getApiErrorMessage(data: unknown, fallback: string) {
  if (typeof data !== "object" || data === null) {
    return fallback;
  }

  const record = data as Record<string, unknown>;

  if (typeof record.detail === "string") {
    return record.detail;
  }

  if (typeof record.error === "string") {
    return record.error;
  }

  return fallback;
}

type Source = {
  id: number;
  content: string;
  metadata: Record<string, unknown> | null;
  similarity: number;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

export default function Home() {
  const [source, setSource] = useState("Phase 1 notes");
  const [documentText, setDocumentText] = useState("");
  const [question, setQuestion] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [lastSources, setLastSources] = useState<Source[]>([]);
  const [ingestStatus, setIngestStatus] = useState("");
  const [uploadStatus, setUploadStatus] = useState("");
  const [chatStatus, setChatStatus] = useState("");
  const [isIngesting, setIsIngesting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);

  const canIngest = useMemo(
    () => documentText.trim().length > 0 && !isIngesting,
    [documentText, isIngesting],
  );
  const canUpload = useMemo(() => pdfFile !== null && !isUploading, [pdfFile, isUploading]);
  const canAsk = useMemo(() => question.trim().length > 0 && !isAsking, [question, isAsking]);

  async function ingestDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canIngest) {
      return;
    }

    setIsIngesting(true);
    setIngestStatus("Chunking text and generating embeddings...");

    try {
      const response = await fetch(`${API_BASE_URL}/api/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source,
          text: documentText,
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(getApiErrorMessage(data, "Ingestion failed."));
      }

      setIngestStatus(`Stored ${data.chunks} chunks from "${data.source}".`);
    } catch (error) {
      setIngestStatus(error instanceof Error ? error.message : "Ingestion failed.");
    } finally {
      setIsIngesting(false);
    }
  }

  async function askQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const currentQuestion = question.trim();

    if (!currentQuestion || !canAsk) {
      return;
    }

    setQuestion("");
    setIsAsking(true);
    setChatStatus("Embedding question, retrieving context, and generating answer...");
    setMessages((current) => [...current, { role: "user", content: currentQuestion }]);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: currentQuestion,
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(getApiErrorMessage(data, "Question failed."));
      }

      setLastSources(data.sources ?? []);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources ?? [],
        },
      ]);
      setChatStatus("");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Question failed.";

      setChatStatus(message);
      setMessages((current) => [...current, { role: "assistant", content: message }]);
    } finally {
      setIsAsking(false);
    }
  }

  async function uploadPdf(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!pdfFile || !canUpload) {
      return;
    }

    const formData = new FormData();
    formData.append("file", pdfFile);

    setIsUploading(true);
    setUploadStatus("Extracting PDF text and generating embeddings...");

    try {
      const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(getApiErrorMessage(data, "PDF upload failed."));
      }

      setUploadStatus(`Stored ${data.chunks} chunks from "${data.source}" across ${data.pages} pages.`);
    } catch (error) {
      setUploadStatus(error instanceof Error ? error.message : "PDF upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f7f4] text-[#171717]">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-5 py-6 lg:px-8">
        <header className="flex flex-col gap-3 border-b border-[#d9d6cc] pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.12em] text-[#5f6f52]">
              Local RAG Engine
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-[#111] md:text-4xl">
              Document Question Answering
            </h1>
          </div>
          <div className="grid gap-1 text-sm text-[#5b5b55]">
            <span>Ollama: qwen3.5:4b</span>
            <span>Embeddings: nomic-embed-text, 768d</span>
            <span>Vector store: PostgreSQL + pgvector</span>
          </div>
        </header>

        <div className="grid flex-1 gap-6 lg:grid-cols-[minmax(320px,0.85fr)_minmax(420px,1.15fr)]">
          <section
            className="flex min-h-[560px] flex-col gap-4 rounded-lg border border-[#d9d6cc] bg-white p-4 shadow-sm"
          >
            <form onSubmit={ingestDocument} className="flex flex-1 flex-col gap-4">
              <div>
                <label htmlFor="source" className="text-sm font-medium text-[#34342f]">
                  Source label
                </label>
                <input
                  id="source"
                  value={source}
                  onChange={(event) => setSource(event.target.value)}
                  className="mt-2 h-11 w-full rounded-md border border-[#c8c3b8] bg-white px-3 text-sm outline-none focus:border-[#57735a]"
                  placeholder="Example: research-notes.txt"
                />
              </div>

              <div className="flex flex-1 flex-col">
                <label htmlFor="document" className="text-sm font-medium text-[#34342f]">
                  Document text
                </label>
                <textarea
                  id="document"
                  value={documentText}
                  onChange={(event) => setDocumentText(event.target.value)}
                  className="mt-2 min-h-[280px] flex-1 resize-none rounded-md border border-[#c8c3b8] bg-[#fcfcfa] p-3 text-sm leading-6 outline-none focus:border-[#57735a]"
                  placeholder="Paste a document, article, notes, or extracted PDF text here..."
                />
              </div>

              <button
                type="submit"
                disabled={!canIngest}
                className="h-11 rounded-md bg-[#243d30] px-4 text-sm font-semibold text-white transition hover:bg-[#1a2f24] disabled:cursor-not-allowed disabled:bg-[#a6aca4]"
              >
                {isIngesting ? "Ingesting..." : "Ingest Document"}
              </button>

              {ingestStatus ? (
                <p className="rounded-md bg-[#eef2e9] px-3 py-2 text-sm text-[#33452d]">
                  {ingestStatus}
                </p>
              ) : null}
            </form>

            <form onSubmit={uploadPdf} className="border-t border-[#e3e0d8] pt-4">
              <label htmlFor="pdf" className="text-sm font-medium text-[#34342f]">
                PDF upload
              </label>
              <div className="mt-2 flex flex-col gap-3 sm:flex-row">
                <input
                  id="pdf"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)}
                  className="min-h-11 flex-1 rounded-md border border-[#c8c3b8] bg-[#fcfcfa] px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-[#e8ece3] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-[#243d30]"
                />
                <button
                  type="submit"
                  disabled={!canUpload}
                  className="h-11 rounded-md bg-[#243d30] px-4 text-sm font-semibold text-white transition hover:bg-[#1a2f24] disabled:cursor-not-allowed disabled:bg-[#a6aca4]"
                >
                  {isUploading ? "Uploading..." : "Upload PDF"}
                </button>
              </div>

              {uploadStatus ? (
                <p className="mt-3 rounded-md bg-[#eef2e9] px-3 py-2 text-sm text-[#33452d]">
                  {uploadStatus}
                </p>
              ) : null}
            </form>
          </section>

          <section className="grid min-h-[560px] gap-4 lg:grid-rows-[1fr_auto]">
            <div className="flex flex-col rounded-lg border border-[#d9d6cc] bg-white shadow-sm">
              <div className="border-b border-[#e3e0d8] px-4 py-3">
                <h2 className="text-base font-semibold">RAG Chat</h2>
              </div>

              <div className="flex-1 space-y-4 overflow-y-auto p-4">
                {messages.length === 0 ? (
                  <div className="flex h-full min-h-[320px] items-center justify-center text-center text-sm text-[#65655f]">
                    Ingest text, then ask a question grounded in the stored chunks.
                  </div>
                ) : (
                  messages.map((message, index) => (
                    <article
                      key={`${message.role}-${index}`}
                      className={`max-w-[88%] rounded-lg px-4 py-3 text-sm leading-6 ${
                        message.role === "user"
                          ? "ml-auto bg-[#243d30] text-white"
                          : "bg-[#f1f0ea] text-[#1f1f1b]"
                      }`}
                    >
                      {message.content}
                    </article>
                  ))
                )}
              </div>

              <form onSubmit={askQuestion} className="border-t border-[#e3e0d8] p-4">
                <div className="flex gap-3">
                  <input
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    className="h-11 flex-1 rounded-md border border-[#c8c3b8] bg-white px-3 text-sm outline-none focus:border-[#57735a]"
                    placeholder="Ask a question about the ingested documents..."
                  />
                  <button
                    type="submit"
                    disabled={!canAsk}
                    className="h-11 rounded-md bg-[#243d30] px-5 text-sm font-semibold text-white transition hover:bg-[#1a2f24] disabled:cursor-not-allowed disabled:bg-[#a6aca4]"
                  >
                    {isAsking ? "Asking..." : "Ask"}
                  </button>
                </div>
                {chatStatus ? <p className="mt-3 text-sm text-[#6b5c20]">{chatStatus}</p> : null}
              </form>
            </div>

            <aside className="rounded-lg border border-[#d9d6cc] bg-white p-4 shadow-sm">
              <h2 className="text-base font-semibold">Retrieved Sources</h2>
              <div className="mt-3 grid gap-3">
                {lastSources.length === 0 ? (
                  <p className="text-sm text-[#65655f]">
                    Sources will appear here after the first question.
                  </p>
                ) : (
                  lastSources.map((sourceItem, index) => (
                    <details
                      key={sourceItem.id}
                      className="rounded-md border border-[#e3e0d8] bg-[#fcfcfa] p-3"
                    >
                      <summary className="cursor-pointer text-sm font-medium">
                        Source {index + 1} · similarity {sourceItem.similarity.toFixed(3)}
                      </summary>
                      <p className="mt-2 text-xs text-[#686862]">
                        {String(sourceItem.metadata?.source ?? "pasted text")} · chunk{" "}
                        {String(sourceItem.metadata?.chunkIndex ?? sourceItem.id)}
                        {sourceItem.metadata?.page ? ` · page ${String(sourceItem.metadata.page)}` : ""}
                      </p>
                      <p className="mt-3 line-clamp-5 text-sm leading-6 text-[#353530]">
                        {sourceItem.content}
                      </p>
                    </details>
                  ))
                )}
              </div>
            </aside>
          </section>
        </div>
      </section>
    </main>
  );
}
