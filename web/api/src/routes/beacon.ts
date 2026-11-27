import { Hono } from "hono";
import { z } from "zod";
import type { HonoEnv } from "../env";
import { clientIp, clock } from "../http";
import { checkRate } from "../rate";
import { isHumanBeacon, normDomain, normPage, readTextCapped, recordWebRow, type WebRow } from "../web-stats";

/**
 * Beacon web analytics không cookie, gửi từ `m.js` của site (cùng origin). Hợp đồng body (JSON, ≤ 2 KB):
 *   { p: "<đường dẫn trang>", e?: "pageview" | "engaged" | "outbound", d?: "<chi tiết>" }
 * - `pageview` (mặc định khi vắng `e`): `d` = tên miền giới thiệu (`document.referrer` hostname khi khác site) hoặc
 *   `utm:<giá trị>`; vắng/sai ⇒ nguồn `direct`.
 * - `engaged`: `d` ∈ ENGAGED_BUCKETS (thời gian trang hiện).
 * - `outbound`: `d` = mã nút ngắn `[a-z0-9_-]{1,32}` (vd. `app_store`, `support_email`).
 * Luôn trả 204 — người gửi không bao giờ biết beacon bị bỏ hay được ghi. Quá BEACON_PER_IP_HOUR lượt/giờ từ một IP ⇒ 204
 * nhưng không đếm (chặn một máy bơm số; đếm SAU bộ lọc người thật để bot không tốn lượt ghi D1).
 */
export const beacon = new Hono<HonoEnv>();

export const BEACON_MAX_BYTES = 2048;
export const ENGAGED_BUCKETS = ["lt10s", "10_30s", "30_120s", "gt2m"] as const;
export const BEACON_PER_IP_HOUR = 120;
const TOKEN_RE = /^[a-z0-9_-]{1,32}$/;

const BeaconSchema = z.object({
  p: z.string().max(512),
  e: z.string().max(32).optional(),
  d: z.string().max(80).optional(),
});

/** Chuẩn hoá một beacon thành một dòng; sự kiện/chi tiết lạ ⇒ null (bỏ). */
function toRow(b: z.infer<typeof BeaconSchema>): { row: WebRow; ref: string | null } | null {
  const page = normPage(b.p);
  const event = b.e ?? "pageview";
  if (event === "pageview") {
    const ref = normDomain(b.d);
    const source = ref === null ? "direct" : ref.startsWith("utm:") ? "utm" : "referral";
    return { row: { page, event, detail: "-", source }, ref };
  }
  if (event === "engaged") {
    return b.d !== undefined && (ENGAGED_BUCKETS as readonly string[]).includes(b.d) ? { row: { page, event, detail: b.d, source: "-" }, ref: null } : null;
  }
  if (event === "outbound") {
    return b.d !== undefined && TOKEN_RE.test(b.d) ? { row: { page, event, detail: b.d, source: "-" }, ref: null } : null;
  }
  return null;
}

beacon.post("/public/beacon", async (c) => {
  const done = () => new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
  const req = c.req.raw;
  // Site có thể phục vụ cả biến thể www của origin công khai.
  const origin = req.headers.get("origin");
  const pub = c.env.PUBLIC_ORIGIN;
  if (!origin || (origin !== pub && origin !== pub.replace("://", "://www.")) || !isHumanBeacon(req)) return done();
  if (!(await checkRate(c.env.DB, `bcn:${clientIp(req)}`, BEACON_PER_IP_HOUR, 3600))) return done();
  const text = await readTextCapped(req, BEACON_MAX_BYTES);
  if (text === null) return done();
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return done();
  }
  const parsed = BeaconSchema.safeParse(raw);
  if (!parsed.success) return done();
  const r = toRow(parsed.data);
  if (r) c.executionCtx.waitUntil(recordWebRow(c.env.DB, req, clock.now(), r.row, r.ref));
  return done();
});
