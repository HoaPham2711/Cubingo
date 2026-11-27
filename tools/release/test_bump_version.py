"""Test tích hợp bump_version.sh trong repo git TẠM (script tạo tag thật — không bao giờ chạy trên repo thật).

Chạy: python3 -m unittest discover -s tools/release -p 'test_*.py'

Repo giả lập dựng `app.config.toml` + `AppHost/Config/Identity.xcconfig` + `tools/common/appconfig.py` (bản thật,
chép từ repo này) — script bump đọc/ghi version qua chúng.

Bất biến chính (FuzzRollbackTests): sau MỌI lần thoát lỗi, hoặc script in "KHÔNG hoàn tác được", hoặc trạng thái
repo y nguyên (5 file y byte, HEAD cũ, index == HEAD, không có tag mới) — không bao giờ "đã hoàn tác" mà lệch.
"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.path.join(HERE, "..", "common")
sys.path.insert(0, COMMON)
import appconfig  # noqa: E402

REAL_GIT = shutil.which("git")
CAT_REL = appconfig.WHATS_NEW_CATALOG
CFG_REL = appconfig.CONFIG_FILE
XCC_REL = appconfig.XCCONFIG
CATALOG = 'WhatsNewCard(id: "b", version: .unreleased)\nWhatsNewCard(\n id: "c", version : CardVersion.unreleased)\n'
CONFIG = """[app]
slug = "demo"
display_name = "Demo"
display_name_internal = "Demo Dev"

[bundle]
store = "com.example.demo"
internal = "com.example.demo.internal"

[apple]
team_id = "0000000000"

[version]
marketing = "0.1.0"
build = "1"

[web]
host_prod = ""
host_dev = ""
"""
FEAT_REL = appconfig.FEATURES_YML
FILES = (CAT_REL, CFG_REL, XCC_REL, FEAT_REL, "CHANGELOG.md")

# git giả: đếm MỌI lần gọi vào $FAKE_COUNT; lần thứ $FAULT_K thì gây lỗi theo $FAULT_MODE; lần thứ $FAULT_SIG_K gửi
# tín hiệu $FAULT_SIG cho CẢ nhóm tiến trình (như Ctrl-C / đóng terminal) rồi chạy git thật; `extra` = sh chạy trước.
FAKE_GIT = r"""#!/bin/sh
{extra}
n=$(( $(cat "$FAKE_COUNT" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$FAKE_COUNT"
if [ "$n" = "${{FAULT_SIG_K:-0}}" ]; then trap '' "$FAULT_SIG"; kill -"$FAULT_SIG" 0; fi
if [ "$n" = "${{FAULT_K:-0}}" ]; then
  case "$FAULT_MODE" in
    exit1) exit 1 ;;
    lock_exit1) : > "$FAKE_LOCK"; exit 1 ;;
    lock_real) : > "$FAKE_LOCK" ;;
    real_exit1) "{real}" "$@"; exit 1 ;;
    real_lock_exit1) "{real}" "$@"; : > "$FAKE_LOCK"; exit 1 ;;
  esac
