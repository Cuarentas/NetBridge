import Foundation
import FlutterMacOS

/// macOS：启动内置 sing-box/xray，并尽量设置系统 HTTP 代理
class VpnPlugin: NSObject, FlutterPlugin {
    private var process: Process?
    private var confURL: URL?

    static func register(with registrar: FlutterPluginRegistrar) {
        let ch = FlutterMethodChannel(name: "com.netbridge/vpn", binaryMessenger: registrar.messenger)
        let inst = VpnPlugin()
        registrar.addMethodCallDelegate(inst, channel: ch)
    }

    public func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        switch call.method {
        case "prepare":
            result(true)
        case "start":
            guard let args = call.arguments as? [String: Any],
                  let core = args["core"] as? String,
                  let config = args["config"] as? String else {
                result(FlutterError(code: "bad_args", message: nil, details: nil))
                return
            }
            do {
                try startCore(core: core, config: config)
                setSystemProxy(enabled: true, port: 7890)
                result("macos-core-started")
            } catch {
                result(FlutterError(code: "start_failed", message: error.localizedDescription, details: nil))
            }
        case "stop":
            stopCore()
            setSystemProxy(enabled: false, port: 7890)
            result(nil)
        case "status":
            result(process?.isRunning == true ? "running" : "stopped")
        default:
            result(FlutterMethodNotImplemented)
        }
    }

    private func corePath(_ name: String) -> URL {
        // 优先 App 内 Resources/core/bin
        if let res = Bundle.main.resourceURL?.appendingPathComponent("core/bin/\(name)"),
           FileManager.default.fileExists(atPath: res.path) {
            return res
        }
        return Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/core/bin/\(name)")
    }

    private func startCore(core: String, config: String) throws {
        stopCore()
        let binName = (core == "xray") ? "xray" : "sing-box"
        let bin = corePath(binName)
        guard FileManager.default.fileExists(atPath: bin.path) else {
            throw NSError(domain: "NetBridge", code: 1, userInfo: [NSLocalizedDescriptionKey: "核心不存在: \(bin.path)"])
        }
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            .appendingPathComponent("NetBridge", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let conf = dir.appendingPathComponent("config.json")
        try config.write(to: conf, atomically: true, encoding: .utf8)
        confURL = conf

        let p = Process()
        p.executableURL = bin
        if core == "xray" {
            p.arguments = ["run", "-c", conf.path]
        } else {
            p.arguments = ["run", "-c", conf.path]
        }
        p.currentDirectoryURL = dir
        try p.run()
        process = p
    }

    private func stopCore() {
        process?.terminate()
        process = nil
    }

    private func setSystemProxy(enabled: Bool, port: Int) {
        let services = ["Wi-Fi", "Ethernet"]
        for s in services {
            if enabled {
                run(["networksetup", "-setwebproxy", s, "127.0.0.1", "\(port)"])
                run(["networksetup", "-setsecurewebproxy", s, "127.0.0.1", "\(port)"])
                run(["networksetup", "-setsocksfirewallproxy", s, "127.0.0.1", "\(port)"])
            } else {
                run(["networksetup", "-setwebproxystate", s, "off"])
                run(["networksetup", "-setsecurewebproxystate", s, "off"])
                run(["networksetup", "-setsocksfirewallproxystate", s, "off"])
            }
        }
    }

    private func run(_ args: [String]) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = args
        try? p.run()
        p.waitUntilExit()
    }
}
