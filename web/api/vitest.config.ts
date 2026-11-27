import { cloudflareTest, readD1Migrations } from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";

// Test KHÔNG đọc wrangler.jsonc (file sinh, mang định danh của app): mọi binding khai ở đây bằng giá trị giả trung tính.
// D1 cục bộ trong Miniflare, migration nạp từ ./migrations ở test/setup.ts. Không mạng: JWKS App Check tiêm qua
// APP_CHECK_JWKS (test/helpers.ts).
export default defineConfig(async () => {
  const migrations = await readD1Migrations("./migrations");
  return {
    plugins: [
      cloudflareTest({
        main: "./src/index.ts",
        miniflare: {
          compatibilityDate: "2026-08-22",
          compatibilityFlags: ["nodejs_compat"],
          d1Databases: ["DB"],
          bindings: {
            TEST_MIGRATIONS: migrations,
            ASSN_BUNDLE_ID: "com.example.app",
            ASSN_ENVIRONMENTS: "Production,Sandbox",
            APP_CHECK_PROJECTS: "test-proj:123456",
            APP_CHECK_REQUIRED: "1",
            PUBLIC_ORIGIN: "https://example.com",
            ADMIN_TOKEN: "admin-test-token",
          },
        },
      }),
    ],
    test: { setupFiles: ["./test/setup.ts"] },
  };
});
