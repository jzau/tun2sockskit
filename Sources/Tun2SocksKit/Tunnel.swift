import Foundation
import Tun2SocksKitC
import HevSocks5Tunnel

public enum Socks5Tunnel {
    public enum Config {
        case file(path: URL)
        case string(content: String)
    }
    
    private static var tunnelFileDescriptor: Int32? {
        var ctlInfo = ctl_info()
        withUnsafeMutablePointer(to: &ctlInfo.ctl_name) {
            $0.withMemoryRebound(to: CChar.self, capacity: MemoryLayout.size(ofValue: $0.pointee)) {
                _ = strcpy($0, "com.apple.net.utun_control")
            }
        }
        for fd: Int32 in 0...1024 {
            var addr = sockaddr_ctl()
            var ret: Int32 = -1
            var len = socklen_t(MemoryLayout.size(ofValue: addr))
            withUnsafeMutablePointer(to: &addr) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    ret = getpeername(fd, $0, &len)
                }
            }
            if ret != 0 || addr.sc_family != AF_SYSTEM {
                continue
            }
            if ctlInfo.ctl_id == 0 {
                ret = ioctl(fd, CTLIOCGINFO, &ctlInfo)
                if ret != 0 {
                    continue
                }
            }
            if addr.sc_id == ctlInfo.ctl_id {
                return fd
            }
        }
        return nil
    }
    
    private static var interfaceName: String? {
        guard let tunnelFileDescriptor = self.tunnelFileDescriptor else {
            return nil
        }
        var buffer = [UInt8](repeating: 0, count: Int(IFNAMSIZ))
        return buffer.withUnsafeMutableBufferPointer { mutableBufferPointer in
            guard let baseAddress = mutableBufferPointer.baseAddress else {
                return nil
            }
            var ifnameSize = socklen_t(IFNAMSIZ)
            let result = getsockopt(
                tunnelFileDescriptor,
                2 /* SYSPROTO_CONTROL */,
                2 /* UTUN_OPT_IFNAME */,
                baseAddress,
                &ifnameSize
            )
            if result == 0 {
                return String(cString: baseAddress)
            } else {
                return nil
            }
        }
    }
    
    @discardableResult
    public static func run(withConfig filePath: String) -> Int32 {
        run(withConfig: .file(path: URL(fileURLWithPath: filePath)))
    }

    /// Blocks until shutdown or an error. The caller owns thread and lifecycle coordination.
    @discardableResult
    public static func run(withConfig config: Config) -> Int32 {
        guard let fileDescriptor = self.tunnelFileDescriptor else {
            return -1
        }
        return run(withFileDescriptor: fileDescriptor, config: config)
    }

    /// Runs on a caller-owned descriptor, which the core does not close.
    /// Only one run may be active in the process, including during cleanup.
    @discardableResult
    public static func run(withFileDescriptor fileDescriptor: Int32, config: Config) -> Int32 {
        guard fileDescriptor >= 0 else { return -1 }
        switch config {
        case .file(let path):
            guard path.isFileURL else { return -1 }
            return path.path.withCString { hev_socks5_tunnel_main($0, fileDescriptor) }
        case .string(let content):
            // The C API takes a UTF-8 byte count, not Swift's character count.
            // Keep a non-null buffer even for empty input (libyaml requires it).
            let bytes = Array(content.utf8) + [0]
            guard let length = UInt32(exactly: bytes.count - 1) else { return -1 }
            return bytes.withUnsafeBufferPointer {
                hev_socks5_tunnel_main_from_str($0.baseAddress, length, fileDescriptor)
            }
        }
    }
    
    /// Requests shutdown; wait for run() to return before starting another run.
    /// Do not call while idle: the core latches an early stop for the next run.
    public static func quit() {
        hev_socks5_tunnel_quit()
    }
}
