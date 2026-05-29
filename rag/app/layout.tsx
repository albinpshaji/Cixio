import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local Document RAG Engine",
  description: "A local Retrieval-Augmented Generation engine built with Next.js, Ollama, and pgvector.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
