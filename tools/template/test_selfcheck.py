"""Test cho tools/template/selfcheck.sh (lớp đồng bộ — phải xanh cả ở template lẫn mọi app sinh ra): luật "template
hay app" (`--kind`) giống `repo_kind` của .githooks/pre-commit — template khi HEAD track file đánh dấu (new_app.py của
template, trong tools/template); HEAD chưa có commit thì xét index; mọi repo khác là app.

Chạy trên repo git dựng trong thư mục tạm có dấu cách (bản chép của selfcheck.sh), không đụng repo thật. Lượt chạy
đầy đủ của selfcheck (lint, build, cổng release) không nằm ở đây.
Chạy: python3 -m unittest discover -s tools/template -p 'test_*.py'
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELFCHECK = HERE / "selfcheck.sh"
MARKER = "tools/template/new_app.py"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra)
    return env


class SelfcheckKindTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo có dấu cách"
        (self.repo / "tools/template").mkdir(parents=True)
        shutil.copy2(SELFCHECK, self.repo / "tools/template/selfcheck.sh")
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        r = subprocess.run(["git", "--no-optional-locks", "-c", "user.name=t", "-c", "user.email=t@invalid",
                            "-c", "commit.gpgsign=false", *args], cwd=self.repo, capture_output=True, text=True,
                           env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)

    def kind(self, **env):
        r = subprocess.run(["bash", "tools/template/selfcheck.sh", "--kind"], cwd=self.repo, capture_output=True,
                           text=True, env=clean_env(**env))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    def commit_all(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c")

    def test_head_track_file_danh_dau_la_template(self):
        (self.repo / MARKER).write_text("# dấu\n")
        self.commit_all()
        self.assertEqual(self.kind(), "template")

    def test_khong_co_file_danh_dau_la_app(self):
        (self.repo / "core.lock").write_text("{}\n")
        self.commit_all()
        self.assertEqual(self.kind(), "app")

    def test_file_danh_dau_chi_tren_dia_khong_track_la_app(self):
        self.commit_all()
        (self.repo / MARKER).write_text("# lạc\n")
        self.assertEqual(self.kind(), "app")

    def test_file_danh_dau_chi_moi_stage_khi_head_co_la_app(self):
        # HEAD quyết định (như hook): stage file đánh dấu trong một app không biến nó thành template.
        self.commit_all()
        (self.repo / MARKER).write_text("# lạc\n")
        self.git("add", MARKER)
        self.assertEqual(self.kind(), "app")

    def test_head_chua_co_thi_xet_index(self):
        (self.repo / MARKER).write_text("# dấu\n")
        self.assertEqual(self.kind(), "app")
        self.git("add", MARKER)
        self.assertEqual(self.kind(), "template")

    def test_khong_tin_bien_git_thua_huong(self):
        # GIT_DIR trỏ repo khác (vd chạy từ hook của repo khác) không được đổi kết luận.
        (self.repo / MARKER).write_text("# dấu\n")
        self.commit_all()
        other = self.repo.parent / "khac"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True, capture_output=True, env=clean_env())
        self.assertEqual(self.kind(GIT_DIR=str(other / ".git")), "template")

    def test_thu_muc_unittest_duoc_phat_hien_khong_viet_cung(self):
        # Đoạn phát hiện thư mục (từ `UNIT_DIRS=()` tới dòng kiểm tối thiểu) chạy riêng trên cây giả: mọi tools/<d>/ có
        # test_*.py vào danh sách đúng một lần, thư mục không có test thì không.
        src = SELFCHECK.read_text(encoding="utf-8")
        start = src.index("UNIT_DIRS=()")
        end = src.index('[ "${#UNIT_DIRS[@]}" -ge 1 ]')
        snippet = src[start:end]
        for d, files in {"analytics": ["test_a.py", "test_b.py"], "cong cu moi": ["test_x.py"], "khong test": ["x.py"],
                         "common": ["test_c.py"]}.items():
            (self.repo / "tools" / d).mkdir(parents=True, exist_ok=True)
            for f in files:
                (self.repo / "tools" / d / f).write_text("")
        r = subprocess.run(["bash", "-c", "set -u\n" + snippet + 'printf "%s\\n" "${UNIT_DIRS[@]}"'], cwd=self.repo,
                           capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(r.stdout.splitlines()), ["tools/analytics", "tools/common", "tools/cong cu moi"])
        # Không còn danh sách cứng; mẫu `-p` trong nháy đơn (hook của agent chỉ chấp nhận dạng đó).
        self.assertNotIn("for D in common", src)
        self.assertIn("-p 'test_*.py'", src)

    def unit_dirs(self):
        src = SELFCHECK.read_text(encoding="utf-8")
        snippet = src[src.index("UNIT_DIRS=()"):src.index('[ "${#UNIT_DIRS[@]}" -ge 1 ]')]
        r = subprocess.run(["bash", "-c", "set -u\n" + snippet + 'printf "%s\\n" "${UNIT_DIRS[@]}"'], cwd=self.repo,
                           capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()

    def test_selfcheck_do_web_tools(self):
        # web/tools/ (cổng site/sitemap/changelog/predeploy) vào cổng unit test khi có test; không có thì không.
        (self.repo / "tools/common").mkdir(parents=True)
        (self.repo / "tools/common/test_c.py").write_text("")
        self.assertEqual(self.unit_dirs(), ["tools/common"])
        (self.repo / "web/tools").mkdir(parents=True)
        (self.repo / "web/tools/check_site.py").write_text("")
        self.assertEqual(self.unit_dirs(), ["tools/common"], "web/tools không có test_*.py ⇒ không vào")
        (self.repo / "web/tools/test_a.py").write_text("")
        (self.repo / "web/tools/test_b.py").write_text("")
        self.assertEqual(self.unit_dirs(), ["tools/common", "web/tools"])

    def web_npm(self, quick, node_version="v25.4.0", npm_rc=0, missing=()):
        """Chạy riêng bước 2b (web npm) của selfcheck với `node`/`npm` GIẢ trên PATH (ghi lời gọi ra file) — không mạng."""
        src = SELFCHECK.read_text(encoding="utf-8")
        snippet = src[src.index("# 2b. web/"):src.index("# 3. Lint harness")]
        bindir = self.repo.parent / "bin gia"
        bindir.mkdir(exist_ok=True)
        calls = self.repo.parent / "calls.txt"
        if calls.exists():
            calls.unlink()
        (bindir / "npm").write_text(f'#!/bin/bash\necho "npm $* @ $(basename "$PWD")" >> "{calls}"\nexit {npm_rc}\n')
        # node giả: `--version` in bản giả; `-e <mã kiểm bản>` chạy CHÍNH mã đó bằng node THẬT với process.versions.node
        # bị thay bằng bản giả (máy không có node ⇒ đánh giá luật >= 22.12 bằng bash).
        real = shutil.which("node")
        if real:
            run_e = ('if [ "$1" = "-e" ]; then exec "' + real + '" -e "Object.defineProperty(process, \\"versions\\", '
                     '{value: {...process.versions, node: \\"${V#v}\\"}}); $2"; fi\n')
        else:
            run_e = ('IFS=. read -r A B _ <<< "${V#v}"\n'
                     'if [ "$A" -gt 22 ] || { [ "$A" -eq 22 ] && [ "$B" -ge 12 ]; }; then exit 0; fi\nexit 1\n')
        (bindir / "node").write_text(
            '#!/bin/bash\nV="' + node_version + '"\nif [ "$1" = "--version" ]; then echo "$V"; exit 0; fi\n' + run_e
            + "exit 3\n")
        for f in ("npm", "node"):
            (bindir / f).chmod(0o755)
        for f in missing:                     # PATH chỉ còn /usr/bin, /bin — không có node/npm thật ở đó
            (bindir / f).unlink()
        (self.repo / "web").mkdir(exist_ok=True)
        (self.repo / "web/package.json").write_text("{}\n")
        prelude = (f'set -u\nQUICK={1 if quick else 0}\nROOT="$PWD"\n'
                   'step_ok() { echo "[selfcheck] $1: OK"; }\nfail() { echo "[selfcheck] FAIL: $1" >&2; exit 1; }\n')
        env = clean_env(PATH=f"{bindir}{os.pathsep}/usr/bin{os.pathsep}/bin")
        r = subprocess.run(["bash", "-c", prelude + snippet + 'echo "[selfcheck] HET"'], cwd=self.repo,
                           capture_output=True, text=True, env=env)
        return r, (calls.read_text().splitlines() if calls.exists() else [])

    def test_selfcheck_quick_bo_qua_npm_co_bao(self):
        r, calls = self.web_npm(quick=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[selfcheck] web npm (npm ci, npm test, npm run typecheck): BỎ QUA (--quick)", r.stdout)
        self.assertEqual(calls, [], "--quick không được gọi npm (npm ci cần mạng)")

    def test_selfcheck_day_du_chay_npm_ci_test_typecheck_trong_web(self):
        r, calls = self.web_npm(quick=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ["npm ci @ web", "npm test @ web", "npm run typecheck @ web"])
        self.assertIn("[selfcheck] web npm ci + test + typecheck: OK", r.stdout)

    def test_selfcheck_day_du_npm_do_thi_do(self):
        r, calls = self.web_npm(quick=False, npm_rc=1)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(calls, ["npm ci @ web"])
        self.assertNotIn("HET", r.stdout)

    def test_selfcheck_day_du_node_cu_thi_do(self):
        for v in ("v22.11.0", "v20.18.1"):
            with self.subTest(v=v):
                r, calls = self.web_npm(quick=False, node_version=v)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("22.12", r.stderr)
                self.assertEqual(calls, [])
        r, _ = self.web_npm(quick=False, node_version="v22.12.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_selfcheck_day_du_thieu_node_hoac_npm_thi_do(self):
        for gone in (("npm",), ("node",), ("node", "npm")):
            with self.subTest(gone=gone):
                r, calls = self.web_npm(quick=False, missing=gone)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("không thấy node/npm", r.stderr)
                self.assertEqual(calls, [])
        r, _ = self.web_npm(quick=True, missing=("node", "npm"))
        self.assertEqual(r.returncode, 0, "--quick không cần node/npm: " + r.stderr)

    def test_khong_co_web_thi_bo_qua(self):
        src = SELFCHECK.read_text(encoding="utf-8")
        snippet = src[src.index("# 2b. web/"):src.index("# 3. Lint harness")]
        r = subprocess.run(["bash", "-c", "set -u\nQUICK=0\nROOT=$PWD\nfail() { exit 1; }\nstep_ok() { :; }\n" + snippet],
                           cwd=self.repo, capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("web npm: BỎ QUA (không có web/package.json)", r.stdout)

    def test_tham_so_la_la_rc2(self):
        r = subprocess.run(["bash", str(SELFCHECK), "--khong-co"], capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
