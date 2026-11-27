"""Test remote.version_state / version_editable bằng runner giả (offline)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401
import remote  # noqa: E402


def _run(attrs):
    calls = []

    def run(args, **kw):
        calls.append(args)
        return {"data": {"attributes": attrs}}
    run.calls = calls
    return run


class VersionStateTests(unittest.TestCase):
    def test_version_state_prefers_app_version_state(self):
        run = _run({"appVersionState": "READY_FOR_DISTRIBUTION", "appStoreState": "READY_FOR_SALE"})
        self.assertEqual(remote.version_state("1.2.3", run=run), "READY_FOR_DISTRIBUTION")
        self.assertEqual(run.calls[0][:2], ["versions", "view"])
        self.assertIn("1.2.3", run.calls[0])

    def test_version_state_falls_back_to_app_store_state(self):
        self.assertEqual(remote.version_state("1", run=_run({"appStoreState": "READY_FOR_SALE"})), "READY_FOR_SALE")

    def test_version_state_missing_returns_none(self):
        self.assertIsNone(remote.version_state("1", run=_run({})))
        self.assertIsNone(remote.version_state("1", run=lambda a, **k: None))
        self.assertIsNone(remote.version_state("1", run=lambda a, **k: {"data": [{"attributes": {"appVersionState": "REJECTED"}}]}))

    def test_version_editable_uses_version_state(self):
        self.assertTrue(remote.version_editable("1", run=_run({"appStoreState": "REJECTED"})))
        self.assertFalse(remote.version_editable("1", run=_run({"appVersionState": "READY_FOR_SALE"})))
        self.assertFalse(remote.version_editable("1", run=_run({})))

    def test_version_state_uses_include_build_envelope(self):
        # 5.17.1: `versions view` KHÔNG --include in summary rút gọn ⇒ phải xin envelope.
        run = _run({"appVersionState": "PREPARE_FOR_SUBMISSION"})
        self.assertEqual(remote.version_state("1.12.0", run=run), "PREPARE_FOR_SUBMISSION")
        self.assertEqual(run.calls[0], ["versions", "view", "--app", _testenv.FAKE_APP_ID,
                                        "--version", "1.12.0", "--include", "build"])

    def test_version_state_accepts_reduced_summary(self):
        for shape in ({"id": "v1", "versionString": "1.12.0", "platform": "IOS", "state": "PREPARE_FOR_SUBMISSION"},
                      {"data": {"id": "v1", "versionString": "1.12.0", "state": "PREPARE_FOR_SUBMISSION"}}):
            with self.subTest(shape):
                self.assertEqual(remote.version_state("1.12.0", run=lambda a, s=shape, **k: s),
                                 "PREPARE_FOR_SUBMISSION")
                self.assertTrue(remote.version_editable("1.12.0", run=lambda a, s=shape, **k: s))
        sale = {"id": "v1", "state": "READY_FOR_SALE"}
        self.assertFalse(remote.version_editable("1", run=lambda a, **k: sale))

    def test_version_state_unknown_shapes_none(self):
        for shape in ({"state": 3}, {"data": {"state": None}}, {"data": "x"}, [], "PREPARE_FOR_SUBMISSION",
                      {"data": {"attributes": "x"}}):
            with self.subTest(shape):
                self.assertIsNone(remote.version_state("1", run=lambda a, s=shape, **k: s))


if __name__ == "__main__":
    unittest.main()
