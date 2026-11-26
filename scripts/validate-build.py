#!/usr/bin/env python3
"""Typecheck the wrapper for every slice, then stress the real host core."""
import json
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
framework = root / "dist/HevSocks5Tunnel.xcframework"
info = plistlib.loads((framework / "Info.plist").read_bytes())
work = root / ".build/validation"
work.mkdir(parents=True, exist_ok=True)
source = root / "Sources/Tun2SocksKit/Tunnel.swift"
shim = root / "Sources/Tun2SocksKitC"
# SwiftPM synthesizes a module map because this target's custom map has a
# nonstandard filename. Do the same when compiling without SwiftPM.
shim_module = work / "shim"
shim_module.mkdir(exist_ok=True)
(shim_module / "module.modulemap").write_text(
    f'module Tun2SocksKitC {{ header "{shim / "Tun2SocksKitC.h"}" export * }}\n')

host_library = None
host_headers = None
for library in info["AvailableLibraries"]:
    directory = framework / library["LibraryIdentifier"]
    headers = directory / library["HeadersPath"]
    for arch in library["SupportedArchitectures"]:
        variant = library.get("SupportedPlatformVariant")
        if library["SupportedPlatform"] == "macos":
            sdk, triple = "macosx", f"{arch}-apple-macos12.0"
            if arch == platform.machine():
                host_library = directory / library["LibraryPath"]
                host_headers = headers
        elif variant == "maccatalyst":
            sdk, triple = "macosx", f"{arch}-apple-ios13.1-macabi"
        elif variant == "simulator":
            sdk, triple = "iphonesimulator", f"{arch}-apple-ios12.0-simulator"
        else:
            sdk, triple = "iphoneos", f"{arch}-apple-ios12.0"
        sdk_path = subprocess.check_output(["xcrun", "--sdk", sdk, "--show-sdk-path"], text=True).strip()
        subprocess.run(["xcrun", "swiftc", "-typecheck", "-target", triple, "-sdk", sdk_path,
                        "-I", str(headers), "-I", str(shim_module), str(source)], check=True)
        print(f"PASS: {triple}", flush=True)
assert host_library, "No native host slice"
executable = work / "lifecycle-tests"
subprocess.run(["xcrun", "swiftc", "-I", str(host_headers), "-I", str(shim_module),
                str(source), str(root / "Tests/Native/main.swift"), str(host_library),
                "-o", str(executable)], check=True)
subprocess.run([str(executable)], check=True, timeout=45)
config = json.loads((root / "release.json").read_text())
provenance = json.loads((root / "dist/BUILD_INFO.json").read_text())
assert provenance["core_revision"] == config["core_revision"]
print("PASS: provenance matches the pinned core")

# Resolve/build the actual SwiftPM targets with a local copy of the unpublished
# archive. This exercises SwiftPM's generated C module map and binary linkage.
with tempfile.TemporaryDirectory(prefix="tun2sockskit-package-") as temporary:
    package = Path(temporary)
    shutil.copytree(root / "Sources", package / "Sources")
    shutil.copytree(framework, package / framework.name)
    manifest = (root / "Package.swift").read_text()
    manifest, replacements = re.subn(
        r'url: "https://[^\"]+",\s*checksum: "[a-f0-9]+"',
        'path: "HevSocks5Tunnel.xcframework"', manifest)
    assert replacements == 1, "Expected exactly one remote binary target"
    (package / "Package.swift").write_text(manifest)
    subprocess.run(["swift", "build", "--package-path", str(package)], check=True, timeout=120)
print("PASS: SwiftPM package builds with the new local XCFramework")
