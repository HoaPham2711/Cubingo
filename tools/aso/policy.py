"""Allowlist lệnh `asc` + logic quyết định của hook guard_asc.

Mô hình đe doạ: hook là DÂY BẪY chống việc ghi App Store Connect do nhầm lẫn hoặc do agent tự làm — KHÔNG phải
sandbox shell. Hàng rào cấu trúc nằm ở chỗ khác: (a) `asc` cài ngoài PATH (`shared_bin_dir()/asc/<ver>/asc`, chạm
thư mục đó trong lệnh ⇒ chặn), (b) mọi lời gọi không phải apply chạy với ASC_READ_ONLY=1 (asc_cli), (c) vai trò của
khoá ASC. Hook CHỈ thấy văn bản một lệnh Bash; nó KHÔNG thấy (ngoài phạm vi, chấp nhận):
- tên ghép lúc chạy: `'as'+'c'` trong Python, `$(printf a)sc`, `${X}sc`, base64/hex, biến shell đặt ở lệnh TRƯỚC;
- code đã nằm sẵn trong file rồi được chạy (script, Makefile, npm script, test), kể cả file do một lệnh được phép
  trước đó ghi ra;
- cấu hình đã nằm sẵn: `.git/config`, `~/.gitconfig`, hook git của repo, `.gitattributes` (filter/textconv) — hook
  chỉ xét lúc ĐẶT các khoá chạy được lệnh trong chính lệnh này, không đọc file cấu hình;
- lệnh mà một tuỳ chọn/khoá/biến cho phép chạy (`--upload-pack`, `-O`, `ext::`, alias git, khoá trơ…) nhưng KHÔNG
  chứa chữ asc và không đụng vùng tools/aso (vd `--upload-pack='sh x.sh'`): đó là code nằm trong file, ngoài phạm vi;
- alias/hàm shell định nghĩa ngoài lệnh đang xét, `PATH` trỏ tới bản `asc` khác tên;
- lệnh chạy ngoài công cụ Bash (tool khác, terminal của người dùng).
Phần đó do các lớp trong chương trình (policy của asc_cli + env chỉ-đọc, applier) và luật của skill gánh.

Lớp allowlist (fail-closed): lệnh có đoạn chạy code (python/bash/eval/env/xargs…, hoặc chạy thẳng
một đường dẫn) mà đụng vùng tools/aso — đường dẫn `tools/aso`, dạng chấm `tools.aso`, tên module
của mình, glob `*?[` chưa nháy, hoặc cwd của lệnh nằm trong `<repo>/tools` — chỉ qua khi TOÀN BỘ
lệnh là một dạng chuẩn tính theo gốc repo. Mỗi đoạn lệnh xét riêng (miễn trừ chỉ-đọc theo đoạn),
kết quả chặt nhất thắng.

Chữ `asc` (Ruling 8): dò KHÔNG phân biệt hoa thường trên MỌI token đã gỡ nháy (shlex) của MỌI đoạn — kể cả git
"text"/"safe", kể cả trong $()/backtick (`_decide_segment` + Backstop 2 `_backstop_asc`). Chỉ hai ngoại lệ: giá trị
message/mẫu tìm của git — THEO LỆNH CON (`GIT_MSG_BY_SUB`: `-m/--message/-F/--file` của commit/tag/merge/stash/notes/
revert/cherry-pick; `--grep/--author/--committer/-S/-G` của log/show/shortlog; không bao giờ bỏ một token bắt đầu bằng
`-`) — và `echo`/`printf` không pipe. Các luật là CẤU TRÚC, không phải danh sách chuỗi:
- gỡ nháy đệ quy (`_variants`): mỗi token được shlex tách lại chữ bên trong tới khi không đổi (nháy lồng của `sh -c`,
  thân alias mà git `split_cmdline` gỡ thêm một lớp), cộng các lớp viết chữ shell gỡ trước khi chạy (`_shell_norm`:
  ANSI-C `$'\\141sc'`, nối dòng `\\⏎`; mở ngoặc nhọn `{a,}sc`; giá trị mặc định `${X:-asc}`); tuỳ chọn ngắn có giá trị
  dính (`-Oasc`) xét cả phần giá trị;
- glob: mảnh có basename là glob NHẮM asc (khớp asc mà không khớp tên thường — `a?c`, `[a]sc`, `A*`; `*`/`[a-z]*` là
  chung chung) = chữ asc; trong `sh -c '…'` từ lệnh là glob ⇒ chặn (ở mức ngoài, luật glob của lớp allowlist gánh);
- wrapper trong suốt (`WRAPPER_SPEC`, `_peel`): timeout/nice/nohup/time/caffeinate/env/command/builtin/exec/stdbuf/
  ionice/sudo/doas/arch/xcrun/xargs/… cùng tuỳ chọn và đối số riêng được bỏ để tìm từ lệnh thật cho MỌI luật (git, shell
  -c, echo, glob, đoạn chạy code); `env -S '…'` xét như một lệnh; git hay shell đứng sau tiền tố LẠ vẫn được xét.
Thư mục cài asc (`_touches_install_dir`): đường dẫn chuẩn hoá (`./`, `//`, `..`, ngoặc nhọn) rồi so từng cặp thành
phần — tên thật hoặc glob khớp — với `ios-app-factory/asc` hay chuỗi `asc/<x>/asc` (cặp hai glob chung chung như `*/*`
không tính), cộng gốc `$IOS_APP_FACTORY_BIN` nếu đặt ⇒ chặn.

Chặn nhầm đã biết (chấp nhận, Ruling 8 — viết lại lệnh):
- `git commit -F - <<'EOF' … asc … EOF`: thân heredoc là các đoạn lệnh riêng ⇒ chữ asc bị dò. Cách làm: ghi message ra
  file rồi `git commit -F <file>`.
- `grep … asc`, `rg asc`, `ORDER BY x ASC`, `--sort=asc`, `git log --format='asc: %s'`, `git checkout ASC`: chữ asc là
  token. Cách làm: tìm bằng công cụ Grep (không qua Bash); đổi chữ trong định dạng.
- glob nhắm asc làm đối số (`ls a*`, `rm x/[a]sc`), cờ ngắn gộp kết thúc bằng `asc` (`ls -lasc`), đường dẫn `*/asc/…`:
  liệt kê tên cụ thể hoặc tách cờ.
Ngoài phạm vi thêm: glob chung chung (`*/*/*/*`) làm đối số của một tiền tố KHÔNG có trong WRAPPER_SPEC — tên file
do hệ thống file quyết định lúc chạy, cùng loại với tên ghép lúc chạy.

git (`_git_parse`) — loại chỉ quyết định luật VÙNG tools/aso (REF_AREA/cwd/import), không miễn luật chữ asc:
"text" (GIT_TEXT: commit/log/show/diff/status/add/…) và "safe" (GIT_SAFE_SUB: checkout/restore/stash/fetch/grep/
config/…) không phải đoạn chạy code ⇒ đường dẫn/message của chúng không bị xét vùng/cwd/import; `-C`/`--git-dir`/
`--work-tree` không đổi loại. Mọi dạng khác (alias = lệnh con lạ, bisect/rebase/submodule/…, `--exec-path`,
`--upload-pack`/`-O`/`--ext-diff`…, process substitution) là "exec". Khoá cấu hình chạy được lệnh (GIT_EXEC_KEY:
core.fsmonitor/hooksPath/pager/sshCommand/editor, *.textconv, diff.external, gpg.program, include.path, includeIf.*,
filter.*, sequence.editor, …; `protocol.*.allow`) ĐẶT qua `git config`, `-c` chỉ qua với giá trị trơ `true`, `:`,
`cat` hoặc rỗng; `--config-env` (giá trị không thấy) ⇒ chặn. Alias: thân `!…` chỉ trơ mới qua; thân git được xét như
một dòng lệnh git. Biến môi trường GIT_CONFIG_*/GIT_PAGER/GIT_EXTERNAL_DIFF/GIT_SSH(_COMMAND)/GIT_EDITOR/
GIT_SEQUENCE_EDITOR/GIT_ALLOW_PROTOCOL/EDITOR/VISUAL…: cùng luật giá trị trơ. Lý do chặn loại này mở đầu bằng
HUMAN_ONLY (việc người dùng tự làm) — hook không gợi ý lệnh ASO cho chúng.

Chỉ stdlib. Hai việc:
- `check_asc_args`: wrapper (aso.py) chỉ cho chạy đúng các lệnh `asc` trong danh sách này.
- `hook_decision`: hook PreToolUse(Bash) dùng để quyết định allow/ask/block cho một dòng lệnh.
"""
import codecs
import fnmatch
import functools
import os
import posixpath
import re
import shlex
from pathlib import Path
from typing import Callable, Optional

