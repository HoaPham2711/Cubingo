import "reflect-metadata"; // @peculiar/x509 (tsyringe) cần polyfill này, phải import TRƯỚC x509.
import * as x509 from "@peculiar/x509";
import { CompactSign } from "jose";

x509.cryptoProvider.set(crypto);
const alg = { name: "ECDSA", namedCurve: "P-256", hash: "SHA-256" } as const;
const ext = (oid: string) => new x509.Extension(oid, false, new Uint8Array([5, 0]));

export interface TestChain {
  /** Gốc GIẢ của chuỗi — test tiêm vào tham số `roots` của verifyJWS (hoặc qua appstoreTrust.roots). */
  root: x509.X509Certificate;
  sign(payload: object, opts?: { tamper?: boolean; noLeafOid?: boolean }): Promise<string>;
}

/**
 * Chuỗi root → intermediate → leaf tự ký, mang OID Apple như chuỗi thật. KHÔNG bao giờ qua được gốc Apple thật:
 * test ca hợp lệ phải tiêm `root` này. `tamper`: thay payload sau khi ký (chữ ký không còn khớp).
 */
export async function makeTestChain(): Promise<TestChain> {
  const notBefore = new Date(Date.now() - 86_400_000);
  const notAfter = new Date(Date.now() + 3650 * 86_400_000);
  const gen = () => crypto.subtle.generateKey(alg, true, ["sign", "verify"]) as Promise<CryptoKeyPair>;
  const [rootKeys, interKeys, leafKeys] = await Promise.all([gen(), gen(), gen()]);
  const root = await x509.X509CertificateGenerator.createSelfSigned({
    serialNumber: "01", name: "CN=Test Root", notBefore, notAfter, keys: rootKeys, signingAlgorithm: alg,
    extensions: [new x509.BasicConstraintsExtension(true, 2, true)],
  });
  const inter = await x509.X509CertificateGenerator.create({
    serialNumber: "02", subject: "CN=Test Inter", issuer: root.subject, notBefore, notAfter,
    publicKey: interKeys.publicKey, signingKey: rootKeys.privateKey, signingAlgorithm: alg,
    extensions: [new x509.BasicConstraintsExtension(true, 0, true), ext("1.2.840.113635.100.6.2.1")],
  });
  const mkLeaf = (withOid: boolean) =>
    x509.X509CertificateGenerator.create({
      serialNumber: "03", subject: "CN=Test Leaf", issuer: inter.subject, notBefore, notAfter,
      publicKey: leafKeys.publicKey, signingKey: interKeys.privateKey, signingAlgorithm: alg,
      extensions: withOid ? [ext("1.2.840.113635.100.6.11.1")] : [],
    });
  const [leaf, leafNoOid] = await Promise.all([mkLeaf(true), mkLeaf(false)]);
  return {
    root,
    async sign(payload, opts = {}) {
      const l = opts.noLeafOid ? leafNoOid : leaf;
      const jws = await new CompactSign(new TextEncoder().encode(JSON.stringify(payload)))
        .setProtectedHeader({ alg: "ES256", x5c: [l, inter, root].map((c) => c.toString("base64")) })
        .sign(leafKeys.privateKey);
      if (!opts.tamper) return jws;
      const [h, , s] = jws.split(".");
      const forged = b64u({ ...payload, tampered: true });
      return `${h}.${forged}.${s}`;
    },
  };
}

export const b64u = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
