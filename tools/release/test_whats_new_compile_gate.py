"""Gác TĨNH cho cổng biên dịch What's New (chốt chính chống ship thẻ `.unreleased`).

Cổng: case `CardVersion.unreleased` (Core/Engage/WhatsNew/WhatsNewCard.swift) chỉ tồn tại dưới
`#if INTERNAL || WHATSNEW_ALLOW_UNRELEASED`; config Release không đặt cờ nào trong hai cờ đó ⇒ archive Store còn sót
thẻ là lỗi biên dịch. Cổng có thể mất LẶNG LẼ (bỏ `#if` ⇒ Debug vẫn xanh, Release với catalog sạch vẫn build) nên gác
bằng test này:
  1. mọi dòng CODE trong nguồn app (`Core/`, `AppHost/AppHost/`, `CoreOptional/` nếu có — `appconfig.SRC_ROOTS`)
     khai báo hoặc so khớp `case …unreleased` nằm trong nhánh `#if`/`#elseif` mà điều kiện chỉ là phép OR của các
     cờ cho phép (không nằm ở `#else`);
  2. AppHost/project.yml: config Release không có INTERNAL / WHATSNEW_ALLOW_UNRELEASED trong cờ Swift; cờ cho phép
     không xuất hiện ở đâu trong project.yml;
  3. chỉ `tools/i18n/verify_catalog.py` (build trích chuỗi) truyền cờ cho phép, và chỉ cho config Release.

Chạy: python3 -m unittest tools/release/test_whats_new_compile_gate.py
"""
import os
import re
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "common"))
import appconfig  # noqa: E402  (bố cục thư mục một nguồn)

# Mọi gốc nguồn biên dịch vào app: lõi + phần của app (+ khối tuỳ chọn khi đã có). Thẻ `.unreleased` lạc ở BẤT KỲ gốc
# nào cũng phải bị bắt — lõi khai case, app viết catalog.
APP_SRC = [os.path.join(REPO, r) for r in dict.fromkeys((*appconfig.SRC_ROOTS, "CoreOptional/"))  # SRC_ROOTS đã có CoreOptional/
           if os.path.isdir(os.path.join(REPO, r))]
PROJECT_YML = os.path.join(REPO, appconfig.PROJ_DIR, "project.yml")
CARD = os.path.join(REPO, "Core", "Engage", "WhatsNew", "WhatsNewCard.swift")
ALLOWED_FLAGS = {"INTERNAL", "WHATSNEW_ALLOW_UNRELEASED"}
ALLOW_FLAG = "WHATSNEW_ALLOW_UNRELEASED"
# Khai báo case (`case unreleased`) hoặc so khớp (`case .unreleased:`, `if case .unreleased = v`). Chỗ DÙNG
# (`version: .unreleased` trong catalog) là hợp lệ trên develop — build Release lỗi chính vì case không tồn tại.
CASE_SITE = re.compile(r"\bcase\b.*\bunreleased\b")


def strip_comment(line: str) -> str:
    """Bỏ phần `//…` (nguồn app không có `//` trong chuỗi ở các dòng liên quan; dòng doc `///` bỏ trọn)."""
    i = line.find("//")
    return line if i < 0 else line[:i]


def guarded_condition_ok(cond: str) -> bool:
    """Điều kiện là OR của các cờ cho phép, vd `INTERNAL || WHATSNEW_ALLOW_UNRELEASED` (không `!`, `&&`, os(…))."""
    parts = [p.strip() for p in cond.split("||")]
    return bool(parts) and all(p in ALLOWED_FLAGS for p in parts)


