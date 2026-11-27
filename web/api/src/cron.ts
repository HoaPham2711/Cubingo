import type { Env } from "./env";
import { clock } from "./http";
import { DAY_MS, utcDay } from "./web-stats";

/** Số liệu web + sự kiện gói giữ 400 ngày (đủ so cùng kỳ năm trước). */
export const RETAIN_DAYS = 400;

/**
 * Việc định kỳ (cron hằng ngày, `triggers.crons` trong wrangler.jsonc sinh). Idempotent. Chỉ dọn bảng:
 * `rate` cũ hơn 1 ngày (`window_start` tính bằng giây), `web_events`/`web_referrers` và `appstore_notifications`
 * cũ hơn RETAIN_DAYS ngày. Feedback KHÔNG bao giờ tự xoá — chỉ admin xoá.
 */
export async function runCron(env: Env): Promise<void> {
  const t = clock.now();
  const oldDay = utcDay(t - RETAIN_DAYS * DAY_MS);
  await env.DB.batch([
    env.DB.prepare("DELETE FROM rate WHERE window_start < ?1").bind(Math.floor((t - DAY_MS) / 1000)),
    env.DB.prepare("DELETE FROM web_events WHERE day < ?1").bind(oldDay),
    env.DB.prepare("DELETE FROM web_referrers WHERE day < ?1").bind(oldDay),
    env.DB.prepare("DELETE FROM appstore_notifications WHERE received_at < ?1").bind(t - RETAIN_DAYS * DAY_MS),
  ]);
}
