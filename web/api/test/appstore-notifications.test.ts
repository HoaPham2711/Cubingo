import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { APPLE_ROOT_G3_B64, APPLE_ROOT_G3_SHA256 } from "../src/auth/apple-root";
import { appleRoots, verifyJWS } from "../src/auth/storekit";
import { appstoreTrust } from "../src/routes/appstore";
import { call, testEnv } from "./helpers";
import { b64u, makeTestChain, type TestChain } from "./storekit-chain";

const BUNDLE = "com.example.app";
let chain: TestChain;
let other: TestChain;
let seq = 0;

beforeAll(async () => {
  [chain, other] = await Promise.all([makeTestChain(), makeTestChain()]);
});
beforeEach(async () => {
  await testEnv().DB.prepare("DELETE FROM appstore_notifications").run();
  // Gốc GIẢ tiêm vào route; setup.ts gỡ mock sau mỗi test ⇒ mặc định quay về gốc Apple thật.
  vi.spyOn(appstoreTrust, "roots").mockReturnValue([chain.root]);
});

const uuid = () => `n-${++seq}-${crypto.randomUUID()}`;
const post = (body: string, env = {}) =>
  call("/api/v1/appstore/notifications", { method: "POST", body, headers: { "content-type": "application/json" } }, env);
const postJws = (jws: string, env = {}) => post(JSON.stringify({ signedPayload: jws }), env);
const count = async () => (await testEnv().DB.prepare("SELECT COUNT(*) AS n FROM appstore_notifications").first<{ n: number }>())!.n;

const tx = (over: object = {}) => ({
  originalTransactionId: "5000", transactionId: "5001", productId: "com.example.app.pro.yearly",
  purchaseDate: 1_700_000_000_000, expiresDate: 1_800_000_000_000, price: 19990, currency: "USD", storefront: "USA", ...over,
});
async function note(c: TestChain, over: Record<string, unknown> = {}, dataOver: Record<string, unknown> = {}, inner: { tx?: string; rn?: string } = {}) {
  const signedTransactionInfo = inner.tx ?? (await c.sign(tx()));
  const signedRenewalInfo = inner.rn ?? (await c.sign({ autoRenewStatus: 0, autoRenewProductId: "x", expirationIntent: 1 }));
  return c.sign({
    notificationType: "DID_CHANGE_RENEWAL_STATUS", subtype: "AUTO_RENEW_DISABLED", notificationUUID: uuid(), signedDate: 1_750_000_000_000,
    data: { bundleId: BUNDLE, environment: "Production", signedTransactionInfo, signedRenewalInfo, ...dataOver }, ...over,
  });
}

describe("gốc Apple ghim", () => {
  it("fingerprint SHA-256 cua Apple Root CA G3 khop", async () => {
    const der = Uint8Array.from(atob(APPLE_ROOT_G3_B64), (ch) => ch.charCodeAt(0));
    const h = [...new Uint8Array(await crypto.subtle.digest("SHA-256", der))].map((b) => b.toString(16).padStart(2, "0")).join("");
    expect(h).toBe(APPLE_ROOT_G3_SHA256);
    expect(appleRoots()).toHaveLength(1);
  });
});

describe("verifyJWS", () => {
  it("chuoi gia voi goc gia tiem vao thi tra payload", async () => {
    expect(await verifyJWS(await chain.sign({ a: 1 }), [chain.root])).toEqual({ a: 1 });
  });
  it("chuoi gia bi goc Apple that tu choi", async () => {
    await expect(verifyJWS(await chain.sign({ a: 1 }), appleRoots())).rejects.toThrow();
  });
  it("leaf thieu OID Apple bi tu choi", async () => {
    await expect(verifyJWS(await chain.sign({ a: 1 }, { noLeafOid: true }), [chain.root])).rejects.toThrow();
  });
  it("header khong phai ES256 hoac thieu x5c bi tu choi", async () => {
    await expect(verifyJWS(`${b64u({ alg: "none" })}.${b64u({ a: 1 })}.${b64u({ s: 1 })}`, [chain.root])).rejects.toThrow();
  });
});

