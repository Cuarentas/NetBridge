import 'dart:convert';
import 'package:flutter/material.dart';
import 'vpn_bridge.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NetBridgeApp());
}

enum Conn { off, connecting, on, err }

class NetBridgeApp extends StatefulWidget {
  const NetBridgeApp({super.key});
  @override
  State<NetBridgeApp> createState() => _NetBridgeAppState();
}

class _NetBridgeAppState extends State<NetBridgeApp> {
  Conn conn = Conn.off;
  String core = 'sing-box';
  String message = '添加节点后连接 · 将走本机 VPN/代理核心';
  final serverCtrl = TextEditingController();
  final portCtrl = TextEditingController(text: '443');
  final uuidCtrl = TextEditingController();
  final sniCtrl = TextEditingController();
  String protocol = 'vless';
  String network = 'tcp';
  bool reality = false;
  final pbkCtrl = TextEditingController();
  final sidCtrl = TextEditingController();

  Color get btnColor {
    switch (conn) {
      case Conn.off:
        return const Color(0xFF007AFF);
      case Conn.connecting:
        return const Color(0xFFFF9500);
      case Conn.on:
        return const Color(0xFF34C759);
      case Conn.err:
        return const Color(0xFFFF3B30);
    }
  }

  String get btnText {
    switch (conn) {
      case Conn.off:
        return '连接';
      case Conn.connecting:
        return '...';
      case Conn.on:
        return '已连接';
      case Conn.err:
        return '重试';
    }
  }

  Map<String, dynamic> _singboxConfig() {
    final port = int.tryParse(portCtrl.text) ?? 443;
    final outbound = <String, dynamic>{
      'type': protocol == 'ss' ? 'shadowsocks' : protocol,
      'tag': 'proxy',
      'server': serverCtrl.text.trim(),
      'server_port': port,
    };
    if (protocol == 'ss') {
      outbound['method'] = 'aes-256-gcm';
      outbound['password'] = uuidCtrl.text.trim();
    } else if (protocol == 'vmess') {
      outbound['uuid'] = uuidCtrl.text.trim();
      outbound['security'] = 'auto';
      outbound['alter_id'] = 0;
    } else if (protocol == 'vless') {
      outbound['uuid'] = uuidCtrl.text.trim();
    } else if (protocol == 'trojan') {
      outbound['password'] = uuidCtrl.text.trim();
    }
    if (reality || sniCtrl.text.isNotEmpty) {
      final tls = <String, dynamic>{
        'enabled': true,
        'server_name': sniCtrl.text.isEmpty ? serverCtrl.text.trim() : sniCtrl.text.trim(),
      };
      if (reality) {
        tls['reality'] = {
          'enabled': true,
          'public_key': pbkCtrl.text.trim(),
          'short_id': sidCtrl.text.trim(),
        };
        tls['utls'] = {'enabled': true, 'fingerprint': 'chrome'};
      }
      outbound['tls'] = tls;
    }
    if (network == 'ws') {
      outbound['transport'] = {'type': 'ws', 'path': '/'};
    } else if (network == 'grpc') {
      outbound['transport'] = {'type': 'grpc', 'service_name': 'GunService'};
    }
    return {
      'log': {'level': 'info'},
      'inbounds': [
        {
          'type': 'tun',
          'tag': 'tun-in',
          'inet4_address': '172.19.0.1/30',
          'auto_route': true,
          'strict_route': true,
          'stack': 'system',
          'sniff': true,
        },
        {
          'type': 'mixed',
          'tag': 'mixed-in',
          'listen': '127.0.0.1',
          'listen_port': 7890,
          'sniff': true,
        }
      ],
      'outbounds': [
        outbound,
        {'type': 'direct', 'tag': 'direct'},
        {'type': 'block', 'tag': 'block'},
      ],
      'route': {'final': 'proxy', 'auto_detect_interface': true},
    };
  }

