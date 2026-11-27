import { createMiddleware } from "hono/factory";
import type { HonoEnv } from "../env";
import { ApiError, clientIp, clock } from "../http";
import { checkRate } from "../rate";

/** Sai token quá chừng này lần trong một giờ từ một IP ⇒ IP đó bị khoá tới hết giờ (kể cả token đúng). */
export const ADMIN_FAILS_PER_HOUR = 10;
const HOUR_SEC = 3600;

async function digest(s: string): Promise<Uint8Array> {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
}

/**
 * So sánh thời gian hằng: băm cả hai về SHA-256 (cùng 32 byte ⇒ độ dài token không lộ qua thời gian), rồi XOR
 * từng byte, không thoát sớm. Token mong đợi rỗng ⇒ luôn false (secret chưa đặt thì không ai vào được).
 */
export async function tokenMatches(got: string, want: string): Promise<boolean> {
  if (!want) return false;
  const [a, b] = await Promise.all([digest(got), digest(want)]);
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a[i] ^ b[i];
  return r === 0;
}

/** Khoá kéo dài ĐÚNG một giờ kể từ lần sai thứ 10 (không phải tới hết giờ đồng hồ). */
export const ADMIN_LOCK_SEC = 3600;

/**
 * Bearer `ADMIN_TOKEN` (secret) + khoá IP. Lần sai đếm ở bảng `rate`, khoá `adm:<ip>` (cửa sổ cố định một giờ); lần sai
 * thứ ADMIN_FAILS_PER_HOUR ghi hàng khoá `admlock:<ip>` mang thời điểm khoá (giây, cột `window_start`) ⇒ mọi request từ
 * IP đó bị 429 (kể cả token đúng) tới khi hàng khoá đủ ADMIN_LOCK_SEC tuổi. Cron dọn cả hai loại hàng sau 1 ngày.
 */
export const requireAdmin = createMiddleware<HonoEnv>(async (c, next) => {
  const db = c.env.DB;
  const ip = clientIp(c.req.raw);
  const now = Math.floor(clock.now() / 1000);
  const lock = await db.prepare("SELECT window_start FROM rate WHERE key = ?1").bind(`admlock:${ip}`).first<{ window_start: number }>();
  if (lock && now - lock.window_start < ADMIN_LOCK_SEC) throw new ApiError(429, "rate_limited", "Too many attempts");
  const header = c.req.header("authorization") ?? "";
  const got = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!(await tokenMatches(got, c.env.ADMIN_TOKEN ?? ""))) {
    // checkRate(limit − 1) trả false đúng từ lần sai thứ ADMIN_FAILS_PER_HOUR trong cửa sổ.
    if (!(await checkRate(db, `adm:${ip}`, ADMIN_FAILS_PER_HOUR - 1, HOUR_SEC))) {
      await db
        .prepare("INSERT INTO rate (key, window_start, count) VALUES (?1, ?2, 1) ON CONFLICT(key) DO UPDATE SET window_start = ?2, count = 1")
        .bind(`admlock:${ip}`, now)
        .run();
    }
    throw new ApiError(401, "unauthorized", "Admin token required");
  }
  await next();
});
