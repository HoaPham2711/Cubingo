"""Test cho tools/template/sync_core.py — core.lock + cổng "file lớp đồng bộ không lệch".

Mỗi test dựng một repo git tạm (đường dẫn có dấu cách) đóng vai app: manifest + vài file sync/seed + file riêng của app,
`core.lock` dựng bằng `build_lock` trên chính cây đó. Mọi biến GIT_* bị gỡ khỏi env
(docs/lessons-learned/test-git-trong-hook-dung-repo-that.md). Không đụng cây thật, không dựa file chỉ-template.
"""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "sync_core.py"
sys.path.insert(0, str(HERE))
import manifest  # noqa: E402
import sync_core  # noqa: E402

MANIFEST = """\
schema = 1
[sync]
paths = ["Loi/", "tools/chung/", "template.manifest.toml"]
[seed]
paths = ["cau-hinh.toml", "App/"]
overlay_dir = "tools/mau/gieo"
[template_only]
paths = ["tools/mau/gieo/", "GIOI-THIEU.md"]
"""
FILES = {
    "Loi/A.swift": "struct A {}\n",
    "Loi/con/B.swift": "struct B {}\n",
    "tools/chung/chay.sh": "echo chạy\n",
    "cau-hinh.toml": "a = 1\n",
    "App/C.swift": "struct C {}\n",
    "GIOI-THIEU.md": "# giới thiệu template\n",
    "tools/mau/gieo/GIOI-THIEU.md": "# giới thiệu app\n",
}
COMMIT = "a" * 40
GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra)
    return env


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SyncCoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo có dấu cách"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        top = self.git("rev-parse", "--show-toplevel").stdout.strip()
        self.assertEqual(Path(top).resolve(), self.root.resolve(), "repo tạm phải là gốc, không phải repo thật")
        self.write(manifest.MANIFEST_FILE, MANIFEST)
        for rel, text in FILES.items():
            self.write(rel, text)
        os.chmod(self.root / "tools/chung/chay.sh", 0o755)
        # Test chạy được cả khi bị gọi từ trong một hook (GIT_INDEX_FILE của repo khác trong env).
        old_idx = os.environ.pop("GIT_INDEX_FILE", None)
        if old_idx is not None:
            self.addCleanup(os.environ.__setitem__, "GIT_INDEX_FILE", old_idx)
        self.git("add", "-A")                 # build_lock lấy danh sách file từ git (ls-files)
        self.lock = sync_core.build_lock(self.root, manifest.load(self.root), source="/duong dan/template",
                                         tag="v0.4.0", commit=COMMIT)
        sync_core.write_lock(self.root, self.lock)
        # File riêng của app (không thuộc lớp nào của template) — thêm SAU khi dựng lock.
        self.write("App/Rieng.swift", "struct Rieng {}\n")
        self.write("ghi-chu-app.md", "# riêng app\n")
        self.git("add", "-A")
        self.git(*GIT_ID, "commit", "-q", "-m", "app")

    def git(self, *args, env=None):
        return subprocess.run(["git", "--no-optional-locks", *args], cwd=self.root, env=env or clean_env(),
                              capture_output=True, text=True)

    def write(self, rel, text, newline=None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline=newline) as fh:
            fh.write(text)

    def cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--root", str(self.root)],
                              cwd=self._tmp.name, env=env or clean_env(), capture_output=True, text=True)

    def drift(self, **kw):
        return sync_core.drift(self.root, **kw)

    def raw_lock(self):
        return json.loads((self.root / sync_core.LOCK).read_text(encoding="utf-8"))

    def put_lock(self, data):
        (self.root / sync_core.LOCK).write_text(json.dumps(data), encoding="utf-8")

    # ------------------------------------------------------------ khớp / lệch

    def test_khop_thi_rc_0(self):
        self.assertEqual(self.drift(), [])
        self.assertEqual(self.drift(staged=True), [])
        r = self.cli("check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_sua_file_dong_bo_bi_bao_M(self):
        self.write("Loi/con/B.swift", "struct B { let x = 1 }\n")
        self.assertEqual(self.drift(), ["M Loi/con/B.swift"])
        r = self.cli("check")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["M Loi/con/B.swift"])

    def test_xoa_file_dong_bo_bi_bao_D(self):
        (self.root / "Loi/A.swift").unlink()
        self.assertEqual(self.drift(), ["D Loi/A.swift"])
        self.assertEqual(self.cli("check").returncode, 1)
        # Cả thư mục cha mất / thành file ⇒ vẫn là D, không traceback.
        (self.root / "Loi/con/B.swift").unlink()
        (self.root / "Loi/con").rmdir()
        self.write("Loi/con", "giờ là file\n")
        self.assertEqual(self.drift(), ["D Loi/A.swift", "D Loi/con/B.swift"])

    def test_doi_bit_thuc_thi_bi_bao(self):
        os.chmod(self.root / "tools/chung/chay.sh", 0o644)
        self.assertEqual(self.drift(), ["M tools/chung/chay.sh"])
        os.chmod(self.root / "tools/chung/chay.sh", 0o755)
        os.chmod(self.root / "Loi/A.swift", 0o744)       # chỉ bit của chủ là thứ git ghi
        self.assertEqual(self.drift(), ["M Loi/A.swift"])
        os.chmod(self.root / "Loi/A.swift", 0o655)       # bit nhóm/khác không tính
        self.assertEqual(self.drift(), [])
        # Index: chmod được stage ⇒ staged cũng thấy.
        os.chmod(self.root / "tools/chung/chay.sh", 0o644)
        self.git("add", "tools/chung/chay.sh")
        self.assertEqual(self.drift(staged=True), ["M tools/chung/chay.sh"])

    def test_file_rieng_cua_app_khong_bi_soi(self):
        self.write("App/Rieng.swift", "struct Rieng { let y = 2 }\n")
        self.write("App/C.swift", "struct C { /* app sửa file gieo */ }\n")
        self.write("cau-hinh.toml", "a = 2\n")
        self.write("moi-tinh.txt", "x\n")
        self.git("add", "-A")
        self.assertEqual(self.drift(), [])
        self.assertEqual(self.drift(staged=True), [])

    def test_staged_doc_tu_index_khong_doc_working_tree(self):
        # Index lệch, working tree khớp ⇒ staged báo; ngược lại thì không.
        self.write("Loi/A.swift", "struct A { lệch }\n")
        self.git("add", "Loi/A.swift")
        self.write("Loi/A.swift", FILES["Loi/A.swift"])
        self.assertEqual(self.drift(), [])
        self.assertEqual(self.drift(staged=True), ["M Loi/A.swift"])
        r = self.cli("check", "--staged")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("M Loi/A.swift", r.stdout)
        self.git("add", "Loi/A.swift")
        self.write("Loi/A.swift", "struct A { lệch nhưng chưa stage }\n")
        self.assertEqual(self.drift(staged=True), [])
        self.assertEqual(self.drift(), ["M Loi/A.swift"])
        # Xoá khỏi index (git rm --cached) ⇒ D ở staged dù file còn trên đĩa.
        self.write("Loi/A.swift", FILES["Loi/A.swift"])
        self.git("rm", "-q", "--cached", "Loi/A.swift")
        self.assertEqual(self.drift(staged=True), ["D Loi/A.swift"])

    def test_staged_doc_lock_tu_index(self):
        # Lệnh đồng bộ stage cả file mới lẫn lock mới ⇒ khớp; lock mới chỉ ở working tree ⇒ staged vẫn lệch.
        self.write("Loi/A.swift", "struct A { bản mới của template }\n")
        lock = sync_core.build_lock(self.root, manifest.load(self.root), source="x", tag="v0.5.0", commit="b" * 40)
        sync_core.write_lock(self.root, lock)
        self.git("add", "Loi/A.swift")
        self.assertEqual(self.drift(staged=True), ["M Loi/A.swift"])
        self.assertEqual(self.drift(), [])
        self.git("add", sync_core.LOCK)
        self.assertEqual(self.drift(staged=True), [])

    def test_staged_ton_trong_index_cua_hook(self):
        # Index tạm kiểu `git commit -a` (GIT_INDEX_FILE trong .git của repo) mang bản lệch; .git/index còn bản cũ.
        self.write("Loi/A.swift", "struct A { sửa tay }\n")
        tmp_index = self.root / ".git" / "index.thu"
        env = clean_env(GIT_INDEX_FILE=str(tmp_index))
        self.git("read-tree", "HEAD", env=env)
        self.git("add", "Loi/A.swift", env=env)
        self.assertEqual(self.drift(staged=True), [], "tiền đề: .git/index còn bản cũ")
        old = os.environ.get("GIT_INDEX_FILE")
        os.environ["GIT_INDEX_FILE"] = str(tmp_index)
        try:
            self.assertEqual(self.drift(staged=True), ["M Loi/A.swift"])
        finally:
            if old is None:
                os.environ.pop("GIT_INDEX_FILE", None)
            else:
                os.environ["GIT_INDEX_FILE"] = old
        r = self.cli("check", "--staged", env=clean_env(GIT_INDEX_FILE=str(tmp_index)))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        # Đường dẫn tương đối (commit thường: `.git/index`) tính từ cwd = gốc work tree.
        r = subprocess.run([sys.executable, str(SCRIPT), "check", "--staged", "--root", str(self.root)],
                           cwd=self.root, env=clean_env(GIT_INDEX_FILE=".git/index.thu"), capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_index_cua_repo_khac_rc_2(self):
        # GIT_INDEX_FILE trỏ index của repo KHÁC ⇒ không biết index nào đang commit ⇒ rc 2, không lặng lẽ đọc .git/index.
        other = Path(self._tmp.name) / "repo khác"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], env=clean_env(), check=True)
        (other / "x").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(other), "add", "x"], env=clean_env(), check=True)
        r = self.cli("check", "--staged", env=clean_env(GIT_INDEX_FILE=str(other / ".git" / "index")))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("không thuộc repo", r.stderr)
        # Working tree không đọc index ⇒ không bị ảnh hưởng.
        self.assertEqual(self.cli("check", env=clean_env(GIT_INDEX_FILE=str(other / ".git" / "index"))).returncode, 0)

    # ------------------------------------------------------------ không bị lừa

    def test_symlink_thay_file_dong_bo_bi_bao_M(self):
        target = self.root / "ghi-chu-app.md"
        (self.root / "Loi/A.swift").unlink()
        (self.root / "Loi/A.swift").symlink_to(target)
        self.assertEqual(self.drift(), ["M Loi/A.swift"])
        r = self.cli("check")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.git("add", "-A")
        self.assertEqual(self.drift(staged=True), ["M Loi/A.swift"])

    def test_thu_muc_cha_la_symlink_bi_bao_M(self):
        # Thư mục `Loi/con` thay bằng symlink tới bản chép y hệt ở ngoài ⇒ nội dung khớp nhưng không còn là file template.
        outside = Path(self._tmp.name) / "ngoai"
        outside.mkdir()
        (outside / "B.swift").write_text(FILES["Loi/con/B.swift"], encoding="utf-8")
        (self.root / "Loi/con/B.swift").unlink()
        (self.root / "Loi/con").rmdir()
        (self.root / "Loi/con").symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.drift(), ["M Loi/con/B.swift"])

    def test_file_dong_bo_thanh_thu_muc_bi_bao_M(self):
        (self.root / "Loi/A.swift").unlink()
        self.write("Loi/A.swift/ben-trong.swift", "x\n")
        self.assertEqual(self.drift(), ["M Loi/A.swift"])
        self.git("add", "-A")
        # File mới bên dưới nằm trong thư mục sync ⇒ thêm dòng A (track rồi nên working tree cũng thấy).
        self.assertEqual(self.drift(staged=True), ["M Loi/A.swift", "A Loi/A.swift/ben-trong.swift"])
        self.assertEqual(self.drift(), ["M Loi/A.swift", "A Loi/A.swift/ben-trong.swift"])

    def test_fifo_thay_file_dong_bo_bi_bao_M_khong_treo(self):
        # Mở FIFO để băm sẽ treo mãi — phải nhận ra "không phải file thường" trước khi mở.
        (self.root / "Loi/A.swift").unlink()
        os.mkfifo(self.root / "Loi/A.swift")
        r = subprocess.run([sys.executable, str(SCRIPT), "check", "--root", str(self.root)], cwd=self._tmp.name,
                           env=clean_env(), capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["M Loi/A.swift"])

    def test_crlf_khac_lf(self):
        self.write("Loi/A.swift", FILES["Loi/A.swift"].replace("\n", "\r\n"), newline="")
        self.assertEqual(self.drift(), ["M Loi/A.swift"])
        self.git("-c", "core.autocrlf=false", "add", "Loi/A.swift")
        self.assertEqual(self.drift(staged=True), ["M Loi/A.swift"])

    # ------------------------------------------------------------ lock hỏng

    def test_lock_hong_rc_2(self):
        (self.root / sync_core.LOCK).write_text("{ không phải json", encoding="utf-8")
        with self.assertRaises(sync_core.LockError):
            sync_core.read_lock(self.root)
        r = self.cli("check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("FAIL:", r.stderr)
        self.assertEqual(self.cli("status").returncode, 2)

    def test_lock_bi_xoa_nhung_con_track_rc_2_kem_lenh_khoi_phuc(self):
        # App xoá core.lock (đĩa) / gỡ khỏi index: vẫn là app (lock được track ở HEAD) ⇒ rc 2, không thành "template".
        (self.root / sync_core.LOCK).unlink()
        self.assertIsNone(sync_core.read_lock(self.root))
        self.assertTrue(sync_core.mf.is_app(self.root))
        with self.assertRaises(sync_core.LockError):
            self.drift()
        r = self.cli("check")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("git restore --staged --worktree core.lock", r.stderr)
        self.assertNotIn("đây là template", r.stderr)
        self.git("add", "-A")                    # = git rm core.lock
        r = self.cli("check", "--staged")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("git restore --staged --worktree core.lock", r.stderr)

    def test_khong_track_lock_la_template_rc_2(self):
        # Repo chưa từng track core.lock (template) ⇒ rc 2 "đây là template"; lock lạc chưa add cũng không làm nó thành app.
        fresh = Path(self._tmp.name) / "template có dấu cách"
        fresh.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(fresh)], env=clean_env(), check=True)
        (fresh / "a.txt").write_text("a\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(fresh), "add", "a.txt"], env=clean_env(), check=True)
        self.assertFalse(sync_core.mf.is_app(fresh))
        r = subprocess.run([sys.executable, str(SCRIPT), "check", "--root", str(fresh)], env=clean_env(),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("đây là template", r.stderr)
        (fresh / sync_core.LOCK).write_text("{}\n", encoding="utf-8")
        self.assertFalse(sync_core.mf.is_app(fresh))
        self.assertIsNone(sync_core.mf.is_app(Path(self._tmp.name)), "không phải repo git ⇒ None")

    def test_luoc_do_sai_bi_tu_choi(self):
        base = self.raw_lock()
        bad = []
        d = json.loads(json.dumps(base)); d["them"] = 1; bad.append(d)
        d = json.loads(json.dumps(base)); del d["seeded"]; bad.append(d)
        d = json.loads(json.dumps(base)); d["schema"] = 2; bad.append(d)
        d = json.loads(json.dumps(base)); d["schema"] = True; bad.append(d)
        d = json.loads(json.dumps(base)); d["template"]["tag"] = 4; bad.append(d)
        d = json.loads(json.dumps(base)); d["template"]["commit"] = "abc"; bad.append(d)
        d = json.loads(json.dumps(base)); d["template"]["x"] = "y"; bad.append(d)
        d = json.loads(json.dumps(base)); d["synced"] = []; bad.append(d)
        d = json.loads(json.dumps(base)); d["synced"]["Loi/A.swift"] = "khong-phai-digest"; bad.append(d)
        d = json.loads(json.dumps(base)); d["seeded"]["Loi/A.swift"] = base["synced"]["Loi/A.swift"]; bad.append(d)
        d = json.loads(json.dumps(base)); d["synced"]["../ngoai.txt"] = sha("x"); bad.append(d)
        d = json.loads(json.dumps(base)); d["synced"]["/etc/hosts"] = sha("x"); bad.append(d)
        d = json.loads(json.dumps(base)); d["synced"]["Loi/../../x"] = sha("x"); bad.append(d)
        d = json.loads(json.dumps(base)); d["synced"]["Loi//A.swift"] = sha("x"); bad.append(d)
        d = json.loads(json.dumps(base)); d["seeded"]["core.lock"] = sha("x"); bad.append(d)
        for data in bad:
            with self.subTest(data=data):
                self.put_lock(data)
                with self.assertRaises(sync_core.LockError):
                    sync_core.read_lock(self.root)
                self.assertEqual(self.cli("check").returncode, 2)
        with self.assertRaises(sync_core.LockError):
            sync_core.write_lock(self.root, bad[10])
        # tag null hợp lệ (tạo app từ commit không tag).
        d = json.loads(json.dumps(base)); d["template"]["tag"] = None
        self.put_lock(d)
        self.assertEqual(sync_core.read_lock(self.root)["template"]["tag"], None)

    def test_lock_la_symlink_bi_tu_choi(self):
        real = self.root / "lock-that.json"
        (self.root / sync_core.LOCK).rename(real)
        (self.root / sync_core.LOCK).symlink_to(real)
        with self.assertRaises(sync_core.LockError):
            sync_core.read_lock(self.root)
        with self.assertRaises(sync_core.LockError):
            sync_core.write_lock(self.root, self.lock)

    # ------------------------------------------------------------ build_lock + status

    def test_build_lock_on_dinh(self):
        m = manifest.load(self.root)
        a = sync_core.build_lock(self.root, m, source="nguồn", tag="v0.4.0", commit=COMMIT)
        b = sync_core.build_lock(self.root, m, source="nguồn", tag="v0.4.0", commit=COMMIT)
        self.assertEqual(sync_core.lock_text(a).encode(), sync_core.lock_text(b).encode())
        text = (self.root / sync_core.LOCK).read_text(encoding="utf-8")
        self.assertEqual(text, sync_core.lock_text(self.lock))
        self.assertTrue(text.endswith("}\n"))
        self.assertIn('\n  "schema": 1', text)
        self.assertIn("/duong dan/template", text)
        # Không thoát ký tự không-ASCII.
        lock = dict(a, template=dict(a["template"], source="/thư mục/template"))
        self.assertIn("/thư mục/template", sync_core.lock_text(lock))
        self.assertEqual(list(json.loads(text)), sorted(json.loads(text)))

    def test_build_lock_noi_dung(self):
        L = self.lock
        self.assertEqual(sorted(L["synced"]), ["Loi/A.swift", "Loi/con/B.swift", "template.manifest.toml",
                                               "tools/chung/chay.sh"])
        self.assertEqual(L["synced"]["Loi/A.swift"], sha(FILES["Loi/A.swift"]))
        self.assertEqual(L["synced"]["tools/chung/chay.sh"], sha(FILES["tools/chung/chay.sh"]) + "+x")
        # seeded: file seed nguyên bản + đích của thư mục gieo mang digest của FILE TRONG THƯ MỤC GIEO.
        self.assertEqual(sorted(L["seeded"]), ["App/C.swift", "GIOI-THIEU.md", "cau-hinh.toml"])
        self.assertEqual(L["seeded"]["GIOI-THIEU.md"], sha(FILES["tools/mau/gieo/GIOI-THIEU.md"]))
        self.assertEqual(L["template"], {"source": "/duong dan/template", "tag": "v0.4.0", "commit": COMMIT})
        # File lớp sync là symlink ⇒ từ chối dựng.
        (self.root / "Loi/L.swift").symlink_to(self.root / "Loi/A.swift")
        self.git("add", "Loi/L.swift")
        with self.assertRaises(sync_core.LockError):
            sync_core.build_lock(self.root, manifest.load(self.root), source="x", tag=None, commit=COMMIT)

    def test_build_lock_lay_danh_sach_tu_git(self):
        # File bị ignore dưới thư mục sync (__pycache__, .DS_Store) KHÔNG bị ghim khi danh sách từ git; cây thường thì có.
        self.write(".gitignore", "__pycache__/\n.DS_Store\n")
        self.write("Loi/__pycache__/m.pyc", "rác\n")
        self.write("Loi/.DS_Store", "rác\n")
        self.git("add", "-A")
        m = manifest.load(self.root)
        lock = sync_core.build_lock(self.root, m, source="x", tag=None, commit=COMMIT)
        self.assertNotIn("Loi/__pycache__/m.pyc", lock["synced"])
        self.assertNotIn("Loi/.DS_Store", lock["synced"])
        sync_core.write_lock(self.root, lock)
        self.git("add", sync_core.LOCK)
        self.assertEqual(self.drift(staged=True), [])
        self.assertEqual(self.drift(), [])
        # `files=` ⇒ đúng danh sách đó (không đi đĩa, không ls-files).
        lock = sync_core.build_lock(self.root, m, source="x", tag=None, commit=COMMIT,
                                    files=["Loi/A.swift", "App/C.swift", "ghi-chu-app.md"])
        self.assertEqual(list(lock["synced"]), ["Loi/A.swift"])
        self.assertEqual(list(lock["seeded"]), ["App/C.swift"])
        with self.assertRaises(sync_core.LockError):
            sync_core.build_lock(self.root, m, source="x", tag=None, commit=COMMIT, files=["../ngoai.txt"])
        with self.assertRaises(sync_core.LockError):
            sync_core.build_lock(self.root, m, source="x", tag=None, commit=COMMIT, files=["Loi/khong-co.swift"])

    def test_ten_nfd_tren_dia_ghim_theo_ten_nfc_cua_git(self):
        import unicodedata
        nfc = "Loi/Tính.swift"
        nfd = unicodedata.normalize("NFD", nfc)
        self.assertNotEqual(nfc, nfd)
        (self.root / nfd).write_text("struct T {}\n", encoding="utf-8")
        on_disk = [n for n in os.listdir(self.root / "Loi") if n.endswith(".swift") and n.startswith("T")]
        if on_disk != [unicodedata.normalize("NFD", "Tính.swift")]:
            self.skipTest(f"ổ đĩa chuẩn hoá tên ({on_disk!r}) — không dựng được ca NFD")
        self.git("-c", "core.precomposeunicode=true", "add", "-A")
        names = self.git("-c", "core.quotePath=false", "ls-files", "Loi").stdout.splitlines()
        self.assertIn(nfc, names, "tiền đề: git lưu tên NFC")
        lock = sync_core.build_lock(self.root, manifest.load(self.root), source="x", tag=None, commit=COMMIT)
        self.assertIn(nfc, lock["synced"])
        self.assertNotIn(nfd, lock["synced"])
        sync_core.write_lock(self.root, lock)
        self.git("add", sync_core.LOCK)
        self.assertEqual(self.drift(staged=True), [])
        self.assertEqual(self.drift(), [])

    # ------------------------------------------------------------ luật A (file mới trong thư mục sync)

    def test_file_moi_trong_thu_muc_dong_bo_bi_bao_A(self):
        self.write("Loi/Moi.swift", "extension A {}\n")
        self.write("tools/chung/them.py", "x = 1\n")
        # Chưa add: không phải file track ⇒ cả hai chế độ không tính (git là nguồn sự thật).
        self.assertEqual(self.drift(), [])
        self.assertEqual(self.drift(staged=True), [])
        self.git("add", "Loi/Moi.swift", "tools/chung/them.py")
        want = ["A Loi/Moi.swift", "A tools/chung/them.py"]
        self.assertEqual(self.drift(staged=True), want)
        self.assertEqual(self.drift(), want)
        r = self.cli("check", "--staged")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines(), want)

    def test_file_moi_cua_app_ngoai_thu_muc_dong_bo_khong_bi_bao(self):
        # Lớp seed (App/), file không lớp (tools/app/…), và mục harness khai TỪNG FILE: agent/skill mới của app là của app.
        text = MANIFEST.replace('"tools/chung/", ', '"tools/chung/", ".claude/agents/goc.md", ".claude/skills/goc/", ')
        self.write(manifest.MANIFEST_FILE, text)
        self.write(".claude/agents/goc.md", "# gốc\n")
        self.write(".claude/skills/goc/SKILL.md", "# gốc\n")
        self.git("add", "-A")
        lock = sync_core.build_lock(self.root, manifest.load(self.root), source="x", tag=None, commit=COMMIT)
        sync_core.write_lock(self.root, lock)
        self.git("add", "-A")
        self.write("App/Moi.swift", "struct M {}\n")
        self.write("tools/app/cong-cu.py", "x = 1\n")
        self.write(".claude/agents/my-app-agent.md", "# app\n")
        self.write(".claude/skills/my-skill/SKILL.md", "# app\n")
        self.git("add", "-A")
        self.assertEqual(self.drift(staged=True), [])
        self.assertEqual(self.drift(), [])
        # Đối chứng: file mới trong skill của template thì bị báo.
        self.write(".claude/skills/goc/them.md", "# lén\n")
        self.git("add", "-A")
        self.assertEqual(self.drift(staged=True), ["A .claude/skills/goc/them.md"])

    def test_status_in_tag_commit_nguon(self):
        r = self.cli("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("v0.4.0", r.stdout)
        self.assertIn(COMMIT, r.stdout)
        self.assertIn("/duong dan/template", r.stdout)
        self.assertIn("file đồng bộ: 4", r.stdout)
        self.assertIn("file gieo: 3", r.stdout)


# ====================================================================== sync --to <tag>

TAY = "### Việc phải làm tay khi lên bản này"
T_MANIFEST = """\
schema = 1
[sync]
paths = ["Loi/", "tools/common/", "tools/template/manifest.py", "tools/template/blocks.py",
         "tools/template/sync_core.py", ".githooks/", "docs/bai-hoc/", "template.manifest.toml"]
[seed]
paths = ["app.config.toml", "AppHost/", ".gitignore", "docs/bai-hoc/app/"]
overlay_dir = "tools/template/seed"
[template_only]
paths = ["CHANGELOG.md", "README.md", "tools/template/new_app.py", "tools/template/seed/"]
"""
T_CONFIG = """\
[app]
slug = "sample"
display_name = "Sample"
display_name_internal = "Sample Dev"

[bundle]
store = "com.example.sample"
internal = "com.example.sample.internal"

[apple]
team_id = "0000000000"

[version]
marketing = "0.1.0"
build = "1"
"""
T_FILES = {
    "Loi/A.txt": "struct A {}\n",
    "Loi/Cu.txt": "struct Cu {}\n",
    "Loi/con/B.txt": "struct B {}\n",
    "Loi/Mau.txt": "struct Mau {}\n",
    "Loi/chay.sh": "echo chạy\n",
    "docs/bai-hoc/mot.md": "# bài học một\n",
    "docs/bai-hoc/app/README.md": "# bài học của app\n",
    "AppHost/App.txt": "struct App {}\n",
    "app.config.toml": T_CONFIG,
    ".gitignore": ".temp/\n__pycache__/\n",
    "README.md": "# README của TEMPLATE\n",
    "CHANGELOG.md": "# Changelog\n\n## v1.0.0 — 2026-11-01\n\n- đầu tiên\n\n" + TAY + "\n\n- Không có.\n",
    "tools/template/new_app.py": "# dấu nhận diện template (giả)\n",
    "tools/template/seed/README.md": "# README của APP\n",
    "tools/template/seed/CHANGELOG.md": "# Changelog của app\n",
}
# Bản chép tool THẬT (đều lớp sync ⇒ có trong app sinh ra — test chạy được trong app, A5).
T_COPIES = ("tools/template/manifest.py", "tools/template/blocks.py", "tools/template/sync_core.py",
            "tools/common/appconfig.py", "tools/common/lint_identity.py", ".githooks/pre-commit")


class SyncTests(unittest.TestCase):
    """`sync --to <tag>` trên hai repo git cục bộ: TEMPLATE giả (tag v1.0.0, mỗi test tự ra v1.1.0) và APP sinh từ v1.0.0
    bằng đúng phần tối thiểu new_app làm (xuất, gieo đè, bỏ template_only, ghi lock, git init, commit)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name) / "khu đồng bộ có dấu cách"
        self.base.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        (self.home / ".gitconfig").write_text(
            "[user]\n\tname = Test\n\temail = test@example.com\n[commit]\n\tgpgsign = false\n"
            # Git >= 2.5x tự repack NỀN sau commit nhiều object ⇒ đua với lúc dọn thư mục tạm (xem test_new_app).
            "[maintenance]\n\tauto = false\n[gc]\n\tauto = 0\n", encoding="utf-8")
        old_idx = os.environ.pop("GIT_INDEX_FILE", None)
        if old_idx is not None:
            self.addCleanup(os.environ.__setitem__, "GIT_INDEX_FILE", old_idx)
        self.tpl = self.base / "template giả"
        self.tpl.mkdir()
        self.git(self.tpl, "init", "-q", "-b", "main")
        self.assertEqual(Path(self.git(self.tpl, "rev-parse", "--show-toplevel").stdout.strip()).resolve(),
                         self.tpl.resolve(), "template giả phải là gốc repo, không phải repo thật")
        self.twrite("template.manifest.toml", T_MANIFEST)
        for rel, text in T_FILES.items():
            self.twrite(rel, text)
        for rel in T_COPIES:
            dst = self.tpl / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE.parents[1] / rel, dst)
        r = subprocess.run([sys.executable, str(self.tpl / "tools/common/appconfig.py"), "render"], cwd=self.tpl,
                           env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.tcommit("v1.0.0", tag="v1.0.0")
        self.app = self.make_app("v1.0.0")

    # ------------------------------------------------------------ tiện ích

    def env(self):
        env = clean_env(HOME=str(self.home))
        env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
        return env

    def git(self, cwd, *args):
        return subprocess.run(["git", "--no-optional-locks", *args], cwd=cwd, env=self.env(), capture_output=True,
                              text=True)

    def twrite(self, rel, text, root=None):
        p = (root or self.tpl) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def tcommit(self, msg, tag=None, root=None):
        root = root or self.tpl
        self.git(root, "add", "-A")
        r = self.git(root, "commit", "-q", "-m", msg)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        if tag:
            self.assertEqual(self.git(root, "tag", tag).returncode, 0)

    def make_app(self, tag):
        app = self.base / "app có dấu cách"
        app.mkdir()
        names = [n for n in self.git(self.tpl, "ls-tree", "-r", "-z", "--name-only", tag).stdout.split("\0") if n]
        commit = self.git(self.tpl, "rev-parse", f"{tag}^{{commit}}").stdout.strip()
        archive = subprocess.run(["git", "-C", str(self.tpl), "archive", "--format=tar", tag], env=self.env(),
                                 capture_output=True, check=True)
        subprocess.run(["tar", "-xf", "-", "-C", str(app)], input=archive.stdout, check=True)
        m = manifest.load(app)
        lock = sync_core.build_lock(app, m, source=str(self.tpl), tag=tag, commit=commit, files=names)
        prefix = m["seed"]["overlay_dir"] + "/"
        targets = [n[len(prefix):] for n in names if n.startswith(prefix)]
        for t in targets:
            shutil.copy2(app / (prefix + t), app / t)
        for n in names:
            if n not in targets and manifest.classify(m, n) == "template_only":
                (app / n).unlink()
        for dirpath, _, _ in sorted(os.walk(app), key=lambda t: -len(t[0])):
            if Path(dirpath) != app and not os.listdir(dirpath):
                os.rmdir(dirpath)
        sync_core.write_lock(app, lock)
        self.git(app, "init", "-q", "-b", "main")
        self.tcommit("app mới", root=app)
        return app

    def release(self, tag="v1.1.0", steps="- Không có.", write=None, delete=(), chmod=None, manifest_text=None,
                moves=()):
        for rel in delete:              # xoá trước: file ↔ thư mục cần chỗ trống
            (self.tpl / rel).unlink()
            parent = (self.tpl / rel).parent
            while parent != self.tpl and not os.listdir(parent):
                parent.rmdir()
                parent = parent.parent
        for rel, text in (write or {}).items():
            self.twrite(rel, text)
        for src, dst in moves:
            (self.tpl / dst).parent.mkdir(parents=True, exist_ok=True)
            self.assertEqual(self.git(self.tpl, "mv", src, dst).returncode, 0)
        for rel, mode in (chmod or {}).items():
            os.chmod(self.tpl / rel, mode)
        if manifest_text is not None:
            self.twrite("template.manifest.toml", manifest_text)
        cl = (self.tpl / "CHANGELOG.md").read_text(encoding="utf-8")
        cl = cl.replace("# Changelog\n\n", f"# Changelog\n\n## {tag} — 2026-12-01\n\n- bản {tag}\n\n{TAY}\n\n{steps}\n\n", 1)
        self.twrite("CHANGELOG.md", cl)
        self.tcommit(tag, tag=tag)
        return self.git(self.tpl, "rev-parse", f"{tag}^{{commit}}").stdout.strip()

    def sync(self, *args):
        """Chạy bản sync_core.py CỦA APP (như người dùng thật; gốc suy từ vị trí script)."""
        return subprocess.run([sys.executable, str(self.app / "tools/template/sync_core.py"), "sync", *args],
                              cwd=self.base, env=self.env(), capture_output=True, text=True)

    def check_app(self, *extra):
        return subprocess.run([sys.executable, str(self.app / "tools/template/sync_core.py"), "check", *extra],
                              cwd=self.app, env=self.env(), capture_output=True, text=True)

    def lock(self):
        return json.loads((self.app / sync_core.LOCK).read_text(encoding="utf-8"))

    def read(self, rel):
        return (self.app / rel).read_text(encoding="utf-8")

    def snap(self):
        """Mọi file của app (trừ .git, .temp, __pycache__) → (bytes, mode) + git status — để khẳng định "không ghi gì".
        __pycache__ bị bỏ: chạy tool trong app ghi bytecode cạnh nguồn (git bỏ qua theo .gitignore), không phải thay đổi."""
        out = {}
        for dirpath, dirnames, filenames in os.walk(self.app):
            if Path(dirpath) == self.app:
                dirnames[:] = [d for d in dirnames if d not in (".git", ".temp")]
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for n in filenames:
                p = Path(dirpath) / n
                out[str(p.relative_to(self.app))] = (p.read_bytes(), os.lstat(p).st_mode)
        out["<status>"] = self.git(self.app, "status", "--porcelain").stdout
        return out

    def assert_no_leftovers(self):
        work = self.app / sync_core.WORK_DIR
        if work.is_dir():
            left = [n for n in os.listdir(work) if n.startswith((".fetch-", ".staging-"))]
            self.assertEqual(left, [], "thư mục tạm của lệnh đồng bộ phải được dọn")

    def assert_clean_after_add(self):
        self.assertEqual(self.check_app().returncode, 0, self.check_app().stdout)
        self.git(self.app, "add", "-A")
        r = self.check_app("--staged")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def assert_ok(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def assert_refused_nothing_written(self, r, before, rc=1):
        self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(self.snap(), before, "bị từ chối nhưng app đã đổi")
        self.assert_no_leftovers()

    # ------------------------------------------------------------ thêm / sửa / xoá / đổi tên

    def test_file_loi_doi_thi_ve_app_va_lock_doi(self):
        new_sync_core = (self.tpl / "tools/template/sync_core.py").read_text(encoding="utf-8") + "# bản v1.1.0\n"
        commit = self.release(write={"Loi/A.txt": "struct A { let moi = 1 }\n",
                                     "tools/template/sync_core.py": new_sync_core},
                              steps="- Chạy lệnh X sau khi đồng bộ.")
        app_config = self.read("app.config.toml")
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertEqual(self.read("Loi/A.txt"), "struct A { let moi = 1 }\n")
        self.assertTrue(self.read("tools/template/sync_core.py").endswith("# bản v1.1.0\n"),
                        "tool thay được chính file nguồn của nó")
        lock = self.lock()
        self.assertEqual(lock["template"], {"source": str(self.tpl), "tag": "v1.1.0", "commit": commit})
        self.assertEqual(lock["synced"]["Loi/A.txt"], sha("struct A { let moi = 1 }\n"))
        self.assertEqual(self.read("app.config.toml"), app_config)
        for want in ("v1.0.0 → v1.1.0", "~ Loi/A.txt", "2 sửa", "Chạy lệnh X sau khi đồng bộ.",
                     "appconfig.py render", "xcodegen generate", "run_tests.py --full",
                     "chore(core): đồng bộ lõi v1.0.0 → v1.1.0"):
            self.assertIn(want, r.stdout)
        self.assertNotIn("v1.0.0:\n", r.stdout, "việc tay của bản cũ (≤ bản đang đứng) không được in lại")
        self.assert_no_leftovers()
        self.assert_clean_after_add()

    def test_file_them_moi_va_file_bi_xoa(self):
        self.release(write={"Loi/Moi.txt": "struct Moi {}\n", "docs/bai-hoc/hai.md": "# hai\n"},
                     delete=["Loi/Cu.txt"])
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertEqual(self.read("Loi/Moi.txt"), "struct Moi {}\n")
        self.assertEqual(self.read("docs/bai-hoc/hai.md"), "# hai\n")
        self.assertFalse(os.path.lexists(self.app / "Loi/Cu.txt"))
        lock = self.lock()
        self.assertIn("Loi/Moi.txt", lock["synced"])
        self.assertNotIn("Loi/Cu.txt", lock["synced"])
        self.assertIn("+ Loi/Moi.txt", r.stdout)
        self.assertIn("- Loi/Cu.txt", r.stdout)
        self.assertIn("2 thêm, 0 sửa, 1 xoá", r.stdout)
        self.assert_clean_after_add()

    def test_file_doi_ten_khong_de_lai_mo_coi(self):
        self.release(moves=[("Loi/con/B.txt", "Loi/khac/B.txt")])
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertEqual(self.read("Loi/khac/B.txt"), T_FILES["Loi/con/B.txt"])
        self.assertFalse(os.path.lexists(self.app / "Loi/con/B.txt"))
        self.assertFalse(os.path.lexists(self.app / "Loi/con"), "thư mục rỗng do xoá để lại phải được dọn")
        self.assertNotIn("Loi/con/B.txt", self.lock()["synced"])
        self.assert_clean_after_add()

    def test_file_chuyen_sang_lop_gieo_duoc_giu_va_bao(self):
        self.release(manifest_text=T_MANIFEST.replace('"AppHost/", ', '"AppHost/", "Loi/Mau.txt", '))
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertEqual(self.read("Loi/Mau.txt"), T_FILES["Loi/Mau.txt"])
        lock = self.lock()
        self.assertNotIn("Loi/Mau.txt", lock["synced"])
        self.assertIn("Loi/Mau.txt", lock["seeded"])
        self.assertIn("> Loi/Mau.txt", r.stdout)
        self.assertIn("nay do app sở hữu", r.stdout)
        self.assertNotIn("* Loi/Mau.txt", r.stdout, "nội dung không đổi ⇒ không phải 'file gieo đổi'")
        self.assert_clean_after_add()
        # Từ nay app sửa được file đó.
        self.twrite("Loi/Mau.txt", "struct Mau { let cuaApp = 1 }\n", root=self.app)
        self.assert_clean_after_add()

    def test_xoa_khong_dung_file_cua_app_trong_thu_muc_gieo_long(self):
        # docs/bai-hoc/ là sync, docs/bai-hoc/app/ là seed (dài nhất thắng). Template xoá bài học duy nhất của nó ⇒
        # chỉ file ĐÃ GHIM bị xoá; file của app trong thư mục con seed còn nguyên.
        self.twrite("docs/bai-hoc/app/rieng.md", "# bài học riêng của app\n", root=self.app)
        self.tcommit("bài học riêng", root=self.app)
        self.release(delete=["docs/bai-hoc/mot.md"])
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertFalse(os.path.lexists(self.app / "docs/bai-hoc/mot.md"))
        self.assertEqual(self.read("docs/bai-hoc/app/rieng.md"), "# bài học riêng của app\n")
        self.assertEqual(self.read("docs/bai-hoc/app/README.md"), T_FILES["docs/bai-hoc/app/README.md"])
        self.assertIn("- docs/bai-hoc/mot.md", r.stdout)
        self.assertNotIn("rieng.md", r.stdout)
        self.assert_clean_after_add()

    # ------------------------------------------------------------ từ chối, không ghi gì

    def test_app_co_file_rieng_trung_duong_dan_bi_tu_choi_khong_ghi(self):
        self.twrite("TienIch/Rieng.txt", "struct RiengCuaApp {}\n", root=self.app)
        self.tcommit("file của app", root=self.app)
        self.release(write={"TienIch/Rieng.txt": "struct CuaTemplate {}\n", "Loi/A.txt": "struct A { v2 }\n"},
                     manifest_text=T_MANIFEST.replace('["Loi/", ', '["Loi/", "TienIch/", '))
        before = self.snap()
        r = self.sync("--to", "v1.1.0")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("TienIch/Rieng.txt", r.stderr)

    def test_app_co_file_khac_trong_thu_muc_template_moi_so_huu_bi_tu_choi_khong_ghi(self):
        # Không trùng đường dẫn: app có tools/x/khac.py, bản mới xếp "tools/x/" lớp sync và chỉ ship tools/x/mytool.py.
        # Đồng bộ mà qua thì `check` báo `A tools/x/khac.py` và hook chặn đúng commit lệnh đồng bộ bảo làm.
        self.twrite("tools/x/khac.py", "# tool riêng của app\n", root=self.app)
        self.tcommit("tool riêng", root=self.app)
        self.release(write={"tools/x/mytool.py": "# tool của template\n"},
                     manifest_text=T_MANIFEST.replace('["Loi/", ', '["Loi/", "tools/x/", '))
        lock_before = self.read(sync_core.LOCK)
        before = self.snap()
        r = self.sync("--to", "v1.1.0")
        self.assert_refused_nothing_written(r, before)
        self.assertEqual(self.read(sync_core.LOCK), lock_before)
        self.assertIn("tools/x/khac.py", r.stderr)
        self.assertIn("thư mục mà ở v1.1.0 template sở hữu", r.stderr)
        self.assertNotIn("tools/x/mytool.py", r.stderr)
        # App chuyển file của nó ra chỗ app sở hữu ⇒ cùng lệnh đồng bộ qua, check / check --staged sạch.
        (self.app / "AppHost/tools").mkdir(parents=True)
        self.assertEqual(self.git(self.app, "mv", "tools/x/khac.py", "AppHost/tools/khac.py").returncode, 0)
        self.tcommit("chuyển tool riêng", root=self.app)
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertEqual(self.read("tools/x/mytool.py"), "# tool của template\n")
        self.assert_clean_after_add()

    def test_cay_ban_bi_tu_choi(self):
        self.release(write={"Loi/A.txt": "struct A { v2 }\n"})
        self.twrite("AppHost/App.txt", "struct App { chưa commit }\n", root=self.app)
        before = self.snap()
        r = self.sync("--to", "v1.1.0")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("chưa sạch", r.stderr)
        self.git(self.app, "restore", "AppHost/App.txt")
        self.twrite("ghi-chu-chua-add.txt", "x\n", root=self.app)
        before = self.snap()
        self.assert_refused_nothing_written(self.sync("--to", "v1.1.0"), before)

    def test_loi_da_bi_sua_tay_bi_tu_choi(self):
        self.twrite("Loi/A.txt", "struct A { sửa tay }\n", root=self.app)
        self.tcommit("sửa tay lõi (repo thử chưa bật hook)", root=self.app)
        self.release(write={"Loi/con/B.txt": "struct B { v2 }\n"})
        before = self.snap()
        r = self.sync("--to", "v1.1.0")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("M Loi/A.txt", r.stderr)

    def test_manifest_moi_tool_cu_khong_doc_duoc_chay_tool_ban_moi_voi_root(self):
        # Bản mới: manifest.py nhận thêm khoá `ghi_chu` ở [template_only] và manifest dùng nó ⇒ manifest.py CŨ của app
        # từ chối. Tool cũ từ chối trước khi ghi và in lệnh `--root`; chính lệnh in ra chạy được tới cuối.
        mpy = (self.tpl / "tools/template/manifest.py").read_text(encoding="utf-8")
        new_mpy = mpy.replace('"template_only": {"paths"}}', '"template_only": {"paths", "ghi_chu"}}')
        self.assertNotEqual(new_mpy, mpy)
        self.release(write={"tools/template/manifest.py": new_mpy, "Loi/A.txt": "struct A { v2 }\n"},
                     manifest_text=T_MANIFEST.replace('[template_only]\n', '[template_only]\nghi_chu = "mới"\n'))
        before = self.snap()
        r = self.sync("--to", "v1.1.0")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("không dùng được", r.stderr)
        cmds = [ln.strip() for ln in r.stderr.splitlines() if ln.strip().startswith("python3 ")]
        self.assertEqual(len(cmds), 1, r.stderr)
        argv = shlex.split(cmds[0])
        self.assertEqual(argv[1:], [str(self.tpl / "tools/template/sync_core.py"), "sync", "--root",
                                    os.path.realpath(self.app), "--to", "v1.1.0", "--source", str(self.tpl)])
        r2 = subprocess.run([sys.executable, *argv[1:]], cwd=self.base, env=self.env(), capture_output=True, text=True)
        self.assert_ok(r2)
        self.assertEqual(self.read("tools/template/manifest.py"), new_mpy)
        self.assertEqual(self.read("Loi/A.txt"), "struct A { v2 }\n")
        self.assertEqual(self.lock()["template"]["tag"], "v1.1.0")
        self.assert_clean_after_add()

    def test_luoc_do_lock_moi_hon_bi_tu_choi_truoc_khi_ghi(self):
        spy = (self.tpl / "tools/template/sync_core.py").read_text(encoding="utf-8")
        new_spy = spy.replace("\nSCHEMA = 1\n", "\nSCHEMA = 2\n", 1)
        self.assertNotEqual(new_spy, spy)
        self.release(write={"tools/template/sync_core.py": new_spy})
        before = self.snap()
        r = self.sync("--to", "v1.1.0")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("lược đồ 2", r.stderr)
        self.assertIn("--root", r.stderr)

    def test_tag_khong_co_rc_1_khong_ghi(self):
        before = self.snap()
        r = self.sync("--to", "v9.9.9")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("v9.9.9", r.stderr)
        self.assert_refused_nothing_written(self.sync("--to", "--x"), before, rc=2)

    def test_nguon_khong_doc_duoc_rc_1(self):
        self.release(write={"Loi/A.txt": "struct A { v2 }\n"})
        before = self.snap()
        r = self.sync("--to", "v1.1.0", "--source", str(self.base / "không có"))
        self.assert_refused_nothing_written(r, before)
        plain = self.base / "thư mục thường"
        plain.mkdir()
        r = self.sync("--to", "v1.1.0", "--source", str(plain))
        self.assert_refused_nothing_written(r, before)
        self.assertIn("không phải repo git", r.stderr)
        r = self.sync("--to", "v1.1.0", "--source", "file://" + str(self.base / "không có"))
        self.assert_refused_nothing_written(r, before)
        # Nguồn trong lock (mặc định) đã mất.
        self.tpl.rename(self.base / "template đã dời")
        self.assert_refused_nothing_written(self.sync("--to", "v1.1.0"), before)

    def test_nguon_url_file_va_lock_giu_nguon_cu(self):
        commit = self.release(write={"Loi/A.txt": "struct A { v2 }\n"})
        r = self.sync("--to", "v1.1.0", "--source", self.tpl.as_uri())
        self.assert_ok(r)
        self.assertEqual(self.read("Loi/A.txt"), "struct A { v2 }\n")
        self.assertEqual(self.lock()["template"], {"source": str(self.tpl), "tag": "v1.1.0", "commit": commit})
        self.assert_clean_after_add()

    def test_chay_o_template_hoac_repo_khong_lock_rc_2(self):
        r = subprocess.run([sys.executable, str(self.tpl / "tools/template/sync_core.py"), "sync", "--to", "v1.0.0"],
                           cwd=self.base, env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("TEMPLATE", r.stderr)
        self.assertEqual(self.git(self.tpl, "status", "--porcelain").stdout, "", "template không bị ghi gì")
        other = self.base / "repo không lock"
        other.mkdir()
        self.git(other, "init", "-q")
        self.twrite("a.txt", "a\n", root=other)
        self.tcommit("a", root=other)
        r = subprocess.run([sys.executable, str(SCRIPT), "sync", "--to", "v1.0.0", "--root", str(other)],
                           env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def sync_failing_at(self, n, *extra, only=None):
        """Chạy sync trong tiến trình, `os.replace` thứ `n` (ghi file mới; `only` ⇒ chỉ đếm đích chứa chuỗi đó) giả lỗi
        đĩa đầy. Trả (rc, stderr, số lần gọi được đếm)."""
        import contextlib
        import io
        from unittest import mock
        calls = []
        real = sync_core._replace

        def flaky(src, dst):
            if only is None or only in str(dst):
                calls.append(dst)
                if len(calls) == n:
                    raise OSError(28, "đĩa đầy (giả)")
            return real(src, dst)

        err = io.StringIO()
        with mock.patch.object(sync_core, "_replace", flaky), contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            rc = sync_core.main(["sync", "--to", "v1.1.0", "--root", str(self.app), *extra])
        return rc, err.getvalue(), len(calls)

    def assert_recovery_restores(self, msg):
        """Lệnh khôi phục in ra (một dòng `cd … && …`) đưa app về đúng trước lúc đồng bộ."""
        line = next(ln.strip() for ln in msg.splitlines() if ln.strip().startswith("cd "))
        self.assertIn("git restore --staged --worktree -- .", line)
        r = subprocess.run(["bash", "-c", line], env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.git(self.app, "status", "--porcelain").stdout, "")
        self.assertEqual(self.check_app().returncode, 0)

    def test_loi_giua_chung_lock_khong_doi(self):
        self.release(write={"Loi/A.txt": "struct A { v2 }\n", "Loi/con/B.txt": "struct B { v2 }\n",
                            "Loi/Moi.txt": "struct Moi {}\n"}, delete=["Loi/Cu.txt"])
        lock_before = (self.app / sync_core.LOCK).read_bytes()
        rc, msg, calls = self.sync_failing_at(2)
        self.assertEqual(rc, 1, msg)
        self.assertEqual(calls, 2, "phải dừng ngay ở lỗi")
        self.assertEqual((self.app / sync_core.LOCK).read_bytes(), lock_before, "core.lock không được đổi")
        self.assertIn("git clean -fd -- Loi/Moi.txt", msg)
        self.assert_no_leftovers()
        self.assert_recovery_restores(msg)
        self.assertEqual(self.read("Loi/Cu.txt"), T_FILES["Loi/Cu.txt"])

    def test_loi_sau_khi_da_xoa_khoi_phuc_ca_file_da_xoa(self):
        # File ghim → thư mục: xoá Loi/Cu.txt chạy TRƯỚC, rồi ghi Loi/A.txt (ok) và Loi/Cu.txt/main.txt (lỗi).
        self.release(write={"Loi/A.txt": "struct A { v2 }\n", "Loi/Cu.txt/main.txt": "struct Main {}\n"},
                     delete=["Loi/Cu.txt"])
        lock_before = (self.app / sync_core.LOCK).read_bytes()
        rc, msg, calls = self.sync_failing_at(2)
        self.assertEqual(rc, 1, msg)
        self.assertEqual((self.app / sync_core.LOCK).read_bytes(), lock_before)
        self.assertFalse((self.app / "Loi/Cu.txt").is_file(), "tiền đề: file đã bị xoá trước khi lỗi")
        self.assertEqual(self.read("Loi/A.txt"), "struct A { v2 }\n", "tiền đề: một file đã được ghi")
        self.assert_no_leftovers()
        self.assert_recovery_restores(msg)
        self.assertEqual(self.read("Loi/Cu.txt"), T_FILES["Loi/Cu.txt"])
        self.assertEqual(self.read("Loi/A.txt"), T_FILES["Loi/A.txt"])

    # ------------------------------------------------------------ đổi tên hoa/thường, file ↔ thư mục

    def case_insensitive(self):
        probe = self.base / "dò hoa thường"
        probe.mkdir()
        (probe / "ab").write_text("x", encoding="utf-8")
        try:
            return os.path.exists(probe / "AB")
        finally:
            shutil.rmtree(probe)

    def test_doi_ten_hoa_thuong_cua_template_qua_duoc(self):
        if not self.case_insensitive():
            self.skipTest("ổ đĩa phân biệt hoa thường — ca này chỉ cắn trên ổ không phân biệt")
        self.release(moves=[("docs/bai-hoc/mot.md", "docs/bai-hoc/Mot.md")])
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertIn("Mot.md", os.listdir(self.app / "docs/bai-hoc"))
        self.assertNotIn("mot.md", os.listdir(self.app / "docs/bai-hoc"), "tên trên đĩa phải là tên MỚI")
        lock = self.lock()
        self.assertIn("docs/bai-hoc/Mot.md", lock["synced"])
        self.assertNotIn("docs/bai-hoc/mot.md", lock["synced"])
        self.assertEqual(self.check_app().returncode, 0, self.check_app().stdout)
        self.git(self.app, "add", "-A")
        st = self.git(self.app, "status", "--porcelain").stdout.splitlines()
        self.assertIn("R  docs/bai-hoc/mot.md -> docs/bai-hoc/Mot.md", st)
        r = self.check_app("--staged")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_file_thanh_thu_muc_qua_duoc(self):
        self.release(write={"Loi/Cu.txt/main.txt": "struct Main {}\n"}, delete=["Loi/Cu.txt"])
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertEqual(self.read("Loi/Cu.txt/main.txt"), "struct Main {}\n")
        self.assertNotIn("Loi/Cu.txt", self.lock()["synced"])
        self.assert_clean_after_add()

    def test_thu_muc_thanh_file_qua_duoc(self):
        self.release(write={"Loi/con": "giờ là file\n"}, delete=["Loi/con/B.txt"])
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertEqual(self.read("Loi/con"), "giờ là file\n")
        self.assert_clean_after_add()

    def test_thu_muc_thanh_file_con_file_cua_app_ben_trong_bi_tu_choi(self):
        # Thư mục còn file bị ignore (không phải của template) ⇒ xung đột, nêu đúng file đó.
        self.twrite("Loi/con/__pycache__/x.pyc", "rác\n", root=self.app)
        self.release(write={"Loi/con": "giờ là file\n"}, delete=["Loi/con/B.txt"])
        before = self.snap()
        r = self.sync("--to", "v1.1.0")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("Loi/con/__pycache__/x.pyc", r.stderr)

    def test_xung_dot_gieo_thanh_dong_bo_bao_git_rm(self):
        self.release(write={"AppHost/App.txt": "struct App { cuaTemplate }\n"},
                     manifest_text=T_MANIFEST.replace('["Loi/", ', '["Loi/", "AppHost/App.txt", '))
        before = self.snap()
        r = self.sync("--to", "v1.1.0")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("AppHost/App.txt", r.stderr)
        self.assertIn("trước là lớp gieo", r.stderr)
        self.assertIn("git rm AppHost/App.txt", r.stderr)
        self.assertNotIn("chuyển/đổi tên file của app", r.stderr)

    # ------------------------------------------------------------ .git, nhận diện template

    def test_duong_dan_git_va_core_lock_bi_tu_choi(self):
        for bad in (".git/hooks/post-merge", ".GIT/hooks/post-merge", "Loi/.git/config", "a/.Git", "core.lock",
                    "CORE.LOCK"):
            with self.subTest(bad=bad), self.assertRaises(sync_core.LockError):
                sync_core._check_path("synced", bad)
        self.assertEqual(sync_core._check_path("synced", ".githooks/pre-commit"), ".githooks/pre-commit")
        self.assertEqual(sync_core._check_path("synced", "Loi/.gitignore"), "Loi/.gitignore")
        # Cây mới "giả" ghim .GIT/hooks/… qua manifest + danh sách file dựng tay ⇒ từ chối, .git của app không đổi.
        tree = self.base / "cây giả"
        (tree / ".GIT/hooks").mkdir(parents=True)
        (tree / ".GIT/hooks/post-merge").write_text("echo bẫy\n", encoding="utf-8")
        (tree / "template.manifest.toml").write_text(
            T_MANIFEST.replace('["Loi/", ', '["Loi/", ".GIT/hooks/", '), encoding="utf-8")
        with self.assertRaises(sync_core.SyncRefused):
            sync_core.plan_sync(self.app, tree, files=["template.manifest.toml", ".GIT/hooks/post-merge"])
        self.assertFalse(os.path.lexists(self.app / ".git/hooks/post-merge"))
        bad_lock = self.lock()
        bad_lock["synced"][".git/hooks/post-merge"] = sha("x")
        with self.assertRaises(sync_core.LockError):
            sync_core.validate(bad_lock)

    def test_nhan_dien_template_theo_head(self):
        # HEAD có: chỉ dấu trong HEAD tính; stage dấu ở app không biến app thành template.
        self.assertTrue(sync_core._is_template(self.tpl))
        self.assertFalse(sync_core._is_template(self.app))
        self.twrite(sync_core.TEMPLATE_MARKER, "# lạc\n", root=self.app)
        self.git(self.app, "add", sync_core.TEMPLATE_MARKER)
        self.assertFalse(sync_core._is_template(self.app))
        # HEAD chưa có: dấu trong index và core.lock chưa từng có ⇒ template; core.lock từng commit (reflog) ⇒ app.
        fresh = self.base / "repo mới chưa commit"
        fresh.mkdir()
        self.git(fresh, "init", "-q", "-b", "main")
        self.twrite(sync_core.TEMPLATE_MARKER, "# dấu\n", root=fresh)
        self.git(fresh, "add", "-A")
        self.assertTrue(sync_core._is_template(fresh))
        orphan = self.base / "repo mồ côi"
        orphan.mkdir()
        self.git(orphan, "init", "-q", "-b", "main")
        self.twrite(sync_core.LOCK, "{}\n", root=orphan)
        self.tcommit("có lock", root=orphan)
        self.git(orphan, "checkout", "-q", "--orphan", "moi")
        self.git(orphan, "rm", "-q", "-r", "--cached", ".")
        self.twrite(sync_core.TEMPLATE_MARKER, "# dấu\n", root=orphan)
        self.git(orphan, "add", sync_core.TEMPLATE_MARKER)
        self.assertFalse(sync_core._is_template(orphan), "core.lock từng có trong lịch sử ⇒ app")

    def test_file_gieo_doi_o_template_duoc_bao_va_khong_bi_ghi_de(self):
        self.twrite("AppHost/App.txt", "struct App { let cuaApp = 1 }\n", root=self.app)
        self.tcommit("app sửa file gieo", root=self.app)
        self.release(write={"AppHost/App.txt": "struct App { let banMoiCuaTemplate = 2 }\n",
                            "tools/template/seed/README.md": "# README của APP — bản mới\n",
                            "README.md": "# README của TEMPLATE — bản mới\n"})
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        self.assertEqual(self.read("AppHost/App.txt"), "struct App { let cuaApp = 1 }\n")
        self.assertEqual(self.read("README.md"), T_FILES["tools/template/seed/README.md"])
        seed_dir = self.app / sync_core.WORK_DIR / "v1.1.0"
        self.assertEqual((seed_dir / "AppHost/App.txt").read_text(encoding="utf-8"),
                         "struct App { let banMoiCuaTemplate = 2 }\n")
        self.assertEqual((seed_dir / "README.md").read_text(encoding="utf-8"), "# README của APP — bản mới\n",
                         "đích của thư mục gieo lấy bản trong thư mục gieo, không phải README của template")
        lock = self.lock()
        self.assertEqual(lock["seeded"]["AppHost/App.txt"], sha("struct App { let banMoiCuaTemplate = 2 }\n"))
        self.assertEqual(lock["seeded"]["README.md"], sha("# README của APP — bản mới\n"))
        self.assertIn("* AppHost/App.txt", r.stdout)
        self.assertIn("* README.md", r.stdout)
        self.assertNotIn("CHANGELOG.md", lock["synced"])
        self.assertEqual(self.git(self.app, "status", "--porcelain").stdout, " M core.lock\n",
                         "chỉ core.lock đổi; bản để so nằm trong .temp/ (ignore)")
        self.assert_clean_after_add()

    def test_file_gieo_doi_co_nhan_va_lenh_diff(self):
        # (đổi): đã gieo, app còn; (mới ở template): chưa từng gieo; (app không còn file này): đã gieo, app đã xoá.
        self.git(self.app, "rm", "-q", "docs/bai-hoc/app/README.md")
        self.tcommit("app xoá file gieo", root=self.app)
        self.release(write={"AppHost/App.txt": "struct App { v2 }\n", "AppHost/Moi.txt": "struct Moi {}\n",
                            "docs/bai-hoc/app/README.md": "# bài học của app v2\n",
                            "tools/template/seed/README.md": "# README của APP v2\n"})
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                r = self.sync("--to", "v1.1.0", *(["--dry-run"] if dry else []))
                self.assert_ok(r)
                out = r.stdout
                self.assertIn("* AppHost/App.txt  (đổi)", out)
                self.assertIn("* AppHost/Moi.txt  (mới ở template)", out)
                self.assertIn("* docs/bai-hoc/app/README.md  (app không còn file này)", out)
                self.assertIn("* README.md  (đổi)", out)
                self.assertIn("NGUYÊN BẢN của template", out)
                src = shlex.quote(str(self.tpl))
                self.assertIn(f"git -C {src} diff v1.0.0..v1.1.0 -- AppHost/Moi.txt", out)
                self.assertIn(f"git -C {src} diff v1.0.0..v1.1.0 -- tools/template/seed/README.md", out,
                              "đích của thư mục gieo: diff đường dẫn trong thư mục gieo")
        # Lệnh in ra chạy được và cho đúng thay đổi.
        d = subprocess.run(["git", "-C", str(self.tpl), "diff", "v1.0.0..v1.1.0", "--", "AppHost/App.txt"],
                           env=self.env(), capture_output=True, text=True)
        self.assertIn("+struct App { v2 }", d.stdout)

    def test_nguon_co_thong_tin_dang_nhap_khong_vao_lock(self):
        secret = "user:tok" + "en@"
        lock = self.lock()
        lock["template"]["source"] = "https://" + secret + "git.example.invalid/org/tpl.git"
        sync_core.write_lock(self.app, sync_core.validate(lock))
        self.tcommit("nguồn URL", root=self.app)
        self.release(write={"Loi/A.txt": "struct A { v2 }\n"})
        r = self.sync("--to", "v1.1.0", "--source", str(self.tpl))
        self.assert_ok(r)
        self.assertEqual(self.lock()["template"]["source"], "https://git.example.invalid/org/tpl.git")
        self.assertNotIn(secret, self.read(sync_core.LOCK))
        self.assertNotIn(secret, r.stdout + r.stderr)

    def test_public_source(self):
        tok = "user:tok" + "en"
        for raw, want in (("https://" + tok + "@h.example/o/r.git", "https://h.example/o/r.git"),
                          ("http://" + tok + "@h.example:8080/r", "http://h.example:8080/r"),
                          ("https://tok" + "en@h.example/r", "https://h.example/r"),
                          ("ssh://git:pw" + "@h.example/r.git", "ssh://git@h.example/r.git"),
                          ("ssh://git@h.example/r.git", "ssh://git@h.example/r.git"),
                          ("git@h.example:o/r.git", "git@h.example:o/r.git"),
                          ("/Users/a b/tpl", "/Users/a b/tpl"),
                          ("https://h.example/o/r@x.git", "https://h.example/o/r@x.git")):
            with self.subTest(raw=raw):
                self.assertEqual(sync_core.public_source(raw), want)

    def test_dry_run_khong_ghi_gi(self):
        self.release(write={"Loi/A.txt": "struct A { v2 }\n", "Loi/Moi.txt": "struct Moi {}\n",
                            "AppHost/App.txt": "struct App { v2 }\n"}, delete=["Loi/Cu.txt"])
        before = self.snap()
        r = self.sync("--to", "v1.1.0", "--dry-run")
        self.assert_ok(r)
        self.assertEqual(self.snap(), before)
        self.assert_no_leftovers()
        self.assertFalse(os.path.lexists(self.app / sync_core.WORK_DIR / "v1.1.0"))
        for want in ("--dry-run", "+ Loi/Moi.txt", "~ Loi/A.txt", "- Loi/Cu.txt", "* AppHost/App.txt"):
            self.assertIn(want, r.stdout)

    def test_dong_bo_cung_tag_la_khong_doi(self):
        before = self.snap()
        r = self.sync("--to", "v1.0.0")
        self.assert_ok(r)
        self.assertIn("không có gì đổi", r.stdout)
        self.assertEqual(self.snap(), before)
        self.assert_no_leftovers()

    def test_ve_tag_cu_hon_co_canh_bao(self):
        self.release(write={"Loi/A.txt": "struct A { v2 }\n"})
        self.assert_ok(self.sync("--to", "v1.1.0"))
        self.tcommit("đồng bộ v1.1.0", root=self.app)
        r = self.sync("--to", "v1.0.0")
        self.assert_ok(r)
        self.assertIn("CẢNH BÁO", r.stdout)
        self.assertEqual(self.read("Loi/A.txt"), T_FILES["Loi/A.txt"])
        self.assertEqual(self.lock()["template"]["tag"], "v1.0.0")

    def test_bit_thuc_thi_duoc_giu(self):
        self.twrite("Loi/moi.sh", "echo mới\n")
        os.chmod(self.tpl / "Loi/moi.sh", 0o755)
        self.release(chmod={"Loi/chay.sh": 0o755})
        r = self.sync("--to", "v1.1.0")
        self.assert_ok(r)
        for rel in ("Loi/chay.sh", "Loi/moi.sh"):
            self.assertTrue(os.stat(self.app / rel).st_mode & 0o100, rel)
            self.assertTrue(self.lock()["synced"][rel].endswith("+x"), rel)
        self.assertFalse(os.stat(self.app / "Loi/A.txt").st_mode & 0o100)
        self.assert_clean_after_add()
        staged = self.git(self.app, "ls-files", "-s", "Loi/chay.sh", "Loi/moi.sh").stdout
        self.assertEqual([ln.split()[0] for ln in staged.splitlines()], ["100755", "100755"])

    # ------------------------------------------------------------ việc phải làm tay

    def test_manual_steps_lay_dung_khoang_ban(self):
        cl = ("# Changelog\n\n## Chưa phát hành\n\n- x\n\n" + TAY + "\n\n- chưa ra bản\n\n"
              "## v0.10.0 — 2026-12-10\n\n- y\n\n" + TAY + "\n\n- việc A1\n- việc A2\n\n### Ghi chú\n\n- không phải việc tay\n\n"
              "## v0.9.0 — 2026-12-01\n\n" + TAY + "\n\n- việc B\n\n"
              "## v0.4.0 — 2026-11-24\n\n" + TAY + "\n\n- Không có.\n\n"
              "## v0.3.0 — 2026-11-23\n\n- cũ, không tiểu mục\n")
        self.assertEqual(sync_core.manual_steps(cl, "v0.4.0", "v0.10.0"),
                         "v0.9.0:\n- việc B\n\nv0.10.0:\n- việc A1\n- việc A2")
        self.assertEqual(sync_core.manual_steps(cl, None, "v0.9.0"), "v0.4.0:\n- Không có.\n\nv0.9.0:\n- việc B")
        self.assertEqual(sync_core.manual_steps(cl, "v0.9.0", "v0.9.0"), "")
        self.assertEqual(sync_core.manual_steps(cl, "v0.10.0", "v0.4.0"), "", "hạ bản ⇒ không có việc tay")
        self.assertEqual(sync_core.manual_steps(cl, "v0.3.0", "khong-phai-ban"), "")
        self.assertNotIn("chưa ra bản", sync_core.manual_steps(cl, None, "v9.0.0"))
        self.assertNotIn("không phải việc tay", sync_core.manual_steps(cl, None, "v9.0.0"))

    # ------------------------------------------------------------ nhận file gieo mới (--adopt-new-seed)

    # Cấu hình CỦA APP khác hẳn của template ("Sample") — biến thay vào file gieo phải lấy từ đây.
    APP_NAME = 'Ứng dụng "Thử"'

    def set_app_config(self):
        cfg = (T_CONFIG.replace('display_name = "Sample"', 'display_name = "Ứng dụng \\"Thử\\""')
               .replace('slug = "sample"', 'slug = "ung-dung-thu"')
               .replace('marketing = "0.1.0"', 'marketing = "2.3.0"')
               .replace('store = "com.example.sample"', 'store = "dev.thu' + '-nghiem.ThuApp"')
               .replace('internal = "com.example.sample.internal"', 'internal = "dev.thu' + '-nghiem.ThuApp.internal"'))
        cfg += '\n[web]\nhost_prod = "thu.invalid"\nhost_dev = "dev.thu.invalid"\n\n[store]\nlocales = ["en-US", "vi"]\n'
        self.twrite("app.config.toml", cfg, root=self.app)
        r = subprocess.run([sys.executable, str(self.app / "tools/common/appconfig.py"), "render"], cwd=self.app,
                           env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.tcommit("cấu hình của app", root=self.app)

    STORE_RELEASE = {
        "tools/template/seed/store/metadata/app-info/$primary_locale.json":
            '{\n  "name": "$display_name",\n  "privacyPolicyUrl": "https://$host_prod/privacy/"\n}\n',
        "tools/template/seed/store/metadata/version/$marketing_version/$primary_locale.json":
            '{\n  "whatsNew": "$display_name $marketing_version ($template_tag)"\n}\n',
        # metadata MẪU của template (lớp gieo, không qua thư mục gieo): không bao giờ tới app
        "store/metadata/app-info/en-US.json": '{\n  "name": "Sample"\n}\n',
        "store/README.md": "# store/\n<!-- template:begin -->\nchỉ ở template\n<!-- template:end -->\ngiữ nguyên $display_name\n",
        "store/review/notes.txt": "notes của app\n",
        "AppHost/Moi.swift": "struct Moi {}\n",        # Swift mới: không nhận (cần sửa file gieo đã có)
    }

    def release_store(self):
        return self.release(write=self.STORE_RELEASE,
                            manifest_text=T_MANIFEST.replace('".gitignore", ', '".gitignore", "store/", '))

    def test_adopt_tao_file_gieo_moi_va_thay_bien_cua_app(self):
        self.set_app_config()
        self.release_store()
        r = self.sync("--to", "v1.1.0", "--adopt-new-seed")
        self.assert_ok(r)
        info = json.loads(self.read("store/metadata/app-info/en-US.json"))
        self.assertEqual(info, {"name": self.APP_NAME, "privacyPolicyUrl": "https://thu.invalid/privacy/"},
                         "biến lấy từ app.config.toml CỦA APP, giá trị JSON được escape")
        self.assertEqual(json.loads(self.read("store/metadata/app-info/vi.json")), info, "nhân sang locale khác")
        ver = json.loads(self.read("store/metadata/version/2.3.0/en-US.json"))
        self.assertEqual(ver, {"whatsNew": f"{self.APP_NAME} 2.3.0 (v1.1.0)"})
        self.assertTrue((self.app / "store/metadata/version/2.3.0/vi.json").is_file())
        self.assertFalse(os.path.lexists(self.app / "store/metadata/version/0.1.0"), "không dùng version của template")
        self.assertEqual(self.read("store/README.md"), "# store/\ngiữ nguyên $display_name\n",
                         "cắt khối template:, file gieo thường không thay biến (như new_app)")
        self.assertEqual(self.read("store/review/notes.txt"), "notes của app\n")
        self.assertFalse(os.path.lexists(self.app / "AppHost/Moi.swift"), "Swift mới không được nhận")
        self.assertFalse(os.path.lexists(self.app / "store/metadata/app-info/$primary_locale.json"))
        seeded = self.lock()["seeded"]
        for key, raw in self.STORE_RELEASE.items():
            k = key.removeprefix("tools/template/seed/")
            self.assertEqual(seeded[k], sha(raw), f"{k}: seeded = digest BẢN NGUYÊN của template")
        for p in ("store/metadata/app-info/en-US.json", "store/metadata/app-info/vi.json",
                  "store/metadata/version/2.3.0/en-US.json", "store/README.md", "store/review/notes.txt"):
            self.assertIn(f"* {p}  (đã tạo ở app)", r.stdout)
        temp = self.app / sync_core.WORK_DIR / "v1.1.0"
        self.assertFalse(os.path.lexists(temp / "store/README.md"), "file đã tạo ở app không chép ra .temp/")
        self.assertTrue((temp / "AppHost/Moi.swift").is_file(), "file không nhận vẫn chép ra .temp/ như cũ")
        self.assertIn("* AppHost/Moi.swift  (mới ở template)", r.stdout)
        self.assertNotIn("* store/metadata/app-info/en-US.json  (mới ở template)", r.stdout,
                         "metadata mẫu của template không báo/chép cạnh bản khung vừa tạo cùng đường dẫn")
        self.assertNotIn("Gợi ý:", r.stdout)
        self.assert_no_leftovers()
        self.assert_clean_after_add()
        # Lần đồng bộ sau: khoá giữ chỗ đã ở `seeded` ⇒ không nhận lại dù app xoá file.
        self.tcommit("nhận store/", root=self.app)
        self.git(self.app, "rm", "-q", "store/review/notes.txt")
        self.tcommit("app bỏ notes", root=self.app)
        self.release(tag="v1.2.0", write={"Loi/A.txt": "struct A { v3 }\n"})
        r = self.sync("--to", "v1.2.0", "--adopt-new-seed")
        self.assert_ok(r)
        self.assertFalse(os.path.lexists(self.app / "store/review/notes.txt"))
        self.assertNotIn("(đã tạo ở app)", r.stdout)

    def test_adopt_khong_dung_file_app_da_co(self):
        self.twrite("store/README.md", "# store của app\n", root=self.app)
        self.twrite(".gitignore", T_FILES[".gitignore"] + "store/review/\n", root=self.app)
        self.tcommit("app có store/README.md, ignore store/review/", root=self.app)
        self.twrite("store/review/notes.txt", "bản nháp chưa track\n", root=self.app)
        self.release_store()
        # Chưa track mà có trên đĩa ⇒ xung đột: không ghi gì.
        before = self.snap()
        r = self.sync("--to", "v1.1.0", "--adopt-new-seed")
        self.assert_refused_nothing_written(r, before)
        self.assertIn("! store/review/notes.txt", r.stderr)
        self.assertEqual(self.read("store/review/notes.txt"), "bản nháp chưa track\n")
        # Dọn chỗ đó ⇒ qua; file app đã track không bị đụng, bản nguyên chép ra .temp/ như cũ.
        (self.app / "store/review/notes.txt").unlink()
        r = self.sync("--to", "v1.1.0", "--adopt-new-seed")
        self.assert_ok(r)
        self.assertEqual(self.read("store/README.md"), "# store của app\n")
        self.assertEqual(self.read("store/review/notes.txt"), "notes của app\n")
        self.assertIn("* store/README.md  (mới ở template)", r.stdout)
        self.assertNotIn("* store/README.md  (đã tạo ở app)", r.stdout)
        self.assertTrue((self.app / sync_core.WORK_DIR / "v1.1.0/store/README.md").is_file())

    def test_khong_co_co_thi_chi_chep_ra_temp(self):
        self.release_store()
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                r = self.sync("--to", "v1.1.0", *(["--dry-run"] if dry else []))
                self.assert_ok(r)
                hints = [ln for ln in r.stdout.splitlines() if "--adopt-new-seed" in ln]
                self.assertEqual(len(hints), 1, r.stdout)
                self.assertIn("4 file gieo mới", hints[0])
                self.assertNotIn("(đã tạo ở app)", r.stdout)
                self.assertNotIn("(sẽ tạo ở app)", r.stdout)
        self.assertFalse(os.path.lexists(self.app / "store"), "không cờ ⇒ app không nhận file gieo nào")
        temp = self.app / sync_core.WORK_DIR / "v1.1.0"
        self.assertTrue((temp / "store/metadata/app-info/$primary_locale.json").is_file(), "chép bản nguyên như cũ")
        self.assertEqual(self.git(self.app, "status", "--porcelain").stdout, " M core.lock\n M template.manifest.toml\n")
        # Dòng gợi ý in sẵn lệnh khôi phục chạy được: về trước lúc đồng bộ, rồi nhận bằng cờ.
        line = next(ln for ln in r.stdout.splitlines() if "--adopt-new-seed" in ln)
        cmd = line[line.index("(cd ") + 1:line.index(") rồi chạy lại")]
        self.assertEqual(subprocess.run(["bash", "-c", cmd], env=self.env()).returncode, 0)
        self.assertEqual(self.git(self.app, "status", "--porcelain").stdout, "")
        self.assert_ok(self.sync("--to", "v1.1.0", "--adopt-new-seed"))
        self.assertTrue((self.app / "store/review/notes.txt").is_file())

    def test_file_sinh_boi_render_khong_bao_doi_khong_nhan(self):
        # Template đổi cấu hình của nó ⇒ Identity.xcconfig (file render sinh, lớp gieo) của template đổi: bản đó là của
        # TEMPLATE — không báo "file gieo đổi", không chép ra .temp/, không nhận; app tự render. Lock vẫn ghi bản nguyên.
        self.twrite("app.config.toml", T_CONFIG.replace('display_name = "Sample"', 'display_name = "Sample Hai"'))
        r = subprocess.run([sys.executable, str(self.tpl / "tools/common/appconfig.py"), "render"], cwd=self.tpl,
                           env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        xc = "AppHost/Config/Identity.xcconfig"
        self.assertIn("Sample Hai", (self.tpl / xc).read_text(encoding="utf-8"), "tiền đề: file sinh của template đổi")
        self.release()
        r = self.sync("--to", "v1.1.0", "--adopt-new-seed")
        self.assert_ok(r)
        self.assertNotIn(xc, r.stdout)
        self.assertIn("* app.config.toml  (đổi)", r.stdout, "file gieo thường vẫn báo như cũ")
        self.assertFalse(os.path.lexists(self.app / sync_core.WORK_DIR / "v1.1.0" / xc))
        self.assertNotIn("Sample Hai", self.read(xc))
        self.assertEqual(self.lock()["seeded"][xc], sha((self.tpl / xc).read_text(encoding="utf-8")))

    def test_adopt_loi_giua_chung_khong_de_lai_file_do(self):
        self.release_store()
        lock_before = (self.app / sync_core.LOCK).read_bytes()
        rc, msg, calls = self.sync_failing_at(2, "--adopt-new-seed", only="/store/")
        self.assertEqual(rc, 1, msg)
        self.assertEqual((self.app / sync_core.LOCK).read_bytes(), lock_before, "core.lock không được đổi")
        self.assertTrue(any((self.app / "store").rglob("*.json")) or (self.app / "store/README.md").exists(),
                        "tiền đề: một file gieo đã được tạo trước khi lỗi")
        self.assertIn("git clean -fd -- ", msg)
        self.assertIn("store/review/notes.txt", msg, "lệnh khôi phục gồm mọi file gieo sẽ tạo")
        self.assert_no_leftovers()
        self.assert_recovery_restores(msg)
        self.assertEqual([p for p in (self.app / "store").rglob("*") if p.is_file()]
                         if (self.app / "store").exists() else [], [], "không còn file gieo dở")

    WEB_PRIVACY_SEED = ("<h1>$display_name</h1>\n"
                        "<!-- feature:web_api:begin -->\n<section data-feature=\"web_api\">feedback</section>\n"
                        "<!-- feature:web_api:end -->\n"
                        "<!-- feature:paywall:begin -->\n<section data-feature=\"paywall\">mua</section>\n"
                        "<!-- feature:paywall:end -->\n<p>https://$host_prod/</p>\n")

    def test_sync_adopt_new_seed_tao_trang_web_va_wrangler(self):
        # App cũ (trước khi template có web/): có host, chưa có trang web gieo lẫn hai wrangler.jsonc sinh. Đồng bộ lên
        # bản có web/ với --adopt-new-seed ⇒ trang được tạo với biến CỦA APP và khối feature cắt theo công tắc CỦA APP;
        # hai wrangler.jsonc do appconfig (cây mới) dựng từ cấu hình CỦA APP — không phải bản sinh của template.
        cfg = (T_CONFIG.replace('display_name = "Sample"', 'display_name = "Thu & Co"')
               .replace('slug = "sample"', 'slug = "ung-dung-thu"')
               + '\n[web]\nhost_prod = "thu.invalid"\nhost_dev = "dev.thu.invalid"\n\n'
               '[features]\npaywall = false\nweb_api = true\napple_ads = false\n')
        self.twrite("app.config.toml", cfg, root=self.app)
        render = subprocess.run([sys.executable, str(self.app / "tools/common/appconfig.py"), "render"], cwd=self.app,
                                env=self.env(), capture_output=True, text=True)
        self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
        for rel in ("web/api/wrangler.jsonc", "web/site/wrangler.jsonc"):   # app cũ: appconfig chưa sinh wrangler
            (self.app / rel).unlink()
        shutil.rmtree(self.app / "web")
        self.tcommit("cấu hình của app (cũ, chưa có web/)", root=self.app)
        # Template ra bản có web/: trang gieo (thư mục gieo) + hai wrangler.jsonc sinh theo cấu hình CỦA TEMPLATE.
        self.twrite("app.config.toml", T_CONFIG + '\n[web]\nhost_prod = "example.com"\nhost_dev = "dev.example.com"\n'
                    '\n[features]\npaywall = false\nweb_api = true\napple_ads = false\n'
                    '\n[firebase]\napp_check_prod = "tpl-proj:1"\napp_check_dev = "tpl-proj:1"\n')
        r = subprocess.run([sys.executable, str(self.tpl / "tools/common/appconfig.py"), "render"], cwd=self.tpl,
                           env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.tpl / "web/api/wrangler.jsonc").is_file(), "tiền đề: template có wrangler sinh")
        self.release(write={"tools/template/seed/web/site/public/privacy/index.html": self.WEB_PRIVACY_SEED},
                     manifest_text=T_MANIFEST.replace('".gitignore", ', '".gitignore", "web/", '))
        r = self.sync("--to", "v1.1.0", "--adopt-new-seed")
        self.assert_ok(r)
        page = self.read("web/site/public/privacy/index.html")
        self.assertEqual(page, "<h1>Thu &amp; Co</h1>\n<section data-feature=\"web_api\">feedback</section>\n"
                               "<p>https://thu.invalid/</p>\n",
                         "biến của app (escape HTML), khối paywall (tắt ở app) bị cắt, dấu khối web_api bị bỏ")
        self.assertIn("* web/site/public/privacy/index.html  (đã tạo ở app)", r.stdout)
        sys.path.insert(0, str(self.app / "tools/common"))
        try:
            import appconfig as ac
        finally:
            sys.path.pop(0)
        app_cfg = ac.load(self.app)
        for rel, want in ((ac.WRANGLER_API, ac.render_wrangler_api(app_cfg)),
                          (ac.WRANGLER_SITE, ac.render_wrangler_site(app_cfg))):
            self.assertEqual(self.read(rel), want, f"{rel}: dựng từ cấu hình của app")
            self.assertIn('"ung-dung-thu-', self.read(rel))
            self.assertNotIn("example.com", self.read(rel), f"{rel}: không phải bản sinh của template")
            self.assertIn(f"* {rel}  (đã tạo ở app)", r.stdout)
        chk = subprocess.run([sys.executable, str(self.app / "tools/common/appconfig.py"), "check"], cwd=self.app,
                             env=self.env(), capture_output=True, text=True)
        self.assertEqual(chk.returncode, 0, chk.stdout + chk.stderr)
        self.assertNotIn("web/api/wrangler.jsonc", r.stdout.replace("* web/api/wrangler.jsonc  (đã tạo ở app)", ""),
                         "file sinh không báo đổi / không chép ra .temp/")
        self.assertFalse(os.path.lexists(self.app / sync_core.WORK_DIR / "v1.1.0/web"))
        self.assert_no_leftovers()
        self.assert_clean_after_add()

    def test_commit_sau_adopt_qua_hook(self):
        self.set_app_config()            # trước khi bật hook: repo thử không có check_storekit (khối 1b)
        self.git(self.app, "config", "core.hooksPath", ".githooks")
        self.release_store()
        self.assert_ok(self.sync("--to", "v1.1.0", "--adopt-new-seed"))
        self.git(self.app, "add", "-A")
        r = self.git(self.app, "commit", "-q", "-m", "chore(core): đồng bộ lõi v1.0.0 → v1.1.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git(self.app, "status", "--porcelain").stdout, "")
        self.assertEqual(self.check_app().returncode, 0)
        self.assertIn("store/metadata/app-info/vi.json", self.git(self.app, "ls-files", "store").stdout)

    # ------------------------------------------------------------ commit thật qua hook

    def test_commit_sau_dong_bo_qua_pre_commit(self):
        self.git(self.app, "config", "core.hooksPath", ".githooks")
        # Đối chứng: hook THẬT đang gác — sửa tay lõi bị chặn.
        self.twrite("Loi/A.txt", "struct A { sửa tay }\n", root=self.app)
        self.git(self.app, "add", "-A")
        r = self.git(self.app, "commit", "-q", "-m", "sửa tay")
        self.assertNotEqual(r.returncode, 0, "hook phải chặn sửa tay lõi:\n" + r.stdout + r.stderr)
        self.git(self.app, "restore", "--staged", "--worktree", "Loi/A.txt")
        self.release(write={"Loi/A.txt": "struct A { v2 }\n", "Loi/Moi.txt": "struct Moi {}\n"},
                     delete=["Loi/Cu.txt"], chmod={"Loi/chay.sh": 0o755},
                     manifest_text=T_MANIFEST.replace('"AppHost/", ', '"AppHost/", "Loi/Mau.txt", '))
        self.assert_ok(self.sync("--to", "v1.1.0"))
        before = self.git(self.app, "rev-parse", "HEAD").stdout.strip()
        self.git(self.app, "add", "-A")
        r = self.git(self.app, "commit", "-q", "-m", "chore(core): đồng bộ lõi v1.0.0 → v1.1.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(self.git(self.app, "rev-parse", "HEAD").stdout.strip(), before)
        self.assertEqual(self.git(self.app, "status", "--porcelain").stdout, "")
        self.assertEqual(self.check_app().returncode, 0)


if __name__ == "__main__":
    unittest.main()