READ_COMMANDS = (
    ("version",),
    ("metadata", "pull"),
    ("metadata", "validate"),
    ("metadata", "keywords", "audit"),
    ("versions", "list"),
    ("versions", "view"),
    ("builds", "list"),
    ("builds", "info"),
    ("builds", "wait"),
    ("localizations", "list"),
    ("apps", "info", "view"),
    ("validate",),
    # Asset library + placements + custom product page (chỉ đọc) — giữ sẵn trong allowlist cho luồng ảnh/video/CPP
    # mà template CHƯA mang (aso.py chưa có lệnh nào dùng).
    ("asset-library", "view"),
    ("asset-library", "images", "list"),
    ("asset-library", "images", "view"),
    ("asset-library", "videos", "list"),
    ("asset-library", "videos", "view"),
    ("localizations", "placements", "list"),
    ("product-pages", "custom-pages", "list"),
    ("product-pages", "custom-pages", "view"),
    ("product-pages", "custom-pages", "versions", "list"),
    ("product-pages", "custom-pages", "localizations", "list"),
    ("product-pages", "custom-pages", "localizations", "placements", "list"),
    ("product-pages", "custom-pages", "localizations", "search-keywords", "list"),
)
# Lệnh ghi: chỉ chạy qua `aso.py apply`. Luồng ra bản dùng upload/tạo version/gắn build.
WRITE_COMMANDS = (
    ("metadata", "push"),
    ("builds", "upload"),
    ("versions", "create"),
    ("versions", "attach-build"),
    # Asset library, placements (ảnh/video lên localization), custom product page + từ khoá — giữ sẵn cho luồng
    # ảnh/video/CPP chưa có ở template; vẫn chỉ chạy được qua `aso.py apply`.
    ("asset-library", "images", "upload"),
    ("asset-library", "videos", "upload"),
    ("asset-library", "videos", "set-poster-frame"),
    ("localizations", "placements", "create"),
    ("localizations", "placements", "delete"),
    ("product-pages", "custom-pages", "localizations", "create"),
    ("product-pages", "custom-pages", "localizations", "update"),
    ("product-pages", "custom-pages", "localizations", "placements", "create"),
    ("product-pages", "custom-pages", "localizations", "placements", "delete"),
    ("product-pages", "custom-pages", "localizations", "search-keywords", "add"),
    ("product-pages", "custom-pages", "localizations", "search-keywords", "delete"),
)
# Lệnh ghi chỉ nhận ĐÚNG bộ cờ này (mỗi cờ một lần, có giá trị, không đối số lạ). Cờ khác — vd
# --if-exists, --copy-metadata-from, --test-notes, --wait — ⇒ PolicyError: không để argv lệch khỏi cái
# đã duyệt trong plan. `--output json` do asc_cli thêm SAU bước kiểm này.
_PLACEMENT_CREATE = {"--localization-id", "--placement-type", "--placement-group"}
_PLACEMENT_DELETE = {"--placement-ids", "--confirm"}
WRITE_FLAGS = {
    ("metadata", "push"): {"--app", "--version", "--dir"},
    ("builds", "upload"): {"--app", "--ipa"},
    ("versions", "create"): {"--app", "--version", "--platform", "--release-type"},
    ("versions", "attach-build"): {"--app", "--version", "--build-number"},
    ("asset-library", "images", "upload"): {"--library-id", "--file", "--category", "--reference-name"},
    ("asset-library", "videos", "upload"): {"--library-id", "--file", "--category", "--reference-name"},
    ("asset-library", "videos", "set-poster-frame"): {"--id", "--time-code"},
    ("localizations", "placements", "create"): _PLACEMENT_CREATE,
    ("product-pages", "custom-pages", "localizations", "placements", "create"): _PLACEMENT_CREATE,
    ("localizations", "placements", "delete"): _PLACEMENT_DELETE,
    ("product-pages", "custom-pages", "localizations", "placements", "delete"): _PLACEMENT_DELETE,
    ("product-pages", "custom-pages", "localizations", "create"):
        {"--custom-page-version-id", "--locale", "--promotional-text"},
    ("product-pages", "custom-pages", "localizations", "update"): {"--localization-id", "--promotional-text"},
    ("product-pages", "custom-pages", "localizations", "search-keywords", "add"): {"--localization-id", "--keywords"},
    ("product-pages", "custom-pages", "localizations", "search-keywords", "delete"):
        {"--localization-id", "--keywords", "--confirm"},
}
# Nhóm "đúng một trong": lệnh phải có ĐÚNG MỘT cờ của mỗi nhóm (ngoài bộ cờ bắt buộc ở WRITE_FLAGS).
WRITE_ONE_OF = {
    ("localizations", "placements", "create"): [{"--image-id", "--video-id"}],
    ("product-pages", "custom-pages", "localizations", "placements", "create"): [{"--image-id", "--video-id"}],
}
# Cờ không có giá trị (boolean). `--confirm` vẫn nằm trong FORBIDDEN_FLAGS; chỉ được miễn ở lệnh nào
# liệt kê nó trong WRITE_FLAGS (xoá placements, xoá search-keywords) — cổng xác nhận do applier/plan gánh.
BARE_FLAGS = {"--confirm"}
# Giá trị bị ghim: version mới luôn MANUAL (Apple duyệt xong người tự bấm phát hành).
WRITE_FLAG_VALUES = {("versions", "create", "--release-type"): {"MANUAL"}}
# Cấm hẳn dù ở chế độ ghi: Claude không bao giờ phát hành/xoá/sửa version hay hết hạn build.
FORBIDDEN_COMMANDS = (
    ("versions", "release"),
    ("versions", "delete"),
    ("versions", "update"),
    ("builds", "expire"),
    # Không bao giờ xoá/lưu trữ/đổi tên asset, hoán đổi placement, xoá/sửa trang, nộp review, thử nghiệm.
    *[("asset-library", k, v) for k in ("images", "videos") for v in ("delete", "archive", "unarchive", "rename")],
    ("localizations", "placements", "swap"),
    ("product-pages", "custom-pages", "localizations", "placements", "swap"),
    # Sắp thứ tự placement: tool không còn sắp (API không cho đọc thứ tự hiển thị — list theo id giảm dần, đo
    # 2026-10-29) ⇒ không op nào cần (least privilege); sắp thứ tự làm tay trên web ASC.
    ("localizations", "placements", "reorder"),
    ("product-pages", "custom-pages", "localizations", "placements", "reorder"),
    ("product-pages", "custom-pages", "delete"),
    ("product-pages", "custom-pages", "update"),
    ("product-pages", "custom-pages", "localizations", "delete"),
    # Tạo CPP / version CPP: không op nào cần (least privilege) — user tạo tay trên ASC (Ruling 24).
    ("product-pages", "custom-pages", "create"),
    ("product-pages", "custom-pages", "versions", "create"),
    ("review",),
    ("product-pages", "experiments"),
)
FORBIDDEN_FLAGS = {"--allow-deletes", "--confirm", "--submit", "--force"}

API_HOST = "api.appstoreconnect.apple.com"
KEY_FILE = "asc-listing.json"
OLD_CPP = "tools/listing/asc_cpp.py"
ASO_TOOL = "tools/aso/aso.py"

# Tiền tố chạy lệnh khác (wrapper) — TRONG SUỐT với mọi luật: `_peel` bỏ chúng cùng tuỳ chọn/đối số riêng để tìm từ
# lệnh thật. Mỗi mục: (tuỳ chọn nhận giá trị ở token kế, số đối số vị trí đứng trước lệnh — vd thời hạn của timeout).
_SUDO_V = {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U", "--user", "--group", "--chdir", "--host",
           "--prompt", "--role", "--type", "--command-timeout", "--other-user", "--close-from"}
