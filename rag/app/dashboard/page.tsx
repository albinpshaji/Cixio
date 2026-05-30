"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Database,
  Loader2,
  MessageSquare,
  BookOpen,
  Clock,
  ArrowRight,
  LogOut,
  Sun,
  Moon,
  Cpu,
  Sparkles,
  FileText,
} from "lucide-react";
import { getAccessToken, getCurrentUser, logoutUser, authFetch, type User } from "@/app/lib/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

type Session = {
  id: string;
  title: string;
  created_at: string;
};

type DocItem = {
  filename: string;
  chunk_count: number;
  uploaded_at: string | null;
  session_id: string | null;
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [documents, setDocuments] = useState<DocItem[]>([]);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // Theme
  useEffect(() => {
    const saved = localStorage.getItem("theme") as "light" | "dark" | null;
    if (saved) {
      setTheme(saved);
      document.documentElement.classList.toggle("dark", saved === "dark");
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const initial = prefersDark ? "dark" : "light";
      setTheme(initial);
      document.documentElement.classList.toggle("dark", initial === "dark");
    }
  }, []);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  // Auth check
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAccessToken();
      if (!token) {
        router.replace("/login");
        return;
      }
      const userData = await getCurrentUser();
      if (!userData) {
        router.replace("/login");
        return;
      }
      setUser(userData);
      setIsLoading(false);

      // Fetch stats
      try {
        const [sessRes, docsRes] = await Promise.all([
          authFetch(`${API_BASE_URL}/api/v1/chat/sessions`),
          authFetch(`${API_BASE_URL}/api/v1/documents`),
        ]);
        if (sessRes.ok) setSessions(await sessRes.json());
        if (docsRes.ok) setDocuments(await docsRes.json());
      } catch (err) {
        console.error("Failed to fetch dashboard data:", err);
      }
    };
    checkAuth();
  }, [router]);

  const handleLogout = async () => {
    await logoutUser();
    router.push("/login");
  };

  function getGreeting(): string {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  }

  function getAccountAge(): string {
    if (!user) return "";
    const created = new Date(user.created_at);
    const now = new Date();
    const diffMs = now.getTime() - created.getTime();
    const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (days === 0) return "Today";
    if (days === 1) return "1 day";
    return `${days} days`;
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Loading your workspace...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30 dark:from-[#0a0a0a] dark:via-[#111111] dark:to-[#0f172a]/50 transition-colors">
      {/* Top Navigation Bar */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-white/70 dark:bg-[#0a0a0a]/70 border-b border-slate-200/80 dark:border-slate-800/60">
        <div className="max-w-6xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-md shadow-blue-500/20">
              <Database className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-900 dark:text-white tracking-wide uppercase">
                SmartHub AI
              </h1>
              <p className="text-[10px] text-slate-500 dark:text-slate-500 font-mono">
                Local Vector RAG Engine
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center p-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 shadow-sm transition-all cursor-pointer"
              title={`Switch to ${theme === "light" ? "Dark" : "Light"} Mode`}
            >
              {theme === "light" ? <Moon className="h-4 w-4 text-indigo-500" /> : <Sun className="h-4 w-4 text-yellow-500" />}
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-red-50 dark:hover:bg-red-950/30 hover:border-red-200 dark:hover:border-red-900/50 text-slate-600 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400 px-3.5 py-2 text-xs font-semibold shadow-sm transition-all cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5" />
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-10">
        {/* Welcome Section */}
        <div className="mb-10">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="h-5 w-5 text-amber-500" />
            <span className="text-sm text-slate-500 dark:text-slate-400 font-medium">{getGreeting()}</span>
          </div>
          <h2 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
            {user?.full_name}
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Welcome to your AI-powered personal workspace. Upload documents, chat with your data, and explore.
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-10">
          <div className="relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-blue-500/10 to-transparent rounded-bl-full" />
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 dark:bg-blue-500/15 text-blue-600 dark:text-blue-400">
                <MessageSquare className="h-5 w-5" />
              </div>
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Chat Sessions</span>
            </div>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">{sessions.length}</p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Total conversations</p>
          </div>

          <div className="relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-emerald-500/10 to-transparent rounded-bl-full" />
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                <BookOpen className="h-5 w-5" />
              </div>
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Documents</span>
            </div>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">{documents.length}</p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Indexed in vector store</p>
          </div>

          <div className="relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-purple-500/10 to-transparent rounded-bl-full" />
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 dark:bg-purple-500/15 text-purple-600 dark:text-purple-400">
                <Clock className="h-5 w-5" />
              </div>
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Member Since</span>
            </div>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">{getAccountAge()}</p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{user?.email}</p>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-10">
          <button
            onClick={() => router.push("/chat")}
            className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 p-6 text-left text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-all cursor-pointer"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/5 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Cpu className="h-5 w-5 text-blue-200" />
                  <span className="text-xs font-bold text-blue-200 uppercase tracking-wider">RAG Chat</span>
                </div>
                <h3 className="text-lg font-bold mb-1">Start Chatting</h3>
                <p className="text-sm text-blue-200/80">
                  Ask questions grounded in your uploaded documents with AI-powered vector search.
                </p>
              </div>
              <ArrowRight className="h-6 w-6 text-white/60 group-hover:text-white group-hover:translate-x-1 transition-all flex-shrink-0" />
            </div>
          </button>

          <button
            onClick={() => router.push("/chat?tab=documents")}
            className="group relative overflow-hidden rounded-2xl bg-white dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 p-6 text-left shadow-sm hover:shadow-md transition-all cursor-pointer"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="h-5 w-5 text-emerald-500" />
                  <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Knowledge Hub</span>
                </div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-1">Manage Documents</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Upload PDFs, manage your vector index, and organize your knowledge base.
                </p>
              </div>
              <ArrowRight className="h-6 w-6 text-slate-300 dark:text-slate-600 group-hover:text-slate-500 dark:group-hover:text-slate-400 group-hover:translate-x-1 transition-all flex-shrink-0" />
            </div>
          </button>
        </div>

        {/* Recent Sessions */}
        {sessions.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                Recent Conversations
              </h3>
              <button
                onClick={() => router.push("/chat")}
                className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-semibold cursor-pointer"
              >
                View all →
              </button>
            </div>
            <div className="bg-white dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 rounded-2xl overflow-hidden shadow-sm">
              {sessions.slice(0, 5).map((session, idx) => (
                <button
                  key={session.id}
                  onClick={() => router.push("/chat")}
                  className={`w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer ${
                    idx < Math.min(sessions.length, 5) - 1 ? "border-b border-slate-100 dark:border-slate-800/50" : ""
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <MessageSquare className="h-4 w-4 text-slate-400 dark:text-slate-500 flex-shrink-0" />
                    <span className="text-sm text-slate-700 dark:text-slate-300 truncate max-w-sm">
                      {session.title}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono flex-shrink-0">
                    {new Date(session.created_at).toLocaleDateString()}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
