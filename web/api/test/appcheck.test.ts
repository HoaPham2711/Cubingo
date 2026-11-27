import { generateKeyPair } from "jose";
import { beforeAll, describe, expect, it } from "vitest";
import { parseProjects, verifyAppCheck } from "../src/auth/appcheck";
import { appCheckToken, envWith, setupAppCheckKeys, TEST_PROJECT, testPrivateKeyAs, testPublicJwk } from "./helpers";

beforeAll(setupAppCheckKeys);

describe("verifyAppCheck", () => {
  it("token hop le cua project da khai duoc nhan", async () => {
    expect(await verifyAppCheck(await appCheckToken(), envWith())).toBe(true);
  });
  it("token ky bang khoa la cung kid bi tu choi", async () => {
    // Claim hoàn toàn đúng, cùng kid "k1" — chỉ chữ ký sai. Gác phép kiểm chữ ký (không được chỉ đọc claim).
    const { privateKey } = await generateKeyPair("RS256", { extractable: true });
    expect(await verifyAppCheck(await appCheckToken({ key: privateKey }), envWith())).toBe(false);
  });
  it("token co kid khong co trong JWKS bi tu choi", async () => {
    expect(await verifyAppCheck(await appCheckToken({ kid: "k-khac" }), envWith())).toBe(false);
  });
  it("token typ khac JWT bi tu choi", async () => {
    expect(await verifyAppCheck(await appCheckToken({ typ: "at+jwt" }), envWith())).toBe(false);
  });
  it("token thuat toan khac RS256 bi tu choi du khoa khop", async () => {
    // JWKS không ghi alg ⇒ jose chấp nhận PS256 với cùng khoá RSA; chỉ `algorithms: ["RS256"]` chặn được.
    const { alg: _a, ...noAlg } = testPublicJwk();
    const env = envWith({ APP_CHECK_JWKS: JSON.stringify({ keys: [noAlg] }) });
    expect(await verifyAppCheck(await appCheckToken(), env)).toBe(true);
    expect(await verifyAppCheck(await appCheckToken({ alg: "PS256", key: await testPrivateKeyAs("PS256") }), env)).toBe(false);
  });
  it("token app check sai audience bi tu choi", async () => {
    // `iss` đúng project đã khai, nhưng `aud` thuộc project khác ⇒ chỉ phép kiểm audience chặn được.
    const token = await appCheckToken({ aud: ["projects/999999", "projects/other-proj"] });
    expect(await verifyAppCheck(token, envWith())).toBe(false);
  });
  it("token cua project khong khai trong APP_CHECK_PROJECTS bi tu choi", async () => {
    expect(await verifyAppCheck(await appCheckToken({ issNumber: "999999" }), envWith())).toBe(false);
  });
  it("token het han bi tu choi", async () => {
    expect(await verifyAppCheck(await appCheckToken({ expInSec: -60 }), envWith())).toBe(false);
  });
  it("token rac hoac rong bi tu choi", async () => {
    expect(await verifyAppCheck("rac.rac.rac", envWith())).toBe(false);
    expect(await verifyAppCheck("", envWith())).toBe(false);
  });
  it("APP_CHECK_PROJECTS rong thi khong token nao qua", async () => {
    expect(await verifyAppCheck(await appCheckToken(), envWith({ APP_CHECK_PROJECTS: "" }))).toBe(false);
  });
  it("nhieu project phan cach dau phay deu duoc nhan", async () => {
    const env = envWith({ APP_CHECK_PROJECTS: ` other:777 , ${TEST_PROJECT.id}:${TEST_PROJECT.number}` });
    expect(await verifyAppCheck(await appCheckToken(), env)).toBe(true);
  });
  it("parseProjects bo khoang trang va muc rong", () => {
    expect(parseProjects(" a:1, ,b:2,")).toEqual([
      { id: "a", number: "1" },
      { id: "b", number: "2" },
    ]);
    expect(parseProjects("")).toEqual([]);
  });
});
