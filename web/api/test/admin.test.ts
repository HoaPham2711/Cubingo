import { beforeEach, describe, expect, it, vi } from "vitest";
import { clock } from "../src/http";
import { call, testEnv } from "./helpers";

const TOKEN = "admin-test-token"; // khớp vitest.config.ts
const db = () => testEnv().DB;

function adm(path: string, opts: { method?: string; body?: unknown; token?: string | null; ip?: string } = {}): Promise<Response> {
  const headers: Record<string, string> = { "cf-connecting-ip": opts.ip ?? "203.0.113.5" };
  const token = opts.token === undefined ? TOKEN : opts.token;
  if (token !== null) headers.authorization = `Bearer ${token}`;
  if (opts.body !== undefined) headers["content-type"] = "application/json";
  return call(`/api/v1/admin${path}`, { method: opts.method ?? "GET", headers, body: opts.body === undefined ? undefined : JSON.stringify(opts.body) });
}

beforeEach(async () => {
  for (const t of ["feedback", "appstore_notifications", "web_events", "web_referrers"]) await db().prepare(`DELETE FROM ${t}`).run();
  await db().prepare("DELETE FROM rate WHERE key LIKE 'adm%'").run();
});

async function addFeedback(id: string, status: string, createdAt: number, message = `msg ${id}`) {
  await db()
    .prepare(
      `INSERT INTO feedback (id, type, message, email, diagnostics, app_version, client_time, created_at, status, updated_at)
       VALUES (?1, 'bug', ?2, 'a@example.com', 'diag', '1.0.0', 1, ?3, ?4, ?3)`,
    )
    .bind(id, message, createdAt, status)
    .run();
}
const ID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

describe("xac thuc admin", () => {
  it("thieu token tra 401", async () => {
    for (const token of [null, "", "admin-test-tokem", "admin-test-token-x"]) {
      const r = await adm("/feedback", { token, ip: "203.0.113.50" });
      expect(r.status).toBe(401);
      expect(((await r.json()) as { error: string }).error).toBe("unauthorized");
    }
    expect((await adm("/feedback", { ip: "203.0.113.50" })).status).toBe(200);
  });

  it("ADMIN_TOKEN rong thi khong ai vao duoc", async () => {
    const headers = { authorization: "Bearer ", "cf-connecting-ip": "203.0.113.51" };
    expect((await call("/api/v1/admin/feedback", { headers }, { ADMIN_TOKEN: "" })).status).toBe(401);
  });

  it("sai token 10 lan khoa ip mot gio", async () => {
    const t0 = Date.UTC(2030, 0, 1, 10, 0, 0);
    vi.spyOn(clock, "now").mockReturnValue(t0);
    for (let i = 0; i < 10; i++) expect((await adm("/feedback", { token: "wrong", ip: "203.0.113.9" })).status).toBe(401);
    // Khoá: kể cả token đúng cũng bị chặn.
    const locked = await adm("/feedback", { ip: "203.0.113.9" });
    expect(locked.status).toBe(429);
    // IP khác không bị ảnh hưởng.
    expect((await adm("/feedback", { ip: "203.0.113.10" })).status).toBe(200);
    // Hết giờ ⇒ mở lại.
    vi.spyOn(clock, "now").mockReturnValue(t0 + 3_600_000);
    expect((await adm("/feedback", { ip: "203.0.113.9" })).status).toBe(200);
  });

  it("khoa du mot gio ke ca khi vuot moc gio dong ho", async () => {
    const t0 = Date.UTC(2030, 0, 3, 10, 59, 50);
    vi.spyOn(clock, "now").mockReturnValue(t0);
    for (let i = 0; i < 10; i++) expect((await adm("/feedback", { token: "wrong", ip: "203.0.113.12" })).status).toBe(401);
    // Sang giờ đồng hồ mới (11:00:10) — cửa sổ đếm đã đổi nhưng khoá vẫn còn.
    vi.spyOn(clock, "now").mockReturnValue(t0 + 20_000);
    expect((await adm("/feedback", { ip: "203.0.113.12" })).status).toBe(429);
    vi.spyOn(clock, "now").mockReturnValue(t0 + 3_599_000);
    expect((await adm("/feedback", { ip: "203.0.113.12" })).status).toBe(429);
    vi.spyOn(clock, "now").mockReturnValue(t0 + 3_600_000);
    expect((await adm("/feedback", { ip: "203.0.113.12" })).status).toBe(200);
  });

  it("9 lan sai chua khoa", async () => {
    vi.spyOn(clock, "now").mockReturnValue(Date.UTC(2030, 0, 2, 10, 0, 0));
    for (let i = 0; i < 9; i++) expect((await adm("/feedback", { token: "wrong", ip: "203.0.113.11" })).status).toBe(401);
    expect((await adm("/feedback", { ip: "203.0.113.11" })).status).toBe(200);
  });
});

