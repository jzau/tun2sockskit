import Foundation

// Link this executable to the actual macOS core, not a simulator stub.
// A socketpair models the caller-owned packet fd without requiring VPN privileges.
func require(_ value: @autoclosure () -> Bool, _ message: String) {
    guard value() else { fatalError(message) }
}

let configuration = """
# \(String(repeating: "隧道🙂", count: 100))
tunnel:
  mtu: 8500
socks5:
  address: ::1
  port: 7890
  udp: udp
misc:
  task-stack-size: 24576
  tcp-buffer-size: 4096
  max-session-count: 64
  log-level: error
"""

require(Socks5Tunnel.run(withFileDescriptor: -1, config: .string(content: configuration)) == -1,
        "Negative descriptors must not reach the native core")
require(Socks5Tunnel.run(withFileDescriptor: 0, config: .file(path: URL(string: "https://example.com")!)) == -1,
        "Non-file URLs must be rejected")
require(Socks5Tunnel.run(withFileDescriptor: 0, config: .string(content: "")) == -1,
        "Empty YAML must return an error without crashing")

let configURL = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".yaml")
try configuration.write(to: configURL, atomically: true, encoding: .utf8)
defer { try? FileManager.default.removeItem(at: configURL) }

for iteration in 0..<100 {
    var descriptors: [Int32] = [-1, -1]
    require(socketpair(AF_UNIX, SOCK_DGRAM, 0, &descriptors) == 0, "socketpair failed")
    let fd = descriptors[0]
    if iteration < 2 {
        // Early stop must survive startup; also exercises UTF-8 byte lengths.
        Socks5Tunnel.quit()
        let config: Socks5Tunnel.Config = iteration == 0 ? .string(content: configuration) : .file(path: configURL)
        require(Socks5Tunnel.run(withFileDescriptor: fd, config: config) == 0,
                "Early-stop run failed")
    } else {
        let entered = DispatchSemaphore(value: 0)
        let returned = DispatchSemaphore(value: 0)
        let worker = Thread {
            entered.signal()
            let result = Socks5Tunnel.run(withFileDescriptor: fd, config: .string(content: configuration))
            require(result == 0, "Native initialization failed")
            returned.signal()
        }
        worker.name = "Tun2SocksKit lifecycle test"
        worker.start()
        entered.wait()
        // Deterministic spread across initialization and the running loop.
        usleep(UInt32((iteration % 10) * 200))
        Socks5Tunnel.quit()
        require(returned.wait(timeout: .now() + 5) == .success, "Native shutdown timed out")
    }
    require(fcntl(fd, F_GETFD) >= 0, "Core closed the caller-owned descriptor")
    close(descriptors[0])
    close(descriptors[1])
}
print("PASS: 100 serial early-stop/start/stop runs, UTF-8/file config, caller fd ownership")