WRAPPER_SPEC = {
    "env": ({"-u", "--unset", "-C", "--chdir", "-P", "-S", "--split-string"}, 0),
    "command": (set(), 0), "builtin": (set(), 0), "exec": ({"-a"}, 0),
    "nohup": (set(), 0), "time": ({"-o"}, 0), "nice": ({"-n", "--adjustment"}, 0),
    "timeout": ({"-s", "--signal", "-k", "--kill-after"}, 1),
    "gtimeout": ({"-s", "--signal", "-k", "--kill-after"}, 1),
    "caffeinate": ({"-t", "-w"}, 0),
    "stdbuf": ({"-i", "-o", "-e", "--input", "--output", "--error"}, 0),
    "ionice": ({"-c", "-n", "-p", "--class", "--classdata", "--pid"}, 0),
    "sudo": (_SUDO_V, 0), "doas": ({"-u", "-C"}, 0),
    "arch": ({"-arch", "-e", "-d"}, 0),
    "xcrun": ({"--sdk", "--toolchain"}, 0),
    "xargs": ({"-I", "-n", "-P", "-L", "-s", "-E", "-d", "-J", "-R", "-S", "-a"}, 0),
    "taskpolicy": ({"-c", "-b", "-d", "-g", "-t", "-l", "-p"}, 0),
    "sandbox-exec": ({"-f", "-n", "-p", "-D"}, 0),
    "setsid": (set(), 0), "unbuffer": (set(), 0), "chronic": (set(), 0),
    "watch": ({"-n", "--interval", "-d"}, 0), "flock": ({"-w", "-E", "--timeout", "--conflict-exit-code"}, 1),
    "script": ({"-F", "-t", "-T"}, 1), "strace": ({"-o", "-e", "-p", "-s", "-u", "-E"}, 0),
    "ltrace": ({"-o", "-e", "-p", "-s", "-u"}, 0), "dtruss": ({"-p", "-n", "-t", "-W"}, 0),
    "valgrind": (set(), 0), "unshare": (set(), 0), "firejail": (set(), 0), "chrt": (set(), 1),
    "systemd-run": (set(), 0), "pkexec": ({"--user"}, 0), "runuser": ({"-u", "-g"}, 0),
}
WRAPPERS = set(WRAPPER_SPEC)
# Tuỳ chọn của `env` mà giá trị là một DÒNG LỆNH (env -S '…') ⇒ xét đệ quy như lệnh.
WRAPPER_CMD_OPT = {"-S", "--split-string"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish", "csh", "tcsh"}
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
BARE_ASC = re.compile(r"(^|[\s;&|(`!=])asc(\s|$)", re.I)


class PolicyError(Exception):
    pass


def check_asc_args(args, *, write):
    """`args` không gồm chữ `asc`. Khớp tiền tố với allowlist; cờ cấm ⇒ PolicyError."""
    args = list(args)
    for prefix in FORBIDDEN_COMMANDS:
        if tuple(args[:len(prefix)]) == prefix:
            raise PolicyError(f"lệnh bị cấm hoàn toàn (kể cả ghi): {' '.join(prefix)}")
    allowed = WRITE_COMMANDS if write else READ_COMMANDS
    matched = next((p for p in allowed if tuple(args[:len(p)]) == p), None)
    # --confirm chỉ được miễn ở lệnh ghi liệt kê nó trong bộ cờ chính xác.
    exempt = {"--confirm"} if (write and matched and "--confirm" in WRITE_FLAGS.get(matched, ())) else set()
    for a in args:
        flag = a.split("=", 1)[0]
        if flag in FORBIDDEN_FLAGS and flag not in exempt:
            raise PolicyError(f"cờ bị cấm: {a}")
    if matched:
        if write:
            _check_write_flags(matched, args[len(matched):])
        return
    kind = "ghi" if write else "đọc"
    raise PolicyError(f"lệnh asc không nằm trong allowlist {kind}: {' '.join(args) or '(rỗng)'}")


def _check_write_flags(prefix, rest):
    """Cờ của lệnh ghi phải đúng bằng WRITE_FLAGS[prefix] (+ đúng một cờ mỗi nhóm WRITE_ONE_OF):
    `--cờ giá-trị` hoặc `--cờ=giá-trị`; cờ trong BARE_FLAGS đứng không."""
    want = WRITE_FLAGS[prefix]
    groups = WRITE_ONE_OF.get(prefix, [])
    allowed = set(want).union(*groups) if groups else set(want)
    seen = {}
    i = 0
    while i < len(rest):
        tok = rest[i]
        if not tok.startswith("--"):
            raise PolicyError(f"đối số lạ cho {' '.join(prefix)}: {tok}")
        if tok in BARE_FLAGS:
            flag, value = tok, True
            i += 1
        elif "=" in tok:
            flag, value = tok.split("=", 1)
            i += 1
        else:
            if i + 1 >= len(rest) or rest[i + 1].startswith("--"):
                raise PolicyError(f"cờ {tok} thiếu giá trị")
            flag, value = tok, rest[i + 1]
            i += 2
        if flag not in allowed:
            raise PolicyError(f"cờ không được phép cho {' '.join(prefix)}: {flag}")
        if flag in BARE_FLAGS and value is not True:
            raise PolicyError(f"cờ {flag} không nhận giá trị")
        if flag in seen:
            raise PolicyError(f"cờ lặp: {flag}")
        if not value:
            raise PolicyError(f"cờ {flag} thiếu giá trị")
        pinned = WRITE_FLAG_VALUES.get((*prefix, flag))
        if pinned is not None and value not in pinned:
            raise PolicyError(f"{flag} chỉ nhận {', '.join(sorted(pinned))}, không nhận {value!r}")
        seen[flag] = value
    missing = set(want) - set(seen)
    if missing:
        raise PolicyError(f"{' '.join(prefix)} thiếu cờ: {', '.join(sorted(missing))}")
    for g in groups:
        n = len(g & set(seen))
        if n != 1:
            raise PolicyError(f"{' '.join(prefix)} cần đúng một trong: {', '.join(sorted(g))}")


# ---------- tách lệnh shell (nhận biết dấu nháy) ----------

def _split(cmd):
    """Trả (các đoạn lệnh đơn, các chuỗi con từ $(...)/backtick cần xét đệ quy)."""
    segs, subs = [], []
    cur = []
    i, n = 0, len(cmd)
    quote = None  # None | "'" | '"'

    def flush():
        s = "".join(cur).strip()
        if s:
            segs.append(s)
        cur.clear()

    while i < n:
        c = cmd[i]
        if quote == "'":
            cur.append(c)
            if c == "'":
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            cur.append(c + cmd[i + 1])
            i += 2
            continue
        if c == "$" and i + 1 < n and cmd[i + 1] == "(":
            depth, j = 1, i + 2
            while j < n and depth:
                depth += (cmd[j] == "(") - (cmd[j] == ")")
                j += 1
            subs.append(cmd[i + 2:j - 1 if depth == 0 else j])
            cur.append(cmd[i:j])
            i = j
            continue
        if c == "`":
            j = cmd.find("`", i + 1)
            j = n if j < 0 else j
            subs.append(cmd[i + 1:j])
            cur.append(cmd[i:j + 1])
            i = j + 1
            continue
        if quote == '"':
            cur.append(c)
            if c == '"':
                quote = None
            i += 1
            continue
        if c in "'\"":
            quote = c
            cur.append(c)
            i += 1
            continue
        if c in ";|&\n":
            flush()
            i += 1
            continue
        cur.append(c)
        i += 1
    flush()
    return segs, subs


def _rank(d):
    return {"allow": 0, "ask": 1, "block": 2}[d]


def _worst(a, b):
    return a if _rank(a[0]) >= _rank(b[0]) else b


APPLY_MSG = "chạy đúng dạng `python3 tools/aso/aso.py apply --plan … --expect …`"
APPLY_WORD = re.compile(r"\bapply\b")
MODULE_ASO = re.compile(r"-m\s+aso\b")
# Chữ `asc` đứng riêng — KHÔNG phân biệt hoa thường; luôn dò trên chữ đã gỡ nháy (`'a''sc'`, `"AS"C` ⇒ asc).
ASC_STANDALONE = re.compile(r"(?<![\w./-])asc(?![\w.-])", re.I)
SAFE_WORDS = {"git", "echo", "printf"}
ASC_WORD = ASC_STANDALONE
# Lý do chặn bắt đầu bằng tiền tố này = việc người dùng tự làm (đặt khoá/biến chạy lệnh) — hook KHÔNG gợi ý lệnh ASO.
HUMAN_ONLY = "việc của người dùng: "
# Giá trị trơ duy nhất mà agent được đặt cho khoá/biến chạy được lệnh (Ruling 8).
INERT_VALUES = {"true", ":", "cat", ""}


def needs_canon_hint(reason):
    """Hook có nối danh sách lệnh chuẩn vào lý do chặn không (không, khi đó là việc người dùng tự làm)."""
    return not reason.startswith(HUMAN_ONLY)


def _peel(toks):
    """Chỉ số từ lệnh thật trong `toks` (token shlex): bỏ gán biến và MỌI wrapper (WRAPPER_SPEC) cùng tuỳ chọn/đối số
    riêng của chúng, lồng nhau bao nhiêu lớp cũng được (`timeout 5 nice -n 5 env X=1 git …`). Trả (chỉ số, các dòng
    lệnh nằm trong giá trị tuỳ chọn wrapper — `env -S '…'`)."""
    i, inner = 0, []
    while i < len(toks):
        t = toks[i]
        if ASSIGN.match(t):
            i += 1
            continue
        w = os.path.basename(t)
        spec = WRAPPER_SPEC.get(w)
        if spec is None:
            break
        vopts, npos = spec
        i += 1
        while i < len(toks) and toks[i].startswith("-") and toks[i] != "-":
            o = toks[i]
            i += 1
            if o == "--":
                break
            name, eq, val = o.partition("=")
            if w == "env" and (name in WRAPPER_CMD_OPT or (name.startswith("-S") and not name.startswith("--"))):
                if name not in WRAPPER_CMD_OPT:     # dạng dính `-S'…'`
                    inner.append(o[2:])
                    continue
                if eq:
                    inner.append(val)
                elif i < len(toks):
                    inner.append(toks[i])
            if o in vopts and i < len(toks):
                i += 1
        while i < len(toks) and ASSIGN.match(toks[i]):
            i += 1
        i += npos
    return min(i, len(toks)), inner


# Tên "thường" — glob khớp được một tên trong số này là glob chung chung (`*`, `[a-z]*`), không phải nhắm asc.
_GLOB_PROBES = ("x", "zz", "zzzz", "x.py", "readme.md", "5.17.1")
_DEQUOTE_DEPTH = 8


def _variants(tok):
    """`tok` và mọi lần gỡ nháy tiếp theo: shlex tách CHỮ BÊN TRONG của token rồi lặp lại trên từng mảnh (nháy lồng
    `'sh -c "a""sc …"'`, thân alias `"fetch --upload-pack='a''sc …'"`), tới khi không đổi nữa (tối đa _DEQUOTE_DEPTH
    lớp). Mảnh không tách được (nháy lẻ) ⇒ bỏ hết nháy/escape (`_dequoted`) rồi xét tiếp."""
    seen, todo = set(), [(tok, 0)]
    while todo and len(seen) < 512:
        s, d = todo.pop()
        if s in seen:
            continue
        seen.add(s)
        if d >= _DEQUOTE_DEPTH:
            continue
        s2 = _shell_norm(s)
        try:
            nxt = shlex.split(s2)
        except ValueError:
            nxt = [_dequoted(s2)]
        # Mở ngoặc nhọn (`{a,}sc` ⇒ asc, sc) và giá trị mặc định của biến (`${X:-asc}`) — dạng viết chữ, không phải
        # tên ghép lúc chạy.
        nxt += [s2] + _brace_expand(s2) + [PARAM_OP.sub(" ", s2).replace("}", " ")]
        todo += [(n, d + 1) for n in nxt if n not in seen]
    return seen


ANSI_C = re.compile(r"\$'((?:[^'\\]|\\.)*)'", re.S)
BRACE = re.compile(r"\{([^{}]*,[^{}]*)\}")
PARAM_OP = re.compile(r"\$\{[#!]?[A-Za-z_0-9@*]*(:?[-=+?#%/^,]+)?")


def _ansi_c_sub(m):
    body = m.group(1)
    try:
        s = codecs.decode(body.encode("latin-1", "backslashreplace"), "unicode_escape")
    except Exception:
        s = _dequoted(body)
    return "'" + s.replace("'", "'\\''") + "'"


def _shell_norm(text):
    """Bỏ hai lớp viết chữ mà shell gỡ trước khi chạy, đúng ngữ cảnh nháy như bash: nối dòng `\\<xuống dòng>`
    (`a\\⏎sc` = asc; ngoài nháy đơn) và nháy ANSI-C `$'\\141sc'` (chỉ ngoài mọi nháy; giải mã thành nháy đơn thường)."""
    if "\\\n" not in text and "$'" not in text:
        return text
    out, i, n, quote = [], 0, len(text), None
    while i < n:
        c = text[i]
        if quote == "'":
            out.append(c)
            quote = None if c == "'" else quote
            i += 1
        elif c == "\\" and text[i + 1:i + 2] == "\n":
            i += 2
        elif c == "\\":
            out.append(text[i:i + 2])
            i += 2
        elif quote is None and text.startswith("$'", i) and (m := ANSI_C.match(text, i)):
            out.append(_ansi_c_sub(m))
            i = m.end()
        elif c == '"':
            quote = None if quote == '"' else '"'
            out.append(c)
            i += 1
        elif c == "'" and quote is None:
            quote = "'"
            out.append(c)
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _brace_expand(s, limit=64):
    """Mở ngoặc nhọn kiểu bash (`a{b,c}` ⇒ ab, ac; lồng nhau từ trong ra), tối đa `limit` kết quả."""
    if "{" not in s:
        return []
    out, todo = [], [s]
    while todo and len(out) + len(todo) < limit:
        x = todo.pop()
        m = BRACE.search(x)
        if not m:
            out.append(x)
            continue
        todo += [x[:m.start()] + alt + x[m.end():] for alt in m.group(1).split(",")]
    return out


def _comp_match(comp, name):
    """Thành phần đường dẫn `comp` là `name` (mọi kiểu hoa) hoặc glob khớp được `name`."""
    c = comp.lower()
    return c == name or (bool(GLOB.search(c)) and fnmatch.fnmatchcase(name, c))


def _generic_glob(comp):
    """`comp` là glob chung chung: khớp cả tên thường (`*`, `?*`, `[a-z]*`)."""
    c = comp.lower()
    return bool(GLOB.search(c)) and any(fnmatch.fnmatchcase(p, c) for p in _GLOB_PROBES)


def _asc_name(piece):
    """Mảnh chữ có basename là asc, hoặc là glob NHẮM asc (khớp asc, không chung chung: `a?c`, `[a]sc`, `A*`)."""
    b = os.path.basename(piece)
    return b.casefold() == "asc" or (_comp_match(b, "asc") and not _generic_glob(b))


@functools.lru_cache(maxsize=4096)
def _asc_token(tok):
    """Một token shlex (đã gỡ nháy) gọi/nhắc `asc` như một từ — xét trên MỌI lớp gỡ nháy (`_variants`): chữ asc đứng
    riêng (thân alias `!asc …`, `X=asc …`, `-Osh -c asc`), hoặc một mảnh (tách theo khoảng trắng, `=`, `:`) có basename
    là asc hay là glob nhắm asc (`~/x/a?c`, `--upload-pack=/p/[a]sc`)."""
    for v in _variants(tok):
        # Tuỳ chọn ngắn có giá trị dính (`-Oasc`, `-Oa?c` của git grep = chạy chương trình đó): xét cả phần giá trị.
        cands = [v, v[2:]] if re.match(r"-[A-Za-z]", v) and len(v) > 2 else [v]
        for s in cands:
            if ASC_STANDALONE.search(s):
                return True
            if any(_asc_name(p) for p in re.split(r"[\s=:;|&()<>`]+", s) if p):
                return True
    return False


def _touches_install_dir(text):
    """Chữ (đã gỡ nháy) chạm thư mục cài asc dùng chung `…/ios-app-factory/asc/<ver>/asc`: đường dẫn được chuẩn hoá
    (`./`, `//`, `..`) rồi so từng cặp thành phần, mỗi thành phần là tên thật hoặc glob khớp được tên đó:
    `ios-app-factory/asc` (vd `*/asc`, `ios-app-factory/*`, `i*/a?c`), hoặc chuỗi `asc/<x>/asc` (vd `a*/*/a?c`). Cặp
    hai glob chung chung (`*/*`) không tính — `ls build/*/*` không phải chạm thư mục cài."""
    plain = _dequoted(_shell_norm(text))
    bin_root = os.environ.get("IOS_APP_FACTORY_BIN", "").strip()
    pieces = [x for p in re.split(r"[\s=:;|&()<>`]+", plain) if p for x in [p, *_brace_expand(p)]]
    if bin_root:                             # thư mục cài đặt riêng (`$IOS_APP_FACTORY_BIN`): `<gốc>/asc…`
        root = posixpath.normpath(os.path.expanduser(bin_root))
        for piece in pieces:
            p = posixpath.normpath(os.path.expanduser(piece))
            if p.startswith(root.rstrip("/") + "/") and _comp_match(p[len(root.rstrip("/")) + 1:].split("/")[0], "asc"):
                return True
    for piece in pieces:
        comps = posixpath.normpath(piece).split("/")
        for k in range(len(comps) - 1):
            c, n = comps[k], comps[k + 1]
            if (_comp_match(c, "ios-app-factory") and _comp_match(n, "asc")
                    and not (_generic_glob(c) and _generic_glob(n))):
                return True
            if k + 2 < len(comps):
                z = comps[k + 2]
                if (_comp_match(c, "asc") and _comp_match(z, "asc")
                        and not _generic_glob(c) and not _generic_glob(z)):
                    return True
    return False


def _canonical_scripts():
    roots = {str(Path(__file__).resolve().parents[2])}
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        roots.add(os.environ["CLAUDE_PROJECT_DIR"].rstrip("/"))
    return {ASO_TOOL, "./" + ASO_TOOL} | {f"{r}/{ASO_TOOL}" for r in roots}


def _decide_segment(seg, plan_summary, depth):
    allow = ("allow", "")
    try:
        toks = shlex.split(seg)
    except ValueError:
        if BARE_ASC.search(_dequoted(seg)):
            return ("block", "không phân tích được lệnh chứa `asc` — gọi asc qua tools/aso/aso.py")
        return allow
    if not toks:
        return allow

    # apply: dò `aso.py` ... `apply` ở BẤT KỲ vị trí nào; chỉ dạng chuẩn mới được hỏi.
    for k, t in enumerate(toks):
        if os.path.basename(t) == "aso.py" and "apply" in toks[k + 1:]:
            if (k == 1 and toks[0] == "python3" and t in _canonical_scripts()
                    and toks[2:3] == ["apply"]):
                return _decide_apply(toks[3:], plan_summary)
            return ("block", APPLY_MSG)

    # Bỏ gán biến + MỌI wrapper (trong suốt) để tìm từ lệnh thật (cho git/echo/shell/version/glob).
    i, inner = _peel(toks)
    core = toks[i:]
    base = os.path.basename(core[0]) if core else ""
    if base == "asc" and core[1:] == ["version"] and i == 0:
        return allow
    # Dòng lệnh nằm trong giá trị tuỳ chọn wrapper (`env -S '…'`) ⇒ xét như một lệnh.
    result = allow
    if depth < 5:
        for c in inner:
            result = _worst(result, _decide(c, plan_summary, depth + 1))
    # Trong `sh -c '…'` (depth > 0) luật glob của lớp allowlist không với tới: từ lệnh là glob ⇒ chặn.
    if depth > 0 and base not in ("[", "[[") and core and GLOB.search(core[0]):
        return ("block", "từ lệnh là glob (shell tự khớp tên file rồi chạy) — " + GLOB_MSG)
    if base in ("echo", "printf"):
        # chữ; pipe sang shell do Backstop 2 bắt. Gán biến/wrapper đứng trước echo vẫn bị dò.
        if any(_asc_token(t) for t in toks[:i]):
            return ("block", "gọi asc qua tools/aso/aso.py (không chạy asc trực tiếp)")
        return result
    # Ruling 8: dò trên MỌI token (đã gỡ nháy) của đoạn — với git thì trừ giá trị message/mẫu tìm.
    scan = _git_strip_messages(toks) if base == "git" else toks
    # Đặt biến môi trường khiến git/editor chạy lệnh (GIT_PAGER, GIT_CONFIG_*, EDITOR, …) với giá trị không trơ ⇒ chặn.
    env = next((t for t in scan if _danger_env(t)), None)
    if env:
        return ("block", f"{HUMAN_ONLY}biến {env.split('=', 1)[0]} làm git/editor chạy lệnh — agent chỉ được đặt giá "
                         f"trị trơ (true, :, cat, rỗng); giá trị khác thì người dùng tự đặt trong terminal")
    if base == "git":
        kind, danger = _git_parse(core)
        if danger:
            return ("block", f"{HUMAN_ONLY}khoá cấu hình git {danger} chạy được lệnh — agent chỉ được đặt giá trị trơ "
                             f"(true, :, cat, rỗng); người dùng tự đặt khoá này trong terminal nếu cần")
        if any(_asc_token(t) for t in scan):
            return ("block", "git có thể chạy lệnh (alias, --upload-pack, -O, ext::…) — không đưa `asc` vào git; "
                             "gọi asc qua tools/aso/aso.py")
        if kind in ("text", "safe"):
            return result
    else:
        # git đứng sau một tiền tố không có trong WRAPPER_SPEC (`strace git -c core.pager=… log`): vẫn xét khoá chạy lệnh.
        for k in range(i + 1, len(toks)):
            if os.path.basename(toks[k]) == "git":
                danger = _git_parse(toks[k:])[1]
                if danger:
                    return ("block", f"{HUMAN_ONLY}khoá cấu hình git {danger} chạy được lệnh — agent chỉ được đặt giá "
                                     f"trị trơ (true, :, cat, rỗng); người dùng tự đặt khoá này trong terminal nếu cần")
    # `asc` là token (đã gỡ nháy, mọi kiểu hoa) ở bất kỳ vị trí nào (timeout/eval/find -exec/xargs/`X=asc …`) ⇒ chặn.
    if any(_asc_token(t) for t in scan):
        return ("block", "gọi asc qua tools/aso/aso.py (không chạy asc trực tiếp)")
    # Shell ở BẤT KỲ vị trí nào từ từ lệnh trở đi (cả sau tiền tố lạ): `sh -c '…'` ⇒ xét chuỗi lệnh như một lệnh.
    if depth < 5:
        for s in (k for k in range(i, len(toks)) if os.path.basename(toks[k]) in SHELLS):
            for k, a in enumerate(toks[s + 1:], start=s + 1):
                if a.startswith("-") and not a.startswith("--") and "c" in a and k + 1 < len(toks):
                    result = _worst(result, _decide(toks[k + 1], plan_summary, depth + 1))
                    break
        if base in SHELLS and ASC_WORD.search(_dequoted(seg)):
            return ("block", "shell đọc lệnh `asc` từ stdin/here-string — gọi asc qua tools/aso/aso.py")
    return result


def _decide_apply(rest, plan_summary):
    if any(("<" in t or ">" in t) for t in rest):
        return ("block", "apply không được có redirect. " + APPLY_MSG)
    vals = {"--plan": [], "--expect": []}
    k = 0
    while k < len(rest):
        t = rest[k]
        if t.startswith("-"):
            name, eq, v = t.partition("=")
            if name not in vals:
                return ("block", f"apply chỉ nhận đúng --plan và --expect (gặp {t}). " + APPLY_MSG)
            if eq:
                vals[name].append(v)
            elif k + 1 < len(rest):
                vals[name].append(rest[k + 1])
                k += 1
            else:
                vals[name].append("")
        k += 1
    if len(vals["--plan"]) != 1 or len(vals["--expect"]) != 1 or not all(
            vals["--plan"] + vals["--expect"]):
        return ("block", "apply cần đúng một --plan và một --expect. " + APPLY_MSG)
    plan, code = vals["--plan"][0], vals["--expect"][0]
    summary = plan_summary(plan, code)
    if summary is None:
        return ("block", f"không đọc được plan {plan}, hoặc mã plan tính lại từ nội dung khác --expect {code} "
                         "— truyền `--plan` đúng nguyên đường dẫn ở dòng `Plan:` và đúng mã đã duyệt")
    return ("ask", f"Push plan {code} lên App Store Connect: {summary}")


def _decide(cmd, plan_summary, depth=0):
    result = ("allow", "")
    segs, subs = _split(_shell_norm(cmd))
    for s in segs:
        result = _worst(result, _decide_segment(s, plan_summary, depth))
    if depth < 5:
        for s in subs:
            result = _worst(result, _decide(s, plan_summary, depth + 1))
    if result[0] == "ask" and (depth > 0 or len(segs) != 1 or subs):
        return ("block", "apply phải chạy một mình (không nối lệnh khác/$()) để hộp Allow "
                         "chỉ che đúng một hành động. " + APPLY_MSG)
    return result


EXEC_WORD = re.compile(r"^(python[\d.]*|ipython\d*|pytest|uv|uvx|pipx|eval|exec|sh|bash|zsh|dash"
                       r"|source|env|xargs|perl|ruby|node|osascript)$")
# Tham chiếu tới vùng tools/aso: đường dẫn (/ . \), tên script, cd/pushd vào tools, PYTHONPATH.
REF_AREA = re.compile(r"tools[./\\]aso|aso\.py|\b(cd|pushd)\s+(\S*/)?tools\b|pythonpath", re.I)
# `\Z` (không phải `$`): `$` khớp cả trước một `\n` cuối ⇒ lọt `…plan\n | tail`.
# Đối số lệnh không-apply: chữ an toàn, hoặc một cụm nháy đơn chữ an toàn + dấu cách (đường dẫn
# state dir "Application Support").
# Lệnh con không-apply của aso.py — MỘT nguồn cho allowlist và cho câu "dùng lệnh chuẩn nào" trong thông báo chặn
# (test gác: khớp đúng tập lệnh con của parser aso.py, trừ `apply`).
SUBCOMMANDS = ("pull", "import", "lint", "plan", "pull-version", "snapshot", "restore", "build", "release-plan")
CANONICAL = [re.compile(x) for x in (
    # Cờ ẩn `--offline-fixture DIR` (chỉ test/tự kiểm, đọc phản hồi asc ghi sẵn) được đứng TRƯỚC lệnh con chỉ-đọc;
    # với apply thì không bao giờ (dò apply ở `_decide_segment` đòi `apply` đứng ngay sau aso.py ⇒ chặn).
    r"^python3 tools/aso/aso\.py( --offline-fixture ([A-Za-z0-9_.:/=@+-]+|'[A-Za-z0-9_.:/=@+ -]+'))? ("
    + "|".join(re.escape(s) for s in SUBCOMMANDS) + r")"
    r"( ([A-Za-z0-9_.:/=@+-]*|'[A-Za-z0-9_.:/=@+ -]*'))*\Z",
    r"^python3 -m unittest( -v)?( (tools/aso/test_[a-z_]+\.py|discover|-s|tools/aso|-p|'test_\*\.py'|-v))*\Z",
    r"^python3 -m unittest( -v)? tools/aso/test_[a-z_]+\.py(\.[A-Za-z_]+)*( -v)?\Z",
    r"^python3 -m unittest( -v)? tools\.aso\.test_[a-z_]+(\.[A-Za-z_]+)*( -v)?\Z",
    r"^bash (-n )?tools/aso/install_asc\.sh\Z",
    r"^python3 -m py_compile( tools/aso/[a-z_]+\.py)+\Z",
)]
# Lệnh chỉ-đọc: đoạn lệnh bắt đầu bằng các từ này (và KHÔNG chứa từ chạy code) được miễn luật import.
READ_ONLY = {"git", "grep", "rg", "cat", "head", "tail", "sed", "less", "wc", "ls", "diff"}
# assets_apply = tên dành sẵn cho lối ghi asset/CPP (chưa có ở template): khi có, chỉ được gọi qua `aso.py apply` —
# chặn import thẳng ngay từ bây giờ.
MODS = r"(aso|asc_cli|applier|assets_apply|remote|snapshot|planner|store|policy|confirm|lint)"
IMPORT_RE = re.compile(
    rf"\b(import|from)\s+{MODS}\b|\b(aso|asc_cli|applier|assets_apply|remote|snapshot)\s*\.\s*"
    r"(main|run|apply|apply_assets|take|pull_remote)\b|\b(import|from)\s+tools\s*\.\s*aso\b|\btools\.aso\.\w+"
    r"|runpy|__import__|importlib")
PY_C_DANGER = re.compile(r"subprocess|os\.system|os\.exec|os\.popen|os\.spawn\w*|commands\.|\bpty\b")
GLOB = re.compile(r"[*?\[]")
# Các dạng chuẩn (chạy từ gốc repo) — hook nối câu này vào mọi thông báo chặn để nói lệnh thay thế.
CANON_FORMS = ("`python3 tools/aso/aso.py <" + "|".join(SUBCOMMANDS) + "> …`, "
               "`python3 tools/aso/aso.py apply --plan … --expect …` (hỏi xác nhận), "
               "`python3 -m unittest discover -s tools/aso -p 'test_*.py'`, "
               "`bash [-n] tools/aso/install_asc.sh`, `python3 -m py_compile tools/aso/….py`")
CANON_MSG = "lệnh chạy code trong tools/aso phải đúng một trong các dạng chuẩn: " + CANON_FORMS
CWD_MSG = ("đang đứng trong thư mục tools/ — chạy từ thư mục gốc repo (`cd` về gốc trước), "
           "dạng chuẩn tính theo gốc repo. " + CANON_MSG)


def _all_segments(cmd, depth=0):
    """Mọi đoạn lệnh đơn, kể cả bên trong $(...)/backtick (đệ quy)."""
    segs, subs = _split(cmd)
    out = list(segs)
    if depth < 5:
        for s in subs:
            out += _all_segments(s, depth + 1)
    return out


def _unquoted(seg):
    """Bỏ phần trong nháy, ký tự escape và biến đặc biệt ($? $* $@ $#) — còn lại là chỗ shell glob."""
    s = re.sub(r"\\.", " ", seg)
    s = re.sub(r"'[^']*'|\"[^\"]*\"", " ", s)
    return re.sub(r"\$[?*@#]", " ", s)


# git "text": đọc / stage / commit — chỉ truyền chữ (message, pathspec, mẫu tìm).
GIT_TEXT = {"commit", "log", "show", "diff", "status", "add", "rm", "mv", "rev-parse", "ls-files", "blame",
            "merge-base"}
# git "safe": việc git thường ngày — không phải "text" nhưng không chạy code ad-hoc ngoài hook/cấu hình đã có của repo;
# đường dẫn/message của chúng không bị xét vùng/cwd/import; chỉ còn luật khoá cấu hình chạy lệnh + chữ asc.
GIT_SAFE_SUB = {"checkout", "restore", "switch", "branch", "fetch", "pull", "push", "stash", "tag", "worktree",
                "remote", "grep", "reset", "clean", "cherry-pick", "merge", "config"}
# Tuỳ chọn toàn cục không đổi cấu hình, không trỏ tới chương trình khác. `-C`/`--git-dir`/`--work-tree`/`--namespace`
# (đổi repo) không đổi loại — cấu hình đã có của repo kia nằm ngoài phạm vi (docstring).
GIT_SAFE_GLOBAL = {"--no-optional-locks", "--no-pager", "-P", "--literal-pathspecs", "--no-replace-objects",
                   "--bare", "--no-advice"}
GIT_REPO_OPT = ("-C", "--git-dir", "--work-tree", "--namespace")
# Tuỳ chọn của lệnh con text/safe mà chạy chương trình ngoài ⇒ "exec".
GIT_EXEC_OPT = re.compile(r"^(--ext-diff|--textconv|--upload-pack|--receive-pack|--exec|-O|--open-files-in-pager"
                          r"|--extcmd|--tool)(=|$)")
# Khoá cấu hình git chạy được lệnh (Ruling 8): ĐẶT chúng (git config, -c, --config-env) chỉ qua với giá trị trơ
# INERT_VALUES; --config-env (giá trị không thấy) ⇒ chặn. `alias.*`: thân `!…` (shell) chỉ trơ mới qua; thân git
# được xét như một dòng lệnh git (`_git_parse`), cộng luật chữ asc trên mọi token.
PROTOCOL_ALLOW_KEY = re.compile(r"^protocol\.(.+\.)?allow$", re.I)
GIT_EXEC_KEY = re.compile(
    r"^(core\.(fsmonitor|hookspath|pager|sshcommand|editor|askpass|gitproxy|alternaterefscommand)"
    r"|.+\.textconv|diff\.external|diff\..+\.command|merge\..+\.driver|gpg(\..+)?\.program|include\.path"
    r"|includeif\..+|filter\..+|sequence\.editor|pager\..+|credential(\..+)?\.helper|(diff|merge)tool\..+\.(cmd|path)"
    r"|uploadpack\.packobjectshook|remote\..+\.(uploadpack|receivepack|vcs)|ssh\.variant|interactive\.difffilter"
    r"|sendemail\..*(cmd|validate)|.+\.(command|cmd))$", re.I)
# Biến môi trường khiến git (hoặc pager/editor của git) chạy lệnh: đặt ở bất kỳ đâu với giá trị không trơ ⇒ chặn.
GIT_ENV_DANGER = re.compile(r"^(GIT_CONFIG\w*|GIT_PAGER|GIT_EXTERNAL_DIFF|GIT_SSH_COMMAND|GIT_SSH|GIT_EDITOR"
                            r"|GIT_SEQUENCE_EDITOR|GIT_ASKPASS|GIT_EXEC_PATH|GIT_PROXY_COMMAND|GIT_TEMPLATE_DIR"
                            r"|GIT_ALLOW_PROTOCOL|EDITOR|VISUAL)=")
# Đối số message/mẫu tìm của git (chữ, không bao giờ được chạy) — giá trị của chúng không bị dò chữ asc/import.
# THEO LỆNH CON: cùng một chữ cái là tuỳ chọn khác ở lệnh khác (`grep -F` = chuỗi cố định, `fetch -m` = --multiple).
_GIT_MSG_COMMIT = frozenset({"-m", "--message", "-F", "--file"})
_GIT_MSG_LOG = frozenset({"--grep", "--author", "--committer", "-S", "-G"})
GIT_MSG_BY_SUB = {**{s: _GIT_MSG_COMMIT for s in ("commit", "tag", "merge", "stash", "notes", "revert", "cherry-pick")},
                  **{s: _GIT_MSG_LOG for s in ("log", "show", "shortlog")}}


def _danger_env(tok):
    """Token `TÊN=giá-trị` đặt biến làm git/editor chạy lệnh, giá trị không trơ."""
    return bool(GIT_ENV_DANGER.match(tok)) and tok.split("=", 1)[1].strip() not in INERT_VALUES
# `git config`: tuỳ chọn có giá trị, và các dạng chỉ đọc/xoá.
GIT_CONFIG_VALUE_OPT = {"--file", "-f", "--blob", "--type", "--default", "--comment", "--value"}
GIT_CONFIG_READ = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "-l", "--list", "--unset", "--unset-all",
                   "--remove-section", "--get-color", "--get-colorbool", "get", "list", "unset", "remove-section"}