describe("feedback admin", () => {
  it("liet ke feedback open", async () => {
    await addFeedback(ID(1), "open", 1000, "x".repeat(300));
    await addFeedback(ID(2), "done", 2000);
    await addFeedback(ID(3), "open", 3000);
    const r = await adm("/feedback?status=open");
    expect(r.status).toBe(200);
    const { items } = (await r.json()) as { items: Record<string, unknown>[] };
    expect(items.map((i) => i.id)).toEqual([ID(3), ID(1)]);
    expect(Object.keys(items[0]).sort()).toEqual(["app_version", "created_at", "id", "preview", "status", "type"]);
    expect((items[1].preview as string).length).toBe(120);
    const all = (await (await adm("/feedback?status=all")).json()) as { items: unknown[] };
    expect(all.items).toHaveLength(3);
    const done = (await (await adm("/feedback?status=done&limit=1")).json()) as { items: { id: string }[] };
    expect(done.items.map((i) => i.id)).toEqual([ID(2)]);
    expect((await adm("/feedback?limit=2")).status).toBe(200);
    expect((await adm("/feedback?limit=201")).status).toBe(400);
    expect((await adm("/feedback?status=spam")).status).toBe(400);
  });

  it("limit 200 tra du 200 ban", async () => {
    const stmts = Array.from({ length: 201 }, (_, i) =>
      db()
        .prepare(`INSERT INTO feedback (id, type, message, app_version, client_time, created_at, updated_at) VALUES (?1, 'bug', 'm', '1', 1, ?2, ?2)`)
        .bind(ID(100 + i), i),
    );
    await db().batch(stmts);
    const { items } = (await (await adm("/feedback?status=open&limit=200")).json()) as { items: unknown[] };
    expect(items).toHaveLength(200);
  });

  it("doi status va note", async () => {
    await addFeedback(ID(5), "open", 1000);
    vi.spyOn(clock, "now").mockReturnValue(5000);
    const r = await adm(`/feedback/${ID(5)}`, { method: "POST", body: { status: "done", note: "fixed in 1.1" } });
    expect(r.status).toBe(200);
    const detail = (await (await adm(`/feedback/${ID(5)}`)).json()) as Record<string, unknown>;
    expect(detail).toMatchObject({ id: ID(5), status: "done", note: "fixed in 1.1", message: `msg ${ID(5)}`, diagnostics: "diag", email: "a@example.com", updated_at: 5000 });
    // Chỉ note ⇒ giữ status.
    await adm(`/feedback/${ID(5)}`, { method: "POST", body: { note: "n2" } });
    expect(await db().prepare("SELECT status, note FROM feedback WHERE id = ?").bind(ID(5)).first()).toEqual({ status: "done", note: "n2" });
    expect((await adm(`/feedback/${ID(5)}`, { method: "POST", body: {} })).status).toBe(400);
    expect((await adm(`/feedback/${ID(5)}`, { method: "POST", body: { status: "closed" } })).status).toBe(400);
    expect((await adm(`/feedback/${ID(6)}`, { method: "POST", body: { status: "done" } })).status).toBe(404);
    expect((await adm(`/feedback/not-an-id`)).status).toBe(404);
  });

  it("xoa feedback", async () => {
    await addFeedback(ID(7), "open", 1000);
    await addFeedback(ID(8), "open", 1000);
    expect((await adm(`/feedback/${ID(7)}/delete`, { method: "POST" })).status).toBe(200);
    expect((await adm(`/feedback/${ID(7)}`)).status).toBe(404);
    expect((await adm(`/feedback/${ID(7)}/delete`, { method: "POST" })).status).toBe(404);
    expect((await db().prepare("SELECT id FROM feedback").all()).results).toEqual([{ id: ID(8) }]);
  });
});

