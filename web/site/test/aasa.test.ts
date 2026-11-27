import { describe, expect, it } from "vitest";
import { aasaBody, parseAppIds, parseAppPaths } from "../src/aasa";
import worker from "../src/worker";
import { makeEnv, req } from "./helpers";

const AASA = "/.well-known/apple-app-site-association";

describe("aasa", () => {
  it("aasa dung dang applinks details components", () => {
    expect(aasaBody(["T.com.example.app"], ["/items", "/items/*"])).toEqual({
      applinks: { details: [{ appIDs: ["T.com.example.app"], components: [{ "/": "/items" }, { "/": "/items/*" }] }] },
    });
  });

  it("aasa app_paths rong thi details rong", async () => {
    expect(aasaBody(["T.com.example.app"], [])).toEqual({ applinks: { details: [] } });
    const res = await worker.fetch(req(AASA), makeEnv({ APP_PATHS: "[]" }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ applinks: { details: [] } });
  });

  it("aasa dev dung bundle internal", async () => {
    const res = await worker.fetch(req(AASA), makeEnv({ APP_IDS: "TEAMID0000.com.example.app.internal", NOINDEX: "1" }));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { applinks: { details: { appIDs: string[]; components: unknown[] }[] } };
    expect(body.applinks.details[0].appIDs).toEqual(["TEAMID0000.com.example.app.internal"]);
    expect(body.applinks.details[0].components).toEqual([{ "/": "/items" }, { "/": "/items/*" }]);
  });

  it("aasa json khong redirect co cache mot gio", async () => {
    const res = await worker.fetch(req(AASA), makeEnv());
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("application/json");
    expect(res.headers.get("cache-control")).toBe("max-age=3600");
    expect(res.headers.get("location")).toBeNull();
    const head = await worker.fetch(req(AASA, { method: "HEAD" }), makeEnv());
    expect(head.status).toBe(200);
    expect(await head.text()).toBe("");
  });

  it("aasa doc dung app_paths tu bien moi truong", async () => {
    const res = await worker.fetch(req(AASA), makeEnv({ APP_PATHS: '["/open/*"]' }));
    const body = (await res.json()) as { applinks: { details: { components: unknown[] }[] } };
    expect(body.applinks.details[0].components).toEqual([{ "/": "/open/*" }]);
  });

  it("app_ids tach dau phay bo khoang trang va phan tu rong", () => {
    expect(parseAppIds(" A.x , ,B.y,")).toEqual(["A.x", "B.y"]);
    expect(parseAppIds(undefined)).toEqual([]);
  });

  it("app_paths hong hoac sai dang thi rong", () => {
    expect(parseAppPaths("khong-phai-json")).toEqual([]);
    expect(parseAppPaths('{"a":1}')).toEqual([]);
    expect(parseAppPaths('["/a", "b", 3]')).toEqual(["/a"]);
    expect(parseAppPaths(undefined)).toEqual([]);
  });
});
