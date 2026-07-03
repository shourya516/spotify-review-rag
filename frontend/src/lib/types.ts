// ── Scrape ───────────────────────────────────────────────────────────

export type ReviewSource = "play_store" | "app_store" | "reddit";

export interface ScrapeRequest {
  source?: ReviewSource | null;
  count?: number;
}

export interface ScrapeJob {
  id: string;
  source: ReviewSource | null;
  status: "pending" | "running" | "completed" | "failed";
  reviews_found: number;
  reviews_added: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// ── Reviews ──────────────────────────────────────────────────────────

export interface Review {
  id: string;
  source: ReviewSource;
  author: string | null;
  rating: number | null;
  cleaned_content: string;
  review_date: string | null;
  scraped_at: string;
}

export interface ReviewListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Review[];
}

export interface ReviewStats {
  total: number;
  by_source: Record<string, number>;
  missing_embeddings: number;
}

// ── Query / RAG ──────────────────────────────────────────────────────

export interface QueryRequest {
  question: string;
  top_k?: number;
  min_similarity?: number;
}

export interface Citation {
  review_id: string;
  source: ReviewSource;
  author: string | null;
  rating: number | null;
  snippet: string;
  similarity: number;
}

export interface QueryResponse {
  question: string;
  answer: string;
  citations: Citation[];
  latency_ms: number | null;
}
