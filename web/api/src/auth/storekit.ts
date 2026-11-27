import "reflect-metadata"; // @peculiar/x509 (tsyringe) cần polyfill này, phải import TRƯỚC x509.
import * as x509 from "@peculiar/x509";
import { compactVerify, decodeProtectedHeader } from "jose";
import { clock } from "../http";
import { APPLE_ROOT_G3_B64 } from "./apple-root";

x509.cryptoProvider.set(crypto);

/** OID Apple: leaf ký App Store (Mac App Store Receipt Signing) và intermediate WWDR. */
const OID_LEAF = "1.2.840.113635.100.6.11.1";
const OID_INTERMEDIATE = "1.2.840.113635.100.6.2.1";

let appleRootCache: x509.X509Certificate[] | null = null;
/** Gốc tin cậy thật cho JWS của App Store: Apple Root CA - G3 (công khai, nhúng trong mã). */
export function appleRoots(): x509.X509Certificate[] {
  appleRootCache ??= [new x509.X509Certificate(APPLE_ROOT_G3_B64)];
  return appleRootCache;
}

function sameBytes(a: ArrayBuffer, b: ArrayBuffer): boolean {
  const x = new Uint8Array(a);
  const y = new Uint8Array(b);
  if (x.length !== y.length) return false;
  let r = 0;
  for (let i = 0; i < x.length; i++) r |= x[i] ^ y[i];
  return r === 0;
}

/**
 * Kiểm một JWS do App Store ký (signedPayload / signedTransactionInfo / signedRenewalInfo): header ES256 + x5c đúng 3
 * chứng chỉ; chứng chỉ cuối TRÙNG BYTE với một gốc trong `roots`; intermediate ký bởi gốc, leaf ký bởi intermediate
 * (kèm hạn hiệu lực theo `clock`); OID Apple trên cả hai; chữ ký ES256 của JWS bằng khoá leaf. Trả payload đã parse.
 * Hỏng bất kỳ bước nào ⇒ ném Error. `roots` là tham số để test tiêm gốc GIẢ — mã chạy thật luôn truyền `appleRoots()`.
 */
export async function verifyJWS(jws: string, roots: x509.X509Certificate[]): Promise<unknown> {
  const header = decodeProtectedHeader(jws);
  if (header.alg !== "ES256" || !Array.isArray(header.x5c) || header.x5c.length !== 3) throw new Error("bad header");
  const [leaf, inter, root] = (header.x5c as string[]).map((c) => new x509.X509Certificate(c));
  if (!roots.some((r) => sameBytes(r.rawData, root.rawData))) throw new Error("untrusted root");
  const date = new Date(clock.now());
  if (!(await inter.verify({ publicKey: root.publicKey, date }))) throw new Error("intermediate sig");
  if (!(await leaf.verify({ publicKey: inter.publicKey, date }))) throw new Error("leaf sig");
  if (!inter.getExtension(OID_INTERMEDIATE) || !leaf.getExtension(OID_LEAF)) throw new Error("apple oid");
  const leafKey = await leaf.publicKey.export({ name: "ECDSA", namedCurve: "P-256" }, ["verify"]);
  const { payload } = await compactVerify(jws, leafKey, { algorithms: ["ES256"] });
  return JSON.parse(new TextDecoder().decode(payload));
}
