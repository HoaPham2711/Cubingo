import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { clock } from "../src/http";
import { appCheckToken, call, setupAppCheckKeys, testEnv } from "./helpers";
import type { Env } from "../src/env";

beforeAll(setupAppCheckKeys);
// D1 không tự reset giữa các test ⇒ dọn bảng và bộ đếm của riêng feedback.
beforeEach(async () => {
  await testEnv().DB.prepare("DELETE FROM feedback").run();
  await testEnv().DB.prepare("DELETE FROM rate WHERE key LIKE 'fb:%'").run();
});

const valid = { type: "bug", message: "Crash when exporting", email: "a@example.com", diagnostics: "app: 1.0.0", appVersion: "1.0.0", clientTime: 1_790_000_000_000 };

async function send(body: unknown, opts: { token?: string | null; ip?: string; env?: Partial<Env> } = {}): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json", "cf-connecting-ip": opts.ip ?? "198.51.100.1" };
  const token = opts.token === undefined ? await appCheckToken() : opts.token;
  if (token) headers["x-firebase-appcheck"] = token;
  return call("/api/v1/feedback", { method: "POST", headers, body: typeof body === "string" ? body : JSON.stringify(body) }, opts.env);
}
const rows = async () => (await testEnv().DB.prepare("SELECT * FROM feedback").all<Record<string, unknown>>()).results;
const errorOf = async (r: Response) => ((await r.json()) as { error: string }).error;

describe("POST /api/v1/feedback", () => {
  it("nhan feedback hop le tra 201 va ghi D1", async () => {
    vi.spyOn(clock, "now").mockReturnValue(Date.UTC(2030, 5, 1));
    const r = await send(valid);
    expect(r.status).toBe(201);
    expect(await r.json()).toEqual({ ok: true });
    const all = await rows();
    expect(all).toHaveLength(1);
    expect(all[0]).toMatchObject({
      type: "bug", message: valid.message, email: valid.email, diagnostics: valid.diagnostics, app_version: "1.0.0",
      client_time: valid.clientTime, created_at: Date.UTC(2030, 5, 1), updated_at: Date.UTC(2030, 5, 1), status: "open", note: "",
    });
    expect(JSON.stringify(all[0])).not.toContain("198.51.100.1");
  });
  it("thieu email va diagnostics van nhan, luu chuoi rong", async () => {
    const { email: _e, diagnostics: _d, ...min } = valid;
    expect((await send(min)).status).toBe(201);
    expect((await rows())[0]).toMatchObject({ email: "", diagnostics: "" });
  });
  it("thieu app check o prod tra 401 app_check_failed", async () => {
    const r = await send(valid, { token: null });
    expect(r.status).toBe(401);
    expect(await errorOf(r)).toBe("app_check_failed");
    expect(await rows()).toHaveLength(0);
  });
  it("token app check sai audience bi tu choi o route", async () => {
    const r = await send(valid, { token: await appCheckToken({ aud: ["projects/999999"] }) });
    expect(r.status).toBe(401);
    expect(await errorOf(r)).toBe("app_check_failed");
  });
  it("thieu app check o dev van nhan", async () => {
    const r = await send(valid, { token: null, env: { APP_CHECK_REQUIRED: "0", APP_CHECK_PROJECTS: "" } });
    expect(r.status).toBe(201);
    expect(await rows()).toHaveLength(1);
  });
  it("APP_CHECK_REQUIRED vang mat thi van doi app check", async () => {
    const r = await send(valid, { token: null, env: { APP_CHECK_REQUIRED: undefined as unknown as string } });
    expect(r.status).toBe(401);
  });
  it("message rong sau trim tra 400", async () => {
    for (const [i, message] of ["", "   \n\t "].entries()) {
      const r = await send({ ...valid, message }, { ip: `198.51.100.${20 + i}` });
      expect(r.status).toBe(400);
      expect(await errorOf(r)).toBe("bad_request");
    }
    expect(await rows()).toHaveLength(0);
  });
  it("message 4000 ky tu qua, 4001 tra 400", async () => {
    expect((await send({ ...valid, message: "a".repeat(4000) })).status).toBe(201);
    expect((await send({ ...valid, message: "a".repeat(4001) }, { ip: "198.51.100.30" })).status).toBe(400);
  });
  it("email qua 320 tra 400", async () => {
    expect((await send({ ...valid, email: "x".repeat(320) })).status).toBe(201);
    expect((await send({ ...valid, email: "x".repeat(321) }, { ip: "198.51.100.31" })).status).toBe(400);
  });
  it("type la, clientTime sai, appVersion sai, diagnostics qua dai tra 400", async () => {
    const bads = [{ type: "spam" }, { clientTime: 0 }, { clientTime: 1.5 }, { clientTime: "now" }, { appVersion: "" }, { appVersion: "v".repeat(65) }, { diagnostics: "x".repeat(12001) }];
    for (const [i, bad] of bads.entries()) {
      expect((await send({ ...valid, ...bad }, { ip: `198.51.100.${40 + i}` })).status, JSON.stringify(bad)).toBe(400);
    }
    expect(await rows()).toHaveLength(0);
  });
  it("JSON hong tra 400, khong 500", async () => {
    const r = await send("{not json");
    expect(r.status).toBe(400);
  });
  it("body qua 32KB tra 413", async () => {
    const r = await send({ ...valid, diagnostics: "x".repeat(33 * 1024) });
    expect(r.status).toBe(413);
    expect(await rows()).toHaveLength(0);
  });
  it("vuot 10 lan mot gio mot IP tra 429", async () => {
    vi.spyOn(clock, "now").mockReturnValue(Date.UTC(2031, 0, 1, 8));
    for (let i = 0; i < 10; i++) expect((await send(valid, { ip: "198.51.100.50" })).status).toBe(201);
    const r = await send(valid, { ip: "198.51.100.50" });
    expect(r.status).toBe(429);
    expect(await errorOf(r)).toBe("rate_limited");
    expect((await send(valid, { ip: "198.51.100.51" })).status).toBe(201);
    expect(await rows()).toHaveLength(11);
  });
  it("request khong co app check khong dot han muc cua IP", async () => {
    vi.spyOn(clock, "now").mockReturnValue(Date.UTC(2031, 0, 3, 8));
    for (let i = 0; i < 13; i++) await send(valid, { token: null, ip: "198.51.100.70" });
    expect((await send(valid, { ip: "198.51.100.70" })).status).toBe(201);
  });
  it("cham tran 500 mot ngay toan he thong tra 429", async () => {
    const t = Date.UTC(2031, 0, 4, 12);
    vi.spyOn(clock, "now").mockReturnValue(t);
    const sec = Math.floor(t / 1000);
    await testEnv().DB.prepare("INSERT INTO rate (key, window_start, count) VALUES ('fb:all', ?1, 500)").bind(sec - (sec % 86400)).run();
    const r = await send(valid, { ip: "198.51.100.80" });
    expect(r.status).toBe(429);
    expect(await errorOf(r)).toBe("rate_limited");
    expect(await rows()).toHaveLength(0);
  });
});

describe("app", () => {
  it("duong dan khong co tra 404 JSON", async () => {
    const r = await call("/nope");
    expect(r.status).toBe(404);
    expect(await errorOf(r)).toBe("not_found");
  });
});
