"use client";

/**
 * ScrapePanel — lets the user trigger a scraping job for one or all
 * sources and shows live job status until the job completes.
 */

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { PlayCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getScrapeJob, listScrapeJobs, triggerScrape } from "@/lib/api";
import type { ReviewSource, ScrapeJob } from "@/lib/types";

const SOURCE_OPTIONS: { value: ReviewSource | "all"; label: string }[] = [
  { value: "all",        label: "All Sources" },
  { value: "play_store", label: "Google Play" },
  { value: "app_store",  label: "App Store"   },
  { value: "reddit",     label: "Reddit"       },
];

const STATUS_BADGE: Record<ScrapeJob["status"], { label: string; variant: "green" | "yellow" | "red" | "gray" | "blue" }> = {
  pending:   { label: "Pending",   variant: "gray"   },
  running:   { label: "Running",   variant: "yellow" },
  completed: { label: "Completed", variant: "green"  },
  failed:    { label: "Failed",    variant: "red"    },
};

function useActiveJob(jobId: string | null) {
  const { data } = useSWR(
    jobId ? `job-${jobId}` : null,
    () => getScrapeJob(jobId!),
    {
      refreshInterval: (data) =>
        data?.status === "running" || data?.status === "pending" ? 2000 : 0,
    }
  );
  return data ?? null;
}

export function ScrapePanel() {
  const [source, setSource] = useState<ReviewSource | "all">("all");
  const [count, setCount] = useState(1000);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeJob = useActiveJob(activeJobId);

  const { data: recentJobs, mutate: refreshJobs } = useSWR(
    "recent-jobs",
    () => listScrapeJobs(6),
    { refreshInterval: 10_000 }
  );

  async function handleScrape() {
    setError(null);
    setLoading(true);
    try {
      const job = await triggerScrape({
        source: source === "all" ? null : source,
        count,
      });
      setActiveJobId(job.id);
      await refreshJobs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start scrape job");
    } finally {
      setLoading(false);
    }
  }

  const isRunning =
    activeJob?.status === "running" || activeJob?.status === "pending";

  return (
    <div className="space-y-6">
      {/* ── Trigger form ── */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-4">Scrape Reviews</h2>

        <div className="flex flex-wrap gap-3 mb-4">
          {SOURCE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setSource(opt.value)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                source === opt.value
                  ? "bg-spotify-green text-black"
                  : "bg-white/10 text-white hover:bg-white/20"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-4 mb-5">
          <label className="text-sm text-spotify-muted" htmlFor="count-input">
            Reviews per source
          </label>
          <input
            id="count-input"
            type="number"
            min={10}
            max={2000}
            step={100}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="w-24 rounded-lg bg-white/5 border border-white/10 px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-spotify-green"
          />
        </div>

        {error && (
          <p className="mb-3 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2 text-sm text-red-400">
            {error}
          </p>
        )}

        <Button
          onClick={handleScrape}
          loading={loading || isRunning}
          disabled={isRunning}
          size="md"
        >
          <PlayCircle className="h-4 w-4" />
          {isRunning ? "Scraping…" : "Start Scrape"}
        </Button>
      </Card>

      {/* ── Active job progress ── */}
      {activeJob && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white">Active Job</h3>
            <Badge
              label={STATUS_BADGE[activeJob.status].label}
              variant={STATUS_BADGE[activeJob.status].variant}
            />
          </div>

          {(activeJob.status === "running" || activeJob.status === "pending") && (
            <div className="flex items-center gap-3 mb-3">
              <Spinner size="sm" />
              <span className="text-sm text-spotify-muted">
                Fetching reviews from{" "}
                {activeJob.source ?? "all sources"}…
              </span>
            </div>
          )}

          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Stat label="Source" value={activeJob.source ?? "All"} />
            <Stat label="Status" value={activeJob.status} />
            <Stat label="Found" value={activeJob.reviews_found} />
            <Stat label="Added" value={activeJob.reviews_added} />
          </dl>

          {activeJob.error_message && (
            <p className="mt-3 rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
              {activeJob.error_message}
            </p>
          )}
        </Card>
      )}

      {/* ── Recent jobs ── */}
      {recentJobs && recentJobs.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-spotify-muted uppercase tracking-wider">
              Recent Jobs
            </h3>
            <button
              onClick={() => refreshJobs()}
              className="text-spotify-muted hover:text-white transition-colors"
              aria-label="Refresh jobs"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
          <div className="space-y-2">
            {recentJobs.map((job) => (
              <Card key={job.id} padding={false}>
                <div className="flex items-center justify-between px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Badge
                      label={STATUS_BADGE[job.status].label}
                      variant={STATUS_BADGE[job.status].variant}
                    />
                    <span className="text-sm text-white">
                      {job.source ?? "All sources"}
                    </span>
                  </div>
                  <span className="text-xs text-spotify-muted">
                    +{job.reviews_added} reviews
                  </span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs text-spotify-muted">{label}</dt>
      <dd className="mt-0.5 font-medium text-white capitalize">{value}</dd>
    </div>
  );
}
