#!/usr/bin/env node
// Kiểm cấu hình rồi (với --deploy) chạy deploy của web/ theo đúng thứ tự — `npm run deploy:dev|prod` gọi file này.
//
//   node web/scripts/predeploy.mjs <dev|prod>            # chỉ kiểm: rc 0 đủ · 1 từ chối (mỗi lý do một dòng TỪ CHỐI:) · 2 sai cách dùng
//   node web/scripts/predeploy.mjs <dev|prod> --deploy   # kiểm, rồi (prod) cổng site, rồi API (chỉ khi có), rồi site
//
// Đọc hai file SINH `web/api/wrangler.jsonc` + `web/site/wrangler.jsonc` (một nguồn: `appconfig.py render` từ
// app.config.toml — Node không có trình đọc TOML; JSONC ở đây = JSON có các dòng `//` đầu file). Môi trường `prod` = khối
// gốc, `dev` = `env.dev`. App CÓ API ⇔ site của môi trường đó có service binding `API` (sinh khi `features.web_api`);
// không có ⇒ chỉ site được deploy và chỉ site được kiểm (Ruling 11: web_api tắt ⇒ không có API — file api vẫn sinh vì
// mã api là lớp đồng bộ, nhưng không dùng). Từ chối khi:
//   - thiếu/hỏng file sinh của site (hoặc của api khi có API) — chạy `python3 tools/common/appconfig.py render`;
//   - biến CHỈ-TEST `APP_CHECK_JWKS` ở bất kỳ đâu trong hai file (khoá tiêm thay JWKS của Google ⇒ ai có khoá riêng tương ứng
//     giả được App Check). Script KHÔNG thấy biến đặt bằng `wrangler secret put` — không bao giờ đặt nó làm secret;
//   - (khi có API) D1 `database_id` còn "TODO-d1-id" (`cloudflare.d1_<env>` rỗng), `APP_CHECK_PROJECTS` rỗng ở prod
//     (`firebase.app_check_prod`; ở dev chỉ CẢNH BÁO — dev có `APP_CHECK_REQUIRED` "0", App Check không có tác dụng),
//     `ASSN_ENVIRONMENTS` rỗng (mọi App Store Server Notification bị bỏ);
//   - (prod, khi có API) host của `PUBLIC_ORIGIN` (= `web.host_prod`) là host giữ chỗ/dành riêng (`example.com|net|org`,
//     `*.example|test|invalid|localhost`, `localhost` — cùng luật `appconfig.is_reserved_host`). App chỉ site: file sinh
//     không mang host prod ⇒ `check_site.py --release` (chạy TRƯỚC mọi deploy prod) bắt cùng lỗi.
// --deploy, sau khi kiểm qua: prod chạy `check_sitemap.py`, `changelog.py --check`, `check_site.py --release` (dừng ở lỗi
// đầu); rồi `npm run deploy:<env> -w api` CHỈ khi có API (API trước site: binding của site trỏ Worker API phải có sẵn);
// rồi `npm run deploy:<env> -w site`. Migration D1 (`--remote`) là bước tay TRƯỚC đó (web/README.md §"Deploy").
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const D1_TODO = "TODO-d1-id";
// Giữ khớp tools/common/appconfig.py (RESERVED_DOMAINS / RESERVED_TLDS).
const RESERVED_DOMAINS = ["example.com", "example.net", "example.org"];
const RESERVED_TLDS = ["example", "test", "invalid", "localhost"];

function isReservedHost(host) {
  const h = String(host).toLowerCase().replace(/\.$/, "");
  if (!h) return false;
  if (RESERVED_TLDS.includes(h.split(".").pop())) return true;
  return RESERVED_DOMAINS.some((d) => h === d || h.endsWith(`.${d}`));
}
const TEST_ONLY_VARS = ["APP_CHECK_JWKS"];

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");

function usage() {
  console.error("dùng: node web/scripts/predeploy.mjs <dev|prod> [--deploy]");
  process.exit(2);
}

/** JSONC của file sinh: bỏ các dòng chú thích `//` (chỉ ở đầu dòng), phần còn lại là JSON. */
function parseGenerated(text) {
  const body = text
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("//"))
    .join("\n");
  return JSON.parse(body);
}

/** Đường dẫn (dạng a.b.c) của mọi khoá tên `name` ở bất kỳ độ sâu nào. */
function findKey(node, name, path = []) {
  if (node === null || typeof node !== "object") return [];
  const out = [];
  for (const [k, v] of Object.entries(node)) {
    const here = [...path, k];
    if (k === name) out.push(here.join("."));
    out.push(...findKey(v, name, here));
  }
  return out;
}

const pick = (cfg, env) => (env === "dev" ? (cfg.env && cfg.env.dev) || {} : cfg);

/** Site của môi trường `env` có service binding `API` ⇔ app có API (features.web_api). */
function hasApi(site, env) {
  const s = pick(site, env);
  return Array.isArray(s.services) && s.services.some((x) => x && x.binding === "API");
}

