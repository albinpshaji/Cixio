"use client";

import { useState, useEffect, useRef, FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  Plus,
  Trash2,
  Paperclip,
  Send,
  Loader2,
  BookOpen,
  Database,
  Terminal,
  Cpu,
  X,
  FileText,
  CheckCircle2,
  ChevronRight,
  Info,
  Brain,
  ChevronDown,
  Sun,
  Moon,
  Square,
  LayoutDashboard,
  LogOut,
} from "lucide-react";
import { getAccessToken, getCurrentUser, logoutUser, authFetch } from "@/app/lib/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

function parseBold(text: string) {
  const parts = text.split("**");
  return parts.map((part, i) => {
    if (i % 2 === 1) {
      return <strong key={i} className="font-bold text-slate-900 dark:text-white">{part}</strong>;
    }
    return part;
  });
}

function renderMarkdown(text: string) {
  if (!text) return null;
  
  const lines = text.split("\n");
  
  return lines.map((line, idx) => {
    if (line.startsWith("### ")) {
      return <h4 key={idx} className="text-base font-bold text-slate-800 dark:text-slate-100 mt-3 mb-1.5">{line.substring(4)}</h4>;
    }
    if (line.startsWith("## ")) {
      return <h3 key={idx} className="text-lg font-bold text-slate-800 dark:text-slate-100 mt-4 mb-2">{line.substring(3)}</h3>;
    }
    if (line.startsWith("# ")) {
      return <h2 key={idx} className="text-xl font-bold text-slate-800 dark:text-slate-100 mt-5 mb-3">{line.substring(2)}</h2>;
    }
    
    const isBullet = line.trim().startsWith("* ") || line.trim().startsWith("- ");
    if (isBullet) {
      const bulletChar = line.includes("* ") ? "* " : "- ";
      const indentCount = line.indexOf(bulletChar);
      const cleanLine = line.substring(indentCount + 2);
      return (
        <ul key={idx} className="list-disc pl-5 my-1 text-sm text-slate-700 dark:text-slate-300 leading-relaxed" style={{ marginLeft: `${indentCount * 4}px` }}>
          <li>{parseBold(cleanLine)}</li>
        </ul>
      );
    }
    
    return (
      <p key={idx} className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed my-1.5 min-h-[0.5rem]">
        {parseBold(line)}
      </p>
    );
  });
}

type Source = {
  id: number;
  content: string;
  metadata: {
    source?: string;
    page?: number;
    chunkIndex?: number;
    hyde_query?: string;
  } | null;
  similarity: number;
};

type Message = {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  thoughts?: string;
  sources?: Source[];
  tokenUsage?: {
    prompt_tokens: number;
    eval_tokens: number;
  };
  token_usage?: {
    prompt_tokens: number;
    eval_tokens: number;
  };
  created_at?: string;
};

type Session = {
  id: string;
  title: string;
  created_at: string;
};

