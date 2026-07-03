import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spotify Review Insights",
  description:
    "Ask natural-language questions about Spotify user feedback, powered by RAG.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-spotify-black text-white antialiased">
        {children}
      </body>
    </html>
  );
}
