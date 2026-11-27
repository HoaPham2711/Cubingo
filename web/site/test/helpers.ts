import type { Env } from "../src/worker";

/** Fetcher giả: ghi lại request nhận được, trả phản hồi cố định. */
export function fakeFetcher(body: string, init: ResponseInit = { status: 200 }) {
  const seen: Request[] = [];
  const fetcher = {
    fetch: async (input: RequestInfo | URL, _init?: RequestInit) => {
      seen.push(input instanceof Request ? input : new Request(String(input)));
      return new Response(body, init);
    },
    connect: () => {
      throw new Error("không dùng");
    },
  } as unknown as Fetcher;
  return { fetcher, seen };
}

/** Env prod giả, giá trị trung tính; `over` ghi đè từng biến. */
export function makeEnv(over: Partial<Env> = {}): Env {
  return {
    ASSETS: fakeFetcher("asset").fetcher,
    APP_IDS: "TEAMID0000.com.example.app",
    APP_PATHS: '["/items", "/items/*"]',
    NOINDEX: "0",
    ...over,
  };
}

export const req = (path: string, init?: RequestInit) => new Request(`https://example.com${path}`, init);
