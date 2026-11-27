"""Test cho tools/template/manifest.py — ba lớp sở hữu + cổng "mọi file có lớp".

Mỗi test dựng một repo git tạm (đường dẫn có dấu cách) với manifest + file giả; mọi biến GIT_* bị gỡ khỏi env
(docs/lessons-learned/test-git-trong-hook-dung-repo-that.md). Không đụng cây thật, không dựa file chỉ-template.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "manifest.py"
sys.path.insert(0, str(HERE))
import manifest  # noqa: E402

BASE_MANIFEST = """\
schema = 1
[sync]
paths = ["Loi/", "tools/chung/", "tai-lieu/kien-truc.md", "template.manifest.toml"]
[seed]
paths = ["cau-hinh.toml", "App/"]
overlay_dir = "tools/mau/gieo"
[template_only]
paths = ["tai-lieu/rieng/", "GIOI-THIEU.md"]
"""
BASE_FILES = {
    "Loi/A.swift": "struct A {}\n",
    "tools/chung/x.py": "print('x')\n",
    "tai-lieu/kien-truc.md": "# Kiến trúc\n",
    "cau-hinh.toml": "a = 1\n",
    "App/B.swift": "struct B {}\n",
    "tai-lieu/rieng/ke-hoach.md": "# kế hoạch\n",
    "GIOI-THIEU.md": "# giới thiệu\n",
}


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo có dấu cách"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        top = self.git("rev-parse", "--show-toplevel").stdout.strip()
        self.assertEqual(Path(top).resolve(), self.root.resolve(), "repo tạm phải là gốc, không phải repo thật")
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST)
        for rel, text in BASE_FILES.items():
            self.write(rel, text)
        old_idx = os.environ.pop("GIT_INDEX_FILE", None)
        if old_idx is not None:
            self.addCleanup(os.environ.__setitem__, "GIT_INDEX_FILE", old_idx)

    def git(self, *args):
        return subprocess.run(["git", "--no-optional-locks", *args], cwd=self.root, env=clean_env(),
                              capture_output=True, text=True)

    def write(self, rel, text, add=True):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        if add:
            r = self.git("add", "--", rel)
            self.assertEqual(r.returncode, 0, r.stderr)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--root", str(self.root)], env=clean_env(),
                              capture_output=True, text=True)

    def check(self):
        return manifest.check(self.root)

    # ------------------------------------------------------------ nền

    def test_cay_tam_sach(self):
        self.assertEqual(self.check(), [])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_duong_dan_dai_nhat_thang(self):
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST.replace(
            '"tai-lieu/rieng/", ', '"tai-lieu/rieng/", "Loi/Rieng/", "Loi/Rieng/Mot.swift", '))
        m = manifest.load(self.root)
        self.assertEqual(manifest.classify(m, "Loi/A.swift"), "sync")
        self.assertEqual(manifest.classify(m, "Loi/Rieng/Hai.swift"), "template_only")
        # Mục file trùng tên với tiền tố của mục thư mục: dài nhất (cụ thể nhất) vẫn thắng.
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST.replace('"App/"]', '"App/", "Loi/Rieng/Mot.swift"]')
                   .replace('"tai-lieu/rieng/", ', '"tai-lieu/rieng/", "Loi/Rieng/", '))
        m = manifest.load(self.root)
        self.assertEqual(manifest.classify(m, "Loi/Rieng/Mot.swift"), "seed")
        self.assertEqual(manifest.classify(m, "Loi/Rieng/Hai.swift"), "template_only")
        self.assertEqual(manifest.classify(m, "Loi/A.swift"), "sync")
        # "Loi/" không khớp "LoiKhac/x" (khớp theo thư mục, không theo tiền tố chuỗi trần).
        self.assertIsNone(manifest.classify(m, "LoiKhac/x.swift"))
        self.assertIsNone(manifest.classify(m, "tai-lieu/kien-truc.md.bak"))
        r = self.run_cli("classify", "Loi/Rieng/Mot.swift", "Loi/A.swift")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["seed\tLoi/Rieng/Mot.swift", "sync\tLoi/A.swift"])

    def test_file_chua_phan_lop_bi_bao(self):
        self.write("tep moi/lạ.txt", "x\n")
        problems = self.check()
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("tep moi/lạ.txt", problems[0])
        self.assertIn("chưa thuộc lớp nào", problems[0])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("tep moi/lạ.txt", r.stdout)
        r = self.run_cli("classify", "tep moi/lạ.txt")
        self.assertEqual(r.returncode, 1)

    def test_file_chua_track_khong_tinh(self):
        self.write("rac.txt", "x\n", add=False)
        self.assertEqual(self.check(), [])

    def test_muc_khai_khong_khop_file_nao_bi_bao(self):
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST.replace('"App/"]', '"App/", "Khong/Co/", "khong-co.md"]'))
        problems = self.check()
        self.assertEqual(sorted(problems), sorted([
            f'{manifest.MANIFEST_FILE}: mục "Khong/Co/" ([seed]) không khớp file track nào',
            f'{manifest.MANIFEST_FILE}: mục "khong-co.md" ([seed]) không khớp file track nào',
        ]))
        self.assertEqual(self.run_cli("check").returncode, 1)

    def test_hai_lop_cung_duong_dan_bi_tu_choi(self):
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST.replace('"GIOI-THIEU.md"]', '"GIOI-THIEU.md", "App/"]'))
        with self.assertRaises(manifest.ManifestError) as cm:
            manifest.load(self.root)
        self.assertIn("App/", str(cm.exception))
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("App/", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        # classify trên dict dựng tay (bỏ qua load) cũng từ chối.
        m = {"schema": 1, "sync": {"paths": ["X/"]}, "seed": {"paths": ["X/"]}, "template_only": {"paths": []}}
        with self.assertRaises(manifest.ManifestError):
            manifest.classify(m, "X/a")

    def test_manifest_hong_rc_2(self):
        cases = {
            "toml hỏng": "schema = 1\n[sync\n",
            "schema sai": BASE_MANIFEST.replace("schema = 1", "schema = 2"),
            "thiếu lớp": BASE_MANIFEST.split("[template_only]")[0],
            "khoá lạ": BASE_MANIFEST + "[them]\npaths = []\n",
            "khoá lạ trong lớp": BASE_MANIFEST.replace("[sync]\n", "[sync]\nmode = 1\n"),
            "paths không phải list": BASE_MANIFEST.replace('paths = ["cau-hinh.toml", "App/"]', 'paths = "App/"'),
            "đường dẫn thoát gốc": BASE_MANIFEST.replace('"App/"]', '"App/", "../ngoai/"]'),
            "đường dẫn tuyệt đối": BASE_MANIFEST.replace('"App/"]', '"App/", "/etc/"]'),
            "khai hai lần cùng lớp": BASE_MANIFEST.replace('"App/"]', '"App/", "App/"]'),
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.write(manifest.MANIFEST_FILE, text)
                r = self.run_cli("check")
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("FAIL:", r.stderr)
                self.assertNotIn("Traceback", r.stderr)
        (self.root / manifest.MANIFEST_FILE).unlink()
        self.assertEqual(self.run_cli("check").returncode, 2)

    def test_khong_phai_repo_git_rc_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "không git"
            root.mkdir()
            (root / manifest.MANIFEST_FILE).write_text(BASE_MANIFEST, encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPT), "check", "--root", str(root)], env=clean_env(),
                               capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    # ------------------------------------------------------------ thư mục gieo

    def test_overlay_de_len_file_khong_phai_chi_template_bi_bao(self):
        self.write("tools/mau/gieo/App/B.swift", "struct B2 {}\n")       # đè file seed ⇒ vi phạm
        self.write("tools/mau/gieo/GIOI-THIEU.md", "# của app\n")        # đè file template_only ⇒ được
        self.write("tools/mau/gieo/tai-lieu/moi.md", "# mới\n")          # tạo file mới ⇒ được
        self.write(manifest.MANIFEST_FILE,
                   BASE_MANIFEST.replace('"GIOI-THIEU.md"]', '"GIOI-THIEU.md", "tools/mau/"]'))
        m = manifest.load(self.root)
        self.assertEqual(manifest.overlay_targets(self.root, m), ["App/B.swift", "GIOI-THIEU.md", "tai-lieu/moi.md"])
        problems = self.check()
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("tools/mau/gieo/App/B.swift", problems[0])
        self.assertIn("seed", problems[0])

    def test_chua_co_thu_muc_gieo_thi_khong_co_dich(self):
        m = manifest.load(self.root)
        self.assertEqual(manifest.overlay_targets(self.root, m), [])
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST.replace('overlay_dir = "tools/mau/gieo"\n', ""))
        self.assertEqual(manifest.overlay_targets(self.root, manifest.load(self.root)), [])
        self.assertEqual(self.check(), [])

    # ------------------------------------------------------------ luật (d)

    def test_file_dong_bo_tro_toi_file_chi_template_bi_bao(self):
        self.write("tai-lieu/kien-truc.md",
                   "# Kiến trúc\n"
                   "Xem `tai-lieu/rieng/ke-hoach.md` để biết lịch sử.\n"           # backtick ⇒ vi phạm
                   "Hay [kế hoạch](rieng/ke-hoach.md#muc).\n"                       # link tương đối ⇒ vi phạm
                   "Thư mục `tai-lieu/rieng/` chỉ ở template.\n"                    # thư mục ⇒ không tính
                   "Tên trần `ke-hoach.md` không resolve.\n"                        # tên trần ⇒ không tính
                   "Chạy `python3 GIOI-THIEU.md:12` cho vui.\n"                     # từ trong lệnh + hậu tố dòng
                   "Trạng thái: `../GIOI-THIEU.md`; còn `../../ngoai.md` thoát gốc.\n")  # backtick ../ từ thư mục file
        self.write("App/C.swift", "// đọc `tai-lieu/rieng/ke-hoach.md`\nstruct C {}\n")   # seed cũng soi
        self.write("tools/chung/run.sh", "#!/bin/bash\n# không backtick: tai-lieu/rieng/ke-hoach.md\n")
        self.write("tai-lieu/rieng/ke-hoach.md", "# kế hoạch\nnhắc `GIOI-THIEU.md` trong file chỉ-template: được\n")
        problems = self.check()
        self.assertEqual(sorted(problems), sorted([
            "App/C.swift:1: nhắc tai-lieu/rieng/ke-hoach.md — file lớp template_only, không có ở app",
            "tai-lieu/kien-truc.md:2: nhắc tai-lieu/rieng/ke-hoach.md — file lớp template_only, không có ở app",
            "tai-lieu/kien-truc.md:3: nhắc tai-lieu/rieng/ke-hoach.md — file lớp template_only, không có ở app",
            "tai-lieu/kien-truc.md:6: nhắc GIOI-THIEU.md — file lớp template_only, không có ở app",
            "tai-lieu/kien-truc.md:7: nhắc GIOI-THIEU.md — file lớp template_only, không có ở app",
        ]))
        self.assertEqual(self.run_cli("check").returncode, 1)

    def test_dich_cua_thu_muc_gieo_duoc_mien_luat_d(self):
        self.write("tai-lieu/kien-truc.md", "# Kiến trúc\nXem [giới thiệu](../GIOI-THIEU.md).\n")
        self.assertEqual(len(self.check()), 1)
        self.write("tools/mau/gieo/GIOI-THIEU.md", "# giới thiệu của app\n")
        self.write(manifest.MANIFEST_FILE,
                   BASE_MANIFEST.replace('"GIOI-THIEU.md"]', '"GIOI-THIEU.md", "tools/mau/"]'))
        self.assertEqual(self.check(), [])

    def test_file_nhi_phan_va_khong_utf8_bi_bo_qua(self):
        p = self.root / "Loi/anh.txt"
        p.write_bytes(b"`tai-lieu/rieng/ke-hoach.md`\xff\xfe\n")
        self.git("add", "Loi/anh.txt")
        q = self.root / "Loi/nhi-phan.json"
        q.write_bytes(b"\0`tai-lieu/rieng/ke-hoach.md`\n")
        self.git("add", "Loi/nhi-phan.json")
        self.assertEqual(self.check(), [])

    def test_file_khong_duoi_cung_duoc_soi(self):
        self.write(".githooks/pre-commit", "#!/bin/bash\n# xem `GIOI-THIEU.md`\n")
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST.replace('"Loi/", ', '"Loi/", ".githooks/", '))
        self.assertEqual(self.check(),
                         [".githooks/pre-commit:2: nhắc GIOI-THIEU.md — file lớp template_only, không có ở app"])

    # ------------------------------------------------------------ khối template: (luật d trên file seed, luật e)

    def test_khoi_template_khong_cap_bi_bao(self):
        self.write("App/GHI-CHU.md", "# App\n<!-- template:begin -->\nchỉ template\n")
        self.write("App/c.yml", "a: 1\n# template:end\n")
        self.write("tai-lieu/kien-truc.md", "# Kiến trúc\n<!-- template:begin -->\n")   # sync: luật e không soi
        problems = self.check()
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(problems[0].startswith("App/GHI-CHU.md:2: "), problems)
        self.assertIn("không có dấu đóng", problems[0])
        self.assertTrue(problems[1].startswith("App/c.yml:2: "), problems)
        self.assertIn("không cặp", problems[1])
        self.assertEqual(self.run_cli("check").returncode, 1)
        self.write("App/GHI-CHU.md", "# App\n<!-- template:begin -->\nchỉ template\n<!-- template:end -->\n")
        self.write("App/c.yml", "a: 1\n")
        self.assertEqual(self.check(), [])

    def test_file_seed_soi_sau_khi_cat_khoi_template_giu_so_dong(self):
        self.write("App/GHI-CHU.md", "# App\n"
                   "<!-- template:begin -->\n"
                   "Lịch sử: `tai-lieu/rieng/ke-hoach.md`.\n"        # trong khối template ⇒ app không nhận ⇒ được
                   "<!-- template:end -->\n"
                   "\n"
                   "Còn đây: `GIOI-THIEU.md`.\n")                     # ngoài khối ⇒ vi phạm, đúng dòng gốc 6
        self.assertEqual(self.check(),
                         ["App/GHI-CHU.md:6: nhắc GIOI-THIEU.md — file lớp template_only, không có ở app"])
        lines = manifest.seed_lines_in_app("App/GHI-CHU.md", (self.root / "App/GHI-CHU.md").read_text())
        self.assertEqual([no for no, _ in lines], [1, 5, 6])
        # File sync không có khái niệm khối template: ⇒ soi cả khối.
        self.write("tai-lieu/kien-truc.md", "<!-- template:begin -->\n`GIOI-THIEU.md`\n<!-- template:end -->\n")
        self.assertIn("tai-lieu/kien-truc.md:2: nhắc GIOI-THIEU.md — file lớp template_only, không có ở app",
                      self.check())

    # ------------------------------------------------------------ digest + list

    def test_digest_phan_biet_bit_thuc_thi(self):
        a = self.root / "a.sh"
        b = self.root / "b.sh"
        a.write_text("echo hi\n", encoding="utf-8")
        b.write_text("echo hi\n", encoding="utf-8")
        os.chmod(a, 0o644)
        os.chmod(b, 0o755)
        da, db = manifest.digest(a), manifest.digest(b)
        self.assertEqual(len(da), 64)
        self.assertEqual(db, da + "+x")
        self.assertEqual(da, hashlib.sha256(b"echo hi\n").hexdigest())
        # Chỉ bit thực thi của CHỦ tính (git chỉ ghi 100755/100644): bit nhóm/khác không đổi digest.
        os.chmod(b, 0o655)
        self.assertEqual(manifest.digest(b), da)
        os.chmod(b, 0o744)
        self.assertEqual(manifest.digest(b), da + "+x")
        b.write_text("echo ho\n", encoding="utf-8")
        self.assertNotEqual(manifest.digest(b)[:64], da)
        link = self.root / "lien-ket"
        link.symlink_to(a)
        with self.assertRaises(manifest.ManifestError):
            manifest.digest(link)

    def test_co_core_lock_thi_check_chi_nhac_va_rc_0(self):
        # Có core.lock ⇔ đây là app: cổng manifest không áp (mục template_only không khớp gì, file của app không lớp).
        self.write("tep moi/lạ.txt", "x\n")
        self.assertEqual(self.run_cli("check").returncode, 1, "tiền đề: ở template thì vi phạm")
        # core.lock LẠC (chưa track) ở template KHÔNG làm nó thành app — cổng vẫn chạy.
        self.write("core.lock", "{}\n", add=False)
        self.assertEqual(self.run_cli("check").returncode, 1)
        self.assertEqual(self.run_cli("is-app").returncode, 1)
        self.write("core.lock", "{}\n")          # track (stage) ⇒ app
        self.assertEqual(self.run_cli("is-app").stdout.strip(), "app")
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "manifest: đây là app — cổng manifest chỉ áp ở template; dùng "
                                           "tools/template/sync_core.py check")

    def test_staged_ton_trong_index_cua_hook(self):
        # Index tạm kiểu `git commit -a` (GIT_INDEX_FILE trong .git của repo) có file chưa phân lớp; .git/index thì không.
        tmp_index = self.root / ".git" / "index.thu"
        env = dict(clean_env(), GIT_INDEX_FILE=str(tmp_index))
        self.write("tep moi/lạ.txt", "x\n", add=False)
        subprocess.run(["git", "add", "-A"], cwd=self.root, env=env, check=True)
        self.assertEqual(self.check(), [])
        old = os.environ.get("GIT_INDEX_FILE")
        os.environ["GIT_INDEX_FILE"] = str(tmp_index)
        try:
            self.assertEqual(manifest.check(self.root), [], "không --staged ⇒ gỡ GIT_INDEX_FILE như mọi GIT_*")
            problems = manifest.check(self.root, staged=True)
        finally:
            if old is None:
                os.environ.pop("GIT_INDEX_FILE", None)
            else:
                os.environ["GIT_INDEX_FILE"] = old
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("tep moi/lạ.txt", problems[0])
        r = subprocess.run([sys.executable, str(SCRIPT), "check", "--staged", "--root", str(self.root)],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("tep moi/lạ.txt", r.stdout)
        # Index của repo KHÁC ⇒ rc 2 (không đoán index nào đang commit).
        other = Path(self._tmp.name) / "repo khác"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], env=clean_env(), check=True)
        r = subprocess.run([sys.executable, str(SCRIPT), "check", "--staged", "--root", str(self.root)],
                           env=dict(clean_env(), GIT_INDEX_FILE=str(other / ".git" / "index")),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("không thuộc repo", r.stderr)

    def test_tracked_va_list_theo_lop(self):
        self.write("App/tên có dấu cách.swift", "struct D {}\n")
        self.assertIn("App/tên có dấu cách.swift", manifest.tracked(self.root))
        r = self.run_cli("list", "seed")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["App/B.swift", "App/tên có dấu cách.swift", "cau-hinh.toml"])
        self.assertEqual(self.run_cli("list", "khong-co").returncode, 2)

    def test_changelog_thieu_tieu_muc_viec_tay_bi_bao(self):
        # CHANGELOG của template (template_only): "Chưa phát hành" và mọi bản từ v0.4.0 phải có tiểu mục việc tay;
        # v0.1.0–v0.3.0 được miễn; so phiên bản theo SỐ (v0.10.0 ≥ v0.4.0).
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST.replace('"GIOI-THIEU.md"]', '"GIOI-THIEU.md", "CHANGELOG.md"]'))
        tay = manifest.MANUAL_HEADING
        good = ("# Changelog\n\n## Chưa phát hành\n\n- việc mới\n\n" + tay + "\n\n- Không có.\n\n"
                "## v0.10.0 — 2026-12-01\n\n- x\n\n" + tay + "\n\n- chạy lệnh A\n\n"
                "## v0.4.0 — 2026-11-24\n\n" + tay + "\n\n- Không có.\n\n"
                "## v0.3.0 — 2026-11-23\n\n- cũ, miễn\n\n## v0.1.0 — 2026-11-21\n\n- cũ\n")
        self.write("CHANGELOG.md", good)
        self.assertEqual(self.check(), [])
        bad = good.replace("## v0.10.0 — 2026-12-01\n\n- x\n\n" + tay, "## v0.10.0 — 2026-12-01\n\n- x\n\n### Khác")
        self.write("CHANGELOG.md", bad)
        problems = self.check()
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(problems[0].startswith("CHANGELOG.md:11:"), problems)
        self.assertIn("v0.10.0", problems[0])
        self.write("CHANGELOG.md", good.replace(tay + "\n\n- Không có.\n\n## v0.10.0", "## v0.10.0", 1))
        problems = self.check()
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("Chưa phát hành", problems[0])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(tay, r.stdout)
        # CHANGELOG không thuộc template_only (vd release notes của app) ⇒ luật không áp.
        self.write(manifest.MANIFEST_FILE, BASE_MANIFEST.replace('"GIOI-THIEU.md"]', '"GIOI-THIEU.md", "CHANGELOG.md"]')
                   .replace('"cau-hinh.toml", "App/"]', '"cau-hinh.toml", "App/", "CHANGELOG.md"]')
                   .replace('"GIOI-THIEU.md", "CHANGELOG.md"]', '"GIOI-THIEU.md"]'))
        self.assertEqual(self.check(), [])


if __name__ == "__main__":
    unittest.main()
