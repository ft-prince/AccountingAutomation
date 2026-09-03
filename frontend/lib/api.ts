// Fetch wrapper: session cookies, CSRF header, RFC 7807 errors unwrapped into ApiError.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface Problem {
  type?: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  constructor(public readonly problem: Problem) {
    super(problem.detail ?? problem.title);
    this.name = "ApiError";
  }
}

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1];
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const csrf = csrfToken();
  if (csrf && init.method && init.method !== "GET") headers.set("X-CSRFToken", csrf);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include" });
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
