import { createExecutionContext, createScheduledController, waitOnExecutionContext } from "cloudflare:test";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runCron } from "../src/cron";
import { clock } from "../src/http";
import worker from "../src/index";
import { envWith, testEnv } from "./helpers";

const DAY_MS = 86_400_000;
const T = Date.UTC(2031, 1, 15, 3, 17);
const db = () => testEnv().DB;
const day = (t: number) => new Date(t).toISOString().slice(0, 10).replace(/-/g, "");

async function seed() {
  const sec = (t: number) => Math.floor(t / 1000);
  await db().batch([
    db().prepare("INSERT INTO rate (key, window_start, count) VALUES ('cron:old', ?, 1)").bind(sec(T - DAY_MS) - 1),
    db().prepare("INSERT INTO rate (key, window_start, count) VALUES ('cron:new', ?, 1)").bind(sec(T - DAY_MS) + 3600),
    db().prepare("INSERT INTO web_events (day, page, event, detail, source, country, device, n) VALUES (?, '/', 'pageview', '-', '-', 'XX', 'ios', 1)").bind(day(T - 401 * DAY_MS)),
    db().prepare("INSERT INTO web_events (day, page, event, detail, source, country, device, n) VALUES (?, '/', 'pageview', '-', '-', 'XX', 'ios', 1)").bind(day(T - 399 * DAY_MS)),
    db().prepare("INSERT INTO web_referrers (day, domain, n) VALUES (?, 'old.example.org', 1)").bind(day(T - 401 * DAY_MS)),
    db().prepare("INSERT INTO web_referrers (day, domain, n) VALUES (?, 'new.example.org', 1)").bind(day(T - 399 * DAY_MS)),
    db().prepare("INSERT INTO appstore_notifications (notification_uuid, notification_type, environment, signed_date, received_at) VALUES ('old', 'TEST', 'Production', 1, ?)").bind(T - 401 * DAY_MS),
    db().prepare("INSERT INTO appstore_notifications (notification_uuid, notification_type, environment, signed_date, received_at) VALUES ('edge', 'TEST', 'Production', 1, ?)").bind(T - 399 * DAY_MS),
    db().prepare("INSERT INTO feedback (id, type, message, app_version, client_time, created_at, updated_at) VALUES ('fb-old', 'bug', 'm', '1', 1, 1, 1)"),
  ]);
}
const col = async (sql: string) => (await db().prepare(sql).all<{ v: string }>()).results.map((r) => r.v);
async function snapshot() {
  return {
    rate: await col("SELECT key AS v FROM rate WHERE key LIKE 'cron:%' ORDER BY key"),
    events: await col("SELECT day AS v FROM web_events ORDER BY day"),
    refs: await col("SELECT domain AS v FROM web_referrers ORDER BY domain"),
    assn: await col("SELECT notification_uuid AS v FROM appstore_notifications ORDER BY v"),
    feedback: await col("SELECT id AS v FROM feedback"),
  };
}
const expected = {
  rate: ["cron:new"],
  events: [day(T - 399 * DAY_MS)],
  refs: ["new.example.org"],
  assn: ["edge"],
  feedback: ["fb-old"], // feedback không bao giờ bị cron xoá
};

beforeEach(async () => {
  for (const t of ["web_events", "web_referrers", "appstore_notifications", "feedback"]) await db().prepare(`DELETE FROM ${t}`).run();
  await db().prepare("DELETE FROM rate WHERE key LIKE 'cron:%'").run();
  vi.spyOn(clock, "now").mockReturnValue(T);
  await seed();
});

describe("cron don bang", () => {
  it("cron xoa rate cu hon 1 ngay va web events cu hon 400 ngay", async () => {
    await runCron(testEnv());
    expect(await snapshot()).toEqual(expected);
    // Chạy lại không đổi gì (idempotent).
    await runCron(testEnv());
    expect(await snapshot()).toEqual(expected);
  });

  it("scheduled cua worker chay cron", async () => {
    const ctx = createExecutionContext();
    await worker.scheduled(createScheduledController({ scheduledTime: T, cron: "17 3 * * *" }), envWith(), ctx);
    await waitOnExecutionContext(ctx);
    expect(await snapshot()).toEqual(expected);
  });
});
