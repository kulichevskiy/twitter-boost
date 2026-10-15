import type { JobOut, PeopleFilter } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
  get unreachable() {
    return this.status === 502 || this.status === 0;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/crm${path}`, {
      method,
      headers: body !== undefined ? { "content-type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Бэкенд недоступен");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data?.detail === "backend_unreachable") detail = "Бэкенд недоступен";
      else if (typeof data?.detail === "string") detail = data.detail;
      else if (data?.detail) detail = JSON.stringify(data.detail);
    } catch {
      /* no body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};

/** SWR fetcher: key is the path after /api/crm. */
export const fetcher = <T>(path: string) => api.get<T>(path);

export function peopleQuery(f: PeopleFilter): URLSearchParams {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) {
      for (const item of v) sp.append(k, String(item));
    } else {
      sp.set(k, String(v));
    }
  }
  return sp;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Poll a job until it leaves the queue. Resolves with the final JobOut. */
export async function pollJob(id: number, { intervalMs = 1500, timeoutMs = 10 * 60_000 } = {}): Promise<JobOut> {
  const started = Date.now();
  for (;;) {
    const job = await api.get<JobOut>(`/jobs/${id}`);
    if (job.status === "done" || job.status === "failed" || job.status === "cancelled") return job;
    if (Date.now() - started > timeoutMs) throw new ApiError(408, "Задача выполняется слишком долго");
    await sleep(intervalMs);
  }
}
