import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { exportJWK, generateKeyPair, importJWK, SignJWT, type JWK } from "jose";
import type { Env } from "../src/env";
import { clock } from "../src/http";
import worker from "../src/index";

export const testEnv = (): Env => env as unknown as Env;

/** Project App Check giả — khớp APP_CHECK_PROJECTS trong vitest.config.ts. */
export const TEST_PROJECT = { id: "test-proj", number: "123456" };

let signingKey: CryptoKey | null = null;
let publicJwk: JWK | null = null;
let jwksJson = "";

/** beforeAll của file test cần App Check: một cặp khoá RS256 giả, JWKS công khai tiêm qua APP_CHECK_JWKS. */
export async function setupAppCheckKeys(): Promise<void> {
  const { privateKey, publicKey } = await generateKeyPair("RS256", { extractable: true });
  const jwk: JWK = { ...(await exportJWK(publicKey)), kid: "k1", alg: "RS256", use: "sig" };
  signingKey = privateKey;
  publicJwk = jwk;
  jwksJson = JSON.stringify({ keys: [jwk] });
}

/** Env của test: binding thật của Miniflare (D1…) + JWKS giả + ghi đè tuỳ test. */
/** JWK công khai của khoá test (để dựng JWKS biến thể trong test). */
export const testPublicJwk = (): JWK => publicJwk!;

/** Khoá riêng test nhập lại cho thuật toán khác (cùng vật liệu khoá RSA). */
export async function testPrivateKeyAs(alg: string): Promise<CryptoKey> {
  const { alg: _a, ...jwk } = await exportJWK(signingKey!);
  return (await importJWK(jwk, alg)) as CryptoKey;
}

export function envWith(overrides: Partial<Env> = {}): Env {
  return { ...testEnv(), APP_CHECK_JWKS: jwksJson, ...overrides };
}

/** Gọi thẳng handler (cùng instance module với test ⇒ mock clock có hiệu lực). */
export async function call(path: string, init: RequestInit = {}, overrides: Partial<Env> = {}): Promise<Response> {
  const ctx = createExecutionContext();
  const res = await worker.fetch(new Request(`https://example.com${path}`, init), envWith(overrides), ctx);
  await waitOnExecutionContext(ctx);
  return res;
}

const nowSec = () => Math.floor(clock.now() / 1000);

export interface TokenOpts {
  /** Project number trong `iss`. */
  issNumber?: string;
  /** Danh sách `aud`; mặc định `projects/<issNumber>` + `projects/<id>` như token thật. */
  aud?: string[];
  expInSec?: number;
  /** Khoá ký khác khoá trong JWKS (mặc định: khoá test). */
  key?: CryptoKey;
  kid?: string;
  alg?: string;
  typ?: string;
}

/** Token App Check giả ký bằng khoá test, hình dạng như token Firebase thật. */
export async function appCheckToken(opts: TokenOpts = {}): Promise<string> {
  const n = opts.issNumber ?? TEST_PROJECT.number;
  return new SignJWT({})
    .setProtectedHeader({ alg: opts.alg ?? "RS256", kid: opts.kid ?? "k1", typ: opts.typ ?? "JWT" })
    .setIssuer(`https://firebaseappcheck.googleapis.com/${n}`)
    .setAudience(opts.aud ?? [`projects/${n}`, `projects/${TEST_PROJECT.id}`])
    .setSubject("1:123456:ios:abc")
    .setIssuedAt(nowSec())
    .setExpirationTime(nowSec() + (opts.expInSec ?? 3600))
    .sign(opts.key ?? signingKey!);
}
