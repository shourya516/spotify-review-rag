"use client";

/**
 * StatsPanel — shows per-source review counts and embedding coverage.
 * Auto-refreshes every 15 seconds.
 */

import useSWR from "swr";
import { Database, Layers, AlertCircle } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getReviewStats } from "@/lib/api";

const SOURCE_LABELS: Record<string, string> = {
  play_store: "Google Play",
  app_store:  "App Store",
  reddit:     "Reddit",
};

export function StatsPanel() {
  const { data, error, isLoading } = useSWR("review-stats", getReviewStats, {
    refreshInterval: 15_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="flex items-center gap-3 text-red-400">
        <AlertCircle className="h-5 w-5 shrink-0" />
        <p className="text-sm">Failed to load stats. Is the backend running?</p>
      </Card>
    );
  }

  if (!data) return null;

  const embeddingCoverage =
    data.total > 0
      ? Math.round(((data.total - data.missing_embeddings) / data.total) * 100)
      : 0;

  return (
    <div className="space-y-4">
      {/* ── Top-level stats ── */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard
          icon={<Database className="h-5 w-5 text-spotify-green" />}
          label="Total Reviews"
          value={data.total.toLocaleString()}
        />
        <StatCard
          icon={<Layers className="h-5 w-5 text-blue-400" />}
          label="Embedded"
          value={`${embeddingCoverage}%`}
          sub={`${data.missing_embeddings} pending`}
        />
      </div>

      {/* ── Per-source breakdown ── */}
      <Card>
        <h3 className="text-sm font-semibold text-spotify-muted uppercase tracking-wider mb-4">
          By Source
        </h3>
        <div className="space-y-3">
          {Object.entries(SOURCE_LABELS).map(([key, label]) => {
            const count = data.by_source[key] ?? 0;
            const pct = data.total > 0 ? (count / data.total) * 100 : 0;
            return (
              <div key={key}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-white">{label}</span>
                  <span className="text-spotify-muted">{count.toLocaleString()}</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-spotify-green transition-all duration-500"
                    style={{ width: `${pct}%` }}
                    role="progressbar"
                    aria-valuenow={Math.round(pct)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* ── Embedding progress bar ── */}
      {data.missing_embeddings > 0 && (
        <Card className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-400" />
          <p className="text-sm text-spotify-muted">
            <span className="text-yellow-400 font-medium">
              {data.missing_embeddings.toLocaleString()} reviews
            </span>{" "}
            still need embeddings. Trigger a scrape to generate them.
          </p>
        </Card>
      )}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <Card>
      <div className="flex items-center gap-3 mb-2">{icon}</div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-spotify-muted mt-1">{label}</p>
      {sub && <p className="text-xs text-yellow-400 mt-0.5">{sub}</p>}
    </Card>
  );
}