def _exec_key(key, value):
    """Khoá cấu hình `key` với giá trị `value` (None = không biết) làm git chạy lệnh ⇒ tên khoá (lý do); không ⇒ None.
    Giá trị trơ (INERT_VALUES) luôn qua."""
    k = key.strip()
    inert = value is not None and value.strip() in INERT_VALUES
    if k.lower().startswith("alias."):
        if value is None:
            return k
        body = value.strip()
        if body.startswith("!"):
            return None if body[1:].strip() in INERT_VALUES else k
        try:
            sub = shlex.split(body)
        except ValueError:
            return k
        return _git_parse(["git", *sub])[1]   # thân alias git = một dòng lệnh git
    if GIT_EXEC_KEY.match(k) or PROTOCOL_ALLOW_KEY.match(k):
        return None if inert else k
    return None


def _git_config_danger(rest):
    """`git config …` ĐẶT một khoá chạy được lệnh ⇒ tên khoá; đọc/xoá/khoá vô hại ⇒ None."""
    pos, i = [], 0
    while i < len(rest):
        t = rest[i]
        if t in GIT_CONFIG_READ:
            return None
        if t in GIT_CONFIG_VALUE_OPT:
            i += 2
            continue
        if not t.startswith("-"):
            pos.append(t)
        i += 1
    if pos[:1] == ["set"]:
        pos = pos[1:]
    if len(pos) < 2:
        return None                          # `git config KEY` = đọc
    return _exec_key(pos[0], pos[1])