/** Danh sách lý do từ chối (rỗng = được deploy). `api` = null khi app không có API. `warn` nhận cảnh báo (không chặn). */
function problems(api, site, env, warn = []) {
  const out = [];
  for (const name of TEST_ONLY_VARS) {
    for (const [file, cfg] of [["api/wrangler.jsonc", api], ["site/wrangler.jsonc", site]]) {
      if (!cfg) continue;
      for (const where of findKey(cfg, name)) {
        out.push(`${file}: có biến chỉ-test ${name} (${where}) — không bao giờ deploy biến này; xoá rồi chạy appconfig.py render`);
      }
    }
  }
  if (!hasApi(site, env)) return out;
  const apiEnv = pick(api, env);
  const dbs = Array.isArray(apiEnv.d1_databases) ? apiEnv.d1_databases : [];
  if (dbs.length === 0) out.push(`api/wrangler.jsonc (${env}): không có d1_databases — chạy appconfig.py render`);
  for (const db of dbs) {
    if (!db.database_id || db.database_id === D1_TODO) {
      out.push(`D1 ${db.database_name ?? "?"} (${env}) chưa có database_id — \`wrangler d1 create ${db.database_name ?? "<tên>"}\`` +
        ` rồi dán id vào cloudflare.d1_${env} của app.config.toml và chạy appconfig.py render`);
    }
  }
  const vars = apiEnv.vars || {};
  if (!String(vars.APP_CHECK_PROJECTS ?? "").trim()) {
    const msg = `APP_CHECK_PROJECTS (${env}) rỗng khi site chuyển /api/* sang API (features.web_api) — điền` +
      ` firebase.app_check_${env} = "<projectId>:<projectNumber>" rồi appconfig.py render`;
    (env === "dev" ? warn : out).push(msg + (env === "dev" ? " (dev không bắt buộc App Check — vẫn deploy)" : ""));
  }
  if (env === "prod") {
    let host = "";
    try { host = new URL(String(vars.PUBLIC_ORIGIN ?? "")).hostname; } catch { host = ""; }
    if (!host || isReservedHost(host)) {
      out.push(`web.host_prod "${host || "?"}" là host giữ chỗ/dành riêng — điền tên miền thật vào app.config.toml rồi appconfig.py render`);
    }
  }
  if (!String(vars.ASSN_ENVIRONMENTS ?? "").trim()) {
    out.push(`ASSN_ENVIRONMENTS (${env}) rỗng — API sẽ bỏ MỌI App Store Server Notification; chạy appconfig.py render`);
  }
  return out;
}

function load(rel) {
  const p = join(WEB, rel);
  if (!existsSync(p)) {
    return { error: `thiếu web/${rel} — chạy python3 tools/common/appconfig.py render (web.host_prod rỗng ⇒ app không có web)` };
  }
  try {
    return { value: parseGenerated(readFileSync(p, "utf8")) };
  } catch (e) {
    return { error: `web/${rel} hỏng (${e.message}) — chạy python3 tools/common/appconfig.py render` };
  }
}

function run(cmd, args) {
  console.log(`predeploy: ${cmd} ${args.join(" ")}`);
  const r = spawnSync(cmd, args, { cwd: WEB, stdio: "inherit" });
  if (r.status !== 0) {
    console.error(`predeploy: DỪNG — \`${cmd} ${args.join(" ")}\` rc ${r.status ?? r.error?.message}`);
    process.exit(1);
  }
}

function main(argv) {
  const args = argv.filter((a) => a !== "--deploy");
  const deploy = args.length === argv.length - 1;
  if (args.length !== 1 || !["dev", "prod"].includes(args[0])) usage();
  const env = args[0];
  const errs = [];
  const warns = [];
  const site = load("site/wrangler.jsonc");
  let api = { value: null };
  let withApi = false;
  if (site.error) errs.push(site.error);
  else {
    withApi = hasApi(site.value, env);
    if (withApi || existsSync(join(WEB, "api/wrangler.jsonc"))) {
      api = load("api/wrangler.jsonc");
      if (api.error && withApi) errs.push(api.error);
      if (api.error) api = { value: null };
    }
    if (!(withApi && api.value === null)) errs.push(...problems(api.value, site.value, env, warns));
  }
  for (const w of warns) console.error(`CẢNH BÁO: ${w}`);
  if (errs.length) {
    for (const e of errs) console.error(`TỪ CHỐI: ${e}`);
    console.error(`predeploy ${env}: KHÔNG deploy (${errs.length} lý do)`);
    process.exit(1);
  }
  console.log(`predeploy ${env}: OK (${withApi ? "API + site" : "chỉ site — features.web_api tắt, không có API"})`);
  if (!deploy) return;
  if (env === "prod") {
    run("python3", ["tools/check_sitemap.py"]);
    run("python3", ["tools/changelog.py", "--check"]);
    run("python3", ["tools/check_site.py", "--release"]);
  }
  if (withApi) run("npm", ["run", `deploy:${env}`, "-w", "api"]);
  run("npm", ["run", `deploy:${env}`, "-w", "site"]);
}

main(process.argv.slice(2));