fi
exec "{real}" "$@"
"""
# (chế độ lỗi tại lần k, tín hiệu, độ lệch so với k của lần gửi tín hiệu). Tín hiệu SAU lỗi rơi vào lúc rollback
# đang chạy ⇒ kiểm `trap '' INT TERM HUP` trong rollback.
FAULT_MODES = (
    ("exit1", None, 0), ("lock_exit1", None, 0), ("lock_real", None, 0), ("real_exit1", None, 0),
    ("real_lock_exit1", None, 0), ("none", "TERM", 0), ("none", "INT", 0), ("none", "HUP", 0),
    ("exit1", "INT", 1), ("exit1", "TERM", 2), ("real_exit1", "HUP", 1), ("real_exit1", "INT", 3),
)
SIG_RC = {"INT": 130, "TERM": 143, "HUP": 129}


def make_repo(root, catalog=CATALOG, changelog=None, config=CONFIG):
    os.makedirs(os.path.join(root, "tools/release"))
    os.makedirs(os.path.join(root, "tools/common"))
    for f in ("bump_version.sh", "stamp_whats_new.py"):
        shutil.copy(os.path.join(HERE, f), os.path.join(root, "tools/release", f))
    shutil.copy(os.path.join(COMMON, "appconfig.py"), os.path.join(root, "tools/common/appconfig.py"))
    files = [(CFG_REL, config), (XCC_REL, appconfig.render_xcconfig(tomllib.loads(config))),
             (appconfig.FEATURES_YML, appconfig.render_features_yml(tomllib.loads(config)))]
    if catalog is not None:
        files.append((CAT_REL, catalog))
    if changelog is not None:
        files.append(("CHANGELOG.md", changelog))
    for rel, text in files:
        os.makedirs(os.path.dirname(os.path.join(root, rel)) or root, exist_ok=True)
        with open(os.path.join(root, rel), "w", encoding="utf-8") as f:
            f.write(text)
    subprocess.run([REAL_GIT, "init", "-q", "-b", "main"], cwd=root, check=True, capture_output=True)
    # Repo thật bỏ __pycache__ bằng .gitignore; chạy tool trong repo tạm ghi bytecode ⇒ loại cục bộ (không track) để status sạch.
    with open(os.path.join(root, ".git/info/exclude"), "a", encoding="utf-8") as f:
        f.write("__pycache__/\n")
    for a in (("config", "user.email", "a@b"), ("config", "user.name", "t"),
              ("add", "-A"), ("commit", "-qm", "init"), ("tag", "-a", "v0.1.0", "-m", "v0.1.0")):
        subprocess.run([REAL_GIT, *a], cwd=root, check=True, capture_output=True)


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.r = os.path.join(self.tmp.name, "repo")
        self.lock = os.path.join(self.r, ".git", "index.lock")

    def git(self, *a):
        return subprocess.run([REAL_GIT, *a], cwd=self.r, capture_output=True, text=True).stdout

    def git_rc(self, *a):
        return subprocess.run([REAL_GIT, *a], cwd=self.r, capture_output=True, text=True).returncode

    def fake_git_env(self, extra="", **fault):
        d = os.path.join(self.tmp.name, "bin")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "git"), "w") as f:
            f.write(FAKE_GIT.format(extra=extra, real=REAL_GIT))
        os.chmod(os.path.join(d, "git"), 0o755)
        env = {"PATH": d + os.pathsep + os.environ["PATH"], "FAKE_COUNT": os.path.join(self.tmp.name, "count"),
               "FAKE_LOCK": self.lock}
        env.update({k: str(v) for k, v in fault.items()})
        return env

    def bump(self, *a, env=None):
        return subprocess.run(["bash", "tools/release/bump_version.sh", *a], cwd=self.r, capture_output=True,
                              text=True, start_new_session=True, timeout=60,
                              env=None if env is None else dict(os.environ, **env))

    def snapshot(self):
        out = {}
        for rel in FILES:
            p = os.path.join(self.r, rel)
            if os.path.exists(p):
                with open(p, "rb") as f:
                    out[rel] = f.read()
            else:
                out[rel] = None
        return out, self.git("rev-parse", "HEAD").strip(), self.git("tag")

    def drop_lock(self):
        if os.path.exists(self.lock):
            os.remove(self.lock)

    def assert_untouched(self, before):
        """Trạng thái sau = trước: 5 file y byte, HEAD cũ, tag cũ, index == HEAD, cây sạch."""
        self.drop_lock()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.git_rc("diff", "--cached", "--quiet", "HEAD"), 0, self.git("status", "--porcelain"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def assert_rollback_honest(self, r, before):
        """rc≠0 ⇒ hoặc báo KHÔNG hoàn tác được, hoặc trạng thái y nguyên."""
        self.assertNotEqual(r.returncode, 0)
        if "KHÔNG hoàn tác được" in r.stderr:
            self.assertNotIn("đã hoàn tác", r.stderr)
        else:
            self.assert_untouched(before)


class BumpTests(RepoCase):
    def setUp(self):
        super().setUp()
        make_repo(self.r)

    def commit_file(self, rel, text, msg="edit"):
        p = os.path.join(self.r, rel)
        if text is None:
            os.remove(p)
        else:
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
        self.git("add", "-A")
        self.git("commit", "-qm", msg)
        self.git("tag", "-d", "v0.1.0")
        self.git("tag", "-a", "v0.1.0", "-m", "v0.1.0")

    def commit_changelog(self):
        self.commit_file("CHANGELOG.md", "# Changelog\n\n## v0.1.0 — x\n\n- old\n", "changelog")

    def test_dry_run_moi_thu_tu_khong_doi_gi(self):
        before = self.snapshot()
        r = self.bump("patch", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2 chỗ unreleased", r.stdout)
        self.assert_untouched(before)
        self.git("checkout", "-q", "-b", "develop")
        for args in (["patch", "--force", "--dry-run"], ["patch", "--dry-run", "--force"]):
            with self.subTest(args):
                r = self.bump(*args)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("[dry-run]", r.stdout)
                self.assert_untouched(before)

    def test_doi_so_la_exit_2_khong_doi_gi(self):
        before = self.snapshot()
        for args in (["patch", "--dryrun"], ["patch", "--dry-run", "extra"], ["huge"]):
            with self.subTest(args):
                r = self.bump(*args)
                self.assertEqual(r.returncode, 2)
                self.assertIn("dùng:", r.stderr)
                self.assert_untouched(before)

    def test_bump_that_dong_dau_trong_cung_commit(self):
        r = self.bump("patch")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(CAT_REL, self.git("show", "--name-only", "--format=", "HEAD"))
        with open(os.path.join(self.r, CAT_REL), encoding="utf-8") as f:
            self.assertNotIn("unreleased", f.read())
        self.assertIn("v0.1.1", self.git("tag").split())
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.git_rc("diff", "--cached", "--quiet", "HEAD"), 0)

    def test_khong_co_catalog_van_bump_duoc(self):
        # hotfix từ main cũ chưa có tính năng What's New
        self.commit_file(CAT_REL, None)
        r = self.bump("patch")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("v0.1.1", self.git("tag").split())

    def test_dang_khong_tu_thay_duoc_thi_ca_hai_che_do_fail(self):
        for text in ("let dev: CardVersion = .unreleased\n", "// .unreleased\nX(version: .released(\"1.0.0\"))\n"):
            self.commit_file(CAT_REL, text)
            before = self.snapshot()
            for args in (["patch"], ["patch", "--dry-run"]):
                with self.subTest(text=text, args=args):
                    r = self.bump(*args)
                    self.assertNotEqual(r.returncode, 0, r.stdout)
                    self.assertIn("FAIL", r.stderr)
                    self.assertNotIn("hoàn tác", r.stderr)  # chặn ở preflight, không phải nhờ rollback
                    self.assert_untouched(before)

    def test_co_catalog_thieu_stamp_thi_fail_truoc_khi_ghi(self):
        self.commit_file("tools/release/stamp_whats_new.py", None)
        before = self.snapshot()
        for args in (["patch"], ["patch", "--dry-run"]):
            with self.subTest(args):
                r = self.bump(*args)
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertIn("thiếu tools/release/stamp_whats_new.py", r.stderr)
                self.assertNotIn("hoàn tác", r.stderr)
                self.assert_untouched(before)

    def test_config_thieu_khoa_version_thi_khong_ghi_gi_ca(self):
        # appconfig từ chối config thiếu version.build ⇒ bump dừng với thông báo nêu đúng khoá
        self.commit_file(CFG_REL, CONFIG.replace('build = "1"\n', ''))
        before = self.snapshot()
        for args in (["patch"], ["patch", "--dry-run"]):
            with self.subTest(args):
                r = self.bump(*args)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("version.build", r.stderr)
                self.assert_untouched(before)

    def test_config_dang_nhay_don_thi_chan_o_preflight(self):
        # appconfig đọc được nhưng sed không thay được ⇒ phải dừng TRƯỚC khi ghi, không ghi hụt
        self.commit_file(CFG_REL, CONFIG.replace('marketing = "0.1.0"', "marketing = '0.1.0'"))
        before = self.snapshot()
        for args in (["patch"], ["patch", "--dry-run"]):
            with self.subTest(args):
                r = self.bump(*args)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(CFG_REL, r.stderr)
                self.assertNotIn("hoàn tác", r.stderr)
                self.assert_untouched(before)

    def test_bump_patch_ghi_config_va_xcconfig(self):
        r = self.bump("patch")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.r, CFG_REL), "rb") as f:
            cfg = tomllib.load(f)
        self.assertEqual(cfg["version"], {"marketing": "0.1.1", "build": "2"})
        with open(os.path.join(self.r, XCC_REL), encoding="utf-8") as f:
            xcc = f.read()
        self.assertIn("APP_MARKETING_VERSION = 0.1.1\n", xcc)
        self.assertIn("APP_BUILD_NUMBER = 2\n", xcc)
        # xcconfig khớp config (không trôi) và nằm cùng commit bump
        self.assertEqual(xcc, appconfig.render_xcconfig(cfg))
        committed = self.git("show", "--name-only", "--format=", "HEAD").split()
        for rel in (CFG_REL, XCC_REL, "CHANGELOG.md"):
            self.assertIn(rel, committed)

    def test_dry_run_khong_doi_gi(self):
        before = self.snapshot()
        r = self.bump("minor", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[dry-run]", r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_buoc_cuoi_fail_thi_hoan_tac_het(self):
        # commit bị hook chặn (bước SAU mọi lần ghi file) ⇒ rollback trả 5 file về nguyên trạng, CHANGELOG mới bị xoá
        before = self.snapshot()
        hook = os.path.join(self.r, ".git/hooks/pre-commit")
        with open(hook, "w") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(hook, 0o755)
        r = self.bump("patch")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("đã hoàn tác", r.stderr)
        self.assert_untouched(before)
        self.assertFalse(os.path.exists(os.path.join(self.r, "CHANGELOG.md")))

    def test_features_yml_cu_trong_cay_thi_hoan_tac_ve_dung_ban_cu(self):
        # bump chạy `render` nên SINH LẠI Features.generated.yml; nếu bump hỏng giữa chừng, file này phải về y byte
        # bản trước (nó nằm trong danh sách sao lưu/hoàn tác như xcconfig). Dựng ca: commit một bản file cũ.
        self.commit_file(FEAT_REL, "# bản cũ commit nhầm\n{}\n", "features cũ")
        before = self.snapshot()
        hook = os.path.join(self.r, ".git/hooks/pre-commit")
        with open(hook, "w") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(hook, 0o755)
        r = self.bump("patch")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("đã hoàn tác", r.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assert_untouched(before)

    def test_bump_that_dua_features_yml_vao_commit_bump(self):
        self.commit_file(FEAT_REL, "# bản cũ commit nhầm\n{}\n", "features cũ")
        r = self.bump("patch")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.r, FEAT_REL), encoding="utf-8") as f:
            self.assertEqual(f.read(), appconfig.render_features_yml(tomllib.loads(CONFIG)))
        self.assertIn(FEAT_REL, self.git("show", "--name-only", "--format=", "HEAD"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_changelog_chi_doc_thi_khong_ghi_gi(self):
        self.commit_changelog()
        os.chmod(os.path.join(self.r, "CHANGELOG.md"), 0o444)
        self.addCleanup(os.chmod, os.path.join(self.r, "CHANGELOG.md"), 0o644)
        before = self.snapshot()
        r = self.bump("patch")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CHANGELOG", r.stderr)
        self.assert_untouched(before)

    def test_index_lock_co_san_chan_o_preflight(self):
        self.commit_changelog()
        before = self.snapshot()
        open(self.lock, "w").close()
        r = self.bump("patch")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("index.lock", r.stderr)
        self.assertNotIn("hoàn tác", r.stderr)
        self.assert_untouched(before)

    def test_tag_da_co_thi_khong_ghi(self):
        self.git("tag", "v0.1.1")
        before = self.snapshot()
        r = self.bump("patch")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("đã tồn tại", r.stderr)
        self.assert_untouched(before)

    def test_khong_hoan_tac_duoc_file_thi_bao_that(self):
        # app.config.toml bị khoá ghi giữa chừng ⇒ chép ngược fail ⇒ KHÔNG được in "đã hoàn tác".
        self.commit_changelog()
        plist = os.path.join(self.r, CFG_REL)
        self.addCleanup(os.chmod, plist, 0o644)
        r = self.bump("patch", env=self.fake_git_env(extra=f'[ "$1" = tag ] && chmod 444 "{plist}" && exit 1'))
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("đã hoàn tác", r.stderr)
        self.assertIn("KHÔNG hoàn tác được", r.stderr)
        self.assertIn("app.config.toml", r.stderr)

    def test_khong_dua_duoc_head_ve_thi_bao_that(self):
        # tag fail sau commit + update-ref (đưa HEAD về) cũng fail ⇒ HEAD kẹt ở commit bump ⇒ phải báo.
        self.commit_changelog()
        r = self.bump("patch", env=self.fake_git_env(
            extra='[ "$1" = tag ] && [ "$2" = -a ] && exit 1; [ "$1" = update-ref ] && exit 1'))
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("đã hoàn tác", r.stderr)
        self.assertIn("KHÔNG hoàn tác được", r.stderr)
        self.assertIn("HEAD", r.stderr)

    def test_khong_xoa_duoc_tag_thi_bao_that(self):
        # bước đồng bộ index cuối fail sau khi đã tag + `git tag -d` cũng fail ⇒ tag mới còn ⇒ phải báo.
        self.commit_changelog()
        r = self.bump("patch", env=self.fake_git_env(
            extra='[ "$1" = reset ] && [ "$#" = 2 ] && exit 1; [ "$1" = tag ] && [ "$2" = -d ] && exit 1'))
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("đã hoàn tác", r.stderr)
        self.assertIn("KHÔNG hoàn tác được", r.stderr)
        self.assertIn("tag v0.1.1", r.stderr)

    def test_khong_dua_duoc_index_ve_thi_bao_that(self):
        # đồng bộ index chạy THẬT rồi báo lỗi + index.lock kẹt ⇒ không đưa index về được ⇒ phải báo.
        self.commit_changelog()
        r = self.bump("patch", env=self.fake_git_env(
            extra=f'[ "$1" = reset ] && [ "$#" = 2 ] && {{ "{REAL_GIT}" "$@"; : > "{self.lock}"; exit 1; }}'))
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("đã hoàn tác", r.stderr)
        self.assertIn("KHÔNG hoàn tác được", r.stderr)
        self.assertIn("index", r.stderr)

    def test_sigterm_giua_chung_van_hoan_tac(self):
        # TERM tới lúc `git commit` đang chạy (commit vẫn xong) ⇒ trap TERM phải hoàn tác, không bỏ dở với HEAD mới.
        self.commit_changelog()
        before = self.snapshot()
        r = self.bump("patch", env=self.fake_git_env(
            extra='[ "$1" = commit ] && { trap "" TERM; kill -TERM 0; }'))
        self.assertEqual(r.returncode, 143, r.stderr)
        self.assertIn("SIGTERM", r.stderr)
        self.assertIn("đã hoàn tác", r.stderr)
        self.assert_untouched(before)

    def test_sigint_giua_chung_van_hoan_tac(self):
        # Ctrl-C (INT tới cả process group) lúc `git tag` ⇒ trap INT hoàn tác commit + tag + file.
        self.commit_changelog()
        before = self.snapshot()
        r = self.bump("patch", env=self.fake_git_env(
            extra='[ "$1" = tag ] && [ "$2" = -a ] && { trap "" INT; kill -INT 0; }'))
        self.assertEqual(r.returncode, 130, r.stderr)
        self.assertIn("SIGINT", r.stderr)
        self.assertIn("đã hoàn tác", r.stderr)
        self.assert_untouched(before)

    def test_sighup_giua_chung_van_hoan_tac(self):
        # đóng terminal (HUP tới cả nhóm) lúc `git commit` ⇒ trap HUP hoàn tác.
        self.commit_changelog()
        before = self.snapshot()
        r = self.bump("patch", env=self.fake_git_env(
            extra='[ "$1" = commit ] && { trap "" HUP; kill -HUP 0; }'))
        self.assertEqual(r.returncode, 129, r.stderr)
        self.assertIn("SIGHUP", r.stderr)
        self.assertIn("đã hoàn tác", r.stderr)
        self.assert_untouched(before)

    def test_tin_hieu_luc_dang_hoan_tac_khong_cat_ngang(self):
        # tag fail ⇒ rollback (ERR); INT/TERM/HUP tới đúng lúc rollback đang chạy git ⇒ rollback vẫn làm hết.
        for sig in ("INT", "TERM", "HUP"):
            with self.subTest(sig):
                self.tearDown_repo()
                before = self.snapshot()
                r = self.bump("patch", env=self.fake_git_env(
                    extra=('[ "$1" = tag ] && [ "$2" = -a ] && exit 1; '
                           f'[ "$1" = for-each-ref ] && [ -f "$FAKE_COUNT.tagfail" ] && {{ trap "" {sig}; kill -{sig} 0; }}; '
                           '[ "$1" = tag ] && : > "$FAKE_COUNT.tagfail"')))
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn("đã hoàn tác", r.stderr)
                self.assert_untouched(before)

    def tearDown_repo(self):
        """Repo mới cho mỗi subTest (đã có CHANGELOG)."""
        shutil.rmtree(self.r, ignore_errors=True)
        for f in ("count", "count.tagfail"):
            p = os.path.join(self.tmp.name, f)
            if os.path.exists(p):
                os.remove(p)
        make_repo(self.r, changelog="# Changelog\n\n## v0.1.0 — x\n\n- old\n")

    def test_dong_bo_index_cuoi_chay_that_roi_loi_thi_dua_index_ve(self):
        # `git reset -q` cuối ĐÃ đổi index rồi mới báo lỗi ⇒ rollback phải đưa index về HEAD cũ (không chỉ báo).
        self.commit_changelog()
        before = self.snapshot()
        r = self.bump("patch", env=self.fake_git_env(
            extra=f'[ "$1" = reset ] && [ "$#" = 2 ] && {{ "{REAL_GIT}" "$@"; exit 1; }}'))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("đã hoàn tác", r.stderr)
        self.assert_untouched(before)


class FuzzRollbackTests(RepoCase):
    """Lỗi ở lần gọi git thứ k (mọi k của một bump thành công) × mọi chế độ lỗi ⇒ bất biến hoàn tác trung thực."""

    @classmethod
    def setUpClass(cls):
        cls.tmpl_dir = tempfile.TemporaryDirectory()
        cls.templates = {}
        for name, changelog in (("co_changelog", "# Changelog\n\n## v0.1.0 — x\n\n- old\n"), ("khong_changelog", None)):
            p = os.path.join(cls.tmpl_dir.name, name)
            make_repo(p, changelog=changelog)
            cls.templates[name] = p

    @classmethod
    def tearDownClass(cls):
        cls.tmpl_dir.cleanup()

    def fresh(self, template):
        if os.path.exists(self.r):
            shutil.rmtree(self.r)
        shutil.copytree(self.templates[template], self.r, symlinks=True)
        count = os.path.join(self.tmp.name, "count")
        if os.path.exists(count):
            os.remove(count)

    def plan(self, template, total):
        """Repo có CHANGELOG: mọi k × mọi chế độ. Repo không CHANGELOG (chỉ khác nhánh 'file trước đó không có'):
        lấy mẫu k (mỗi 4 lần gọi) × 4 chế độ — giữ cả file test dưới ~90 s."""
        if template == "co_changelog":
            return [(k, m) for k in range(1, total + 1) for m in FAULT_MODES]
        return [(k, m) for k in range(1, total + 1, 4) for m in FAULT_MODES[:4]]

    def test_fuzz_moi_lan_goi_git_moi_che_do(self):
        t0 = time.monotonic()
        runs = 0
        stats = {}
        for template in self.templates:
            self.fresh(template)
            r = self.bump("patch", env=self.fake_git_env())
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(self.tmp.name, "count")) as f:
                total = int(f.read())
            self.assertGreater(total, 8)
            for k, (mode, sig, off) in self.plan(template, total):
                with self.subTest(template=template, k=k, mode=mode, sig=sig, off=off):
                    self.fresh(template)
                    before = self.snapshot()
                    fault = {"FAULT_K": k, "FAULT_MODE": mode}
                    if sig:
                        fault.update(FAULT_SIG=sig, FAULT_SIG_K=k + off)
                    r = self.bump("patch", env=self.fake_git_env(**fault))
                    runs += 1
                    kind = ("rc0" if r.returncode == 0 else "KHÔNG hoàn tác được" if "KHÔNG hoàn tác được" in r.stderr
                            else "đã hoàn tác" if "đã hoàn tác" in r.stderr else "dừng trước khi ghi")
                    for name in SIG_RC:
                        if f"(SIG{name})" in r.stderr:
                            kind += f" (SIG{name})"
                    if sig and mode != "none" and "đã hoàn tác" in kind:
                        kind += " + tín hiệu lúc hoàn tác"
                    stats[kind] = stats.get(kind, 0) + 1
                    if r.returncode == 0:
                        self.drop_lock()
                        self.assertIn("v0.1.1", self.git("tag").split())
                        self.assertEqual(self.git("rev-parse", "HEAD~1").strip(), before[1])
                        self.assertEqual(self.git("status", "--porcelain"), "")
                        self.assertEqual(self.git_rc("diff", "--cached", "--quiet", "HEAD"), 0)
                        after = self.snapshot()[0]
                        for rel in (CFG_REL, XCC_REL, CAT_REL, "CHANGELOG.md"):
                            self.assertNotEqual(after[rel], before[0][rel], rel)
                    else:
                        self.assert_rollback_honest(r, before)
                        # Không có index.lock kẹt thì không có gì cản hoàn tác ⇒ PHẢI hoàn tác được (bắt rollback bỏ
                        # bước đưa index về mà vẫn "trung thực" nhờ báo KHÔNG hoàn tác được).
                        if "lock" not in mode:
                            self.assertNotIn("KHÔNG hoàn tác được", r.stderr)
        print(f"\n[fuzz] {runs} lần bump có lỗi tiêm trong {time.monotonic() - t0:.1f}s: {stats}", flush=True)
        # Fuzz phải thật sự đi qua: hoàn tác thành công, báo không hoàn tác được, trap từng tín hiệu, tín hiệu giữa
        # lúc đang hoàn tác.
        for kind in ("đã hoàn tác", "KHÔNG hoàn tác được", "đã hoàn tác (SIGTERM)", "đã hoàn tác (SIGINT)",
                     "đã hoàn tác (SIGHUP)", "đã hoàn tác + tín hiệu lúc hoàn tác"):
            self.assertIn(kind, stats)

if __name__ == "__main__":
    unittest.main()
