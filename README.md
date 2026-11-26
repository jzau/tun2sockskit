# Tun2SocksKit

Swift wrapper and Apple XCFramework build for [hev-socks5-tunnel](https://github.com/heiher/hev-socks5-tunnel).

Version **2.8.0** packages core **2.20.0**, pinned to
`75dbc1e9ace6c70d3d1b94df7c283efe1de7effc` and its recorded submodule commits.
Supports iOS 12+, macOS 12+, and Mac Catalyst 13.1+. The arm64/x86_64
simulator slices contain the real core, rather than placeholder functions.

## Usage

Existing string-path calls remain supported:

```swift
import Tun2SocksKit

let result = Socks5Tunnel.run(withConfig: localConfigFileURL.path)
```

New typed configuration and explicit descriptor APIs:

```swift
let result = Socks5Tunnel.run(withConfig: .file(path: localConfigFileURL))
let result = Socks5Tunnel.run(withConfig: .string(content: yaml))
// Prefer the explicit API when the caller already has its TUN descriptor.
let result = Socks5Tunnel.run(withFileDescriptor: fd, config: .string(content: yaml))
```

All run calls **block until shutdown or failure**. Return value is 0 on normal
completion and -1 on error, including failure to discover a TUN descriptor.
Run on a caller-owned dedicated thread. Only one run may exist per process;
serialize replacement runs until the previous call has returned.

`Socks5Tunnel.quit()` requests shutdown, including during native initialization.
It does not wait for cleanup. Call it only for a committed/current run: the
native core remembers an early stop and can otherwise cancel a future run.
The explicit descriptor remains owned by the caller and is not closed by the core.

The simulator core is useful for integration tests, but does not create an iOS
VPN entitlement or a packet-flow descriptor for an ordinary simulator app.
Real-device Network Extension tests remain necessary.

## Configuration

```yaml
tunnel:
  mtu: 8500
socks5:
  port: 7890
  address: ::1
  udp: 'udp'
misc:
  task-stack-size: 24576
  tcp-buffer-size: 4096
  connect-timeout: 5000
  read-write-timeout: 60000
  log-file: stderr
  log-level: error
  limit-nofile: 65535
```

The core also supports `max-session-count`, `tcp-read-write-timeout`, and
`udp-read-write-timeout`. Choose session limits using the extension's measured
memory budget; the core's default session count is unlimited. See the
[core documentation](https://github.com/heiher/hev-socks5-tunnel/blob/2.20.0/README.md).

## Build and release

Requires macOS, full Xcode with iPhone/simulator SDKs, Python 3, Git, and Make.
`release.json` records the wrapper version and immutable native source revision.

```sh
python3 scripts/build-xcframework.py
python3 scripts/validate-build.py
python3 scripts/prepare-release.py
```

Outputs live under `dist/`: the XCFramework, its ZIP, and `BUILD_INFO.json`
with native/submodule revisions, SDK versions, and the ZIP checksum. Native
license notices are embedded in the XCFramework. Validation typechecks every
supported slice, builds the SwiftPM targets locally, and runs 100 real-core
lifecycle cases on the host Mac using caller-owned socketpairs.

`Package.swift` points at the corresponding GitHub release. Until that release
is published, use the local XCFramework for validation; the validation script
stages a temporary package automatically. Never replace assets on an existing
release: a new archive requires a new version and matching package checksum.

The manual **Release** workflow builds and validates first. With `publish`
unchecked it only uploads reviewable artifacts. With `publish` checked it also
commits the generated manifest on the selected branch, creates the version tag,
uploads a draft release, downloads and verifies the archive, then publishes it.
Publication fails if the source branch moved or the version tag already exists.
If upload fails after the tag was pushed, investigate the draft/tag before
retrying; do not overwrite the release asset or reuse its version automatically.

The release workflow pins the GitHub-hosted stable `macos-26` image with Xcode 26.6 and requires no
self-hosted runner, SSH configuration, or application-specific infrastructure.

See [the upstream review](docs/upstream-review.md) for adopted changes,
remaining lifecycle constraints, and integration checks.