def unguarded_uses(text: str) -> tuple:
    """Trả (số dòng `case …unreleased`, danh sách dòng KHÔNG được gác)."""
    stack = []  # mỗi frame: True nếu nhánh hiện tại của khối #if là nhánh "cờ cho phép"
    uses, bad = 0, []
    in_block_comment = False
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw
        if in_block_comment:
            end = line.find("*/")
            if end < 0:
                continue
            line, in_block_comment = line[end + 2:], False
        while "/*" in line:
            a = line.find("/*")
            b = line.find("*/", a + 2)
            if b < 0:
                line, in_block_comment = line[:a], True
                break
            line = line[:a] + line[b + 2:]
        code = strip_comment(line).strip()
        m = re.match(r"#(if|elseif)\b(.*)$", code)
        if m:
            ok = guarded_condition_ok(m.group(2))
            if m.group(1) == "if":
                stack.append(ok)
            elif stack:
                stack[-1] = ok
            continue
        if re.match(r"#else\b", code):
            if stack:
                stack[-1] = False
            continue
        if re.match(r"#endif\b", code):
            if stack:
                stack.pop()
            continue
        if CASE_SITE.search(code):
            uses += 1
            if not any(stack):
                bad.append(f"{no}: {raw.strip()}")
    return uses, bad


FLAG_KEYS = ("SWIFT_ACTIVE_COMPILATION_CONDITIONS", "OTHER_SWIFT_FLAGS")
CONFIGS = ("Debug", "Internal", "Release")


def _flow_pairs(val: str) -> list:
    """Cặp (khoá, giá trị) của một flow mapping một dòng `{ A: "x y", B: z }` (project.yml của template viết config
    dạng này). Giá trị có thể trong ngoặc kép (chứa dấu phẩy/dấu cách); không lồng `{}`."""
    inner = val.strip()[1:-1]
    return re.findall(r'([A-Za-z0-9_\-]+)\s*:\s*("[^"]*"|[^,]*)', inner)


def release_swift_flag_lines(yml: str) -> dict:
    """{tên config: [giá trị cờ Swift]} theo cây thụt lề của project.yml (chỉ đọc khoá, không cần PyYAML). Hiểu cả
    dạng khối (`Release:` xuống dòng rồi khoá con) lẫn flow mapping một dòng (`Release: { KEY: "…" }`)."""
    out, path = {}, []
    for raw in yml.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        m = re.match(r"\s*([A-Za-z0-9_\-]+)\s*:(.*)$", raw)
        if not m:
            continue
        while path and path[-1][0] >= indent:
            path.pop()
        key, val = m.group(1), m.group(2).strip()
        ancestors = [anc for _, anc in path]
        if key in FLAG_KEYS:
            for anc in ancestors:
                if anc in CONFIGS:
                    out.setdefault(anc, []).append(val)
        elif val.startswith("{") and val.endswith("}"):
            owners = [a for a in (*ancestors, key) if a in CONFIGS]
            for k, v in _flow_pairs(val):
                if k in FLAG_KEYS:
                    for anc in owners:
                        out.setdefault(anc, []).append(v.strip())
        path.append((indent, key))
    return out


