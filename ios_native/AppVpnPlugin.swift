import Flutter
import UIKit
import NetworkExtension

/// App 侧：通过 NETunnelProviderManager 启动扩展
class AppVpnPlugin: NSObject, FlutterPlugin {
    static func register(with registrar: FlutterPluginRegistrar) {
        let ch = FlutterMethodChannel(name: "com.netbridge/vpn", binaryMessenger: registrar.messenger())
        registrar.addMethodCallDelegate(AppVpnPlugin(), channel: ch)
    }

    func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        switch call.method {
        case "prepare":
            result(true)
        case "start":
            // 保存配置到 App Group 供 Extension 读取（需配置 App Group）
            if let args = call.arguments as? [String: Any],
               let config = args["config"] as? String {
                UserDefaults.standard.set(config, forKey: "netbridge_config")
            }
            NETunnelProviderManager.loadAllFromPreferences { managers, error in
                if let error = error {
                    result(FlutterError(code: "load", message: error.localizedDescription, details: nil))
                    return
                }
                let mgr = managers?.first ?? NETunnelProviderManager()
                let proto = NETunnelProviderProtocol()
                proto.providerBundleIdentifier = "com.netbridge.netbridge.Tunnel"
                proto.serverAddress = "NetBridge"
                mgr.protocolConfiguration = proto
                mgr.localizedDescription = "NetBridge"
                mgr.isEnabled = true
                mgr.saveToPreferences { err in
                    if let err = err {
                        result(FlutterError(code: "save", message: err.localizedDescription, details: nil))
                        return
                    }
                    do {
                        try mgr.connection.startVPNTunnel()
                        result("ios-tunnel-start")
                    } catch {
                        result(FlutterError(code: "start", message: error.localizedDescription, details: nil))
                    }
                }
            }
        case "stop":
            NETunnelProviderManager.loadAllFromPreferences { managers, _ in
                managers?.forEach { $0.connection.stopVPNTunnel() }
                result(nil)
            }
        case "status":
            result("unknown")
        default:
            result(FlutterMethodNotImplemented)
        }
    }
}
