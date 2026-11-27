import { describe, expect, it } from "vitest";

// m.js là JS thuần trong public/ (đồng bộ, gắn hợp đồng beacon của API) — nạp động để tsc không phải đọc nó.
// Không có `document` trong môi trường node ⇒ import không tự chạy start().
type MJs = {
  engagedBucket: (ms: number) => string;
  referrerOf: (referrer: string, search: string, ownHost: string) => string | undefined;
};
const path: string = "../public/m.js";
const m = (await import(/* @vite-ignore */ path)) as MJs;

describe("m.js", () => {
  it("engaged dung khoang cua api", () => {
    // Khớp ENGAGED_BUCKETS ở web/api/src/routes/beacon.ts.
    expect([5000, 10000, 60000, 200000].map(m.engagedBucket)).toEqual(["lt10s", "10_30s", "30_120s", "gt2m"]);
  });

  it("nguon utm truoc ten mien gioi thieu khac site", () => {
    expect(m.referrerOf("https://www.search.example/q", "?utm_source=News Letter!", "example.com")).toBe("utm:newsletter");
    expect(m.referrerOf("https://www.search.example/q", "", "example.com")).toBe("search.example");
    expect(m.referrerOf("https://www.example.com/privacy/", "", "example.com")).toBeUndefined();
    expect(m.referrerOf("", "", "example.com")).toBeUndefined();
  });
});
