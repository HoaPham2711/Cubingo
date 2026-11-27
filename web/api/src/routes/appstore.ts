import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { appleRoots, verifyJWS } from "../auth/storekit";
import type { HonoEnv } from "../env";
import { ApiError, clock } from "../http";

/**
 * App Store Server Notifications V2 — CHỈ GHI sự kiện gói vào `appstore_notifications`. Không lưu JWS thô, không log
 * payload / JWS / originalTransactionId. Khác bundle hoặc môi trường ⇒ 200 không lưu (Apple không gửi lại).
 */
export const appstore = new Hono<HonoEnv>();

/** Gốc tin cậy của route. Điểm DUY NHẤT test thay (vi.spyOn(appstoreTrust, "roots")) để tiêm gốc giả — không có
 *  biến môi trường nào mở được lối này. */
export const appstoreTrust = { roots: () => appleRoots() };

const JWS_RE = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;
type Obj = Record<string, unknown>;

const bad = (m: string) => new ApiError(400, "bad_request", m);
const isObj = (x: unknown): x is Obj => typeof x === "object" && x !== null && !Array.isArray(x);
const str = (x: unknown): string | null => (typeof x === "string" ? x : null);
const num = (x: unknown): number | null => (typeof x === "number" && Number.isFinite(x) ? x : null);
const ok = () => new Response(null, { status: 200 });

const limit = bodyLimit({
  maxSize: 64 * 1024,
  onError: () => {
    throw new ApiError(413, "payload_too_large", "Body too large");
  },
});

/** Payload CHƯA kiểm chữ ký — chỉ để lấy notificationUUID cho bước chặn trùng (hàng đã lưu chắc chắn đã qua kiểm). */
function unverifiedPayload(jws: string): Obj {
  try {
    const part = jws.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const bin = atob(part + "=".repeat((4 - (part.length % 4)) % 4));
    const v = JSON.parse(new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0))));
    if (isObj(v)) return v;
  } catch {
    /* rơi xuống lỗi dạng */
  }
  throw bad("bad payload");
}

async function verified(jws: string): Promise<unknown> {
  try {
    return await verifyJWS(jws, appstoreTrust.roots());
  } catch {
    throw bad("bad sig");
  }
}

/** JWS bên trong (`signedTransactionInfo` / `signedRenewalInfo`): vắng ⇒ null; có mà hỏng ⇒ 400. */
async function verifyInner(jws: unknown): Promise<Obj | null> {
  if (jws === undefined || jws === null) return null;
  if (typeof jws !== "string" || !JWS_RE.test(jws)) throw bad("bad jws");
  const v = await verified(jws);
  return isObj(v) ? v : null;
}

appstore.post("/appstore/notifications", limit, async (c) => {
  let body: unknown;
  try {
    body = JSON.parse(await c.req.text());
  } catch {
    throw bad("bad json");
  }
  const signed = isObj(body) ? body.signedPayload : undefined;
  if (typeof signed !== "string" || !JWS_RE.test(signed)) throw bad("bad signedPayload");

  // Chặn trùng RẺ trước khi kiểm chữ ký.
  const uuid = str(unverifiedPayload(signed).notificationUUID);
  if (!uuid) throw bad("bad payload");
  if (await c.env.DB.prepare("SELECT 1 AS x FROM appstore_notifications WHERE notification_uuid = ?1").bind(uuid).first()) return ok();

  const p = await verified(signed);
  if (!isObj(p) || p.notificationUUID !== uuid) throw bad("bad payload");
  const type = str(p.notificationType);
  if (!type) throw bad("bad payload");

  // Lọc bundle + môi trường. Không có `data` ⇒ dùng `summary`; không có cả hai (vd. externalPurchaseToken) ⇒ bỏ.
  const data = isObj(p.data) ? p.data : null;
  const common = data ?? (isObj(p.summary) ? p.summary : null);
  if (!common) return ok();
  // ASSN_ENVIRONMENTS rỗng ⇒ KHÔNG môi trường nào được nhận ⇒ mọi thông báo bị bỏ (vẫn 200) — cấu hình sinh phải có
  // "Production" (prod) / "Sandbox" (dev); tài liệu deploy nhắc điều này.
  const envs = (c.env.ASSN_ENVIRONMENTS ?? "").split(",").map((x) => x.trim()).filter(Boolean);
  const environment = str(common.environment);
  if (common.bundleId !== c.env.ASSN_BUNDLE_ID || !environment || !envs.includes(environment)) return ok();

  const t = (data ? await verifyInner(data.signedTransactionInfo) : null) ?? {};
  const r = (data ? await verifyInner(data.signedRenewalInfo) : null) ?? {};
  const now = clock.now();
  await c.env.DB.prepare(
    `INSERT OR IGNORE INTO appstore_notifications (notification_uuid, notification_type, subtype, environment, signed_date, received_at,
       original_tx_id, transaction_id, product_id, purchase_date, expires_date, revocation_date, revocation_reason, offer_type,
       price, currency, storefront, auto_renew_status, auto_renew_product_id, expiration_intent, grace_period_expires_date)
     VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20,?21)`,
  )
    .bind(
      uuid, type, str(p.subtype), environment, num(p.signedDate) ?? now, now,
      str(t.originalTransactionId), str(t.transactionId), str(t.productId), num(t.purchaseDate), num(t.expiresDate),
      num(t.revocationDate), num(t.revocationReason), num(t.offerType), num(t.price), str(t.currency), str(t.storefront),
      num(r.autoRenewStatus), str(r.autoRenewProductId), num(r.expirationIntent), num(r.gracePeriodExpiresDate),
    )
    .run();
  return ok();
});
