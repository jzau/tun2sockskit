# Upstream review (2026-11-26)

## Reviewed sources

- Existing fork: jzau/tun2sockskit, 2.7.6 / `3c6e3c724f6b0ec6b58861de2a5b2621dd182d1f`.
- Maintained wrapper: [EbrahimTahernejad/Tun2SocksKit](https://github.com/EbrahimTahernejad/Tun2SocksKit/tree/40ec5b39c22d9a8487cf33536ed50e4ac396d266), revision `40ec5b39c22d9a8487cf33536ed50e4ac396d266`.
- Native core: [heiher/hev-socks5-tunnel 2.20.0](https://github.com/heiher/hev-socks5-tunnel/tree/75dbc1e9ace6c70d3d1b94df7c283efe1de7effc).

Both wrapper repositories are standalone on GitHub; the fork began with an
import rather than shared Git ancestry. Comparisons are source/content reviews,
not a claim about an exact Git merge base. The maintained README credits arror.

The existing fork changed release download URLs, build platforms, runner type,
and `<sys/types.h>` for Xcode 16. Since its initial import its Swift tunnel
implementation had not changed. The old workflow built a floating native branch,
so the wrapper version alone cannot establish the old binary's exact core commit.

## Adopted

- Pinned native core 2.20.0, with submodules checked out at its gitlinks.
- File-URL and inline-string `Config` APIs, preserving `run(withConfig: String)`.
- Error return instead of process termination when descriptor discovery fails.
- Release provenance and checksum generation from the archive being uploaded.
- Explicit descriptor entry point, avoiding process-wide scanning where the
  caller already owns the correct TUN descriptor.
- UTF-8 byte length for inline YAML. The maintained wrapper passes Swift
  `content.count`, which can truncate non-ASCII input in the C parser.
- Real native simulator builds. Mac Catalyst support is retained from this fork.

The native initialization/shutdown fix is commit
[`31055abd`](https://github.com/heiher/hev-socks5-tunnel/commit/31055abd387e29cd0f45a3b3a57e12e7afe6081e),
first included in 2.17.0 and also present in 2.20.0. Source review and inspection
of the maintained release's iPhone ARM64 binary confirmed the atomic early-stop
handling. The old 2.7.6 binary has the earlier event-descriptor-only stop path.
2.20.0 also brings session-limit enforcement under churn, memory improvements,
and session-creation deadlock fixes relevant to an iOS extension.

## Deliberately omitted

- Upstream's global dispatch-queue run helper. Thread ownership and lifecycle
  coordination remain explicit responsibilities of the consuming application.
- The Swift stats property. Its underlying C counters are plain shared memory,
  with no snapshot synchronization. Adding a safe stats contract is separate work.
- CocoaPods changes, removed again by maintained upstream. This package uses SwiftPM.
- Upstream's removal of explicit platform declarations and Mac Catalyst support.
- Upstream's simulator stub (its run methods return -2 and quit does nothing).

The maintained `5.20.0` tag's manifest expects checksum `a915e2e7...`, whereas its
current ZIP hashes to `cef44848...`. Actual `swift package resolve` fails for
that tag and succeeds at corrected revision `40ec5b3`. This fork builds its own
archive and never republishes an existing version's binary.

## Lifecycle and integration

The native core is still a process-global singleton. Its early-stop latch
addresses lost shutdown during initialization; it is not a per-session token or
an acknowledgement that cleanup has completed. A `quit()` while idle can affect
the next run. Cancel queued starts in the caller, call native quit only for a committed run,
and wait for that run to return before replacement. No new
readiness callback or concurrent-run guarantee is claimed.

Version 2.8.0 preserves the existing string-path API and stays within the 2.x
version range. Applications can adopt the typed configuration or explicit-fd
entry points independently. Published releases contain no application code,
branding, private infrastructure configuration, or application-specific settings.

Applications using Network Extension should validate real-device rapid ON/OFF,
configuration reload/restart, TCP/UDP/DNS, descriptor stability, and memory
pressure under their own workload. Host socketpair lifecycle tests exercise
native startup/shutdown but do not prove iOS packet routing or Network Extension
lifecycle behavior.
