from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare-lock.sh"


class PendingLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.commit_lock("original")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, text=True, check=True, capture_output=True).stdout.strip()

    def commit_lock(self, value):
        (self.root / "flake.lock").write_text(value)
        self.git("add", "flake.lock")
        self.git("commit", "-m", value)

    def make_pending(self):
        self.git("switch", "-c", "update")
        self.commit_lock("pending")
        self.git("update-ref", "refs/remotes/origin/automation/update-magpie", "HEAD")
        self.git("switch", "main")

    def prepare(self):
        subprocess.run(["bash", str(SCRIPT)], cwd=self.root, check=True, capture_output=True)
        return (self.root / "flake.lock").read_text()

    def test_without_pending_branch(self):
        self.assertEqual(self.prepare(), "original")

    def test_preserve_pending_dependency_update(self):
        self.make_pending()
        self.assertEqual(self.prepare(), "pending")

    def test_main_dependency_update_takes_precedence(self):
        self.make_pending()
        self.commit_lock("newer main")
        self.assertEqual(self.prepare(), "newer main")

    def test_merged_branch_is_ignored(self):
        self.make_pending()
        self.git("merge", "--ff-only", "update")
        self.assertEqual(self.prepare(), "pending")


if __name__ == "__main__":
    unittest.main()