def _git_parse(toks):
    """`toks` bắt đầu bằng `git` (đã gỡ nháy). Trả (loại, lý do-đặt-khoá-chạy-lệnh | None); loại ∈ "text" | "safe" |
    "exec". Không mở đường dẫn thật nào."""
    i = 1
    while i < len(toks) and toks[i].startswith("-"):
        t = toks[i]
        if t in GIT_SAFE_GLOBAL or t.startswith(tuple(o + "=" for o in GIT_REPO_OPT[1:])):
            i += 1
        elif t in GIT_REPO_OPT and i + 1 < len(toks):
            i += 2
        elif t == "-c" and i + 1 < len(toks) or (t.startswith("-c") and len(t) > 2 and not t.startswith("--")):
            kv = toks[i + 1] if t == "-c" else t[2:]
            i += 2 if t == "-c" else 1
            key, eq, val = kv.partition("=")
            danger = _exec_key(key, val if eq else "")
            if danger:
                return "exec", danger
        elif t == "--config-env" and i + 1 < len(toks) or t.startswith("--config-env="):
            spec = toks[i + 1] if t == "--config-env" else t.split("=", 1)[1]
            i += 2 if t == "--config-env" else 1
            danger = _exec_key(spec.rsplit("=", 1)[0], None)
            if danger:
                return "exec", danger
        else:
            return "exec", None              # --exec-path, --list-cmds, tuỳ chọn lạ
    if i >= len(toks):
        return "text", None                  # `git` trần
    sub, rest = toks[i], toks[i + 1:]
    if any(GIT_EXEC_OPT.match(t) for t in rest):
        return "exec", None
    if sub == "config":
        return "safe", _git_config_danger(rest)
    if sub in GIT_TEXT:
        return "text", None
    if sub in GIT_SAFE_SUB:
        return "safe", None
    return "exec", None                      # alias, bisect, rebase, submodule, difftool, lệnh con lạ


