import { aasaBody, parseAppIds, parseAppPaths } from "./aasa";

/**
 * Worker nhỏ của site tĩnh. `wrangler.jsonc` (file sinh) cho nó chạy trước asset ở
 * `/.well-known/*` và `/api/*` (prod) — ở dev chạy trước MỌI đường dẫn để gắn được `X-Robots-Tag` lên cả trang tĩnh.
 *   - `/.well-known/apple-app-site-association` ⇒ JSON dựng từ `APP_IDS` + `APP_PATHS` (không redirect, cache 1 giờ);
 *   - `/api/*` ⇒ chuyển nguyên request sang Worker API qua service binding `API` (chỉ có khi `features.web_api`);
 *     không có binding ⇒ 404 `{"error":"no_api"}`;
 *   - còn lại ⇒ asset tĩnh (`ASSETS`);
 *   - `NOINDEX = "1"` (dev) ⇒ mọi phản hồi mang `X-Robots-Tag: noindex`.
 * App thêm route riêng ⇒ thêm ở template (file này là lớp đồng bộ) hoặc dựng Worker riêng của app — xem web/README.md.
 */
export interface Env {
  ASSETS: Fetcher;
  API?: Fetcher;
  APP_IDS?: string;
  APP_PATHS?: string;
  NOINDEX?: string;
}

export const AASA_PATH = "/.well-known/apple-app-site-association";

function json(body: unknown, status: number, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
}

async function route(request: Request, env: Env): Promise<Response> {
  const { pathname } = new URL(request.url);
  if (pathname === AASA_PATH && (request.method === "GET" || request.method === "HEAD")) {
    const res = json(aasaBody(parseAppIds(env.APP_IDS), parseAppPaths(env.APP_PATHS)), 200, {
      "cache-control": "max-age=3600",
    });
    return request.method === "HEAD" ? new Response(null, { status: 200, headers: res.headers }) : res;
  }
  if (pathname === "/api" || pathname.startsWith("/api/")) {
    return env.API ? env.API.fetch(request) : json({ error: "no_api" }, 404, { "cache-control": "no-store" });
  }
  return env.ASSETS.fetch(request);
}

/** Dev: gắn `X-Robots-Tag` (dựng lại Response — header của phản hồi từ fetch có thể bất biến). */
function withNoindex(res: Response, flag: string | undefined): Response {
  if (flag !== "1") return res;
  const headers = new Headers(res.headers);
  headers.set("x-robots-tag", "noindex");
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return withNoindex(await route(request, env), env.NOINDEX);
  },
};