export default function ChatPage() {
  const router = useRouter();
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [activeDrawerSources, setActiveDrawerSources] = useState<Source[] | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [thinkLevel, setThinkLevel] = useState<"none" | "low" | "medium" | "max">("medium");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchDepth, setSearchDepth] = useState<"fast" | "balanced" | "deep">("balanced");
  const [searchDepthOpen, setSearchDepthOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [activeTab, setActiveTab] = useState<"chat" | "documents">("chat");
  const [hydeEnabled, setHydeEnabled] = useState(false);

  // Read active tab query param on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("tab") === "documents") {
        setActiveTab("documents");
      }
    }
  }, []);

  // Auth guard — redirect to /login if not authenticated
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAccessToken();
      if (!token) {
        router.replace("/login");
        return;
      }
      const user = await getCurrentUser();
      if (!user) {
        router.replace("/login");
        return;
      }
      setIsAuthChecking(false);
    };
    checkAuth();
  }, [router]);

  const handleLogout = async () => {
    await logoutUser();
    router.push("/login");
  };

  // Initialize theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as "light" | "dark" | null;
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.classList.toggle("dark", savedTheme === "dark");
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const initialTheme = prefersDark ? "dark" : "light";
      setTheme(initialTheme);
      document.documentElement.classList.toggle("dark", initialTheme === "dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    localStorage.setItem("theme", nextTheme);
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
  };

  // Document Manager states
  interface UploadedDoc {
    filename: string;
    chunk_count: number;
    uploaded_at: string | null;
    session_id: string | null;
  }
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const globalFileInputRef = useRef<HTMLInputElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Stop LLM Generation function
  function stopGeneration() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsAsking(false);
    }
  }

  // Fetch uploaded documents from API
  async function fetchUploadedDocs() {
    setIsLoadingDocs(true);
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/documents`);
      if (res.ok) {
        const data = await res.json();
        setUploadedDocs(data);
      }
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    } finally {
      setIsLoadingDocs(false);
    }
  }

  // Handle Global PDF/TXT Upload Ingestion
  async function handleGlobalFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    setIsLoadingDocs(true);

    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/documents/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      // Refresh list of documents
      await fetchUploadedDocs();
    } catch (err) {
      console.error("Failed to upload global document", err);
      alert("Failed to upload global document. Please check backend connection.");
    } finally {
      setIsLoadingDocs(false);
      if (globalFileInputRef.current) {
        globalFileInputRef.current.value = "";
      }
    }
  }

  // Delete an uploaded document
  async function handleDeleteDoc(filename: string, sessionId: string | null) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
      const url = `${API_BASE_URL}/api/v1/documents?filename=${encodeURIComponent(filename)}` + (sessionId ? `&sessionId=${encodeURIComponent(sessionId)}` : "");
      const res = await authFetch(url, { method: "DELETE" });
      if (res.ok) {
        fetchUploadedDocs();
      }
    } catch (err) {
      console.error("Failed to delete document:", err);
    }
  }

  useEffect(() => {
    if (activeTab === "documents") {
      fetchUploadedDocs();
    }
  }, [activeTab]);

  // Auto-scroll chat window only if the user is already near the bottom
  const scrollToBottom = (force = false) => {
    const container = chatContainerRef.current;
    if (!container) return;

    // Check if the user is near the bottom (within 150px threshold)
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight <= 150;

    if (isAtBottom || force) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    // If the last message is from the user, force a scroll to the bottom!
    const lastMessage = messages[messages.length - 1];
    const isUserMsg = lastMessage?.role === "user";
    scrollToBottom(isUserMsg);

    // Auto-scroll the active thinking block as it generates
    const activeThoughtBox = document.getElementById("active-thought-box");
    if (activeThoughtBox) {
      activeThoughtBox.scrollTop = activeThoughtBox.scrollHeight;
    }
  }, [messages]);

  // Initial load: fetch sessions
  useEffect(() => {
    fetchSessions();
  }, []);

  // Fetch all chat history sessions
  async function fetchSessions() {
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/chat/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
        if (data.length > 0) {
          selectSession(data[0].id);
        } else {
          // If no sessions exist, auto-create one
          createNewSession();
        }
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  }

  // Create a fresh conversation session
  async function createNewSession() {
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New Conversation" }),
      });
      if (res.ok) {
        const newSession = await res.json();
        setSessions((prev) => [newSession, ...prev]);
        selectSession(newSession.id);
      }
    } catch (err) {
      console.error("Failed to create session", err);
    }
  }

  // Select/switch active chat session
  async function selectSession(id: string) {
    setActiveSessionId(id);
    setMessages([]);
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/chat/sessions/${id}/messages`);
      if (res.ok) {
        const history = await res.json();
        setMessages(history);
        setTimeout(() => scrollToBottom(true), 50);
      }
    } catch (err) {
      console.error("Failed to fetch messages for session", err);
    }
  }

  // Delete chat session
  async function deleteSession(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this chat session?")) return;

    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/chat/sessions/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeSessionId === id) {
          const remaining = sessions.filter((s) => s.id !== id);
          if (remaining.length > 0) {
            selectSession(remaining[0].id);
          } else {
            setActiveSessionId(null);
            setMessages([]);
            createNewSession();
          }
        }
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  }

  // Handle PDF/TXT Upload Ingestion
  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !activeSessionId) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("sessionId", activeSessionId);

    setIsUploading(true);
    
    // Add pending upload message to the chat
    const tempSystemId = `sys-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: tempSystemId,
        role: "system",
        content: `Uploading and indexing "${file.name}"... Creating vector chunks in ChromaDB.`,
      },
    ]);

    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/documents/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      const data = await res.json();

      // Replace system message with successful confirmation
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === tempSystemId
            ? {
                ...msg,
                content: `📁 Document "${data.source}" successfully processed! Split into ${data.chunks} chunks across ${data.pages} pages. Dynamic RAG priority boosting is active.`,
              }
            : msg
        )
      );

      // Auto update sidebar title if it was default
      const activeSession = sessions.find((s) => s.id === activeSessionId);
      if (activeSession && activeSession.title === "New Conversation") {
        const newTitle = `Chat: ${file.name.substring(0, 20)}`;
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSessionId ? { ...s, title: newTitle } : s
          )
        );
        authFetch(`${API_BASE_URL}/api/v1/chat/sessions/${activeSessionId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: newTitle }),
        }).catch((err) => console.error("Failed to persist session title:", err));
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === tempSystemId
            ? {
                ...msg,
                content: `❌ Ingestion failed for "${file.name}". Please make sure the backend is active and accepts the file type.`,
              }
            : msg
        )
      );
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  // Send grounded chat message (SSE Stream)
  async function handleSendMessage(e: FormEvent) {
    e.preventDefault();
    const currentQuestion = question.trim();
    if (!currentQuestion || isAsking || !activeSessionId) return;

    setQuestion("");
    setIsAsking(true);

    // Append user message and instant assistant loading state
    const tempId = `asst-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: currentQuestion },
      { id: tempId, role: "assistant", content: "", thoughts: "", sources: [] },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/chat/sessions/${activeSessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: currentQuestion,
          sessionId: activeSessionId,
          think: thinkLevel !== "none",
          think_level: thinkLevel,
          search_depth: searchDepth,
          hyde: hydeEnabled,
        }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error("Connection failed");

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let assistantAnswer = "";
      let assistantThoughts = "";
      let retrievedSources: Source[] = [];

      // Assistant placeholder is already appended instantly at the top of handleSendMessage

      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.replace("event: ", "").trim();
          } else if (line.startsWith("data: ")) {
            const rawData = line.substring(6);
            try {
              const parsed = JSON.parse(rawData);
              if (currentEvent === "sources") {
                retrievedSources = parsed;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === tempId ? { ...msg, sources: retrievedSources } : msg
                  )
                );
              } else if (currentEvent === "thinking") {
                assistantThoughts += parsed;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === tempId ? { ...msg, thoughts: assistantThoughts } : msg
                  )
                );
              } else if (currentEvent === "token") {
                assistantAnswer += parsed;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === tempId ? { ...msg, content: assistantAnswer } : msg
                  )
                );
              } else if (currentEvent === "usage") {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === tempId ? { ...msg, tokenUsage: parsed } : msg
                  )
                );
              }
            } catch (err) {
              // Ignore parsed block errors in stream partitions
            }
          }
        }
      }

      // Update sidebar session title if it was first message
      const activeSession = sessions.find((s) => s.id === activeSessionId);
      if (activeSession && activeSession.title === "New Conversation") {
        const shortenedTitle = currentQuestion.substring(0, 24) + (currentQuestion.length > 24 ? "..." : "");
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSessionId ? { ...s, title: shortenedTitle } : s
          )
        );
        authFetch(`${API_BASE_URL}/api/v1/chat/sessions/${activeSessionId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: shortenedTitle }),
        }).catch((err) => console.error("Failed to persist session title:", err));
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempId
              ? {
                  role: "assistant",
                  content: "Generation stopped.",
                }
              : msg
          )
        );
        return;
      }
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === tempId
            ? {
                role: "assistant",
                content: "Sorry, I encountered a communication error with the local RAG FastAPI engine. Check if port 8001 is open.",
              }
            : msg
        )
      );
    } finally {
      setIsAsking(false);
      abortControllerRef.current = null;
    }
  }

  if (isAuthChecking) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Verifying session...</p>
      </div>
    );
  }

  return (
    <main className="flex h-screen w-screen overflow-hidden bg-background text-foreground font-sans antialiased">
      {/* 1. LEFT SIDEBAR PANEL (ChatGPT Minimal Theme) */}
      <section
        className={`flex h-full flex-col border-r border-custom-border bg-sidebar transition-all duration-300 ${
          sidebarOpen ? "w-80" : "w-0"
        } overflow-hidden`}
      >
        {/* Sidebar Header */}
        <div className="flex items-center gap-3 border-b border-custom-border px-5 py-4 bg-sidebar">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-200 dark:bg-slate-800 text-foreground">
            <Database className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-wide text-foreground uppercase font-sans">
              SmartHub AI
            </h1>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Local Vector RAG Engine</p>
          </div>
        </div>

        {/* Dashboard Navigation Action */}
        <div className="px-4 pt-4 pb-0">
          <button
            onClick={() => router.push("/dashboard")}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-custom-border bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 px-4 py-2.5 text-sm font-semibold text-slate-700 dark:text-slate-300 transition-all shadow-sm cursor-pointer"
          >
            <LayoutDashboard className="h-4 w-4 text-blue-500" />
            Back to Dashboard
          </button>
        </div>

        {/* Start New Session action */}
        <div className="px-4 pt-4 pb-2">
          <button
            onClick={createNewSession}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 dark:bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-700 px-4 py-2.5 text-sm font-medium text-white transition-all shadow-sm cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            New Conversation
          </button>
        </div>

        {/* Tab Selection */}
        <div className="px-4 pb-3 flex gap-2">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex-1 flex items-center justify-center gap-1.5 rounded-xl py-1.5 text-xs font-semibold border transition-all cursor-pointer ${
              activeTab === "chat"
                ? "bg-white dark:bg-slate-800 border-custom-border text-foreground shadow-sm"
                : "bg-transparent border-transparent text-slate-500 hover:bg-slate-200/50 dark:hover:bg-slate-800/40"
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Chats
          </button>
          <button
            onClick={() => setActiveTab("documents")}
            className={`flex-1 flex items-center justify-center gap-1.5 rounded-xl py-1.5 text-xs font-semibold border transition-all cursor-pointer ${
              activeTab === "documents"
                ? "bg-white dark:bg-slate-800 border-custom-border text-foreground shadow-sm"
                : "bg-transparent border-transparent text-slate-500 hover:bg-slate-200/50 dark:hover:bg-slate-800/40"
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            Documents
          </button>
        </div>

        {/* Dynamic Conversational History Sessions List */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
          {sessions.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-center text-xs text-slate-400">
              No sessions active. Create one!
            </div>
          ) : (
            sessions.map((s) => {
              const isActive = s.id === activeSessionId;
              return (
                <div
                  key={s.id}
                  onClick={() => {
                    selectSession(s.id);
                    setActiveTab("chat");
                  }}
                  className={`group flex cursor-pointer items-center justify-between gap-3 rounded-xl px-3 py-2 transition-all duration-150 ${
                    isActive && activeTab === "chat"
                      ? "bg-slate-200/70 dark:bg-slate-800/70 text-foreground font-medium"
                      : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/40 dark:hover:bg-slate-800/40 hover:text-foreground"
                  }`}
                >
                  <div className="flex items-center gap-2.5 overflow-hidden">
                    <MessageSquare className={`h-4 w-4 flex-shrink-0 ${isActive && activeTab === "chat" ? "text-foreground" : "text-slate-400"}`} />
                    <span className="truncate text-sm">{s.title}</span>
                  </div>
                  <button
                    onClick={(e) => deleteSession(s.id, e)}
                    className="opacity-0 group-hover:opacity-100 hover:text-red-600 p-0.5 rounded transition-opacity duration-150"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500 hover:text-red-600" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* 2. MAIN WORKSPACE */}
      <section className="flex h-full flex-1 flex-col overflow-hidden bg-background">
        {/* Top Header workspace */}
        <header className="flex items-center justify-between border-b border-custom-border bg-background px-6 py-3.5">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen((prev) => !prev)}
              className="rounded-lg p-1.5 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200 cursor-pointer"
            >
              <ChevronRight className={`h-5 w-5 transform transition-transform ${sidebarOpen ? "rotate-180" : ""}`} />
            </button>
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                {activeTab === "documents" ? "Knowledge Hub" : (sessions.find((s) => s.id === activeSessionId)?.title || "SmartHub RAG")}
              </h2>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="inline-flex items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400 uppercase font-mono tracking-wider bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                  <Cpu className="h-2.5 w-2.5 text-blue-500" /> qwen3.5:4b
                </span>
                <span className="inline-flex items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400 uppercase font-mono tracking-wider bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                  <BookOpen className="h-2.5 w-2.5 text-green-500" /> nomic-embed
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span className="hidden md:flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-lg font-mono">
              <Terminal className="h-3.5 w-3.5 text-blue-500" />
              FastAPI: port 8001
            </span>
            <button
              onClick={() => router.push("/dashboard")}
              className="flex items-center gap-1.5 rounded-xl border border-custom-border bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 px-2.5 py-1.5 text-xs font-semibold shadow-sm transition-all cursor-pointer"
              title="Back to Dashboard"
            >
              <LayoutDashboard className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Dashboard</span>
            </button>
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center p-2 rounded-xl border border-custom-border bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-800 dark:hover:text-slate-100 shadow-sm transition-all cursor-pointer hover:scale-105"
              title={`Switch to ${theme === "light" ? "Dark" : "Light"} Mode`}
            >
              {theme === "light" ? (
                <Moon className="h-4.5 w-4.5 text-indigo-500 rotate-0 hover:-rotate-12 transition-transform" />
              ) : (
                <Sun className="h-4.5 w-4.5 text-yellow-500 rotate-0 hover:rotate-45 transition-transform" />
              )}
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-xl border border-custom-border bg-white dark:bg-slate-900 hover:bg-red-50 dark:hover:bg-red-950/30 hover:border-red-200 dark:hover:border-red-900/50 text-slate-500 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400 px-2.5 py-1.5 text-xs font-semibold shadow-sm transition-all cursor-pointer"
              title="Logout"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>

        {activeTab === "chat" ? (
          <>
            {/* Chat Stream message container */}
            <div ref={chatContainerRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
              {messages.length === 0 ? (
                /* Futuristic landing empty state */
                <div className="mx-auto flex h-full max-w-xl flex-col justify-center text-center space-y-6">
                  <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-600 shadow-inner">
                    <Database className="h-8 w-8 animate-pulse" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="text-xl font-semibold text-foreground">Grounded Document Assistant</h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
                      Start a dynamic conversation. Upload your PDFs or text files to instantly segment, generate vector embeddings, and chat in absolute session-isolation.
                    </p>
                  </div>
                  
                  <div className="grid gap-3 grid-cols-2 text-left mt-4">
                    <div className="rounded-xl bg-white dark:bg-slate-900 border border-custom-border p-4 shadow-sm">
                      <div className="flex items-center gap-2 mb-1.5">
                        <FileText className="h-4 w-4 text-blue-500" />
                        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Session Isolated</span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Uploaded documents are strictly queried within this specific conversation thread.
                      </p>
                    </div>
                    <div className="rounded-xl bg-white dark:bg-slate-900 border border-custom-border p-4 shadow-sm">
                      <div className="flex items-center gap-2 mb-1.5">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Priority Boosting</span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Your uploaded papers are given a similarity boost, retaining global context only as a fallback.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                messages.map((msg, index) => {
                  const isUser = msg.role === "user";
                  const isSystem = msg.role === "system";

                  if (isSystem) {
                    const isLoading = msg.content.includes("Uploading") || msg.content.includes("indexing");
                    const isError = msg.content.includes("❌") || msg.content.includes("failed");
                    return (
                      <div key={index} className="flex justify-center">
                        <div className="inline-flex items-center gap-2 rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800/80 px-4 py-2.5 text-xs text-slate-700 dark:text-slate-300 font-mono shadow-sm max-w-lg">
                          {isLoading ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500 flex-shrink-0" />
                          ) : isError ? (
                            <X className="h-3.5 w-3.5 text-red-500 flex-shrink-0" />
                          ) : (
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                          )}
                          <span>{msg.content}</span>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={index}
                      className={`flex gap-4 ${isUser ? "justify-end" : "justify-start animate-fade-in"}`}
                    >
                      {!isUser && (
                        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600/10 dark:bg-blue-500/20 border border-blue-500/20 dark:border-blue-800/80 text-blue-600 dark:text-blue-400">
                          <Cpu className="h-5 w-5" />
                        </div>
                      )}

                      <div className="space-y-1.5 max-w-[80%]">
                        {/* Collapsible reasoning thought block */}
                        {!isUser && msg.thoughts && (
                          <details open className="group mb-2 max-w-full overflow-hidden border border-slate-200 dark:border-slate-800 rounded-xl bg-slate-100/50 dark:bg-slate-900/40 text-xs text-slate-500 dark:text-slate-400">
                            <summary className="flex items-center justify-between px-3.5 py-2 cursor-pointer list-none select-none hover:bg-slate-200/40 dark:hover:bg-slate-850 transition-colors">
                              <div className="flex items-center gap-2">
                                <Brain className="h-3.5 w-3.5 text-blue-500 animate-pulse" />
                                <span className="font-semibold text-slate-700 dark:text-slate-350">Thought Process</span>
                              </div>
                              <ChevronRight className="h-3.5 w-3.5 transform transition-transform group-open:rotate-90 text-slate-400 dark:text-slate-500" />
                            </summary>
                            <div 
                              id={index === messages.length - 1 ? "active-thought-box" : undefined}
                              className="px-3.5 pb-2.5 pt-1.5 border-t border-slate-200 dark:border-slate-800 font-mono text-[11px] leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto text-slate-600 dark:text-slate-350 scrollbar-thin"
                            >
                              {msg.thoughts}
                            </div>
                          </details>
                        )}

                        <div
                          className={
                            isUser
                              ? "bg-slate-100 dark:bg-slate-800 text-slate-850 dark:text-slate-100 rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm max-w-[85%] ml-auto"
                              : "text-slate-850 dark:text-slate-200 text-sm leading-relaxed pl-1.5"
                          }
                        >
                          {isUser ? (
                            <p className="whitespace-pre-line">{msg.content}</p>
                          ) : msg.content === "" && (!msg.thoughts || msg.thoughts === "") ? (
                            <div className="flex items-center gap-1.5 py-2">
                              {(() => {
                                const isHydePhase = hydeEnabled && (!msg.sources || msg.sources.length === 0);
                                const dotColorClass = isHydePhase 
                                  ? "bg-amber-500 dark:bg-amber-400 shadow-sm shadow-amber-500/20" 
                                  : "bg-blue-500 dark:bg-blue-400";
                                return (
                                  <>
                                    <span className={`h-2 w-2 rounded-full ${dotColorClass} animate-bounce transition-colors duration-1000 ease-in-out`} style={{ animationDelay: "0ms" }} />
                                    <span className={`h-2 w-2 rounded-full ${dotColorClass} animate-bounce transition-colors duration-1000 ease-in-out`} style={{ animationDelay: "150ms" }} />
                                    <span className={`h-2 w-2 rounded-full ${dotColorClass} animate-bounce transition-colors duration-1000 ease-in-out`} style={{ animationDelay: "300ms" }} />
                                  </>
                                );
                              })()}
                            </div>
                          ) : (
                            renderMarkdown(msg.content)
                          )}
                        </div>

                        {/* Citations references */}
                        {!isUser && msg.sources && msg.sources.length > 0 && (
                          <button
                            onClick={() => setActiveDrawerSources(msg.sources || null)}
                            className="inline-flex items-center gap-1.5 text-xs text-green-600 hover:text-green-700 bg-green-500/10 dark:bg-green-500/5 border border-green-500/20 dark:border-green-800/30 px-2.5 py-1 rounded-full cursor-pointer hover:bg-green-500/20 transition-all"
                          >
                            <Info className="h-3 w-3" />
                            Grounded in {msg.sources.length} document sources · Click to inspect
                          </button>
                        )}

                        {/* Token Usage references */}
                        {!isUser && (msg.tokenUsage || msg.token_usage) && (
                          <div className="flex flex-wrap items-center gap-1.5 mt-1.5 pl-1.5 text-[10px] text-slate-400 dark:text-slate-500 font-mono select-none">
                            {(() => {
                              const usage = msg.tokenUsage || msg.token_usage;
                              if (!usage) return null;
                              return (
                                <>
                                  <span className="flex items-center gap-1">
                                    <Cpu className="h-2.5 w-2.5 text-slate-400 dark:text-slate-500" />
                                    Context: {usage.prompt_tokens?.toLocaleString() || "0"} / 8,192 tokens ({Math.min(100, Math.round((usage.prompt_tokens / 8192) * 100))}% used)
                                  </span>
                                  <span>·</span>
                                  <span>Response: {usage.eval_tokens?.toLocaleString() || "0"} tokens</span>
                                </>
                              );
                            })()}
                          </div>
                        )}
                      </div>

                      {isUser && (
                        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-350">
                          <MessageSquare className="h-4 w-4" />
                        </div>
                      )}
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar Section */}
            <footer className="bg-background p-4 border-t border-custom-border/50">
              <form onSubmit={handleSendMessage} className="mx-auto max-w-4xl relative">
                <div className="relative flex flex-col bg-white dark:bg-[#151515] border border-custom-border rounded-2xl p-3 shadow-md focus-within:border-slate-350 dark:focus-within:border-slate-750 focus-within:shadow-lg transition-all duration-200">
                  
                  {/* Top Row: Full-width spacious Text Area for multiline / long queries */}
                  <div className="w-full">
                    <textarea
                      value={question}
                      disabled={isAsking}
                      onChange={(e) => setQuestion(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          const form = e.currentTarget.form;
                          if (form) {
                            form.requestSubmit();
                          }
                        }
                      }}
                      rows={2}
                      placeholder="Ask a question grounded in your session's index..."
                      className="w-full bg-transparent px-2 py-1.5 text-sm text-foreground outline-none placeholder-slate-400 dark:placeholder-slate-500 disabled:opacity-50 font-sans resize-none min-h-[50px] max-h-[160px] scrollbar-thin"
                    />
                  </div>

                  {/* Divider */}
                  <div className="border-t border-slate-100 dark:border-slate-800/40 my-2" />

                  {/* Bottom Row: Flex row for controls and trigger action */}
                  <div className="flex items-center justify-between gap-3">
                    
                    {/* Left Controls Group */}
                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Paperclip attachment triggers hidden upload input */}
                      <button
                        type="button"
                        disabled={isUploading}
                        onClick={() => fileInputRef.current?.click()}
                        className="p-1.5 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 cursor-pointer transition-colors"
                        title="Upload Document"
                      >
                        {isUploading ? (
                          <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                        ) : (
                          <Paperclip className="h-4 w-4 hover:rotate-12 transition-transform" />
                        )}
                      </button>

                      {/* Glowing Brain Reasoning Level Selector */}
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => setDropdownOpen((prev) => !prev)}
                          className="flex items-center gap-1.5 border border-custom-border bg-white dark:bg-slate-900 rounded-xl px-2.5 py-1 shadow-sm hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all cursor-pointer select-none"
                        >
                          <div
                            title={`AI Reasoning Level: ${thinkLevel.toUpperCase()}`}
                            className={`p-0.5 rounded-lg flex items-center justify-center ${
                              thinkLevel !== "none" ? "text-blue-500" : "text-slate-400"
                            }`}
                          >
                            <Brain className={`h-4 w-4 ${thinkLevel !== "none" && thinkLevel !== "low" ? "animate-pulse" : ""}`} />
                          </div>
                          <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-350 font-sans flex items-center gap-1">
                            {thinkLevel === "none" && "⚡ Fast"}
                            {thinkLevel === "low" && "🧠 Low"}
                            {thinkLevel === "medium" && "🧠🧠 Medium"}
                            {thinkLevel === "max" && "🧠🧠🧠 Max"}
                            <ChevronDown className={`h-3 w-3 text-slate-400 transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`} />
                          </span>
                        </button>

                        {/* Premium Custom Dropdown Menu */}
                        {dropdownOpen && (
                          <>
                            <div
                              className="fixed inset-0 z-40 cursor-default"
                              onClick={() => setDropdownOpen(false)}
                            />
                            <div className="absolute bottom-full mb-2 left-0 z-50 min-w-[200px] overflow-hidden rounded-2xl border border-custom-border bg-white dark:bg-slate-900 p-1.5 shadow-2xl transition-all duration-150 ease-out">
                              <div className="px-2.5 py-1.5 text-[9px] font-bold tracking-wider text-slate-400 uppercase font-mono border-b border-custom-border mb-1">
                                AI Reasoning Depth
                              </div>
                              {[
                                { value: "none", label: "⚡ Fast", desc: "Instant response, no thinking" },
                                { value: "low", label: "🧠 Low", desc: "1-sentence quiet reasoning" },
                                { value: "medium", label: "🧠🧠 Medium", desc: "Short, structured logic" },
                                { value: "max", label: "🧠🧠🧠 Max", desc: "Exhaustive deep thinking" },
                              ].map((opt) => (
                                <button
                                  key={opt.value}
                                  type="button"
                                  onClick={() => {
                                    setThinkLevel(opt.value as any);
                                    setDropdownOpen(false);
                                  }}
                                  className={`w-full text-left flex flex-col gap-0.5 rounded-xl px-2.5 py-1.5 text-xs transition-all cursor-pointer ${
                                    thinkLevel === opt.value
                                      ? "bg-slate-100 dark:bg-slate-800 text-foreground font-semibold"
                                      : "text-slate-650 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
                                  }`}
                                >
                                  <span>{opt.label}</span>
                                  <span className="text-[10px] text-slate-400 font-normal">
                                    {opt.desc}
                                  </span>
                                </button>
                              ))}
                            </div>
                          </>
                        )}
                      </div>

                      {/* Premium RAG Search Depth Selector */}
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => setSearchDepthOpen((prev) => !prev)}
                          className="flex items-center gap-1.5 border border-custom-border bg-white dark:bg-slate-900 rounded-xl px-2.5 py-1 shadow-sm hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all cursor-pointer select-none"
                        >
                          <div
                            title={`Search Depth: ${searchDepth.toUpperCase()}`}
                            className={`p-0.5 rounded-lg flex items-center justify-center ${
                              searchDepth === "deep" ? "text-green-500 animate-pulse" : searchDepth === "fast" ? "text-amber-500" : "text-blue-500"
                            }`}
                          >
                            <Database className="h-4 w-4" />
                          </div>
                          <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-350 font-sans flex items-center gap-1">
                            {searchDepth === "fast" && "⚡ Fast (4)"}
                            {searchDepth === "balanced" && "🔍 Balanced (8)"}
                            {searchDepth === "deep" && "🧠 Deep (12)"}
                            <ChevronDown className={`h-3 w-3 text-slate-400 transition-transform duration-200 ${searchDepthOpen ? "rotate-180" : ""}`} />
                          </span>
                        </button>

                        {searchDepthOpen && (
                          <>
                            <div
                              className="fixed inset-0 z-40 cursor-default"
                              onClick={() => setSearchDepthOpen(false)}
                            />
                            <div className="absolute bottom-full mb-2 left-0 z-50 min-w-[220px] overflow-hidden rounded-2xl border border-custom-border bg-white dark:bg-slate-900 p-1.5 shadow-2xl transition-all duration-150 ease-out">
                              <div className="px-2.5 py-1.5 text-[9px] font-bold tracking-wider text-slate-400 uppercase font-mono border-b border-custom-border mb-1">
                                RAG Search Context
                              </div>
                              {[
                                { value: "fast", label: "⚡ Fast Context", desc: "Retrieve top 4 chunks (Maximum speed)" },
                                { value: "balanced", label: "🔍 Balanced Context", desc: "Retrieve top 8 chunks (Ideal precision)" },
                                { value: "deep", label: "🧠 Deep Research", desc: "Retrieve top 12 chunks (Maximum context depth)" },
                              ].map((opt) => (
                                <button
                                  key={opt.value}
                                  type="button"
                                  onClick={() => {
                                    setSearchDepth(opt.value as any);
                                    setSearchDepthOpen(false);
                                  }}
                                  className={`w-full text-left flex flex-col gap-0.5 rounded-xl px-2.5 py-1.5 text-xs transition-all cursor-pointer ${
                                    searchDepth === opt.value
                                      ? "bg-slate-100 dark:bg-slate-800 text-foreground font-semibold"
                                      : "text-slate-650 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
                                  }`}
                                >
                                  <span>{opt.label}</span>
                                  <span className="text-[10px] text-slate-400 font-normal">
                                    {opt.desc}
                                  </span>
                                </button>
                              ))}
                            </div>
                          </>
                        )}
                      </div>

                      {/* Premium HyDE Toggle Button */}
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => setHydeEnabled((prev) => !prev)}
                          className={`flex items-center gap-1.5 border rounded-xl px-2.5 py-1 shadow-sm transition-all cursor-pointer select-none ${
                            hydeEnabled
                              ? "border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 hover:bg-amber-100/70 dark:hover:bg-amber-900/40"
                              : "border-custom-border bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                          }`}
                          title="HyDE Expansion: Generates hypothetical document paragraphs to improve search relevancy for short queries"
                        >
                          <Brain className={`h-4 w-4 ${hydeEnabled ? "text-amber-500 animate-pulse" : "text-slate-400"}`} />
                          <span className="text-[11px] font-semibold font-sans">
                            {hydeEnabled ? "⚡ HyDE ON" : "⚡ HyDE OFF"}
                          </span>
                        </button>
                      </div>
                    </div>

                    {/* Right Trigger Send Group */}
                    <div className="flex-shrink-0">
                      {isAsking ? (
                        <button
                          type="button"
                          onClick={stopGeneration}
                          className="bg-red-600 hover:bg-red-700 dark:bg-red-600 dark:hover:bg-red-700 text-white p-2 rounded-xl transition-all shadow-sm cursor-pointer hover:scale-105"
                          title="Stop generating"
                        >
                          <Square className="h-4 w-4 fill-white text-white" />
                        </button>
                      ) : (
                        <button
                          type="submit"
                          disabled={!question.trim()}
                          className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700 text-white p-2 rounded-xl transition-all disabled:bg-slate-100 dark:disabled:bg-slate-800 disabled:text-slate-400 disabled:cursor-not-allowed shadow-sm cursor-pointer"
                        >
                          <Send className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/pdf,.pdf,.txt"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </div>
              </form>
            </footer>
          </>
        ) : (
          /* Documents Management Dashboard Tab View */
          <div className="flex-1 overflow-y-auto p-8 max-w-5xl mx-auto w-full">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-xl font-bold text-foreground">Knowledge Hub</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                  Manage vector documents stored in your local indexing database.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => globalFileInputRef.current?.click()}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-blue-700 shadow-sm transition-all cursor-pointer"
                >
                  Upload Global Document
                </button>
                <button
                  onClick={fetchUploadedDocs}
                  className="inline-flex items-center gap-2 rounded-lg border border-custom-border bg-white dark:bg-slate-900 px-3.5 py-2 text-xs font-semibold text-foreground hover:bg-slate-50 dark:hover:bg-slate-800 shadow-sm transition-all cursor-pointer"
                >
                  Refresh Index
                </button>
                <input
                  ref={globalFileInputRef}
                  type="file"
                  accept="application/pdf,.pdf,.txt"
                  onChange={handleGlobalFileUpload}
                  className="hidden"
                />
              </div>
            </div>

            {isLoadingDocs ? (
              <div className="flex h-64 flex-col items-center justify-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                <span className="text-sm font-medium text-slate-500 dark:text-slate-400 font-mono">Scanning vector collections...</span>
              </div>
            ) : uploadedDocs.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-custom-border bg-white dark:bg-slate-900 p-8 text-center">
                <BookOpen className="h-10 w-10 text-slate-350 dark:text-slate-500 mb-3 animate-pulse" />
                <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300">No documents indexed</h4>
                <p className="text-xs text-slate-450 dark:text-slate-450 max-w-sm mt-1">
                  Upload PDF, DOCX, or text files directly inside chat sessions to populate your knowledge library.
                </p>
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-900 border border-custom-border rounded-2xl overflow-hidden shadow-sm">
                <table className="w-full border-collapse text-left text-sm text-slate-600 dark:text-slate-400">
                  <thead className="bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-350 uppercase font-mono text-[10px] tracking-wider border-b border-custom-border">
                    <tr>
                      <th className="px-6 py-4 font-semibold">Document Name</th>
                      <th className="px-6 py-4 font-semibold">Scope / Session</th>
                      <th className="px-6 py-4 font-semibold">Vectors</th>
                      <th className="px-6 py-4 font-semibold">Indexed At</th>
                      <th className="px-6 py-4 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-custom-border">
                    {uploadedDocs.map((doc, idx) => {
                      const isGlobal = !doc.session_id;
                      return (
                        <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors">
                          <td className="px-6 py-4.5 font-medium text-foreground max-w-xs truncate" title={doc.filename}>
                            {doc.filename}
                          </td>
                          <td className="px-6 py-4.5">
                            {isGlobal ? (
                              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-full border border-emerald-100 dark:border-emerald-900/50">
                                🌐 Global
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 px-2 py-0.5 rounded-full border border-blue-100 dark:border-blue-900/50 max-w-[140px] truncate" title={doc.session_id || ""}>
                                🔒 Session-Bound
                              </span>
                            )}
                          </td>
                          <td className="px-6 py-4.5 font-mono text-xs">
                            {doc.chunk_count} chunks
                          </td>
                          <td className="px-6 py-4.5 text-xs text-slate-400 font-mono">
                            {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleString() : "N/A"}
                          </td>
                          <td className="px-6 py-4.5 text-right">
                            <button
                              onClick={() => handleDeleteDoc(doc.filename, doc.session_id)}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-all cursor-pointer"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>

      {/* 3. SLIDING DRAWER: Inspect Matched Vector Citations */}
      {activeDrawerSources && (
        <section className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="h-full w-full max-w-xl bg-white dark:bg-[#171717] border-l border-custom-border shadow-2xl flex flex-col animate-slide-in">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-custom-border">
              <div className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-green-600" />
                <h3 className="font-semibold text-foreground">Retrieved Citations</h3>
              </div>
              <button
                onClick={() => setActiveDrawerSources(null)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-250 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* List of matched vector chunks */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {activeDrawerSources[0]?.metadata?.hyde_query && (
                <div className="rounded-xl border border-amber-200/80 dark:border-amber-900/60 bg-amber-500/5 p-4 text-xs transition-all shadow-sm">
                  <div className="flex items-center gap-2 mb-1.5 text-amber-700 dark:text-amber-400 font-bold uppercase tracking-wider font-mono text-[9px]">
                    <Brain className="h-4 w-4 text-amber-500 animate-pulse flex-shrink-0" />
                    HyDE Expanded Concept
                  </div>
                  <p className="text-slate-650 dark:text-slate-350 leading-relaxed font-mono italic select-text whitespace-pre-wrap">
                    {activeDrawerSources[0].metadata.hyde_query}
                  </p>
                </div>
              )}
              {activeDrawerSources.map((source, idx) => (
                <div
                  key={source.id}
                  className="rounded-xl border border-custom-border bg-slate-50/50 dark:bg-slate-900/30 p-4 hover:border-green-500/30 transition-all duration-200"
                >
                  {/* Metadata */}
                  <div className="flex items-center justify-between mb-2">
                    <span className="inline-flex items-center gap-1.5 text-xs text-green-600 bg-green-500/10 px-2 py-0.5 rounded font-mono">
                      Chunk {idx + 1} · Match {(source.similarity * 100).toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-slate-500 dark:text-slate-400 font-mono">
                      File: {source.metadata?.source || "Pasted text"}{" "}
                      {source.metadata?.page ? `· Page ${source.metadata.page}` : ""}
                    </span>
                  </div>

                  {/* Extract Text */}
                  <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed bg-white dark:bg-[#212121] p-3 rounded-lg border border-custom-border font-mono select-text whitespace-pre-wrap max-h-56 overflow-y-auto">
                    {source.content}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
