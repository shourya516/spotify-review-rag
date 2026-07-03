import { QueryInterface } from "@/components/query/QueryInterface";
import { ScrapePanel } from "@/components/scrape/ScrapePanel";
import { StatsPanel } from "@/components/dashboard/StatsPanel";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* ── Header ── */}
      <header className="border-b border-white/5 bg-spotify-dark/80 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
          {/* Spotify-style wordmark */}
          <svg viewBox="0 0 24 24" className="h-7 w-7 fill-spotify-green" aria-hidden="true">
            <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
          </svg>
          <h1 className="text-sm font-semibold tracking-tight text-white">
            Spotify Review Insights
          </h1>
          <span className="ml-auto text-xs text-spotify-muted hidden sm:inline">
            Powered by RAG
          </span>
        </div>
      </header>

      {/* ── Main layout ── */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[340px_1fr]">

          {/* ── Left sidebar: scrape + stats ── */}
          <aside className="space-y-8">
            <section aria-labelledby="ingest-heading">
              <h2
                id="ingest-heading"
                className="mb-4 text-xs font-semibold uppercase tracking-widest text-spotify-muted"
              >
                Data Ingestion
              </h2>
              <ScrapePanel />
            </section>

            <section aria-labelledby="stats-heading">
              <h2
                id="stats-heading"
                className="mb-4 text-xs font-semibold uppercase tracking-widest text-spotify-muted"
              >
                Review Stats
              </h2>
              <StatsPanel />
            </section>
          </aside>

          {/* ── Main: Q&A ── */}
          <section aria-labelledby="qa-heading">
            <h2
              id="qa-heading"
              className="mb-4 text-xs font-semibold uppercase tracking-widest text-spotify-muted"
            >
              Ask a Question
            </h2>
            <QueryInterface />
          </section>

        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-white/5 py-4 text-center text-xs text-spotify-muted">
        Spotify Review Insights · for internal product research only
      </footer>
    </div>
  );
}
