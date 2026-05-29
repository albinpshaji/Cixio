"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Database } from "lucide-react";
import { getAccessToken, getCurrentUser } from "@/app/lib/auth";

export default function RootPage() {
  const router = useRouter();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      const token = getAccessToken();
      if (!token) {
        router.replace("/login");
        return;
      }

      const user = await getCurrentUser();
      if (user) {
        router.replace("/dashboard");
      } else {
        router.replace("/login");
      }
    };

    checkAuth();
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/40 dark:from-[#0a0a0a] dark:via-[#111827] dark:to-[#0f172a] gap-5">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg shadow-blue-500/30">
        <Database className="h-8 w-8" />
      </div>
      <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
      <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Loading SmartHub AI...</p>
    </div>
  );
}
