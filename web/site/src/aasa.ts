/**
 * Tệp apple-app-site-association (Universal Link) dựng từ biến môi trường của Worker — `wrangler.jsonc` (file sinh từ
 * app.config.toml) đặt `APP_IDS` = "<team>.<bundle>" (bundle Store ở prod, bundle Internal ở dev) và `APP_PATHS` = JSON
 * của `[web] app_paths`. Nhờ vậy dev và prod phục vụ đúng tệp riêng mà không cần API.
 */

export interface AasaBody {
  applinks: { details: { appIDs: string[]; components: { "/": string }[] }[] };
}

/** `paths` rỗng (app không mở đường dẫn nào) hoặc không có app id ⇒ `details: []` — tệp vẫn hợp lệ. */
export function aasaBody(appIds: string[], paths: string[]): AasaBody {
  if (appIds.length === 0 || paths.length === 0) return { applinks: { details: [] } };
  return { applinks: { details: [{ appIDs: appIds, components: paths.map((p) => ({ "/": p })) }] } };
}

/** `APP_IDS`: danh sách ngăn bằng dấu phẩy; bỏ khoảng trắng hai đầu và phần tử rỗng. */
export function parseAppIds(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s !== "");
}

/** `APP_PATHS`: mảng JSON các chuỗi bắt đầu bằng "/"; hỏng/sai dạng ⇒ []; phần tử sai bị bỏ. */
export function parseAppPaths(raw: string | undefined): string[] {
  let v: unknown;
  try {
    v = JSON.parse(raw ?? "[]");
  } catch {
    return [];
  }
  if (!Array.isArray(v)) return [];
  return v.filter((p): p is string => typeof p === "string" && p.startsWith("/"));
}
