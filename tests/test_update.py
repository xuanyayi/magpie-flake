import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("updater", Path(__file__).resolve().parents[1] / "scripts/update.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = {
            "version": "0.1.1294", "rev": "a" * 40,
            "hash": updater.FAKE_HASH, "vendorHash": updater.FAKE_HASH,
        }
        (self.root / "sources.json").write_text(json.dumps(self.source))
        (self.root / "flake.lock").write_text('{"version":7}\n')
        self.before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        root_patch = patch.object(updater, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def test_latest_tag_does_not_require_a_release_entry(self):
        refs = "\n".join([
            "a" * 40 + "\trefs/tags/v0.1.999",
            "b" * 40 + "\trefs/tags/v0.1.1295",
            "c" * 40 + "\trefs/tags/v0.1.1295^{}",
            "d" * 40 + "\trefs/tags/v0.1.1296-rc1",
            "e" * 40 + "\trefs/tags/v0.1.1294",
        ])
        with patch.object(updater, "run", return_value=subprocess.CompletedProcess([], 0, refs, "")):
            self.assertEqual(updater.latest_tag(), ("0.1.1295", "c" * 40))

    def test_lightweight_tag(self):
        refs = "b" * 40 + "\trefs/tags/v0.1.1295\n"
        with patch.object(updater, "run", return_value=subprocess.CompletedProcess([], 0, refs, "")):
            self.assertEqual(updater.latest_tag(), ("0.1.1295", "b" * 40))

    def test_no_version_tag_rejected(self):
        with patch.object(updater, "run", return_value=subprocess.CompletedProcess([], 0, "", "")), self.assertRaisesRegex(ValueError, "no vX.Y.Z"):
            updater.latest_tag()

    def test_downgrade_and_moved_tag_rejected(self):
        for version, rev in [("0.1.999", "b" * 40), ("0.1.1294", "b" * 40)]:
            with self.subTest(version=version), self.assertRaises(ValueError):
                updater.check_release(self.source, version, rev)

    def test_unchanged_does_not_build(self):
        with patch.object(updater, "latest_tag", return_value=("0.1.1294", "a" * 40)), patch.object(updater, "run") as run:
            self.assertFalse(updater.update())
            run.assert_not_called()

    def test_failed_update_restores_both_files(self):
        def run(*args, **kwargs):
            if args[:3] == ("nix", "flake", "update"):
                (self.root / "flake.lock").write_text("new lock")
                return subprocess.CompletedProcess(args, 0, "", "")
            return subprocess.CompletedProcess(args, 0, json.dumps({"hash": updater.FAKE_HASH}), "")

        with patch.object(updater, "latest_tag", return_value=("0.1.1295", "b" * 40)), patch.object(updater, "run", side_effect=run), patch.object(updater, "vendor_hash", side_effect=RuntimeError("patch no longer applies")):
            with self.assertRaisesRegex(RuntimeError, "patch no longer applies"):
                updater.update(update_nixpkgs=True)
        for name, content in self.before.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_success_verifies_vendor_hash(self):
        new_hash = "sha256-" + "B" * 43 + "="
        command = ("nix", "build", "test-vendor")
        with patch.object(updater, "latest_tag", return_value=("0.1.1295", "b" * 40)), patch.object(updater, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps({"hash": updater.FAKE_HASH}), "")) as run, patch.object(updater, "vendor_hash", return_value=(new_hash, command)):
            self.assertTrue(updater.update())
            run.assert_any_call(*command)
        source = json.loads((self.root / "sources.json").read_text())
        self.assertEqual(source["version"], "0.1.1295")
        self.assertEqual(source["vendorHash"], new_hash)

    def test_build_failure_is_not_mistaken_for_hash_mismatch(self):
        results = [
            subprocess.CompletedProcess([], 0, "x86_64-linux", ""),
            subprocess.CompletedProcess([], 1, "", "patch failed"),
        ]
        with patch.object(updater, "run", side_effect=results), self.assertRaisesRegex(RuntimeError, "could not determine vendorHash"):
            updater.vendor_hash()


if __name__ == "__main__":
    unittest.main()
