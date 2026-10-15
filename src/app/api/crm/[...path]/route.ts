import type { NextRequest } from "next/server";

// Transparent proxy to the FastAPI backend. The browser never sees the bearer
// token: it is added here from the server environment.

const BACKEND = (process.env.CRM_BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const TOKEN = process.env.CRM_API_TOKEN ?? "";

async function proxy(request: NextRequest, ctx: RouteContext<"/api/crm/[...path]">) {
  const { path } = await ctx.params;
  const url = new URL(`${BACKEND}/api/crm/${path.join("/")}`);
  url.search = request.nextUrl.search;

  const headers = new Headers();
  const ct = request.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  headers.set("accept", request.headers.get("accept") ?? "application/json");
  if (TOKEN) headers.set("authorization", `Bearer ${TOKEN}`);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return Response.json({ detail: "backend_unreachable" }, { status: 502 });
  }

  if (upstream.status >= 300 && upstream.status < 400) {
    const location = upstream.headers.get("location") ?? "/crm/settings";
    return Response.redirect(new URL(location, request.nextUrl.origin), 307);
  }

  const out = new Headers();
  const uct = upstream.headers.get("content-type");
  if (uct) out.set("content-type", uct);
  return new Response(upstream.status === 204 ? null : upstream.body, { status: upstream.status, headers: out });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
