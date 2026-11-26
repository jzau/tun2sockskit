#!/usr/bin/env python3
"""Publish only the archive validated by the build job. Run via Actions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
os.chdir(root)


def run(*args):
    return subprocess.check_output(args, text=True).strip()


config = json.loads((root / "release.json").read_text())
version = config["version"]
branch = os.environ["RELEASE_BRANCH"]
expected = os.environ["EXPECTED_REVISION"]
assert os.environ.get("GITHUB_ACTIONS") == "true", "Publish via the manual release workflow"
assert os.environ["GITHUB_REPOSITORY"].lower() == config["repository"].lower()
assert run("git", "rev-parse", "HEAD") == expected
assert not run("git", "status", "--porcelain", "--untracked-files=no"), "Checkout must be clean"
assert run("git", "ls-remote", "origin", f"refs/heads/{branch}").split()[0] == expected, "Branch moved; rebuild"
assert not run("git", "ls-remote", "origin", f"refs/tags/{version}"), "Version already exists; do not replace release assets"
info = json.loads((root / "dist/BUILD_INFO.json").read_text())
assert info["wrapper_revision"] == expected and not info["wrapper_dirty"]
subprocess.run(["python3", "scripts/prepare-release.py"], check=True)
assert (root / "Package.swift").read_bytes() == (root / "dist/Package.swift").read_bytes()
run("git", "config", "user.name", "github-actions[bot]")
run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
run("git", "add", "Package.swift")
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode:
    run("git", "commit", "-m", f"Release Tun2SocksKit {version} (hev {config['core_version']})")
run("git", "tag", "-a", version, "-m", f"Tun2SocksKit {version}; hev {config['core_revision']}")
run("git", "push", "--atomic", "origin", f"HEAD:refs/heads/{branch}", f"refs/tags/{version}")
notes = (f"Built from hev-socks5-tunnel {config['core_version']} ({config['core_revision']}).\n\n"
         "Real iOS simulator core; iOS, macOS and Mac Catalyst. See BUILD_INFO.json for submodule and SDK revisions.\n"
         "The existing run(withConfig: String) API remains supported.\n")
with tempfile.TemporaryDirectory() as temp:
    notes_path = Path(temp) / "notes.md"
    notes_path.write_text(notes)
    run("gh", "release", "create", version, "dist/HevSocks5Tunnel.xcframework.zip", "dist/BUILD_INFO.json",
        "--repo", config["repository"], "--verify-tag", "--draft", "--title", version,
        "--notes-file", str(notes_path))
    run("gh", "release", "download", version, "--repo", config["repository"],
        "--pattern", "HevSocks5Tunnel.xcframework.zip", "--dir", temp)
    downloaded = Path(temp) / "HevSocks5Tunnel.xcframework.zip"
    assert hashlib.sha256(downloaded.read_bytes()).hexdigest() == info["sha256"], "Uploaded checksum mismatch"
run("gh", "release", "edit", version, "--repo", config["repository"], "--draft=false", "--latest")