class CompileGateTests(unittest.TestCase):
    def test_moi_cho_dung_unreleased_trong_app_deu_duoc_gac(self):
        total, bad = 0, []
        # chống pass rỗng: phải duyệt cả lõi lẫn phần của app
        self.assertGreaterEqual(len(APP_SRC), 2, APP_SRC)
        for root, _, files in (w for src in APP_SRC for w in os.walk(src)):
            for f in files:
                if f.endswith(".swift"):
                    p = os.path.join(root, f)
                    with open(p, encoding="utf-8") as fh:
                        n, b = unguarded_uses(fh.read())
                    total += n
                    bad += [f"{os.path.relpath(p, REPO)}:{x}" for x in b]
        self.assertEqual(bad, [], "dùng `unreleased` ngoài `#if INTERNAL || WHATSNEW_ALLOW_UNRELEASED`")
        with open(CARD, encoding="utf-8") as fh:
            card_uses, _ = unguarded_uses(fh.read())
        # khai báo case + nhánh switch trong effective(current:) — chống pass rỗng nếu đổi tên/đường dẫn
        self.assertGreaterEqual(card_uses, 2)
        self.assertGreaterEqual(total, 2)

    def test_bo_quet_bat_duoc_dang_khong_gac(self):
        cases = {
            "trần": ("enum C {\n    case unreleased\n}\n", 1),
            "#else": ("#if INTERNAL\n#else\ncase unreleased\n#endif\n", 1),
            "điều kiện khác": ("#if os(iOS)\ncase unreleased\n#endif\n", 1),
            "phủ định": ("#if !INTERNAL\ncase unreleased\n#endif\n", 1),
            "AND": ("#if INTERNAL && DEBUG\ncase unreleased\n#endif\n", 1),
            "sau #endif": ("#if INTERNAL\n#endif\ncase .unreleased: return x\n", 1),
            "gác đúng": ("#if INTERNAL || WHATSNEW_ALLOW_UNRELEASED\ncase unreleased\n#endif\n", 0),
            "lồng trong khối khác": ("#if INTERNAL\n#if os(iOS)\ncase .unreleased: 1\n#endif\n#endif\n", 0),
            "chỉ comment": ("/// `.unreleased`\n// unreleased\n/* unreleased */\n", 0),
            "if case trần": ("if case .unreleased = v { }\n", 1),
            "chỗ dùng trong catalog": ("X(id: \"a\", version: .unreleased)\n", 0),
        }
        for name, (src, n_bad) in cases.items():
            with self.subTest(name):
                self.assertEqual(len(unguarded_uses(src)[1]), n_bad)

    def test_project_yml_release_khong_co_co_internal_hay_allow(self):
        with open(PROJECT_YML, encoding="utf-8") as fh:
            yml = fh.read()
        self.assertNotIn(ALLOW_FLAG, yml, "cờ cho phép chỉ được truyền qua dòng lệnh build trích chuỗi")
        flags = release_swift_flag_lines(yml)
        # chống pass rỗng: parser phải thấy INTERNAL ở Debug và Internal
        for cfg in ("Debug", "Internal"):
            self.assertTrue(any("INTERNAL" in v for v in flags.get(cfg, [])), f"không đọc được cờ của {cfg}")
        for v in flags.get("Release", []):
            # `-DINTERNAL` (OTHER_SWIFT_FLAGS) không có ranh giới từ trước `I` ⇒ cho phép tiền tố -D.
            self.assertNotRegex(v, r"(?:\b|-D)INTERNAL\b|" + ALLOW_FLAG)

    def test_parser_yml_thay_co_release(self):
        yml = ("settings:\n  configs:\n    Debug:\n      SWIFT_ACTIVE_COMPILATION_CONDITIONS: \"DEBUG INTERNAL\"\n"
               "    Release:\n      SWIFT_ACTIVE_COMPILATION_CONDITIONS: \"$(inherited) INTERNAL\"\n")
        self.assertEqual(release_swift_flag_lines(yml)["Release"], ['"$(inherited) INTERNAL"'])
        # Dạng flow mapping một dòng (bố cục của AppHost/project.yml), kể cả khoá khác đứng cùng dòng.
        flow = ("settings:\n  configs:\n    Debug:    { SWIFT_ACTIVE_COMPILATION_CONDITIONS: \"DEBUG INTERNAL\" }\n"
                "    Release:  { APP_WEB_HOST: x, OTHER_SWIFT_FLAGS: \"-DINTERNAL\" }\n")
        got = release_swift_flag_lines(flow)
        self.assertEqual(got["Debug"], ['"DEBUG INTERNAL"'])
        self.assertEqual(got["Release"], ['"-DINTERNAL"'])

    def test_chi_build_trich_chuoi_release_truyen_co_allow(self):
        sys.path.insert(0, os.path.join(REPO, "tools", "i18n"))
        import verify_catalog  # noqa: E402
        self.assertEqual(verify_catalog.release_extract_overrides("Release"),
                         [f"SWIFT_ACTIVE_COMPILATION_CONDITIONS=$(inherited) {ALLOW_FLAG}"])
        self.assertEqual(verify_catalog.release_extract_overrides("Internal"), [])
        # Không script phát hành nào khác nhắc cờ (archive Store / verify_release_clean / bump).
        users = []
        for root, _, files in os.walk(os.path.join(REPO, "tools")):
            for f in files:
                if f.endswith((".py", ".sh")) and not f.startswith("test_"):
                    p = os.path.join(root, f)
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        if ALLOW_FLAG in fh.read():
                            users.append(os.path.relpath(p, REPO))
        self.assertEqual(users, ["tools/i18n/verify_catalog.py"])


if __name__ == "__main__":
    unittest.main()
