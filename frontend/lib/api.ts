// Fetch wrapper: session cookies, CSRF header, RFC 7807 errors unwrapped into ApiError.
// Requests are always same-origin; next.config.ts proxies /api/* to Django so the
// session and csrftoken cookies are set on the frontend origin.

export interface Problem {
  type?: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  errors?: Record<string, unknown>;
  [key: string]: unknown;
}

export class ApiError extends Error {
  constructor(public readonly problem: Problem) {
    super(problem.detail ?? problem.title);
    this.name = "ApiError";
  }

  get status(): number {
    return this.problem.status;
  }

  get isUnauthenticated(): boolean {
    return this.problem.status === 401 || this.problem.status === 403;
  }
}

const CSRF_COOKIE = "csrftoken";
const CSRF_HEADER = "X-CSRFToken";
const CSRF_SEED_PATH = "/api/auth/me"; // wrapped in ensure_csrf_cookie server-side

export function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie.match(new RegExp(`(?:^|;\\s*)${CSRF_COOKIE}=([^;]+)`))?.[1];
}

/** Guarantees a csrftoken cookie exists before the first mutating request (e.g. login). */
export async function ensureCsrfCookie(): Promise<void> {
  if (csrfToken()) return;
  await fetch(CSRF_SEED_PATH, { credentials: "include", headers: { Accept: "application/json" } });
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const csrf = csrfToken();
  if (csrf && init.method && init.method !== "GET") headers.set(CSRF_HEADER, csrf);

  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (res.ok) return res.status === 204 ? (undefined as T) : ((await res.json()) as T);

  let problem: Problem = { title: res.statusText || "Request failed", status: res.status };
  try {
    const body = (await res.json()) as Partial<Problem>;
    problem = { ...problem, ...body, status: body.status ?? res.status };
  } catch {
    // non-JSON error body; keep the status-derived problem
  }
  throw new ApiError(problem);
}