  Future<void> toggle() async {
    if (conn == Conn.on) {
      await VpnBridge.stop();
      setState(() {
        conn = Conn.off;
        message = '已断开';
      });
      return;
    }
    if (serverCtrl.text.trim().isEmpty) {
      setState(() => message = '请填写服务器地址');
      return;
    }
    setState(() {
      conn = Conn.connecting;
      message = '正在请求 VPN 权限并启动核心...';
    });
    try {
      final ok = await VpnBridge.prepare();
      if (!ok) {
        setState(() {
          conn = Conn.err;
          message = '用户拒绝 VPN 权限';
        });
        return;
      }
      final cfg = jsonEncode(_singboxConfig());
      final r = await VpnBridge.start(core: core, configJson: cfg);
      setState(() {
        conn = Conn.on;
        message = '已连接 · $r';
      });
    } catch (e) {
      setState(() {
        conn = Conn.err;
        message = '失败: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NetBridge',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: const Color(0xFF007AFF),
        scaffoldBackgroundColor: const Color(0xFFF2F2F7),
      ),
      home: Scaffold(
        appBar: AppBar(title: const Text('NetBridge VPN'), centerTitle: true),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // connect button
              Center(
                child: GestureDetector(
                  onTap: toggle,
                  child: Container(
                    width: 150,
                    height: 150,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: btnColor,
                      boxShadow: [
                        BoxShadow(color: btnColor.withOpacity(0.35), blurRadius: 20, offset: const Offset(0, 8)),
                      ],
                    ),
                    child: conn == Conn.connecting
                        ? const CircularProgressIndicator(color: Colors.white)
                        : Text(btnText, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w600)),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Text(message, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF8E8E93))),
              const SizedBox(height: 16),
              Row(
                children: [
                  const Text('核心'),
                  const SizedBox(width: 12),
                  ChoiceChip(
                    label: const Text('sing-box'),
                    selected: core == 'sing-box',
                    onSelected: (_) => setState(() => core = 'sing-box'),
                  ),
                  const SizedBox(width: 8),
                  ChoiceChip(
                    label: const Text('Xray'),
                    selected: core == 'xray',
                    onSelected: (_) => setState(() => core = 'xray'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(controller: serverCtrl, decoration: const InputDecoration(labelText: '服务器', border: OutlineInputBorder())),
              const SizedBox(height: 8),
              TextField(controller: portCtrl, decoration: const InputDecoration(labelText: '端口', border: OutlineInputBorder()), keyboardType: TextInputType.number),
              const SizedBox(height: 8),
              TextField(controller: uuidCtrl, decoration: const InputDecoration(labelText: 'UUID / 密码', border: OutlineInputBorder())),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                value: protocol,
                items: const [
                  DropdownMenuItem(value: 'vless', child: Text('VLESS')),
                  DropdownMenuItem(value: 'vmess', child: Text('VMess')),
                  DropdownMenuItem(value: 'trojan', child: Text('Trojan')),
                  DropdownMenuItem(value: 'ss', child: Text('Shadowsocks')),
                ],
                onChanged: (v) => setState(() => protocol = v ?? 'vless'),
                decoration: const InputDecoration(labelText: '协议', border: OutlineInputBorder()),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                value: network,
                items: const [
                  DropdownMenuItem(value: 'tcp', child: Text('TCP')),
                  DropdownMenuItem(value: 'ws', child: Text('WebSocket')),
                  DropdownMenuItem(value: 'grpc', child: Text('gRPC')),
                ],
                onChanged: (v) => setState(() => network = v ?? 'tcp'),
                decoration: const InputDecoration(labelText: '传输', border: OutlineInputBorder()),
              ),
              const SizedBox(height: 8),
              TextField(controller: sniCtrl, decoration: const InputDecoration(labelText: 'SNI（可选）', border: OutlineInputBorder())),
              SwitchListTile(
                title: const Text('Reality'),
                value: reality,
                onChanged: (v) => setState(() => reality = v),
              ),
              if (reality) ...[
                TextField(controller: pbkCtrl, decoration: const InputDecoration(labelText: 'Reality pbk', border: OutlineInputBorder())),
                const SizedBox(height: 8),
                TextField(controller: sidCtrl, decoration: const InputDecoration(labelText: 'Reality sid', border: OutlineInputBorder())),
              ],
              const SizedBox(height: 12),
              const Text(
                'Android：系统 VPN 权限 + 内置核心\n'
                'macOS：启动核心并设置系统代理 / TUN\n'
                'iOS：Network Extension（需签名）',
                style: TextStyle(fontSize: 12, color: Color(0xFF8E8E93)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
