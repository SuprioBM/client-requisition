import type { ApiEnvelope } from "./types";

/**
 * All JSON requests go through the same-origin Next proxy (`/api/backend/*`),
 * which injects the backend base URL + API key server-side. See
 * `src/app/api/backend/[...path]/route.ts`.
 */
export const API_BASE = "/api/backend";

/**
 * Base for the SSE job stream only. On a platform where serverless functions
 * time out mid-stream (e.g. Vercel), set `NEXT_PUBLIC_SSE_BASE` to the backend's
 * public origin so the browser's EventSource connects to it directly. The stream
 * endpoint is an unauthenticated GET, so this exposes no secret — but the
 * backend must then allow the dashboard origin via `CORS_ORIGINS`. Unset (the
 * default) → the stream also goes through the proxy.
 */
export const SSE_BASE =
  process.env.NEXT_PUBLIC_SSE_BASE?.replace(/\/$/, "") || API_BASE;

export class ApiError extends Error {
  code: string;
  status: number;
  context?: Record<string, unknown>;

  constructor(code: string, message: string, status: number, context?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.context = context;
  }
}

type ReqOpts = {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined | null>;
};

function buildQuery(query?: ReqOpts["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

export async function apiFetch<T>(path: string, opts: ReqOpts = {}): Promise<T> {
  const url = `${API_BASE}${path}${buildQuery(opts.query)}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: opts.method ?? "GET",
      headers: { "Content-Type": "application/json" },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
      cache: "no-store",
    });
  } catch (err) {
    throw new ApiError("NETWORK_ERROR", `Request failed: ${(err as Error).message}`, 0);
  }

  let payload: ApiEnvelope<T> | null = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text) as ApiEnvelope<T>;
    } catch {
      throw new ApiError(
        "MALFORMED_RESPONSE",
        `Backend returned a non-JSON response (HTTP ${res.status}).`,
        res.status,
      );
    }
  }

  if (!res.ok || (payload && payload.success === false)) {
    const e = payload?.error;
    throw new ApiError(
      e?.code ?? `HTTP_${res.status}`,
      e?.message ?? `Request failed with HTTP ${res.status}`,
      res.status,
      e?.context,
    );
  }

  // Some endpoints (readiness) return { success:false } with data — but those
  // are handled above. Normal case: unwrap `data`.
  if (payload && "data" in payload) return payload.data as T;
  return undefined as T;
}
