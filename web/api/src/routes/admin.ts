import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { z } from "zod";
import { requireAdmin } from "../auth/admin";
import type { HonoEnv } from "../env";
import { ApiError, clock } from "../http";
import { DAY_MS, utcDay } from "../web-stats";

/**
 * API quản trị (Bearer `ADMIN_TOKEN`) — đọc bằng `curl` hoặc `tools/analytics/{web_pull,subs_pull}.py`, không có trang
 * admin. Mọi phản hồi `cache-control: no-store`.
 */
export const admin = new Hono<HonoEnv>();
admin.use("/admin/*", requireAdmin);

const noStore = { "cache-control": "no-store" };
const notFound = () => new ApiError(404, "not_found", "Not found");
const badQuery = () => new ApiError(400, "bad_request", "Bad query");

/** Số liệu web giữ 400 ngày (cron) ⇒ kẹp `days` 1–400; vắng/sai ⇒ 30. */
export const STATS_MAX_DAYS = 400;

admin.get("/admin/stats", async (c) => {
  const raw = Math.floor(Number(c.req.query("days") ?? 30));
  const days = Number.isFinite(raw) && raw > 0 ? Math.min(STATS_MAX_DAYS, raw) : 30;
  const from = utcDay(clock.now() - (days - 1) * DAY_MS);
  const q = <T>(sql: string) => c.env.DB.prepare(sql).bind(from).all<T>().then((r) => r.results);
  const [pages, referrers, countries, devices] = await Promise.all([
    q<{ page: string; views: number }>(
      "SELECT page, SUM(n) AS views FROM web_events WHERE day >= ?1 AND event = 'pageview' GROUP BY page ORDER BY views DESC, page LIMIT 100",
    ),
    q<{ domain: string; n: number }>("SELECT domain, SUM(n) AS n FROM web_referrers WHERE day >= ?1 GROUP BY domain ORDER BY n DESC, domain LIMIT 50"),
    q<{ country: string; n: number }>(
      "SELECT country, SUM(n) AS n FROM web_events WHERE day >= ?1 AND event = 'pageview' GROUP BY country ORDER BY n DESC, country LIMIT 30",
    ),
    q<{ device: string; n: number }>(
      "SELECT device, SUM(n) AS n FROM web_events WHERE day >= ?1 AND event = 'pageview' GROUP BY device ORDER BY n DESC, device",
    ),
  ]);
  return c.json({ days, pages, referrers, countries, devices }, 200, noStore);
});

// ---- Feedback từ app ----

export const FEEDBACK_STATUSES = ["open", "done"] as const;
export const FEEDBACK_LIST_MAX = 200;
export const FEEDBACK_PREVIEW_CHARS = 120;
const FEEDBACK_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const FEEDBACK_DETAIL_COLS = "id, type, message, email, diagnostics, app_version, client_time, created_at, status, note, updated_at";

const FeedbackQuery = z.object({
  status: z.enum(["open", "done", "all"]).default("open"),
  limit: z.coerce.number().int().min(1).max(FEEDBACK_LIST_MAX).default(50),
});
const FeedbackPatch = z
  .object({ status: z.enum(FEEDBACK_STATUSES).optional(), note: z.string().max(2000).optional() })
  .refine((b) => b.status !== undefined || b.note !== undefined, "status or note required");

const validQuery = <T extends z.ZodType>(schema: T) =>
  zValidator("query", schema, (r) => {
    if (!r.success) throw badQuery();
  });
const jsonBody = <T extends z.ZodType>(schema: T) =>
  zValidator("json", schema, (r) => {
    if (!r.success) throw new ApiError(400, "bad_request", r.error.issues.map((i) => `${i.path.join(".") || "body"}: ${i.message}`).join("; "));
  });
const smallBody = bodyLimit({
  maxSize: 16 * 1024,
  onError: () => {
    throw new ApiError(413, "payload_too_large", "Body too large");
  },
});

function feedbackId(raw: string): string {
  if (!FEEDBACK_ID_RE.test(raw)) throw notFound();
  return raw;
}

/** Danh sách — bản tóm tắt (không diagnostics/email), mới nhất trước. */
admin.get("/admin/feedback", validQuery(FeedbackQuery), async (c) => {
  const { status, limit } = c.req.valid("query");
  const { results } = await c.env.DB
    .prepare(
      `SELECT id, type, created_at, status, app_version, substr(message, 1, ${FEEDBACK_PREVIEW_CHARS}) AS preview FROM feedback
       WHERE (?1 = 'all' OR status = ?1) ORDER BY created_at DESC, id DESC LIMIT ?2`,
    )
    .bind(status, limit)
    .all();
  return c.json({ items: results }, 200, noStore);
});

admin.get("/admin/feedback/:id", async (c) => {
  const row = await c.env.DB.prepare(`SELECT ${FEEDBACK_DETAIL_COLS} FROM feedback WHERE id = ?1`).bind(feedbackId(c.req.param("id"))).first();
  if (!row) throw notFound();
  return c.json(row, 200, noStore);
});

admin.post("/admin/feedback/:id", smallBody, jsonBody(FeedbackPatch), async (c) => {
  const { status, note } = c.req.valid("json");
  const row = await c.env.DB
    .prepare(
      `UPDATE feedback SET status = COALESCE(?2, status), note = COALESCE(?3, note), updated_at = ?4
       WHERE id = ?1 RETURNING ${FEEDBACK_DETAIL_COLS}`,
    )
    .bind(feedbackId(c.req.param("id")), status ?? null, note ?? null, clock.now())
    .first();
  if (!row) throw notFound();
  return c.json(row, 200, noStore);
});

admin.post("/admin/feedback/:id/delete", async (c) => {
  const r = await c.env.DB.prepare("DELETE FROM feedback WHERE id = ?1").bind(feedbackId(c.req.param("id"))).run();
  if (!r.meta.changes) throw notFound();
  return c.json({ ok: true }, 200, noStore);
});

// ---- Sự kiện gói (App Store Server Notifications V2) — CHỈ ĐỌC ----

export const SUB_EVENTS_MAX = 500;
const SubEventsQuery = z.object({
  since: z.coerce.number().int().min(0).default(0),
  limit: z.coerce.number().int().min(1).max(SUB_EVENTS_MAX).default(SUB_EVENTS_MAX),
});

/** Phân trang theo `since` (ms, so với `signed_date`, GỒM cả mốc — Ruling 8): trang sau dùng `since` = `signed_date` cuối
 *  (KHÔNG +1, để không bỏ sót sự kiện trùng mốc), client khử trùng theo `notification_uuid`, dừng khi trang không thêm gì
 *  mới hoặc ít hơn `limit`. */
admin.get("/admin/subscription-events", validQuery(SubEventsQuery), async (c) => {
  const { since, limit } = c.req.valid("query");
  const { results } = await c.env.DB
    .prepare(
      `SELECT notification_uuid, notification_type AS type, subtype, environment, signed_date, product_id, original_tx_id, price, currency, storefront
       FROM appstore_notifications WHERE signed_date >= ?1 ORDER BY signed_date, notification_uuid LIMIT ?2`,
    )
    .bind(since, limit)
    .all();
  return c.json({ items: results }, 200, noStore);
});
