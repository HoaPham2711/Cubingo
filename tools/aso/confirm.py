"""Bản xác nhận markdown (spec §6.3) cho một Plan."""
import difflib
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint as lint_mod  # noqa: E402

LONG = 300


def _size(field: str, text: str) -> str:
    n = len(text)
    if field == "keywords":
        return f"{n} ký tự, {len(text.encode('utf-8'))}/{lint_mod.KEYWORDS_BYTES} byte"
    limit = lint_mod.LIMITS.get(field)
    return f"{n}/{limit} ký tự" if limit else f"{n} ký tự"


def _fence(text: str, lang: str = "") -> list[str]:
    """Khối code có rào dài hơn mọi chuỗi backtick trong text."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    f = "`" * max(3, longest + 1)
    return [f + lang, text, f]


def _ends(s: str) -> str:
    return f"đầu {s[:20]!r}, cuối {s[-20:]!r}"


def _ws_note(old, new) -> str:
    if old is None or old == new:
        return ""
    norm = lambda t: t.replace("\r\n", "\n").replace("\r", "\n")
    if old.strip() == new.strip() or norm(old) == norm(new) or "".join(old.split()) == "".join(new.split()):
        return f"(chỉ khác khoảng trắng / xuống dòng: cũ {_ends(old)}; mới {_ends(new)})"
    return ""


def render(plan) -> str:
    """Bản xác nhận markdown của plan metadata hoặc plan release."""
    if getattr(plan, "kind", None) == "release":
        import release  # import muộn: release.py import planner
        return release.render(plan)
    out = [f"# Bản xác nhận push ASC — version {plan.version}", "",
           f"App (apple.app_store_id): {plan.app_id or '(plan không ghi — làm plan mới)'}", ""]
    if not plan.ops:
        out += ["Không có thay đổi so với ASC.", ""]
    else:
        out += ["## Tóm tắt", "", "| Locale | Số field đổi |", "|---|---|"]
        for loc, n in sorted(Counter(o.locale for o in plan.ops).items()):
            out.append(f"| {loc} | {n} |")
        out += ["", f"Tổng: {len(plan.ops)} thao tác.", ""]
    out += ["## Xoá / thay", "", "**Không xoá gì**", ""]
    if plan.ops:
        out += ["## Chi tiết", ""]
        for o in plan.ops:
            out.append(f"### [{o.locale}] {o.field} ({o.scope}, {o.kind})")
            out.append("")
            old = o.old if o.old is not None else ""
            if len(o.new) > LONG or len(old) > LONG:
                diff = list(difflib.unified_diff(old.splitlines(keepends=True), o.new.splitlines(keepends=True),
                                                 "cũ", "mới", n=1))
                diff = [d if d.endswith("\n") else d + "\n\\ (không có xuống dòng cuối)\n" for d in diff]
                out += _fence("".join(diff).rstrip("\n"), "diff")
            else:
                out.append("Cũ:")
                out += _fence(o.old) if o.old is not None else ["(chưa có)"]
                out.append("Mới:")
                out += _fence(o.new)
            note = _ws_note(o.old, o.new)
            if note:
                out.append(note)
            if o.old is not None:
                out.append(f"- Cỡ cũ: {_size(o.field, o.old)}")
            out += [f"- Cỡ mới: {_size(o.field, o.new)}", ""]
    if plan.warnings:
        out += ["## Cảnh báo (field không đổi)", "",
                "Lint thấy vấn đề ở field plan này KHÔNG đổi (đang có sẵn trên ASC/store). Không chặn push; "
                "nên sửa ở lần sau (version đang bán chỉ sửa được promotionalText).", ""]
        out += [f"- {w}" for w in plan.warnings] + [""]
    out += ["## Cổng đã qua", "",
            "- lint: qua cho mọi field plan đổi (giới hạn ký tự/byte, chữ cấm, placeholder, trùng name/subtitle)",
            "- không xoá trắng field nào", "",
            f"Mã plan: {plan.plan_id}"]
    return "\n".join(out) + "\n"
