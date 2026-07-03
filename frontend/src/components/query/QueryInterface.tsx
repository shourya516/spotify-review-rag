"use client";

/**
 * QueryInterface — the main Q&A panel.
 * Accepts a natural-language question, calls POST /api/query,
 * and renders the answer alongside citation cards.
 */

import { FormEvent, useState } from "react";
import { SendHorizontal, Star, Clock } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { queryReviews } from "@/lib/api";
import type { Citation, QueryResponse } from "@/lib/types";

const EXAMPLE_QUESTIONS = [
  "Why do users struggle to discover new music?",
  "What are the most common complaints about Spotify recommendations?",
  "Which features are requested most frequently?",
  "What issues are commonly reported after recent updates?",
  "How do premium users' concerns differ from free users'?",
];

const SOURCE_LABEL: Record<string, string> = {
  play_store: "Google Play",
  app_store:  "App Store",
  reddit:     "Reddit",
};

const SOURCE_COLOR: Record<string, "green" | "blue" | "yellow"> = {
  play_store: "green",
  app_store:  "blue",
  reddit:     "yellow",
};

export function QueryInterface() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e?: FormEvent) {
    e?.preventDefault();
    if (!question.trim() || loading) return;

    setError(null);
    setLoading(true);
    setResponse(null);

    try {
      const res = await queryReviews({ question: question.trim() });
      setResponse(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  function handleExample(q: string) {
    setQuestion(q);
    setResponse(null);
    setError(null);
  }

  return (
    <div className="space-y-6">
      {/* ── Input form ── */}
      <Card>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="Ask anything about Spotify user feedback…"
              rows={3}
              maxLength={1000}
              className="w-full resize-none rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-sm text-white placeholder-spotify-muted focus:outline-none focus:ring-2 focus:ring-spotify-green"
              aria-label="Question input"
            />
            <span className="absolute bottom-3 right-3 text-xs text-spotify-muted">
              {question.length}/1000
            </span>
          </div>

          {error && (
            <p className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2 text-sm text-red-400">
              {error}
            </p>
          )}

          <div className="flex items-center justify-between">
            <p className="text-xs text-spotify-muted hidden sm:block">
              Press Enter to submit · Shift+Enter for new line
            </p>
            <Button
              type="submit"
              loading={loading}
              disabled={!question.trim()}
              size="md"
            >
              <SendHorizontal className="h-4 w-4" />
              Ask
            </Button>
          </div>
        </form>
      </Card>

      {/* ── Example questions ── */}
      {!response && !loading && (
        <div>
          <p className="text-xs text-spotify-muted uppercase tracking-wider mb-3">
            Try an example
          </p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleExample(q)}
                className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-spotify-muted hover:text-white hover:border-white/30 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Loading state ── */}
      {loading && (
        <Card className="flex items-center gap-4">
          <Spinner size="md" />
          <div>
            <p className="text-sm font-medium text-white">Searching reviews…</p>
            <p className="text-xs text-spotify-muted">
              Embedding query → retrieving top reviews → generating answer
            </p>
          </div>
        </Card>
      )}

      {/* ── Answer ── */}
      {response && (
        <div className="space-y-5">
          <Card>
            <div className="flex items-start justify-between gap-4 mb-3">
              <h3 className="text-sm font-semibold text-spotify-muted uppercase tracking-wider">
                Answer
              </h3>
              {response.latency_ms != null && (
                <span className="flex items-center gap-1 text-xs text-spotify-muted">
                  <Clock className="h-3 w-3" />
                  {response.latency_ms}ms
                </span>
              )}
            </div>
            <p className="text-sm text-white leading-relaxed whitespace-pre-wrap">
              {response.answer}
            </p>
          </Card>

          {/* ── Citations ── */}
          {response.citations.length > 0 && (
            <div>
              <p className="text-xs text-spotify-muted uppercase tracking-wider mb-3">
                Supporting Reviews ({response.citations.length})
              </p>
              <div className="space-y-3">
                {response.citations.map((c, i) => (
                  <CitationCard key={c.review_id} index={i + 1} citation={c} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card padding={false}>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-4 py-3"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-mono text-spotify-muted">[{index}]</span>
          <Badge
            label={SOURCE_LABEL[citation.source] ?? citation.source}
            variant={SOURCE_COLOR[citation.source] ?? "gray"}
          />
          {citation.rating != null && (
            <span className="flex items-center gap-1 text-xs text-yellow-400">
              <Star className="h-3 w-3 fill-yellow-400" />
              {citation.rating}/5
            </span>
          )}
          {citation.author && (
            <span className="text-xs text-spotify-muted">{citation.author}</span>
          )}
          <span className="ml-auto text-xs text-spotify-muted">
            {(citation.similarity * 100).toFixed(0)}% match
          </span>
        </div>

        <p className={`mt-2 text-xs text-spotify-muted ${expanded ? "" : "line-clamp-2"}`}>
          {citation.snippet}
        </p>

        <p className="mt-1 text-xs text-spotify-green">
          {expanded ? "Show less ▲" : "Show more ▼"}
        </p>
      </button>
    </Card>
  );
}
