#!/usr/bin/env python3
"""Cổng String Catalog dựa trên BUILD — chính xác, không heuristic.

Khác `lint_localizable.py` (tĩnh, nhanh, chạy pre-commit): script này build thật rồi đọc các
file `.stringsdata` mà trình biên dịch Swift sinh ra. Đó là tập chuỗi Xcode THỰC SỰ extract,
kèm `source` + `location` — nên mọi kết luận ở đây là sự thật của build, không phải suy đoán
từ regex.

Điểm mấu chốt phát hiện 2026-09-06: `xcodebuild` CLI chỉ chạy `xcstringstool compile --dry-run`,
**không bao giờ ghi lại** `Localizable.xcstrings` — chỉ Xcode IDE mới ghi. Vì vậy "build rồi
git diff" là cách kiểm SAI (luôn sạch). Đường đúng là tự chạy `xcstringstool sync` lên một BẢN
COPY rồi so, và đó cũng chính là cách `--write` tái sinh catalog mà không cần mở Xcode.

Bốn cổng (ngôn ngữ khai ở `app.config.toml` mục `[i18n] languages`):

  G1  Bất biến: tập key của build `Internal` == tập key của build `Release`.
      Vỡ G1 nghĩa là catalog lại phụ thuộc config build → file phồng/teo theo lần build cuối.
  G2  Không key nào đến từ vùng không-phải-UI-sản-phẩm: file chỉ-INTERNAL (thư mục `Internal/`,
      vd `Core/Internal/InternalEntry.swift`) hoặc khối `#Preview` (Xcode extract cả `#Preview` — chuỗi
      mẫu sẽ thành key thật, bắt mọi ngôn ngữ phải dịch nó).
  G3  Catalog đã commit == catalog `xcstringstool sync` sinh ra từ build `Release`.
      Thiếu key = chuỗi UI mới chưa vào catalog. Thừa/`stale` = key mồ côi, source đã xoá.
  G4  Mọi ngôn ngữ khai trong `[i18n] languages` của app.config.toml phải dịch ĐỦ (state=translated),
      kể cả các nhánh `variations` (plural/device). Và ngôn ngữ có trong catalog mà không
      khai báo cũng FAIL.

    python3 tools/i18n/verify_catalog.py --check          # cổng (build cả 2 config)
    python3 tools/i18n/verify_catalog.py --write          # tái sinh catalog từ source
    python3 tools/i18n/verify_catalog.py --check --clean   # xoá DerivedData trước (dùng ở release)
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from lint_localizable import preview_lines   # noqa: E402  (dùng chung định nghĩa vùng #Preview)
import appconfig                              # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PROJ_DIR = REPO / appconfig.PROJ_DIR
PROJECT = REPO / appconfig.PROJECT
SCHEME = appconfig.SCHEME
APP_SRC = REPO / appconfig.SRC_ROOTS[0]
CATALOG = APP_SRC / "Localizable.xcstrings"
DD_ROOT = REPO / ".temp" / "i18n-dd"          # .temp/ đã nằm trong .gitignore
XCSTRINGSTOOL = "/Applications/Xcode.app/Contents/Developer/usr/bin/xcstringstool"

# Một định nghĩa với lint_localizable.py: code chỉ-INTERNAL nằm dưới thư mục `Internal/`.
INTERNAL_ONLY_DIRS = {"Internal"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def declared_languages() -> list[str]:
    """Ngôn ngữ cam kết, đọc từ app.config.toml (`i18n.languages`)."""
    langs = appconfig.get(appconfig.load(REPO), "i18n.languages")
    if not isinstance(langs, list) or not all(isinstance(x, str) and x for x in langs):
        raise appconfig.ConfigError("i18n.languages phải là danh sách chuỗi không rỗng")
    return langs


def simulator_udid() -> str:
    """UDID iPhone Simulator bất kỳ — destination generic thường không resolve được."""
    out = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "--json"],
                         capture_output=True, text=True, check=True).stdout
    for runtime, devices in json.loads(out)["devices"].items():
        if "iOS" not in runtime:
            continue
        for d in devices:
            if d.get("isAvailable") and "iPhone" in d.get("name", ""):
                return d["udid"]
    raise SystemExit("Không tìm thấy iPhone Simulator khả dụng (xcrun simctl list devices).")


# Build Release ở đây CHỈ để đọc `.stringsdata`, không ship. Trên `develop` catalog What's New có thẻ `.unreleased`
# mà case đó chỉ tồn tại dưới `#if INTERNAL || WHATSNEW_ALLOW_UNRELEASED` (WhatsNewCard.swift) ⇒ build Release thường
# lỗi biên dịch — đúng ý cho archive Store, nhưng làm vỡ `--check`/`--write`. Bật cờ riêng cho build trích chuỗi này
# (`$(inherited)` giữ các cờ sẵn có); case không mang chuỗi nào nên tập key (G1) không đổi. Archive Store /
# verify_release_clean KHÔNG truyền cờ.
WHATSNEW_ALLOW_FLAG = "WHATSNEW_ALLOW_UNRELEASED"


def release_extract_overrides(config: str) -> list:
    if config != "Release":
        return []
    return [f"SWIFT_ACTIVE_COMPILATION_CONDITIONS=$(inherited) {WHATSNEW_ALLOW_FLAG}"]


def build(config: str, udid: str, clean: bool) -> Path:
    """Build cho Simulator, trả về thư mục Intermediates chứa `.stringsdata`."""
    dd = DD_ROOT / config
    if clean and dd.exists():
        shutil.rmtree(dd)
    dd.mkdir(parents=True, exist_ok=True)
    print(f"  build {config} …", flush=True)
    cmd = ["xcodebuild", "-project", str(PROJECT), "-scheme", SCHEME,
           "-destination", f"id={udid}", "-configuration", config,
           "-derivedDataPath", str(dd), "build", "CODE_SIGNING_ALLOWED=NO"]
    cmd += release_extract_overrides(config)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join((r.stdout + r.stderr).splitlines()[-25:])
        raise SystemExit(f"build {config} FAIL:\n{tail}")
    return dd / f"Build/Intermediates.noindex/{SCHEME}.build" / \
        f"{config}-iphonesimulator/{SCHEME}.build/Objects-normal"


def stringsdata_files(objects_normal: Path) -> list[Path]:
    """`.stringsdata` của build hiện tại, đã loại file mồ côi.

    Build tăng dần giữ lại `.stringsdata` của source ĐÃ XOÁ — nếu không lọc thì key của file
    đã xoá vẫn được coi là còn dùng, và cổng G3 sẽ bỏ sót key mồ côi.
    """
    out, orphaned = [], 0
    for f in sorted(objects_normal.rglob("*.stringsdata")):
        try:
            src = json.loads(f.read_text(encoding="utf-8")).get("source", "")
        except (json.JSONDecodeError, OSError):
            continue
        if src and not Path(src).exists():
            orphaned += 1
            continue
        out.append(f)
    if orphaned:
        print(f"  (bỏ {orphaned} .stringsdata của source đã xoá)")
    return out


def keys_by_source(files: list[Path]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """({key: {source, …}}, {key: {"file:dòng" trong #Preview, …}}).

    Vế thứ hai dùng `location.startingLine` của `.stringsdata` đối chiếu với vùng `#Preview`
    của chính file đó — nhờ vậy G2 bắt được chuỗi preview mà không cần đoán.
    """
    m: dict[str, set[str]] = {}
    pv: dict[str, set[str]] = {}
    preview_cache: dict[str, set[int]] = {}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        raw = d.get("source", "")
        try:
            # So với gốc repo, không với thư mục nguồn đầu tiên: nguồn nằm ở nhiều root (AppHost/AppHost/, Core/).
            src = str(Path(raw).relative_to(REPO))
        except ValueError:
            src = raw or "?"
        if raw and src not in preview_cache:
            try:
                preview_cache[src] = preview_lines(
                    Path(raw).read_text(encoding="utf-8").splitlines())
            except OSError:
                preview_cache[src] = set()
        for entries in (d.get("tables") or {}).values():
            for e in entries:
                m.setdefault(e["key"], set()).add(src)
                line = (e.get("location") or {}).get("startingLine")
                if line and (line - 1) in preview_cache.get(src, set()):
                    pv.setdefault(e["key"], set()).add(f"{src}:{line}")
    return m, pv


def is_internal_source(rel: str) -> bool:
    p = Path(rel)
    return bool(INTERNAL_ONLY_DIRS & set(p.parts[:-1]))


def synced_catalog(files: list[Path], workdir: Path) -> dict:
    """Chạy `xcstringstool sync` lên BẢN COPY của catalog → catalog "đúng" theo source."""
    copy = workdir / CATALOG.name
    shutil.copy2(CATALOG, copy)
    r = subprocess.run([XCSTRINGSTOOL, "sync", str(copy), "--stringsdata", *map(str, files)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"xcstringstool sync FAIL:\n{r.stdout}\n{r.stderr}")
    return json.loads(copy.read_text(encoding="utf-8"))


def translation_gaps(cat: dict, lang: str) -> list[str]:
    """Key chưa dịch xong cho `lang`, kể cả nhánh `variations` (plural/device)."""
    def unit_ok(node: dict) -> bool:
        if "stringUnit" in node:
            return node["stringUnit"].get("state") == "translated"
        if "variations" in node:
            return all(
                unit_ok(case)
                for kind in node["variations"].values()
                for case in kind.values()
            )
        return False

    gaps = []
    for key, entry in cat.get("strings", {}).items():
        if entry.get("shouldTranslate") is False:
            continue
        node = (entry.get("localizations") or {}).get(lang)
        if node is None or not unit_ok(node):
            gaps.append(key)
    return gaps


def run(check: bool, clean: bool) -> int:
    if not PROJECT.exists():
        raise SystemExit(f"Chưa có {PROJECT} — chạy `cd {PROJ_DIR.name} && xcodegen generate`.")
    udid = simulator_udid()
    failures = 0

    rel_dir = build("Release", udid, clean)
    rel_files = stringsdata_files(rel_dir)
    rel_keys, rel_preview = keys_by_source(rel_files)

    if check:
        int_dir = build("Internal", udid, clean)
        int_keys, int_preview = keys_by_source(stringsdata_files(int_dir))

        # G1 — bất biến: catalog không phụ thuộc config build.
        only_i, only_r = set(int_keys) - set(rel_keys), set(rel_keys) - set(int_keys)
        if only_i or only_r:
            failures += 1
            fail(f"G1 tập key khác nhau giữa Internal và Release "
                 f"(chỉ-Internal {len(only_i)}, chỉ-Release {len(only_r)}) — "
                 f"catalog sẽ phồng/teo theo config build cuối")
            for k in sorted(only_i)[:20]:
                print(f"    chỉ-Internal  {sorted(int_keys[k])}  {k!r}")
            for k in sorted(only_r)[:20]:
                print(f"    chỉ-Release   {sorted(rel_keys[k])}  {k!r}")
        else:
            print(f"  G1 OK — Internal và Release cùng {len(rel_keys)} key")

        # G2 — không chuỗi debug / chuỗi mẫu preview nào vào hệ localize.
        dbg = {k: s for k, s in int_keys.items() if any(is_internal_source(x) for x in s)}
        pv = {**rel_preview, **int_preview}
        if dbg or pv:
            failures += 1
            if dbg:
                fail(f"G2 {len(dbg)} key extract từ file chỉ-INTERNAL — dùng dtext(...)")
                for k, s in sorted(dbg.items())[:20]:
                    print(f"    debug    {sorted(s)}  {k!r}")
            if pv:
                fail(f"G2 {len(pv)} key extract từ khối #Preview — dùng Text(verbatim:)")
                for k, s in sorted(pv.items())[:20]:
                    print(f"    preview  {sorted(s)}  {k!r}")
        else:
            print("  G2 OK — 0 key từ file chỉ-INTERNAL, 0 key từ #Preview")

    # G3 — catalog đã commit khớp với source.
    workdir = DD_ROOT / "sync"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    want = synced_catalog(rel_files, workdir)
    have = json.loads(CATALOG.read_text(encoding="utf-8"))

    if not check:
        # Chép thẳng bản `xcstringstool sync` sinh ra — giữ đúng định dạng của Apple, không
        # tự serialize lại (JSON tự dump sẽ lệch cách xuống dòng/escape với bản Xcode IDE ghi).
        shutil.copy2(workdir / CATALOG.name, CATALOG)
        print(f"  đã ghi {CATALOG.relative_to(REPO)} ({len(want.get('strings', {}))} key)")
        return 0

    missing = set(want.get("strings", {})) - set(have.get("strings", {}))
    extra = set(have.get("strings", {})) - set(want.get("strings", {}))
    stale = {k for k, v in have.get("strings", {}).items()
             if v.get("extractionState") == "stale"}
    if missing or extra or stale:
        failures += 1
        fail(f"G3 catalog lệch source: thiếu {len(missing)}, thừa {len(extra)}, stale {len(stale)}"
             f" — chạy `python3 tools/i18n/verify_catalog.py --write`")
        for k in sorted(missing)[:20]:
            print(f"    THIẾU  {sorted(rel_keys.get(k, []))}  {k!r}")
        for k in sorted(extra)[:20]:
            print(f"    THỪA   {k!r}")
        for k in sorted(stale)[:20]:
            print(f"    STALE  {k!r}")
    elif have != want:
        failures += 1
        fail("G3 catalog cùng tập key nhưng nội dung khác bản sync — chạy --write")
    else:
        print(f"  G3 OK — catalog khớp source ({len(have.get('strings', {}))} key)")

    # G4 — đủ bản dịch cho mọi ngôn ngữ đã cam kết.
    declared = declared_languages()
    source_lang = have.get("sourceLanguage", "en")
    in_catalog = {lang for e in have.get("strings", {}).values()
                  for lang in (e.get("localizations") or {})}
    undeclared = in_catalog - set(declared)
    if undeclared:
        failures += 1
        fail(f"G4 catalog có ngôn ngữ chưa khai trong app.config.toml [i18n] languages: "
             f"{sorted(undeclared)}")
    total = len(have.get("strings", {}))
    cov = []
    for lang in declared:
        if lang == source_lang:
            cov.append(f"{lang} {total}/{total} (nguồn)")
            continue
        gaps = translation_gaps(have, lang)
        cov.append(f"{lang} {total - len(gaps)}/{total}")
        if gaps:
            failures += 1
            fail(f"G4 `{lang}` thiếu bản dịch cho {len(gaps)} key")
            for k in sorted(gaps)[:30]:
                print(f"    {lang} chưa dịch: {k!r}")
            if len(gaps) > 30:
                print(f"    … và {len(gaps) - 30} key nữa")
    print(f"  G4 coverage — {' · '.join(cov)}")

    if failures:
        print(f"\n--- {failures} cổng KHÔNG đạt ---", file=sys.stderr)
        return 1
    print("\nPASS: String Catalog đúng và đủ.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="chạy 4 cổng, không sửa file")
    g.add_argument("--write", action="store_true", help="tái sinh catalog từ source (không cần Xcode IDE)")
    ap.add_argument("--clean", action="store_true",
                    help="xoá DerivedData trước khi build (dùng cho cổng release)")
    ap.add_argument("--force", action="store_true",
                    help="chạy --check cả khi cấu hình chỉ có ngôn ngữ nguồn")
    a = ap.parse_args()
    try:
        skip = a.check and not a.force and only_source_language()
    except appconfig.ConfigError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    if skip:
        print("SKIP: app.config.toml [i18n] languages chỉ có ngôn ngữ nguồn (en) — cổng catalog chưa cần "
              "(thiếu key chỉ hiện đúng literal tiếng Anh). Tự bật khi thêm ngôn ngữ; ép chạy: --force.")
        return 0
    try:
        return run(check=a.check, clean=a.clean)
    except appconfig.ConfigError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2


def only_source_language() -> bool:
    """App chỉ ship ngôn ngữ nguồn ⇒ 4 cổng (G1–G4) không đổi được gì user thấy.

    Quyết định user 2026-11-09: đa ngôn ngữ còn xa; mỗi lần --check build 2 config (~2–5 phút) và đã chạy
    85 lần trong 3 ngày mission. Catalog có thể trôi (thiếu/thừa key) trong lúc này — trước khi thêm ngôn
    ngữ chạy `--write` một lần rồi `--check`.
    """
    return declared_languages() == ["en"]


if __name__ == "__main__":
    raise SystemExit(main())
