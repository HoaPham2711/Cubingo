"""Test snapshot.py và remote.py bằng runner giả (offline)."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401 — thư mục trạng thái + cấu hình giả
import remote  # noqa: E402
import snapshot  # noqa: E402


def fake_pull(*, with_default=False, vdir="version"):
    """Runner giả: `metadata pull` ghi 1 locale (+ tuỳ chọn default.json); `versions view` trả JSON."""
    def run(args, **kw):
        if args[:2] == ["metadata", "pull"]:
            d = Path(args[args.index("--dir") + 1])
            v = args[args.index("--version") + 1]
            (d / "app-info").mkdir(parents=True)
            (d / "app-info" / "en-US.json").write_text(json.dumps({"name": "Thu App"}))
            (d / vdir / v).mkdir(parents=True)
            (d / vdir / v / "en-US.json").write_text(json.dumps({"whatsNew": "x"}))
            if with_default:
                (d / vdir / v / "default.json").write_text(json.dumps({"whatsNew": "y"}))
            return None
        raise AssertionError(args)
    return run


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aso thu "))
        self.state = _testenv.isolate(self)

    def _mk(self, name):
        (snapshot.root() / name).mkdir(parents=True)

    def test_prune_keeps_recent_and_last_ten(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        for i in range(12):
            self._mk((now - timedelta(days=40 + i)).strftime(snapshot.TS_FORMAT))
        for i in range(3):
            self._mk((now - timedelta(days=i)).strftime(snapshot.TS_FORMAT))
        removed = snapshot.prune(snapshot.root(), now=now)
        self.assertEqual(len(removed), 5)
        self.assertEqual(len(list(snapshot.root().iterdir())), 10)

    def test_prune_nothing_when_all_recent(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        for i in range(15):
            self._mk((now - timedelta(days=5, seconds=i)).strftime(snapshot.TS_FORMAT))
        self.assertEqual(snapshot.prune(snapshot.root(), now=now), [])
        self.assertEqual(len(list(snapshot.root().iterdir())), 15)

    def test_prune_ignores_unparsable_names(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        self._mk("khong-phai-ngay")
        self.assertEqual(snapshot.prune(snapshot.root(), keep=0, now=now), [])
        self.assertTrue((snapshot.root() / "khong-phai-ngay").exists())

    def test_take_writes_metadata_and_fingerprint(self):
        now = datetime(2026, 10, 29, 1, 2, 3, tzinfo=timezone.utc)
        snap = snapshot.take("1.2.3", run=fake_pull(), now=now)
        self.assertEqual(snap.name, "20261029T010203Z")
        self.assertTrue((snap / "metadata" / "app-info" / "en-US.json").is_file())
        self.assertEqual(len((snap / "fingerprint.txt").read_text().strip()), 64)

    def test_take_same_second_does_not_delete_existing(self):
        now = datetime(2026, 10, 29, 1, 2, 3, tzinfo=timezone.utc)
        old = snapshot.root() / now.strftime(snapshot.TS_FORMAT)
        old.mkdir(parents=True)
        (old / "marker").write_text("x")
        for run in (fake_pull(), lambda a, **k: 1 / 0):
            with self.assertRaises(FileExistsError):
                snapshot.take("1.2.3", run=run, now=now)
        self.assertTrue((old / "marker").exists())

    def test_take_failure_leaves_nothing(self):
        def boom(args, **kw):
            raise RuntimeError("asc exit 1")
        with self.assertRaises(RuntimeError):
            snapshot.take("1.2.3", run=boom)
        root = snapshot.root()
        self.assertEqual(list(root.iterdir()) if root.exists() else [], [])


class RemoteTests(unittest.TestCase):
    def test_pull_remote_deletes_default_json(self):
        d = Path(tempfile.mkdtemp(prefix="aso thu ")) / "pull"
        values = remote.pull_remote("1.2.3", d, run=fake_pull(with_default=True))
        self.assertFalse(list(d.rglob("default.json")))
        self.assertEqual(values[("version", "en-US", "whatsNew")], "x")

    def test_pull_remote_reports_version_dirname(self):
        for vdir in ("version", "versions"):
            with tempfile.TemporaryDirectory(prefix="aso thu ") as d:
                values = remote.pull_remote("1.2.3", Path(d) / "p", run=fake_pull(vdir=vdir))
            self.assertEqual(values.vdir, vdir)
            self.assertEqual(values[("version", "en-US", "whatsNew")], "x")

    def test_pull_remote_requires_empty_dir(self):
        d = Path(tempfile.mkdtemp(prefix="aso thu "))
        (d / "x").write_text("1")
        with self.assertRaises(ValueError):
            remote.pull_remote("1.2.3", d, run=fake_pull())

    def test_editable_states(self):
        for state, want in [("PREPARE_FOR_SUBMISSION", True), ("REJECTED", True),
                            ("READY_FOR_SALE", False), ("WAITING_FOR_REVIEW", False)]:
            run = lambda a, **k: {"data": {"attributes": {"appVersionState": state}}}
            self.assertEqual(remote.version_editable("1", run=run), want, state)

    def test_missing_key_not_editable(self):
        self.assertFalse(remote.version_editable("1", run=lambda a, **k: {"data": {"x": 1}}))
        self.assertFalse(remote.version_editable("1", run=lambda a, **k: None))


if __name__ == "__main__":
    unittest.main()
