// @ts-check
// Số liệu web không cookie — gửi tới API của app (chỉ gắn vào trang khi features.web_api bật; web/tools/check_site.py
// gác). Hợp đồng: POST cùng origin /api/v1/public/beacon, JSON { p, e?, d? } (xem web/api/src/routes/beacon.ts):
//   pageview (một lần, d = tên miền giới thiệu hoặc "utm:<nguồn>"), engaged (một lần khi trang ẩn, d = khoảng thời gian
//   trang hiện), outbound (bấm link có data-out="<mã>", d = mã). Không cookie, không định danh, không lưu gì ở máy.

const ENDPOINT = "/api/v1/public/beacon";
const TOKEN = /^[a-z0-9_-]{1,32}$/;

/** @param {number} ms */
export function engagedBucket(ms) {
  return ms < 10000 ? "lt10s" : ms < 30000 ? "10_30s" : ms < 120000 ? "30_120s" : "gt2m";
}

/** Nguồn của lượt xem: "utm:<nguồn>" > tên miền giới thiệu khác site > không có (trực tiếp / nội bộ).
 * @param {string} referrer @param {string} search @param {string} ownHost @returns {string | undefined} */
export function referrerOf(referrer, search, ownHost) {
  const utm = (new URLSearchParams(search).get("utm_source") ?? "").toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 32);
  if (utm) return "utm:" + utm;
  try {
    const host = new URL(referrer).hostname.toLowerCase().replace(/^www\./, "");
    return host && host !== ownHost.replace(/^www\./, "") ? host : undefined;
  } catch {
    return undefined;
  }
}

/** @param {string} p @param {string} [e] @param {string} [d] */
function send(p, e, d) {
  /** @type {Record<string, string>} */
  const body = { p };
  if (e) body.e = e;
  if (d) body.d = d;
  try {
    navigator.sendBeacon?.(ENDPOINT, JSON.stringify(body));
  } catch {
    /* không bao giờ làm hỏng trang */
  }
}

function start() {
  if (navigator.webdriver) return;
  const page = location.pathname;
  send(page, "pageview", referrerOf(document.referrer, location.search, location.hostname));
  let shown = 0;
  let since = document.visibilityState === "visible" ? performance.now() : -1;
  let engagedSent = false;
  const hide = () => {
    if (since >= 0) shown += performance.now() - since;
    since = -1;
    if (!engagedSent && shown >= 1000) {
      engagedSent = true;
      send(page, "engaged", engagedBucket(shown));
    }
  };
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") hide();
    else if (since < 0) since = performance.now();
  });
  // pagehide có thể tới khi trang còn "visible" (đóng tab) — gửi luôn.
  addEventListener("pagehide", hide);
  document.addEventListener("click", (ev) => {
    const a = ev.target instanceof Element ? ev.target.closest("[data-out]") : null;
    const code = a instanceof HTMLElement ? a.dataset.out ?? "" : "";
    if (TOKEN.test(code)) send(page, "outbound", code);
  }, { capture: true, passive: true });
}

if (typeof document !== "undefined") start();
