import { Hono } from "hono";
import type { Env, HonoEnv } from "./env";
import { runCron } from "./cron";
import { errorResponse, json } from "./http";
import { admin } from "./routes/admin";
import { appstore } from "./routes/appstore";
import { beacon } from "./routes/beacon";
import { feedback } from "./routes/feedback";

/** App gốc. Mỗi file routes/* export một Hono con, gắn vào đây. */
export const app = new Hono<HonoEnv>();
app.onError((e) => errorResponse(e));
app.notFound(() => json({ error: "not_found", message: "Not found" }, 404));

app.route("/api/v1", feedback);
app.route("/api/v1", appstore);
app.route("/api/v1", admin);
app.route("/api/v1", beacon);

export default {
  fetch: app.fetch,
  /** Cron hằng ngày: dọn bảng (src/cron.ts). */
  async scheduled(_c: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runCron(env));
  },
} satisfies ExportedHandler<Env>;
