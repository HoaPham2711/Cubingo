/**
 * Web analytics không cookie: đếm GỘP theo ngày vào `web_events` / `web_referrers`. Mọi chiều là tập hữu hạn hoặc đã
 * chuẩn hoá chặt — không IP, không user-agent, không URL đầy đủ, không gì nhét được định danh vào.
 */

export const DAY_MS = 86_400_000;

/** 'YYYYMMDD' theo UTC. */
export const utcDay = (t: number): string => new Date(t).toISOString().slice(0, 10).replace(/-/g, "");

const BOT_RE =
  /bot|crawler|spider|facebookexternalhit|slack|twitter|whatsapp|telegram|discord|linkedin|embedly|preview|skype|headless|lighthouse|pagespeed|gtmetrix|phantomjs|selenium|puppeteer|playwright|python-requests|curl|wget/i;

export function deviceOf(ua: string): "ios" | "android" | "desktop" {
  if (/iPhone|iPad|iPod/i.test(ua)) return "ios";
  if (/Android/i.test(ua)) return "android";
  return "desktop";
}

/** Cloudflare gắn `cf-ipcountry` ở edge; site chuyển tiếp nguyên header khi gọi API qua service binding. */
export function countryOf(req: Request): string {
  const c = (req.headers.get("cf-ipcountry") ?? "").toUpperCase();
  return /^[A-Z]{2}$/.test(c) ? c : "XX";
}

/**
 * Lượt người thật trên trình duyệt, gửi từ CHÍNH site: có user-agent không phải bot, không phải bot Cloudflare đã xác
 * minh, không mang `x-app-owner: 1` (app/chủ máy tự đánh dấu để không tự đếm mình), và `Sec-Fetch-Site: same-origin`
 * — trình duyệt hiện đại tự gắn, trang web không ghi đè được; crawler, curl, trang khác gửi chéo đều trượt.
 */
export function isHumanBeacon(req: Request): boolean {
  const ua = req.headers.get("user-agent") ?? "";
  const cf = (req as Request & { cf?: { verifiedBotCategory?: string } }).cf;
  return (
    ua !== "" &&
    !BOT_RE.test(ua) &&
    !cf?.verifiedBotCategory &&
    req.headers.get("x-app-owner") !== "1" &&
    req.headers.get("sec-fetch-site") === "same-origin"
  );
}

const PAGE_RE = /^\/[a-z0-9._~\/-]*$/;
export const PAGE_MAX = 64;
/** Tối đa số đoạn đường dẫn (`/a/b/c/d/` = 4) — chặn sinh vô hạn dòng `page` khác nhau. */
export const PAGE_MAX_DEPTH = 4;

/** Đường dẫn trang: bỏ query/hash, chữ thường, thêm `/` cuối khi đoạn cuối không có đuôi file; sai dạng, dài quá
 *  PAGE_MAX hoặc sâu quá PAGE_MAX_DEPTH đoạn ⇒ "other". */
export function normPage(v: unknown): string {
  if (typeof v !== "string") return "other";
  let p = v.split(/[?#]/)[0].toLowerCase();
  if (p !== "/" && !p.endsWith("/") && !(p.split("/").pop() ?? "").includes(".")) p += "/";
  const depth = p.split("/").filter(Boolean).length;
  return p.length <= PAGE_MAX && depth <= PAGE_MAX_DEPTH && PAGE_RE.test(p) && !p.includes("//") ? p : "other";
}

const HOST_RE = /^[a-z0-9-]+(\.[a-z0-9-]+)+$/;
const UTM_RE = /^[a-z0-9_-]{1,32}$/;

/** Tên miền giới thiệu: hostname (bỏ `www.`, ≤ 64 ký tự) hoặc `utm:<giá trị>`; sai dạng ⇒ null. */
export function normDomain(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const s = v.toLowerCase();
  if (s.startsWith("utm:")) return UTM_RE.test(s.slice(4)) ? s : null;
  const h = s.replace(/^www\./, "");
  return h.length <= 64 && HOST_RE.test(h) ? h : null;
}

/** Đọc body tối đa `max` byte — dừng sớm, không nạp body lớn. null = quá lớn. */
export async function readTextCapped(req: Request, max: number): Promise<string | null> {
  if (Number(req.headers.get("content-length") ?? 0) > max) return null;
  if (!req.body) return "";
  const reader = req.body.getReader();
  const chunks: Uint8Array[] = [];
  let n = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    n += value.length;
    if (n > max) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const all = new Uint8Array(n);
  let o = 0;
  for (const ch of chunks) {
    all.set(ch, o);
    o += ch.length;
  }
  return new TextDecoder().decode(all);
}

export type WebRow = { page: string; event: string; detail: string; source: string };

const UPSERT_EVENT = `INSERT INTO web_events (day, page, event, detail, source, country, device, n) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, 1)
  ON CONFLICT(day, page, event, detail, source, country, device) DO UPDATE SET n = n + 1`;
const UPSERT_REF = `INSERT INTO web_referrers (day, domain, n) VALUES (?1, ?2, 1)
  ON CONFLICT(day, domain) DO UPDATE SET n = n + 1`;

/** Một lần ghi = MỘT batch (sự kiện + referrer nếu có). Nơi gọi đặt nó trong `waitUntil`; lỗi chỉ log. */
export function recordWebRow(db: D1Database, req: Request, t: number, row: WebRow, refDomain: string | null): Promise<void> {
  const day = utcDay(t);
  const stmts = [db.prepare(UPSERT_EVENT).bind(day, row.page, row.event, row.detail, row.source, countryOf(req), deviceOf(req.headers.get("user-agent") ?? ""))];
  if (refDomain) stmts.push(db.prepare(UPSERT_REF).bind(day, refDomain));
  return db.batch(stmts).then(() => undefined).catch((e) => console.error("web_events", e instanceof Error ? e.message : "error"));
}
