import { z } from "zod";

/** Loại phản hồi client gửi được (khớp `FeedbackDraft.type` của app). */
export const FEEDBACK_TYPES = ["bug", "feature", "other"] as const;

/**
 * Body `POST /api/v1/feedback` — hợp đồng với `FeedbackRequestEncoder` của app (sáu field). Đổi tên/kiểu/trần ở đây
 * là đổi hợp đồng: sửa client cùng lúc. Trần đếm theo ký tự UTF-16 (client đếm byte UTF-8 ⇒ client chặt hơn).
 */
export const FeedbackCreateSchema = z.object({
  type: z.enum(FEEDBACK_TYPES),
  message: z.string().trim().min(1).max(4000),
  email: z.string().max(320).default(""),
  diagnostics: z.string().max(12000).default(""),
  appVersion: z.string().min(1).max(64),
  clientTime: z.number().int().positive(),
});
export type FeedbackCreate = z.infer<typeof FeedbackCreateSchema>;
