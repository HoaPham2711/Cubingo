import { describe, expect, it } from "vitest";

// App nướng cứng các đường dẫn này (Core/Bootstrap/AppConfig.swift): `/`, `/privacy/`, `/terms/`, `/support/` — trang
// phải có trong public/ (Workers static assets phục vụ `<dir>/index.html` cho `<dir>/`).
const pages = import.meta.glob("../public/**/index.html", { query: "?raw", import: "default", eager: true }) as Record<
  string,
  string
>;

describe("trang bat bien", () => {
  it("duong dan bat bien privacy terms support ton tai trong public", () => {
    for (const p of ["../public/index.html", "../public/privacy/index.html", "../public/terms/index.html",
      "../public/support/index.html"]) {
      expect(Object.keys(pages)).toContain(p);
      expect(pages[p]).toMatch(/<html[\s>]/);
    }
  });
});