def _git_sub_index(toks, g):
    """`toks[g]` là `git`: chỉ số lệnh con (bỏ tuỳ chọn toàn cục, cả `-C x`, `-c k=v`, `--config-env x`). Gặp tuỳ chọn
    toàn cục không biết ⇒ len(toks) (không xác định được lệnh con ⇒ không bỏ message nào: an toàn khi git hiểu khác)."""
    j = g + 1
    while j < len(toks) and toks[j].startswith("-"):
        t = toks[j]
        if t in (*GIT_REPO_OPT, "-c", "--config-env"):
            j += 2
        elif t in GIT_SAFE_GLOBAL or t.startswith(tuple(o + "=" for o in (*GIT_REPO_OPT[1:], "--config-env"))) or (
                t.startswith("-c") and len(t) > 2 and not t.startswith("--")):
            j += 1
        else:
            return len(toks)
    return j


def _git_strip_messages(toks):
    """Bỏ GIÁ TRỊ message/mẫu tìm — chữ, không bao giờ được chạy — CHỈ ở lệnh con mà tuỳ chọn đó là message
    (GIT_MSG_BY_SUB: `commit -m X`, `tag -F f`, `log --grep X`…; `grep -F`/`fetch -m` không có giá trị ⇒ không bỏ gì).
    Không bao giờ bỏ một token bắt đầu bằng `-` làm giá trị (`-m -O'…'` ⇒ `-O…` vẫn bị dò)."""
    g, _ = _peel(toks)
    if g >= len(toks) or os.path.basename(toks[g]) != "git":
        return toks
    j = _git_sub_index(toks, g)
    opts = GIT_MSG_BY_SUB.get(toks[j]) if j < len(toks) else None
    if not opts:
        return toks
    short = tuple(o for o in opts if len(o) == 2)
    out, i = toks[:j + 1], j + 1
    while i < len(toks):
        t = toks[i]
        if t in opts:
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            i += 2 if (nxt is not None and not nxt.startswith("-")) else 1
            continue
        if (t.startswith("--") and "=" in t and t.split("=", 1)[0] in opts) or (
                t[:2] in short and len(t) > 2 and not t.startswith("--")):
            i += 1                               # `--message=X`, dạng dính `-mX`
            continue
        out.append(t)
        i += 1
    return out


