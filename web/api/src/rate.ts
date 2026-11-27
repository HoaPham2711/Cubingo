import { clock } from "./http";

/**
 * Giới hạn tần suất cửa sổ cố định trên bảng `rate` (một hàng mỗi khoá). Mỗi lần gọi là một lượt: tăng bộ đếm của
 * cửa sổ hiện tại (cửa sổ mới ⇒ đếm lại từ 1). true = lượt này còn trong hạn mức.
 * `window_start` tính bằng GIÂY epoch, căn theo bội của `windowSec`. SQLite đọc giá trị CŨ trong mọi biểu thức SET.
 */
export async function checkRate(db: D1Database, key: string, limit: number, windowSec: number): Promise<boolean> {
  const t = Math.floor(clock.now() / 1000);
  const ws = t - (t % windowSec);
  const row = await db
    .prepare(
      `INSERT INTO rate (key, window_start, count) VALUES (?1, ?2, 1)
       ON CONFLICT(key) DO UPDATE SET
         count = CASE WHEN rate.window_start = ?2 THEN rate.count + 1 ELSE 1 END,
         window_start = ?2
       RETURNING count`,
    )
    .bind(key, ws)
    .first<{ count: number }>();
  // Không có hàng trả về (lỗi bất thường) ⇒ đóng: coi như vượt hạn mức.
  return row != null && row.count <= limit;
}
