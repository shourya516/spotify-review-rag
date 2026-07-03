/**
 * Thin fetch wrapper for the FastAPI backend.
 * All requests go through /api/* which Next.js proxies to localhost:8000.
 */

import type {
  Citation,
  QueryRequest,
  QueryResponse,
  ReviewListResponse,
  ReviewStats,
  ScrapeJob,
  ScrapeRequest,
} from "./types";

const BASE = "/api";

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ── Scrape ───────────────────────────────────────────────────────────

export async function triggerScrape(body: ScrapeRequest): Promise<ScrapeJob> {
  return request("/scrape", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getScrapeJob(jobId: string): Promise<ScrapeJob> {
  return request(`/scrape/${jobId}`);
}

export async function listScrapeJobs(limit = 10): Promise<ScrapeJob[]> {
  return request(`/scrape?limit=${limit}`);
}

// ── Reviews ──────────────────────────────────────────────────────────

export async function getReviewStats(): Promise<ReviewStats> {
  return request("/reviews/stats");
}

export async function listReviews(params?: {
  source?: string;
  rating?: number;
  page?: number;
  page_size?: number;
}): Promise<ReviewListResponse> {
  const qs = new URLSearchParams();
  if (params?.source) qs.set("source", params.source);
  if (params?.rating != null) qs.set("rating", String(params.rating));
  if (params?.page != null) qs.set("page", String(params.page));
  if (params?.page_size != null) qs.set("page_size", String(params.page_size));
  const query = qs.toString() ? `?${qs}` : "";
  return request(`/reviews${query}`);
}

// ── Query ────────────────────────────────────────────────────────────

export async function queryReviews(body: QueryRequest): Promise<QueryResponse> {
  return request("/query", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