def _git_kind(seg):
    """Loại đoạn lệnh git: None (không phải git) | "text" | "safe" | "exec" (xem `_git_parse`). Gán biến môi trường
    nguy hiểm trước git hoặc process substitution ⇒ "exec"."""
    try:
        toks = shlex.split(seg)
    except ValueError:
        return None
    i, _ = _peel(toks)
    if i >= len(toks) or os.path.basename(toks[i]) != "git":
        return None
    if any(_danger_env(t) for t in toks[:i]) or re.search(r"[<>]\(", seg):
        return "exec"
    return _git_parse(toks[i:])[0]


def _backstop_asc(seg, *, piped):
    """Đoạn `seg` có chữ asc (đã gỡ nháy, mọi kiểu hoa) ở token có thể bị chạy."""
    try:
        toks = shlex.split(seg)
    except ValueError:
        return bool(ASC_STANDALONE.search(_dequoted(seg)))
    k, _ = _peel(toks)
    base = os.path.basename(toks[k]) if k < len(toks) else ""
    if base in ("echo", "printf") and not piped:
        toks = toks[:k]                      # gán biến/wrapper trước echo vẫn bị dò
    elif base == "git":
        toks = _git_strip_messages(toks)
    return any(_asc_token(t) for t in toks)


def _without_git_messages(seg):
    """Đoạn git ⇒ văn bản không còn đối số message/mẫu tìm (không bao giờ quét import trong message); khác ⇒ nguyên."""
    if _git_kind(seg) is None:
        return seg
    try:
        return " ".join(_git_strip_messages(shlex.split(seg)))
    except ValueError:
        return seg


def _is_exec_segment(seg):
    """Đoạn lệnh có thể chạy code: có từ chạy code ở bất kỳ đâu, `. file`, hoặc từ lệnh là
    đường dẫn/glob (chạy thẳng script qua shebang). git "text"/"safe" ⇒ không; git "exec" ⇒ có."""
    git = _git_kind(seg)
    if git is not None:
        return git == "exec"
    toks = [os.path.basename(t) for t in re.split(r"[\s;|&()<>\"'`$]+", seg) if t]
    if any(EXEC_WORD.match(t) for t in toks) or re.match(r"\s*\.\s", seg):
        return True
    words = [w for w in seg.split() if not ASSIGN.match(w)]
    heads = [words[0]] if words else []
    try:
        toks = shlex.split(seg)
        k, _ = _peel(toks)
        if k < len(toks):
            heads.append(toks[k])            # từ lệnh sau wrapper (`timeout 5 ~/x/a?c`, `nice -n 5 ./x.sh`)
    except ValueError:
        pass
    return any(h not in ("[", "[[") and ("/" in h or bool(GLOB.search(h))) for h in heads)


def _has_glob(seg):
    return any(w not in ("[", "[[", "]", "]]") and GLOB.search(w) for w in _unquoted(seg).split())


def _is_read_only(seg):
    words = seg.split()
    return bool(words) and os.path.basename(words[0]) in READ_ONLY and not _is_exec_segment(seg)


def _cwd_in_tools(cwd):
    """cwd nằm trong `<repo>/tools` (của repo này hay bất kỳ checkout nào có tools/aso)."""
    if not cwd:
        return False
    try:
        p = Path(cwd).resolve()
    except (OSError, ValueError):
        return False
    roots = {Path(__file__).resolve().parents[2]}
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        roots.add(Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve())
    for r in roots:
        if p == r / "tools" or (r / "tools") in p.parents:
            return True
    return any(a.name == "tools" and (a / "aso" / "policy.py").exists() for a in [p, *p.parents])


# Đuôi cho phép sau dạng chuẩn KHÔNG phải apply: `2>&1` và/hoặc một pipe vào sink chỉ-đọc.
SINK_SUFFIX = re.compile(
    r"( 2>&1)?( \| (tail|head)( -n \d+| -\d+)?| \| grep( -[A-Za-z]+)* ([A-Za-z0-9_.:=-]+|'[^'\n]*'))?\Z")
GLOB_MSG = ("glob chưa quote trong lệnh chạy code — hãy quote đối số glob hoặc liệt kê file cụ thể")
FEEDER = re.compile(r"\bxargs\b|\s-exec(dir)?\b")
# Tên/đường dẫn thật của vùng — pattern -name/-path của find khớp được chúng ⇒ nhắm vào tools/aso.
AREA_NAMES = ("aso.py", "aso", "asc_cli.py", "applier.py", "tools/aso/aso.py", "./tools/aso/aso.py",
              "tools/aso", "./tools/aso")
FIND_NAME_ARG = re.compile(r"^-(i?name|i?path|i?wholename|regex)$")


def _is_canonical(raw, plan_summary):
    """Toàn bộ lệnh là đúng MỘT dạng chuẩn (tính theo thư mục gốc repo). Dạng không-apply được
    thêm đuôi sink chỉ-đọc; apply phải đứng một mình tuyệt đối (không pipe, không redirect)."""
    m = SINK_SUFFIX.search(raw)
    core = raw[:m.start()] if m else raw
    if any(c.match(core) for c in CANONICAL):
        return True
    return _decide(raw, plan_summary)[0] == "ask" and not re.search(r"[;|&\n`$<>]", raw)


