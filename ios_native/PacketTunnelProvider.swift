import NetworkExtension

/// iOS Packet Tunnel — 需在 Xcode 中加入 Network Extension Target 并签名
class PacketTunnelProvider: NEPacketTunnelProvider {
    private var process: Process? // iOS 上不能随意起进程；正式应链入 libbox / 内嵌核心

    override func startTunnel(options: [String : NSObject]?, completionHandler: @escaping (Error?) -> Void) {
        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: "127.0.0.1")
        settings.ipv4Settings = NEIPv4Settings(addresses: ["10.0.0.2"], subnetMasks: ["255.255.255.252"])
        settings.ipv4Settings?.includedRoutes = [NEIPv4Route.default()]
        settings.dnsSettings = NEDNSSettings(servers: ["1.1.1.1"])
        setTunnelNetworkSettings(settings) { err in
            // TODO: 在此启动内嵌 sing-box（需 libbox 或可静态链接的核心）
            // 当前完成 VPN 隧道框架，核心集成需在 Xcode 链入二进制/库
            completionHandler(err)
        }
    }

    override func stopTunnel(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
        completionHandler()
    }
}
