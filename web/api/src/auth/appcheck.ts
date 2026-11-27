import { createLocalJWKSet, createRemoteJWKSet, decodeJwt, jwtVerify, type JWTVerifyGetKey } from "jose";
import type { Env } from "../env";
import { clock } from "../http";

export interface AppCheckProject {
  id: string;
  number: string;
}

const ISSUER_PREFIX = "https://firebaseappcheck.googleapis.com/";

// JWKS công khai của Firebase App Check — jose tự cache theo Cache-Control. Không cần Admin SDK.
const remoteKeys: JWTVerifyGetKey = createRemoteJWKSet(new URL("https://firebaseappcheck.googleapis.com/v1/jwks"));

/** `APP_CHECK_PROJECTS` = "<projectId>:<projectNumber>[,…]"; bỏ khoảng trắng và mục rỗng/hỏng. */
export function parseProjects(s: string): AppCheckProject[] {
  return (s ?? "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean)
    .map((x) => {
      const [id = "", number = ""] = x.split(":").map((p) => p.trim());
      return { id, number };
    })
    .filter((p) => p.id !== "" && p.number !== "");
}

function keysFor(env: Env): JWTVerifyGetKey {
  // Chỉ test khai APP_CHECK_JWKS (không mạng trong test). wrangler.jsonc sinh ra không bao giờ có biến này.
  if (env.APP_CHECK_JWKS) return createLocalJWKSet(JSON.parse(env.APP_CHECK_JWKS));
  return remoteKeys;
}

/**
 * Kiểm token App Check (header `X-Firebase-AppCheck`). Project chọn theo `iss` (số project), rồi jose kiểm chữ ký
 * RS256 theo JWKS, `typ` JWT, hạn, `iss` và `aud` phải chứa `projects/<projectNumber>` — `aud` là phép kiểm token
 * được cấp cho ĐÚNG project này. Mọi lỗi ⇒ false (không ném).
 */
export async function verifyAppCheck(token: string, env: Env): Promise<boolean> {
  const projects = parseProjects(env.APP_CHECK_PROJECTS);
  if (!token || projects.length === 0) return false;
  let iss: unknown;
  try {
    iss = decodeJwt(token).iss;
  } catch {
    return false;
  }
  if (typeof iss !== "string" || !iss.startsWith(ISSUER_PREFIX)) return false;
  const p = projects.find((x) => `${ISSUER_PREFIX}${x.number}` === iss);
  if (!p) return false;
  try {
    await jwtVerify(token, keysFor(env), {
      issuer: `${ISSUER_PREFIX}${p.number}`,
      audience: `projects/${p.number}`,
      algorithms: ["RS256"],
      typ: "JWT",
      currentDate: new Date(clock.now()),
    });
    return true;
  } catch {
    return false;
  }
}
