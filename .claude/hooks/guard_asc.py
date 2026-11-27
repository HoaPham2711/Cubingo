#!/usr/bin/env python3
"""PreToolUse(Bash): mọi thao tác App Store Connect chỉ đi qua tools/aso/aso.py.

- `python3 tools/aso/aso.py apply --plan P --expect CODE` ⇒ "ask" (hộp Allow/Deny; lý do = mã plan TÍNH LẠI từ nội
  dung file + version + số thay đổi / các bước release); plan không đọc được hoặc mã tính lại ≠ --expect ⇒ chặn.
- gọi `asc` trực tiếp, API api.appstoreconnect.apple.com, file cấu hình khoá asc-listing.json, lệnh chạy code đụng
  tools/aso mà không đúng dạng chuẩn ⇒ exit 2 (chặn; stderr — kèm các lệnh chuẩn thay thế — trả về cho Claude).
- Lỗi nội bộ (VD policy.py hỏng) mà lệnh có dấu hiệu ASC hoặc đụng vùng công cụ (REF_AREA của policy + -m aso,
  applier, tools.aso) ⇒ chặn (fail-closed); lệnh khác ⇒ cho qua.
  JSON stdin hỏng ⇒ cho qua (như mọi hook của harness).
Logic + test: tools/aso/policy.py (`hook_decision`), tools/aso/test_policy.py, tools/aso/test_guard_asc.py.
"""
import json
import os
import re
import sys
from pathlib import Path

# Khoá an toàn khi lỗi phải phủ ÍT NHẤT vùng mà policy gác: REF_AREA_SRC là bản sao NGUYÊN VĂN của `policy.REF_AREA`
# (policy hỏng thì không import được; test gác hai chuỗi trùng nhau), cộng các chữ dưới (chuỗi con, không phân biệt hoa).
REF_AREA_SRC = r"tools[./\\]aso|aso\.py|\b(cd|pushd)\s+(\S*/)?tools\b|pythonpath"
FALLBACK_RE = re.compile(REF_AREA_SRC + r"|-m\s+aso\b", re.I)
FALLBACK_WORDS = ("asc", "aso.py", "tools/aso", "tools.aso", "applier", "pythonpath",
                  "api.appstoreconnect.apple.com", "asc-listing.json")
FALLBACK_HINT = ("dùng `python3 tools/aso/aso.py <lệnh>` từ gốc repo; ghi lên ASC chỉ qua "
                 "`python3 tools/aso/aso.py apply --plan … --expect …`")

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def make_plan_summary(cwd):
    """`plan_summary(path, expect)`: đường dẫn tương đối tính theo `cwd` của lệnh Bash (trường `cwd` của hook; không
    có ⇒ gốc repo) — đúng file mà aso.py sẽ mở. Đọc bằng planner.load_plan, TÍNH LẠI plan_id từ nội dung; khác
    `expect` hoặc lỗi bất kỳ ⇒ None (⇒ chặn)."""
    base = Path(cwd) if cwd else root

    def plan_summary(path, expect):
        try:
            import planner  # noqa: E402 — tools/aso đã nằm trong sys.path
            p = Path(path).expanduser()
            if not p.is_absolute():
                p = base / p
            plan = planner.load_plan(p)
            pid = plan.plan_id
            if pid != expect:
                return None
            if getattr(plan, "kind", None) == "release":
                steps = " → ".join(o.action for o in plan.ops)
                return f"mã tính lại {pid}, release {plan.version} build {plan.build}: {steps}"
            return f"mã tính lại {pid}, version {plan.version}, {len(plan.ops)} thay đổi"
        except Exception:
            return None
    return plan_summary


try:
    payload = json.load(sys.stdin)
    cmd = str(payload.get("tool_input", {}).get("command", ""))
    cwd = payload.get("cwd")  # thư mục làm việc của lệnh Bash (giữ qua các lệnh) — None nếu không có
except Exception:
    sys.exit(0)

try:
    sys.path.insert(0, str(root / "tools" / "aso"))
    import policy  # noqa: E402
    decision, reason = policy.hook_decision(cmd, make_plan_summary(cwd), cwd=cwd)
    if decision == "block" and policy.CANON_FORMS not in reason and policy.needs_canon_hint(reason):
        reason = f"{reason}. Lệnh chuẩn (chạy từ gốc repo): {policy.CANON_FORMS}"
except BaseException:
    # Fail-closed: hook hỏng mà lệnh có dấu hiệu ASC ⇒ chặn; lệnh khác thì cho qua.
    if FALLBACK_RE.search(cmd) or any(w in cmd.casefold() for w in FALLBACK_WORDS):
        sys.stderr.write(f"BLOCKED: guard_asc lỗi nội bộ, chặn lệnh nghi liên quan App Store Connect — {FALLBACK_HINT}.\n")
        sys.exit(2)
    sys.exit(0)

if decision == "ask":
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason}}, ensure_ascii=False))
elif decision == "block":
    sys.stderr.write(f"BLOCKED: {reason}\n")
    sys.exit(2)
sys.exit(0)
