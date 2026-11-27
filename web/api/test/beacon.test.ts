import { beforeEach, describe, expect, it, vi } from "vitest";
import { clock } from "../src/http";
import { call, testEnv } from "./helpers";

type Row = { day: string; page: string; event: string; detail: string; source: string; country: string; device: string; n: number };
const rows = async () => (await testEnv().DB.prepare("SELECT * FROM web_events ORDER BY page, event, detail, device, country").all<Row>()).results;
const refs = async () => (await testEnv().DB.prepare("SELECT domain, n FROM web_referrers ORDER BY domain").all<{ domain: string; n: number }>()).results;

const browser = {
  origin: "https://example.com", // PUBLIC_ORIGIN của vitest.config.ts
  "sec-fetch-site": "same-origin",
  "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1",
  "cf-ipcountry": "de",
  "content-type": "text/plain;charset=UTF-8",
};
const beacon = (body: unknown, headers: Record<string, string | null> = {}) => {
  const h: Record<string, string> = {};
  for (const [k, v] of Object.entries({ ...browser, ...headers })) if (v !== null) h[k] = v;
  return call("/api/v1/public/beacon", { method: "POST", headers: h, body: typeof body === "string" ? body : JSON.stringify(body) });
};

beforeEach(async () => {
  await testEnv().DB.prepare("DELETE FROM web_events").run();
  await testEnv().DB.prepare("DELETE FROM web_referrers").run();
  await testEnv().DB.prepare("DELETE FROM rate WHERE key LIKE 'bcn:%'").run();
  vi.spyOn(clock, "now").mockReturnValue(Date.UTC(2030, 6, 4, 8));
});

describe("POST /api/v1/public/beacon", () => {
  it("beacon hop le cong n", async () => {
    const r = await beacon({ p: "/support/" });
    expect(r.status).toBe(204);
    await beacon({ p: "/support/", e: "pageview" });
    await beacon({ p: "/", e: "pageview", d: "news.example.org" });
    await beacon({ p: "/", e: "engaged", d: "30_120s" });
    await beacon({ p: "/", e: "outbound", d: "app_store" });
    const base = { day: "20300704", country: "DE", device: "ios", detail: "-" };
    expect(await rows()).toEqual([
      { ...base, page: "/", event: "engaged", detail: "30_120s", source: "-", n: 1 },
      { ...base, page: "/", event: "outbound", detail: "app_store", source: "-", n: 1 },
      { ...base, page: "/", event: "pageview", source: "referral", n: 1 },
      { ...base, page: "/support/", event: "pageview", source: "direct", n: 2 },
    ]);
    expect(await refs()).toEqual([{ domain: "news.example.org", n: 1 }]);
  });

  it("beacon bot hoac thieu sec-fetch khong dem", async () => {
    const cases: Record<string, string | null>[] = [
      { "user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1)" },
      { "user-agent": "curl/8.4.0" },
      { "user-agent": null },
      { "sec-fetch-site": null },
      { "sec-fetch-site": "cross-site" },
      { "sec-fetch-site": "none" },
      { origin: "https://evil.example.net" },
      { origin: null },
      { "x-app-owner": "1" },
    ];
    for (const h of cases) expect((await beacon({ p: "/" }, h)).status).toBe(204);
    expect(await rows()).toEqual([]);
    expect(await refs()).toEqual([]);
    // Chứng: cùng beacon với header trình duyệt đầy đủ thì có đếm.
    await beacon({ p: "/" });
    expect(await rows()).toHaveLength(1);
  });

  it("gia tri la thi chuan hoa hoac bo, khong ghi dinh danh", async () => {
    await beacon({ p: "/Privacy?utm=x#top" }); // query/hash bị cắt, chữ thường
    await beacon({ p: "javascript:alert(1)" }); // ⇒ other
    await beacon({ p: "/" + "a".repeat(200) }); // quá dài ⇒ other
    await beacon({ p: "/", e: "hack" }); // sự kiện lạ ⇒ bỏ
    await beacon({ p: "/", e: "engaged", d: "forever" }); // detail lạ ⇒ bỏ
    await beacon({ p: "/", e: "outbound", d: "user@example.com" }); // detail sai dạng ⇒ bỏ
    await beacon({ p: "/", d: "not a domain" }); // referrer sai ⇒ direct, không ghi referrer
    await beacon("not json");
    await beacon({ e: "pageview" }); // thiếu p
    await beacon({ p: "/", pad: "x".repeat(4000) }); // quá lớn
    expect((await rows()).map((r) => [r.page, r.event, r.source, r.n])).toEqual([
      ["/", "pageview", "direct", 1],
      ["/privacy/", "pageview", "direct", 1],
      ["other", "pageview", "direct", 2],
    ]);
    expect(await refs()).toEqual([]);
  });

  it("referrer bo www va nhan utm", async () => {
    await beacon({ p: "/", d: "www.News.Example.org" });
    await beacon({ p: "/", d: "utm:launch_1" });
    expect(await refs()).toEqual([{ domain: "news.example.org", n: 1 }, { domain: "utm:launch_1", n: 1 }]);
  });

  it("thieu cf-ipcountry thi XX, android va desktop tach rieng", async () => {
    await beacon({ p: "/" }, { "cf-ipcountry": null, "user-agent": "Mozilla/5.0 (Linux; Android 14)" });
    await beacon({ p: "/" }, { "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)" });
    expect((await rows()).map((r) => [r.country, r.device])).toEqual([
      ["XX", "android"],
      ["DE", "desktop"],
    ]);
  });

  it("qua 120 beacon mot gio tu mot ip thi khong dem them", async () => {
    const ip = { "cf-connecting-ip": "198.51.100.77" };
    for (let i = 0; i < 121; i++) expect((await beacon({ p: "/" }, ip)).status).toBe(204);
    await beacon({ p: "/" }, { "cf-connecting-ip": "198.51.100.78" });
    expect((await rows()).map((r) => r.n)).toEqual([121]);
  });

  it("duong dan sau qua 4 doan thanh other", async () => {
    await beacon({ p: "/a/b/c/d/" });
    await beacon({ p: "/a/b/c/d/e/" });
    await beacon({ p: "/a/b/c/d/e.html" });
    expect((await rows()).map((r) => r.page)).toEqual(["/a/b/c/d/", "other"]);
    expect((await rows()).map((r) => r.n)).toEqual([1, 2]);
  });
});