def _dequoted(text):
    """Bỏ `"`, `'` và `\\` — gần đúng chữ mà shell thực sự truyền đi sau khi gỡ nháy/escape."""
    return re.sub(r"[\"'\\]", "", text)


def _strip_quotes(tok):
    return tok.replace("'", "").replace('"', "")


def _glob_area_ref(raw):
    """Glob nhắm vào vùng tools (kể cả trong nháy — find/xargs tự khớp): token bắt đầu `tools/`
    có `*?[`, hoặc đối số -name/-path của find có glob + chữ a…s…o, hay chứa `aso`."""
    toks = [_strip_quotes(t) for t in raw.split()]
    for k, t in enumerate(toks):
        if t.startswith(("tools/", "./tools/")) and GLOB.search(t):
            return True
        if k > 0 and FIND_NAME_ARG.match(toks[k - 1]) and (
                "aso" in t.lower() or any(fnmatch.fnmatch(n, t.lower()) for n in AREA_NAMES)
                or (GLOB.search(t) and re.search(r"a.*s.*o", t, re.I))):
            return True
    return False


HEREDOC = re.compile(r"<<(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
SHELL_CONSUMER = re.compile(r"(^|[\s/;|&(])(sh|bash|zsh|dash|ksh|source|eval|exec|xargs|\.)(\s|$)")


def _strip_inert_heredocs(raw):
    """Bỏ THÂN heredoc mà shell không glob và không chạy như lệnh shell: shell không bao giờ khớp
    tên file trong thân heredoc, nên `*`/`?`/`[` trong code python đưa qua `python3 - <<'EOF'` không
    phải glob. Giữ nguyên khi người nhận là shell (`bash <<EOF` — thân là lệnh), khi thân có chữ
    `apply` (lối vòng tới aso.py apply) hoặc heredoc không đóng. Chỉ dùng cho luật glob; luật
    import/vùng vẫn xét văn bản thô."""
    lines = raw.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = HEREDOC.search(line)
        i += 1
        if not m:
            continue
        dash, delim = m.group(1), m.group(3)
        j = i
        while j < len(lines) and (lines[j].lstrip("\t") if dash else lines[j]) != delim:
            j += 1
        body = "\n".join(lines[i:j])
        # Cả dòng mở (không chỉ phần trước `<<`): `cat <<EOF | bash` cũng đưa thân cho shell chạy.
        opener = line[:m.start()] + " " + line[m.end():]
        if j >= len(lines) or SHELL_CONSUMER.search(opener) or APPLY_WORD.search(_dequoted(body)):
            continue  # giữ thân: vòng lặp xét tiếp từng dòng như lệnh
        out.append(lines[j])
        i = j + 1
    return "\n".join(out)


def _allowlist_layer(raw, plan_summary, cwd):
    """Lớp fail-closed. Một luật: lệnh có đoạn chạy code mà đụng vùng tools/aso (đường dẫn/chấm,
    tên module, glob, hay cwd nằm trong tools/) chỉ được qua nếu TOÀN BỘ lệnh là một dạng chuẩn.
    Mỗi đoạn (tách theo ; && || | & xuống dòng, cả trong $()/backtick) xét riêng, kết quả chặt nhất thắng."""
    segs = _all_segments(raw)
    # Thân heredoc trơ (người nhận không phải shell) không phải lệnh: `git commit -F - <<EOF` có chữ
    # "python" trong message không phải đoạn chạy code. Luật import (dưới) vẫn xét `segs` thô.
    inert = _strip_inert_heredocs(raw)
    exec_segs = [s for s in _all_segments(inert) if _is_exec_segment(s)]
    feeder = bool(FEEDER.search(inert))
    if exec_segs and _cwd_in_tools(cwd):
        return ("block", CWD_MSG)
    if _is_canonical(raw, plan_summary):
        return None
    if exec_segs or feeder:
        if REF_AREA.search(raw) or _glob_area_ref(raw):
            return ("block", CANON_MSG)
        # xargs / find -exec đưa tên file đi chạy (python/sh hay thẳng qua shebang) kèm chữ `apply` ⇒ chặn.
        # Xét sau khi bỏ nháy/backslash: `ap""ply`, `ap\ply`, `'ap'ply` đều thành apply khi shell chạy.
        if feeder and APPLY_WORD.search(_dequoted(raw)):
            return ("block", "không đưa file đi chạy qua xargs/find -exec cùng `apply`. " + APPLY_MSG)
        # Có feeder ⇒ glob ở BẤT KỲ đoạn nào (vd `ls t?ols/a?o/a?o.py | xargs …`) có thể sinh tên file
        # đem đi chạy; không feeder ⇒ chỉ đoạn chạy code.
        gsegs = _all_segments(inert)
        if not feeder:
            gsegs = [x for x in gsegs if _is_exec_segment(x)]
        if any(_has_glob(x) for x in gsegs):
            return ("block", GLOB_MSG)
    for s in segs:
        if not _is_read_only(s) and IMPORT_RE.search(_without_git_messages(s)):
            return ("block", "không import/gọi module của tools/aso trong code ad-hoc — dùng tools/aso/aso.py")
    return None


def hook_decision(command, plan_summary: Callable[[str, str], Optional[str]], cwd=None):
    """Trả ("allow"|"ask"|"block", lý do). `cwd` = thư mục làm việc của lệnh (trường `cwd` của hook).

    `plan_summary(plan_path, expect)` ⇒ tóm tắt plan, hoặc None (⇒ chặn) nếu không đọc được plan hay
    mã tính lại từ nội dung khác `expect`.
    """
    raw = command.strip()
    words = raw.split()
    first = os.path.basename(words[0]) if words else ""
    execw = any(_is_exec_segment(x) for x in _all_segments(raw))
    layer = _allowlist_layer(raw, plan_summary, cwd)
    if layer:
        return layer
    if (re.search(r"\bpython[\d.]*\b", raw) and re.search(r"\s-[a-zA-Z]*c\b", raw)
            and PY_C_DANGER.search(raw)):
        return ("block", "không chạy subprocess/os.system qua python -c")
    if re.search(r"\bgit\s+(-\S+\s+)*-c\s+alias\.", raw) and "!" in raw:
        return ("block", "không dùng git alias shell (`!`)")
    result = _decide(command, plan_summary)
    if result[0] == "block":
        return result
    # Backstop 1 (văn bản thô): nhắc tới aso.py/-m aso/runpy cùng từ `apply` ở bất kỳ đâu
    # (kể cả trong chuỗi nháy, eval, bash -c, pipe vào sh) ⇒ chỉ `ask` nếu TOÀN BỘ lệnh là đúng
    # một lệnh apply chuẩn, không toán tử/redirect/nền. Hệ quả chấp nhận: lệnh khác có cả
    # `aso.py` lẫn chữ `apply` (vd `... plan && echo apply`) cũng bị chặn — hãy viết lại.
    if (APPLY_WORD.search(_dequoted(raw)) and not (first in READ_ONLY and not execw)
            and ("aso.py" in raw or MODULE_ASO.search(raw) or "runpy" in raw)):
        if result[0] == "ask" and not re.search(r"[;|&\n`$<>]", raw):
            return result
        return ("block", APPLY_MSG)
    # Thư mục cài asc dùng chung (ngoài PATH) — chạm tới bằng bất kỳ lệnh nào ⇒ chặn.
    if _touches_install_dir(raw):
        return ("block", "không chạm thư mục cài asc — gọi asc qua tools/aso/aso.py")
    # Backstop 2 (Ruling 8): chữ `asc` (mọi kiểu hoa) trên MỌI token đã gỡ nháy của MỌI đoạn (cả trong $()/backtick,
    # cả git "text"/"safe") — trừ giá trị message/mẫu tìm của git và echo/printf không pipe.
    if raw != "asc version":
        for s in _all_segments(_shell_norm(raw)):
            if _backstop_asc(s, piped="|" in raw):
                return ("block", "gọi asc qua tools/aso/aso.py (không chạy asc trực tiếp)")
    # Luật 3/4: chuỗi nhạy cảm — trừ khi chính là công cụ của mình.
    # "Công cụ của mình" = đúng một lệnh đơn, không nối thêm lệnh khác (tránh đi tắt bằng `; curl ...`).
    head = command.split(None, 2)
    own = (len(head) >= 2 and head[0].startswith("python") and head[1] == ASO_TOOL
           and not re.search(r"[;|&\n`$]", command))
    if not own:
        low = command.casefold()
        if API_HOST in low or KEY_FILE in low:
            return ("block", "không truy cập API App Store Connect/khoá trực tiếp — dùng tools/aso/aso.py")
        if OLD_CPP in low:
            return ("block", "tools/listing/asc_cpp.py đã gỡ — dùng tools/aso/aso.py")
    return result
