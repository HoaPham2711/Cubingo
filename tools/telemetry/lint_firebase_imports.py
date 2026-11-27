#!/usr/bin/env python3
"""Chặn `import Firebase*` lọt ra ngoài Core/Telemetry/FirebaseSink.swift (và khối tuỳ chọn CoreOptional/WebAPI/).

Vì sao cần cổng máy: cả kiến trúc telemetry đứng trên đúng một lời hứa — Firebase bị nhốt sau
facade `Track`/`AnalyticsSink`. Lời hứa đó bị phá bởi MỘT dòng import ở một View nào đó, và
không có triệu chứng nào cho tới ngày muốn đổi/bỏ vendor thì phát hiện nó đã bám vào 40 file.

Quét các thư mục `appconfig.SRC_ROOTS`, `Core/` và `CoreOptional/` (nếu có) dưới gốc repo — mỗi thư mục một lần
(SRC_ROOTS đã chứa `Core/` từ P2; root lồng nhau cũng chỉ quét một lần).

Chỗ được phép cũng bị giới hạn MODULE: sink chỉ `FirebaseCore`/`FirebaseAnalytics`/`FirebaseCrashlytics`; khối
WebAPI chỉ ĐÚNG MỘT file (`AppCheckTokenSource.swift`) và chỉ `FirebaseAppCheck` + `FirebaseCore` (để hỏi
`FirebaseApp.app()` trước khi chạm App Check — chưa configure thì `AppCheck.appCheck()` crash). File khác trong
WebAPI/ không được import Firebase. `FirebaseAuth` không vào template ở đâu cả.

Chạy tay:  python3 tools/telemetry/lint_firebase_imports.py [--root <thư mục gốc>]
Tự động:   .githooks/pre-commit, tools/template/selfcheck.sh (bước 1)
Exit: 0 sạch, 1 có vi phạm, 2 không tìm thấy thư mục nguồn nào.
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "common"))
import appconfig  # noqa: E402

GOC_MAC_DINH = pathlib.Path(__file__).resolve().parents[2]
# Đường dẫn tương đối so với gốc repo → module Firebase được import ở đó. Khoá kết thúc bằng `/` là thư mục
# (mọi file .swift bên dưới); còn lại là đúng một file.
ALLOWED = {
    "Core/Telemetry/FirebaseSink.swift": {"FirebaseCore", "FirebaseAnalytics", "FirebaseCrashlytics"},
    "CoreOptional/WebAPI/AppCheckTokenSource.swift": {"FirebaseAppCheck", "FirebaseCore"},
}
ROOTS_THEM = ("Core/", "CoreOptional/")
# Khớp trên văn bản ĐÃ BỎ comment + chuỗi (`bo_comment_va_chuoi`), nên comment/ghi chú đuôi dòng không che được
# import, còn comment/chuỗi chỉ NHẮC tới `import Firebase…` thì không bị bắt. Chấp nhận thuộc tính đứng trước
# (`@_exported`, `@testable`, `@preconcurrency`, `@_implementationOnly`, `@_spi(X)`…) và dạng import một symbol
# (`import struct FirebaseCore.FirebaseOptions`). Tên module có ranh giới từ (`\w*` tham lam + `\b`). Câu lệnh có
# thể đứng sau `;` trên cùng dòng (`import Foundation; import FirebaseCore`), và `import` với tên module có thể nằm
# trên hai dòng (dòng báo lỗi = dòng của từ `import`).
MAU = re.compile(
    r"(?:^|;)[ \t]*(?:@\w+(?:\([^)\n]*\))?[ \t]+)*import\s+"
    r"(?:(?:typealias|struct|class|enum|protocol|let|var|func)\s+)?"
    r"(Firebase\w*|GoogleAppMeasurement\w*)\b",
    re.M,
)


def bo_comment_va_chuoi(src: str) -> str:
    """Thay comment (`//`, `/* */` lồng nhau) và literal chuỗi (`"…"`, `\"\"\"…\"\"\"`, cả dạng `#"…"#`) bằng dấu
    cách, GIỮ nguyên xuống dòng ⇒ số dòng báo lỗi vẫn đúng. Trình quét đơn giản, đủ cho câu hỏi "dòng này có phải
    một câu lệnh import thật không" — không cần hiểu nội suy chuỗi.

    Chuỗi KHÔNG có dấu đóng (vd `#"` trong regex literal `/#"/`) không được nuốt phần còn lại của file: chuỗi thô một
    dòng phải đóng trên chính dòng đó, không thì `#` được coi là ký tự thường; chuỗi nhiều dòng không đóng chỉ xoá tới
    hết dòng mở. Lỗ hổng đã biết: regex literal không được hiểu như literal (nội dung của nó vẫn được quét)."""
    out: list[str] = []
    i, n = 0, len(src)

    def trang(s: str) -> str:
        return "".join(c if c == "\n" else " " for c in s)

    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(trang(src[i:j]))
            i = j
        elif src.startswith("/*", i):
            sau, j = 1, i + 2
            while j < n and sau:
                if src.startswith("/*", j):
                    sau, j = sau + 1, j + 2
                elif src.startswith("*/", j):
                    sau, j = sau - 1, j + 2
                else:
                    j += 1
            out.append(trang(src[i:j]))
            i = j
        elif c == "#" or c == '"':
            # Literal chuỗi, có thể có dấu thăng bao ngoài (`#"…"#`, `##"""…"""##`).
            k = i
            while k < n and src[k] == "#":
                k += 1
            if k >= n or src[k] != '"':
                out.append(src[i:k] if k > i else c)
                i = k if k > i else i + 1
                continue
            thang = "#" * (k - i)
            mo = '"""' if src.startswith('"""', k) else '"'
            dong = mo + thang
            j = src.find(dong, k + len(mo))
            if mo == '"' and not thang:
                # Chuỗi một dòng thường: bỏ qua ký tự thoát `\"`.
                j = k + 1
                while j < n and src[j] not in '"\n':
                    j += 2 if src[j] == "\\" else 1
                j = j + 1 if j < n and src[j] == '"' else j
            elif mo == '"':
                # Chuỗi thô một dòng: dấu đóng phải nằm trên CHÍNH dòng này, không thì `#` không mở chuỗi.
                het_dong = src.find("\n", k)
                het_dong = n if het_dong < 0 else het_dong
                if j < 0 or j > het_dong:
                    out.append(thang)
                    i = k
                    continue
                j += len(dong)
            elif j < 0:
                # Chuỗi nhiều dòng không đóng: chỉ xoá tới hết dòng mở, không nuốt cả file.
                j = src.find("\n", k)
                j = n if j < 0 else j
            else:
                j += len(dong)
            out.append(trang(src[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Chặn import Firebase* ngoài FirebaseSink.swift")
    ap.add_argument("--root", default=str(GOC_MAC_DINH), help="gốc repo cần quét (mặc định: gốc của script)")
    goc = pathlib.Path(ap.parse_args().root).resolve()

    # dict.fromkeys: bỏ trùng mà giữ thứ tự — nếu không, một import lẻ trong Core/ bị báo hai lần.
    thu_muc = [d for d in dict.fromkeys((goc / r).resolve() for r in (*appconfig.SRC_ROOTS, *ROOTS_THEM))
               if d.is_dir()]
    # Root nằm trong root khác (vd ai đó thêm `Core/Telemetry/`) ⇒ bỏ, root cha đã quét.
    thu_muc = [d for d in thu_muc if not any(o != d and o in d.parents for o in thu_muc)]
    if not thu_muc:
        print(f"FAIL: không tìm thấy thư mục nguồn nào dưới {goc}")
        return 2
    def module_duoc_phep(f: pathlib.Path) -> set[str]:
        rel = f.relative_to(goc).as_posix()
        for cho, mods in ALLOWED.items():
            if rel == cho or (cho.endswith("/") and rel.startswith(cho)):
                return mods
        return set()

    vi_pham = []
    for d in thu_muc:
        for f in sorted(d.rglob("*.swift")):
            duoc = module_duoc_phep(f)
            noi_dung = bo_comment_va_chuoi(f.read_text(encoding="utf-8", errors="ignore"))
            for m in MAU.finditer(noi_dung):
                if m.group(1) in duoc:
                    continue
                dong = noi_dung[: m.start()].count("\n") + 1
                vi_pham.append(f"{f.relative_to(goc)}:{dong}: {m.group(0).strip()}")

    if vi_pham:
        print("FAIL: `import Firebase*` chỉ được phép ở các chỗ sau, đúng các module này:")
        for cho, mods in ALLOWED.items():
            print(f"  {cho}: {', '.join(sorted(mods))}")
        print("Vi phạm:")
        for v in vi_pham:
            print("  " + v)
        print("\nDùng Track.log(.tenEvent(...)) tại call site thay vì import trực tiếp.")
        return 1

    print("OK: Firebase vẫn bị nhốt trong " + " + ".join(ALLOWED) + " (đúng module được phép)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
