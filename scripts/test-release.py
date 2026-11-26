#!/usr/bin/env python3
"""Exercise release guards without publishing or contacting GitHub."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class ReleaseGuards(unittest.TestCase):
    def setUp(self):
        self.original_directory = Path.cwd()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        (self.root / "dist").mkdir()
        (self.root / "Templates").mkdir()
        for name in ("prepare-release.py", "publish-release.py"):
            shutil.copyfile(ROOT / "scripts" / name, self.root / "scripts" / name)
        shutil.copyfile(ROOT / "release.json", self.root / "release.json")
        shutil.copyfile(ROOT / "Templates/Package.template", self.root / "Templates/Package.template")
        self.config = json.loads((self.root / "release.json").read_text())
        self.environment = patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": self.config["repository"],
            "RELEASE_BRANCH": "test", "EXPECTED_REVISION": "expected",
        })
        self.environment.start()

    def tearDown(self):
        os.chdir(self.original_directory)
        self.environment.stop()
        self.temporary.cleanup()

    def check_git(self, args, **kwargs):
        self.assertIn(args[:2], [("git", "rev-parse"), ("git", "status"), ("git", "ls-remote")])
        if args[1] == "rev-parse":
            return "expected"
        if args[1] == "status":
            return ""
        if args[-1].startswith("refs/heads/"):
            return self.remote_head + "\t" + args[-1]
        return self.remote_tag

    def assert_publish_rejected(self, message):
        with patch("subprocess.check_output", side_effect=self.check_git), patch("subprocess.run") as mutation:
            with self.assertRaisesRegex(AssertionError, message):
                runpy.run_path(str(self.root / "scripts/publish-release.py"), run_name="__main__")
            mutation.assert_not_called()

    def test_moved_branch_does_not_publish(self):
        self.remote_head, self.remote_tag = "newer", ""
        self.assert_publish_rejected("Branch moved")

    def test_existing_tag_is_never_replaced(self):
        self.remote_head, self.remote_tag = "expected", "existing-tag"
        self.assert_publish_rejected("Version already exists")

    def test_dirty_build_does_not_publish(self):
        self.remote_head, self.remote_tag = "expected", ""
        (self.root / "dist/BUILD_INFO.json").write_text(json.dumps({
            "wrapper_revision": "expected", "wrapper_dirty": True,
        }))
        self.assert_publish_rejected("")

    def test_modified_archive_does_not_change_manifest(self):
        (self.root / "Package.swift").write_text("original")
        (self.root / "dist/HevSocks5Tunnel.xcframework.zip").write_bytes(b"changed")
        (self.root / "dist/BUILD_INFO.json").write_text(json.dumps({
            "core_revision": self.config["core_revision"], "wrapper_version": self.config["version"],
            "sha256": hashlib.sha256(b"original").hexdigest(),
        }))
        with self.assertRaisesRegex(AssertionError, "Archive changed"):
            runpy.run_path(str(self.root / "scripts/prepare-release.py"), run_name="__main__")
        self.assertEqual((self.root / "Package.swift").read_text(), "original")


if __name__ == "__main__":
    unittest.main()