describe("subscription events", () => {
  it("subscription events theo since", async () => {
    const ins = (u: string, signed: number) =>
      db()
        .prepare(
          `INSERT INTO appstore_notifications (notification_uuid, notification_type, subtype, environment, signed_date, received_at,
             product_id, original_tx_id, price, currency, storefront, transaction_id)
           VALUES (?1, 'DID_RENEW', NULL, 'Production', ?2, ?2, 'p.yearly', 'otx', 999, 'USD', 'USA', 'tx')`,
        )
        .bind(u, signed)
        .run();
    await ins("u1", 100);
    await ins("u2", 200);
    await ins("u3", 300);
    const r = await adm("/subscription-events?since=200");
    expect(r.status).toBe(200);
    const { items } = (await r.json()) as { items: Record<string, unknown>[] };
    expect(items).toEqual([
      { notification_uuid: "u2", type: "DID_RENEW", subtype: null, environment: "Production", signed_date: 200, product_id: "p.yearly", original_tx_id: "otx", price: 999, currency: "USD", storefront: "USA" },
      { notification_uuid: "u3", type: "DID_RENEW", subtype: null, environment: "Production", signed_date: 300, product_id: "p.yearly", original_tx_id: "otx", price: 999, currency: "USD", storefront: "USA" },
    ]);
    const page = (await (await adm("/subscription-events?limit=2")).json()) as { items: { notification_uuid: string }[] };
    expect(page.items.map((i) => i.notification_uuid)).toEqual(["u1", "u2"]);
    expect((await adm("/subscription-events?limit=501")).status).toBe(400);
    expect((await adm("/subscription-events?since=abc")).status).toBe(400);
  });
});

describe("stats", () => {
  it("stats gom theo trang va referrer", async () => {
    const t = Date.UTC(2030, 3, 10, 12);
    vi.spyOn(clock, "now").mockReturnValue(t);
    const ev = (day: string, page: string, event: string, country: string, device: string, n: number) =>
      db()
        .prepare("INSERT INTO web_events (day, page, event, detail, source, country, device, n) VALUES (?, ?, ?, '-', '-', ?, ?, ?)")
        .bind(day, page, event, country, device, n);
    const ref = (day: string, domain: string, n: number) => db().prepare("INSERT INTO web_referrers (day, domain, n) VALUES (?, ?, ?)").bind(day, domain, n);
    await db().batch([
      ev("20300410", "/", "pageview", "US", "ios", 5),
      ev("20300409", "/", "pageview", "VN", "desktop", 2),
      ev("20300409", "/support/", "pageview", "US", "ios", 3),
      ev("20300410", "/support/", "engaged", "US", "ios", 9),
      ev("20300301", "/", "pageview", "US", "ios", 100), // ngoài 7 ngày
      ref("20300410", "news.example.org", 4),
      ref("20300409", "news.example.org", 1),
      ref("20300408", "search.example.net", 2),
      ref("20300301", "old.example.com", 50),
    ]);
    const r = await adm("/stats?days=7");
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({
      days: 7,
      pages: [{ page: "/", views: 7 }, { page: "/support/", views: 3 }],
      referrers: [{ domain: "news.example.org", n: 5 }, { domain: "search.example.net", n: 2 }],
      countries: [{ country: "US", n: 8 }, { country: "VN", n: 2 }],
      devices: [{ device: "ios", n: 8 }, { device: "desktop", n: 2 }],
    });
    // days kẹp 1–400, mặc định 30.
    expect(((await (await adm("/stats?days=9999")).json()) as { days: number }).days).toBe(400);
    expect(((await (await adm("/stats")).json()) as { days: number }).days).toBe(30);
    expect(((await (await adm("/stats?days=x")).json()) as { days: number }).days).toBe(30);
  });
});
