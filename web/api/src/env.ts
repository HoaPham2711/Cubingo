/** Binding + biến môi trường của Worker API. Biến (vars) sinh vào wrangler.jsonc từ app.config.toml; secret: ADMIN_TOKEN. */
export type Env = {
  DB: D1Database;
  /** Bundle id mà App Store Server Notifications phải mang để được ghi — bundle STORE ở CẢ prod lẫn dev: Apple gửi
   *  thông báo theo bản ghi App Store Connect (bản Store), Sandbox về dev cũng vậy; bản .internal không có bản ghi đó.
   *  API không có biến "bundle của app đang chạy" (chỉ AASA của site cần bundle .internal ở dev — biến APP_IDS của site). */
  ASSN_BUNDLE_ID: string;
  /** Môi trường App Store Server Notifications được ghi, phân cách dấu phẩy (prod "Production", dev "Sandbox"). */
  ASSN_ENVIRONMENTS: string;
  /** Project Firebase được nhận cho App Check: `<projectId>:<projectNumber>`, nhiều mục phân cách dấu phẩy; rỗng = không nhận ai. */
  APP_CHECK_PROJECTS: string;
  /** "1" (prod) = bắt buộc App Check; "0" (dev) = không bắt buộc. Vắng/giá trị khác ⇒ coi như bắt buộc (đóng khi cấu hình hỏng). */
  APP_CHECK_REQUIRED: string;
  /** Origin công khai của site ở môi trường này. */
  PUBLIC_ORIGIN: string;
  ADMIN_TOKEN: string;
  /** CHỈ test: JWKS JSON tiêm vào thay cho fetch JWKS thật của Google. KHÔNG khai ở wrangler.jsonc. */
  APP_CHECK_JWKS?: string;
};

export type HonoEnv = { Bindings: Env };
