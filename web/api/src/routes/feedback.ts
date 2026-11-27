import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { createMiddleware } from "hono/factory";
import { verifyAppCheck } from "../auth/appcheck";
import type { HonoEnv } from "../env";
import { ApiError, clientIp, clock } from "../http";
import { checkRate } from "../rate";
import { FeedbackCreateSchema } from "../schemas";

const HOUR_SEC = 3600;
const DAY_SEC = 86_400;
/** Người thật gửi vài phản hồi mỗi giờ là nhiều. */
export const FEEDBACK_PER_IP_HOUR = 10;
/** Trần toàn hệ thống mỗi ngày — bảo vệ D1 nếu App Check bị vượt. */
export const FEEDBACK_PER_DAY = 500;
export const FEEDBACK_MAX_BODY = 32 * 1024;

const limitBody = bodyLimit({
  maxSize: FEEDBACK_MAX_BODY,
  onError: () => {
    throw new ApiError(413, "payload_too_large", "Body too large");
  },
});

/**
 * Chỉ App Check (không đăng nhập): gửi phản hồi không phụ thuộc tài khoản. `APP_CHECK_REQUIRED` "0" (dev) bỏ qua
 * phép kiểm; mọi giá trị khác (kể cả vắng) đều bắt buộc — cấu hình hỏng thì đóng, không mở.
 */
const appCheck = createMiddleware<HonoEnv>(async (c, next) => {
  if (c.env.APP_CHECK_REQUIRED !== "0") {
    const token = c.req.header("x-firebase-appcheck");
    if (!token || !(await verifyAppCheck(token, c.env))) throw new ApiError(401, "app_check_failed", "App Check failed");
  }
  await next();
});

/**
 * Đứng SAU App Check (người ngoài không đốt được hạn mức IP của người dùng thật sau NAT) và TRƯỚC validate body
 * (request sai định dạng cũng bị đếm).
 */
const rate = createMiddleware<HonoEnv>(async (c, next) => {
  const ok =
    (await checkRate(c.env.DB, `fb:ip:${clientIp(c.req.raw)}`, FEEDBACK_PER_IP_HOUR, HOUR_SEC)) &&
    (await checkRate(c.env.DB, "fb:all", FEEDBACK_PER_DAY, DAY_SEC));
  if (!ok) throw new ApiError(429, "rate_limited", "Too many requests");
  await next();
});

const body = zValidator("json", FeedbackCreateSchema, (r) => {
  if (!r.success) {
    throw new ApiError(400, "bad_request", r.error.issues.map((i) => `${i.path.join(".") || "body"}: ${i.message}`).join("; "));
  }
});

export const feedback = new Hono<HonoEnv>();

feedback.post("/feedback", limitBody, appCheck, rate, body, async (c) => {
  const b = c.req.valid("json");
  const t = clock.now();
  await c.env.DB
    .prepare(
      `INSERT INTO feedback (id, type, message, email, diagnostics, app_version, client_time, created_at, updated_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?8)`,
    )
    .bind(crypto.randomUUID(), b.type, b.message, b.email, b.diagnostics, b.appVersion, b.clientTime, t)
    .run();
  return c.json({ ok: true }, 201, { "cache-control": "no-store" });
});