describe("POST /api/v1/appstore/notifications", () => {
  it("jws chuoi hop le duoc luu", async () => {
    const res = await postJws(await note(chain));
    expect(res.status).toBe(200);
    const row = await testEnv().DB.prepare("SELECT * FROM appstore_notifications").first<Record<string, unknown>>();
    expect(row).toMatchObject({
      notification_type: "DID_CHANGE_RENEWAL_STATUS", subtype: "AUTO_RENEW_DISABLED", environment: "Production", signed_date: 1_750_000_000_000,
      original_tx_id: "5000", transaction_id: "5001", product_id: "com.example.app.pro.yearly", price: 19990, currency: "USD",
      storefront: "USA", auto_renew_status: 0, auto_renew_product_id: "x", expiration_intent: 1,
    });
  });

  it("jws chu ky hong tra 400 khong luu", async () => {
    const outer = await chain.sign({ notificationType: "TEST", notificationUUID: uuid(), data: { bundleId: BUNDLE, environment: "Production" } }, { tamper: true });
    expect((await postJws(outer)).status).toBe(400);
    // JWS bên trong (giao dịch / renewal) hỏng chữ ký cũng bị từ chối dù JWS ngoài hợp lệ.
    expect((await postJws(await note(chain, {}, {}, { tx: await chain.sign(tx(), { tamper: true }) }))).status).toBe(400);
    expect((await postJws(await note(chain, {}, {}, { rn: await chain.sign({ autoRenewStatus: 1 }, { tamper: true }) }))).status).toBe(400);
    expect(await count()).toBe(0);
  });

  it("chuoi khong toi goc tra 400", async () => {
    // Chuỗi ngoài ký bằng gốc khác gốc tin cậy.
    expect((await postJws(await note(other))).status).toBe(400);
    // JWS trong ký bằng chuỗi khác.
    expect((await postJws(await note(chain, {}, {}, { tx: await other.sign(tx()) }))).status).toBe(400);
    // Không tiêm gốc giả ⇒ gốc Apple thật ⇒ chuỗi giả không qua.
    vi.restoreAllMocks();
    expect((await postJws(await note(chain))).status).toBe(400);
    expect(await count()).toBe(0);
  });

  it("bundle khac tra 200 khong luu", async () => {
    expect((await postJws(await note(chain, {}, { bundleId: `${BUNDLE}.internal` }))).status).toBe(200);
    const summary = await chain.sign({ notificationType: "RENEWAL_EXTENSION", notificationUUID: uuid(), signedDate: 3, summary: { bundleId: "com.example.other", environment: "Production" } });
    expect((await postJws(summary)).status).toBe(200);
    expect(await count()).toBe(0);
  });

  it("moi truong khac tra 200 khong luu", async () => {
    expect((await postJws(await note(chain, {}, { environment: "Xcode" }))).status).toBe(200);
    expect((await postJws(await note(chain), { ASSN_ENVIRONMENTS: "Sandbox" })).status).toBe(200);
    expect(await count()).toBe(0);
    // Cùng thông báo, môi trường được nhận ⇒ lưu.
    expect((await postJws(await note(chain, {}, { environment: "Sandbox" }), { ASSN_ENVIRONMENTS: "Sandbox" })).status).toBe(200);
    expect(await count()).toBe(1);
  });

  it("bien dev: thong bao Sandbox mang bundle Store duoc luu, bundle internal thi bo", async () => {
    // Vars env.dev do appconfig.py render sinh: Apple gửi thông báo Sandbox (TestFlight, App Review, sandbox tester,
    // "Send Test Notification") về URL dev với bundle STORE — bản .internal không có bản ghi App Store Connect.
    const dev = { ASSN_BUNDLE_ID: BUNDLE, ASSN_ENVIRONMENTS: "Sandbox" };
    expect((await postJws(await note(chain, {}, { environment: "Sandbox" }), dev)).status).toBe(200);
    expect(await count()).toBe(1);
    expect((await postJws(await note(chain, {}, { environment: "Sandbox", bundleId: `${BUNDLE}.internal` }), dev)).status).toBe(200);
    expect(await count()).toBe(1);
  });

  it("trung notification_uuid khong ghi lan hai", async () => {
    const jws = await note(chain);
    const roots = vi.mocked(appstoreTrust.roots);
    expect((await postJws(jws)).status).toBe(200);
    const verifications = roots.mock.calls.length;
    expect(verifications).toBe(3); // JWS ngoài + giao dịch + renewal
    // Lần hai bị chặn trước khi kiểm chữ ký (không tốn crypto cho Apple gửi lại).
    expect((await postJws(jws)).status).toBe(200);
    expect(roots.mock.calls.length).toBe(verifications);
    expect(await count()).toBe(1);
  });

  it("chi co summary thi luu cot chung, khong co ca hai thi bo", async () => {
    const summary = await chain.sign({ notificationType: "RENEWAL_EXTENSION", subtype: "SUMMARY", notificationUUID: uuid(), signedDate: 3, summary: { bundleId: BUNDLE, environment: "Production" } });
    expect((await postJws(summary)).status).toBe(200);
    const ext = await chain.sign({ notificationType: "EXTERNAL_PURCHASE_TOKEN", notificationUUID: uuid(), signedDate: 3, externalPurchaseToken: { bundleId: BUNDLE } });
    expect((await postJws(ext)).status).toBe(200);
    expect(await testEnv().DB.prepare("SELECT notification_type, original_tx_id FROM appstore_notifications").all()).toMatchObject({
      results: [{ notification_type: "RENEWAL_EXTENSION", original_tx_id: null }],
    });
  });

  it("body sai dang tra 400, qua 64 KB tra 413", async () => {
    for (const b of ["not json", "{}", "[]", JSON.stringify({ signedPayload: 5 }), JSON.stringify({ signedPayload: "a.b" }), JSON.stringify({ signedPayload: "a.b.c" })]) {
      expect((await post(b)).status).toBe(400);
    }
    expect((await post(JSON.stringify({ signedPayload: "a.b.c", pad: "x".repeat(70_000) }))).status).toBe(413);
    expect(await count()).toBe(0);
  });

  it("console khong chua originalTransactionId hay JWS", async () => {
    const log = vi.spyOn(console, "log");
    const err = vi.spyOn(console, "error");
    const jws = await note(chain, {}, {}, { tx: await chain.sign(tx({ originalTransactionId: "SECRET-TX-77" })) });
    await postJws(jws);
    await postJws("a.b.c");
    const all = JSON.stringify([...log.mock.calls, ...err.mock.calls]);
    expect(all).not.toContain("SECRET-TX-77");
    expect(all).not.toContain(jws.slice(10, 40));
  });
});
