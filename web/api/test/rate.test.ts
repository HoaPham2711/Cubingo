import { beforeEach, describe, expect, it, vi } from "vitest";
import { clock } from "../src/http";
import { checkRate } from "../src/rate";
import { testEnv } from "./helpers";

// D1 không tự reset giữa các test ⇒ dọn bộ đếm của riêng file này.
beforeEach(async () => {
  await testEnv().DB.prepare("DELETE FROM rate WHERE key LIKE 't:%'").run();
});

describe("checkRate", () => {
  it("cho qua dung limit lan trong mot cua so roi chan", async () => {
    vi.spyOn(clock, "now").mockReturnValue(Date.UTC(2030, 0, 1, 10, 5));
    for (let i = 0; i < 3; i++) expect(await checkRate(testEnv().DB, "t:a", 3, 3600)).toBe(true);
    expect(await checkRate(testEnv().DB, "t:a", 3, 3600)).toBe(false);
  });
  it("sang cua so moi thi dem lai tu dau", async () => {
    const t = Date.UTC(2030, 0, 1, 10, 59);
    const spy = vi.spyOn(clock, "now").mockReturnValue(t);
    for (let i = 0; i < 2; i++) await checkRate(testEnv().DB, "t:b", 2, 3600);
    expect(await checkRate(testEnv().DB, "t:b", 2, 3600)).toBe(false);
    spy.mockReturnValue(Date.UTC(2030, 0, 1, 11, 0));
    expect(await checkRate(testEnv().DB, "t:b", 2, 3600)).toBe(true);
  });
  it("D1 khong tra hang thi chan (dong khi loi)", async () => {
    const db = { prepare: () => ({ bind: () => ({ first: async () => null }) }) } as unknown as D1Database;
    expect(await checkRate(db, "t:e", 10, 60)).toBe(false);
  });
  it("hai khoa dem rieng", async () => {
    vi.spyOn(clock, "now").mockReturnValue(Date.UTC(2030, 0, 2));
    expect(await checkRate(testEnv().DB, "t:c", 1, 60)).toBe(true);
    expect(await checkRate(testEnv().DB, "t:c", 1, 60)).toBe(false);
    expect(await checkRate(testEnv().DB, "t:d", 1, 60)).toBe(true);
  });
});

describe("migration 0001", () => {
  it("migration 0001 khong co bang share link", async () => {
    const { results } = await testEnv()
      .DB.prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
      .all<{ name: string }>();
    const own = results.map((r) => r.name).filter((n) => !n.startsWith("sqlite_") && !n.startsWith("_cf_") && n !== "d1_migrations");
    // Đúng tập bảng của template — không mang bảng share link/user/file/hồ sơ của app nguồn.
    expect(own).toEqual(["appstore_notifications", "feedback", "rate", "web_events", "web_referrers"]);
    for (const n of own) expect(n).not.toMatch(/link|user|file|profile|share|claim/);
  });
});
