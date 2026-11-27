import { describe, expect, it } from "vitest";
import worker from "../src/worker";
import { fakeFetcher, makeEnv, req } from "./helpers";

describe("worker site", () => {
  it("api khong co binding tra 404 no_api", async () => {
    const res = await worker.fetch(req("/api/v1/feedback", { method: "POST", body: "{}" }), makeEnv());
    expect(res.status).toBe(404);
    expect(res.headers.get("content-type")).toContain("application/json");
    expect(await res.json()).toEqual({ error: "no_api" });
  });

  it("api co binding chuyen nguyen request sang api", async () => {
    const api = fakeFetcher("tu-api", { status: 201 });
    const assets = fakeFetcher("asset");
    const res = await worker.fetch(req("/api/v1/public/beacon", { method: "POST", body: "x" }),
      makeEnv({ API: api.fetcher, ASSETS: assets.fetcher }));
    expect(res.status).toBe(201);
    expect(await res.text()).toBe("tu-api");
    expect(api.seen).toHaveLength(1);
    expect(api.seen[0].method).toBe("POST");
    expect(new URL(api.seen[0].url).pathname).toBe("/api/v1/public/beacon");
    expect(assets.seen).toHaveLength(0);
  });

  it("duong dan khac giao cho assets", async () => {
    const assets = fakeFetcher("trang", { status: 200, headers: { "content-type": "text/html" } });
    const api = fakeFetcher("tu-api");
    for (const p of ["/", "/privacy/", "/.well-known/khac", "/apiary/"]) {
      const res = await worker.fetch(req(p), makeEnv({ ASSETS: assets.fetcher, API: api.fetcher }));
      expect(await res.text()).toBe("trang");
    }
    expect(assets.seen).toHaveLength(4);
    expect(api.seen).toHaveLength(0);
  });

  it("noindex o dev", async () => {
    const env = makeEnv({ NOINDEX: "1", API: fakeFetcher("tu-api").fetcher });
    for (const p of ["/", "/.well-known/apple-app-site-association", "/api/v1/x"]) {
      const res = await worker.fetch(req(p), env);
      expect(res.headers.get("x-robots-tag")).toBe("noindex");
    }
    const noApi = await worker.fetch(req("/api/v1/x"), makeEnv({ NOINDEX: "1" }));
    expect(noApi.headers.get("x-robots-tag")).toBe("noindex");
  });

  it("prod khong gan noindex", async () => {
    for (const p of ["/", "/.well-known/apple-app-site-association", "/api/v1/x"]) {
      const res = await worker.fetch(req(p), makeEnv());
      expect(res.headers.get("x-robots-tag")).toBeNull();
    }
  });
});
