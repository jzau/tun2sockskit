#!/usr/bin/env python3
"""Build the real pinned core for every supported Apple platform."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "release.json").read_text())


def run(*args, cwd=None, capture=False):
    result = subprocess.run(args, cwd=cwd, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Existing disposable core checkout")
    args = parser.parse_args()
    source = (args.source or ROOT / ".build/core").resolve()
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", CONFIG["core_repository"], str(source))
    # Never build a floating branch or silently discard source changes.
    run("git", "diff", "--exit-code", "HEAD", cwd=source)
    if run("git", "remote", "get-url", "origin", cwd=source, capture=True) != CONFIG["core_repository"]:
        sys.exit("Unexpected core repository")
    run("git", "checkout", "--detach", CONFIG["core_revision"], cwd=source)
    run("git", "submodule", "update", "--init", "--recursive", cwd=source)
    submodules = run("git", "submodule", "status", "--recursive", cwd=source, capture=True)
    if any(line.startswith(("-", "+", "U")) for line in submodules.splitlines()):
        sys.exit("Submodules do not match the pinned tree")
    run("git", "submodule", "foreach", "--recursive", "git diff --exit-code HEAD", cwd=source)

    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    work = ROOT / ".build/apple-libraries"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    framework = output / "HevSocks5Tunnel.xcframework"
    if framework.exists():
        shutil.rmtree(framework)

    # Use explicit triples and SDKs, including Catalyst and genuine simulator code.
    platforms = [
        ("ios-arm64", "iphoneos", "arm64", "arm64-apple-ios12.0"),
        ("sim-arm64", "iphonesimulator", "arm64", "arm64-apple-ios12.0-simulator"),
        ("sim-x86_64", "iphonesimulator", "x86_64", "x86_64-apple-ios12.0-simulator"),
        ("mac-arm64", "macosx", "arm64", "arm64-apple-macos12.0"),
        ("mac-x86_64", "macosx", "x86_64", "x86_64-apple-macos12.0"),
        ("catalyst-arm64", "macosx", "arm64", "arm64-apple-ios13.1-macabi"),
        ("catalyst-x86_64", "macosx", "x86_64", "x86_64-apple-ios13.1-macabi"),
    ]
    sdks = {}
    for name, sdk, arch, target in platforms:
        print(f"Building {name}", flush=True)
        sdk_path = run("xcrun", "--sdk", sdk, "--show-sdk-path", capture=True)
        sdks[sdk] = run("xcrun", "--sdk", sdk, "--show-sdk-version", capture=True)
        # The dependency Makefiles invoke the preprocessor separately.
        compiler = f"xcrun --sdk {sdk} clang"
        flags = f"-target {target} -isysroot {sdk_path}"
        run("make", "clean", cwd=source)
        run("make", f"-j{min(os.cpu_count() or 2, 8)}", f"PP={compiler}", f"CC={compiler}",
            f"CFLAGS={flags}", f"LFLAGS={flags}", "static", cwd=source)
        directory = work / name
        directory.mkdir()
        run("xcrun", "libtool", "-static", "-o", str(directory / "libhev-socks5-tunnel.a"),
            *[str(source / p) for p in [
                "bin/libhev-socks5-tunnel.a", "third-part/lwip/bin/liblwip.a",
                "third-part/yaml/bin/libyaml.a", "third-part/hev-task-system/bin/libhev-task-system.a"]])

    libraries = [work / "ios-arm64/libhev-socks5-tunnel.a"]
    for name in ("sim", "mac", "catalyst"):
        merged = work / f"{name}.a"
        run("xcrun", "lipo", "-create", str(work / f"{name}-arm64/libhev-socks5-tunnel.a"),
            str(work / f"{name}-x86_64/libhev-socks5-tunnel.a"), "-output", str(merged))
        libraries.append(merged)
    headers = work / "include"
    headers.mkdir()
    shutil.copyfile(source / "src/hev-main.h", headers / "hev-socks5-tunnel.h")
    shutil.copyfile(ROOT / "Templates/HevSocks5Tunnel.template", headers / "module.modulemap")
    command = ["xcodebuild", "-create-xcframework"]
    for library in libraries:
        command += ["-library", str(library), "-headers", str(headers)]
    run(*command, "-output", str(framework))

    # Distribute the native dependencies' license notices with the binary.
    licenses = framework / "LICENSES"
    licenses.mkdir()
    for name, path in [("hev-socks5-tunnel", "."), ("hev-socks5-core", "src/core"),
                       ("hev-task-system", "third-part/hev-task-system"),
                       ("lwip", "third-part/lwip"), ("yaml", "third-part/yaml")]:
        shutil.copyfile(source / path / "LICENSE", licenses / f"{name}.txt")
    info = {
        "wrapper_version": CONFIG["version"], "core_version": CONFIG["core_version"],
        "core_revision": run("git", "rev-parse", "HEAD", cwd=source, capture=True),
        "submodules": submodules.splitlines(),
        "wrapper_revision": run("git", "rev-parse", "HEAD", cwd=ROOT, capture=True),
        "wrapper_dirty": bool(run("git", "status", "--porcelain", cwd=ROOT, capture=True)),
        "xcode": run("xcodebuild", "-version", capture=True), "sdks": sdks,
        "simulator": "real core (not a stub)",
    }
    (framework / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n")
    archive = output / "HevSocks5Tunnel.xcframework.zip"
    if archive.exists():
        archive.unlink()
    run("ditto", "-c", "-k", "--keepParent", "--norsrc", str(framework), str(archive))
    info["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n")
    print(f"Built {archive}\nSHA256 {info['sha256']}")


if __name__ == "__main__":
    main()
