import { HTTPException } from "hono/http-exception";

/** Điểm đọc giờ DUY NHẤT — test thay bằng vi.spyOn(clock, "now"). */
export const clock = { now: (): number => Date.now() };

/** Lỗi có mã ổn định cho client: body `{ error: code, message }`. */
export class ApiError extends Error {
  constructor(public status: number, public code: string, message?: string) {
    super(message ?? code);
  }
}

export function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...headers },
  });
}

export function errorResponse(e: unknown): Response {
  if (e instanceof ApiError) return json({ error: e.code, message: e.message }, e.status);
  // Lỗi đầu vào do Hono ném (JSON hỏng trong validator…) là lỗi của client, không phải 500.
  if (e instanceof HTTPException && e.status < 500) return json({ error: "bad_request", message: e.message || "Bad request" }, e.status);
  console.error(e);
  return json({ error: "internal", message: "Internal error" }, 500);
}

export function clientIp(req: Request): string {
  return req.headers.get("cf-connecting-ip") ?? "unknown";
}
