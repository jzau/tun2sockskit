#!/usr/bin/env python3
"""Render the package from the exact archive that will be uploaded."""
import hashlib
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parent.parent
config = json.loads((root / "release.json").read_text())
assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", config["version"]), "Invalid version"
archive = root / "dist/HevSocks5Tunnel.xcframework.zip"
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
info = json.loads((root / "dist/BUILD_INFO.json").read_text())
assert info["core_revision"] == config["core_revision"]
assert info["wrapper_version"] == config["version"]
assert info["sha256"] == checksum, "Archive changed after build"
template = (root / "Templates/Package.template").read_text()
(root / "Package.swift").write_text(template.replace("VERSION", config["version"]).replace("CHECKSUM", checksum))
print(f"Prepared {config['version']} using {checksum}")
