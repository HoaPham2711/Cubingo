import { defineConfig } from "vitest/config";

// Worker site không cần Miniflare: test gọi thẳng `worker.fetch` với env giả (ASSETS/API là đối tượng có `fetch`).
// Không đọc wrangler.jsonc (file sinh, mang định danh của app) — giá trị trong test là giá trị giả trung tính.
export default defineConfig({
  test: { environment: "node", include: ["test/**/*.test.ts"] },
});
