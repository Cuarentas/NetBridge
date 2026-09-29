import 'package:flutter/material.dart';

void main() {
  runApp(const NetBridgeApp());
}

enum ConnectStatus { disconnected, connecting, connected }

class NetBridgeApp extends StatefulWidget {
  const NetBridgeApp({super.key});

  @override
  State<NetBridgeApp> createState() => _NetBridgeAppState();
}

class _NetBridgeAppState extends State<NetBridgeApp> {
  ConnectStatus status = ConnectStatus.disconnected;
  String nodeName = '示例节点';
  String upload = '0 B/s';
  String download = '0 B/s';
  final nodes = <String>['示例节点', '节点 A', '节点 B'];
  int selected = 0;

  Color get btnColor {
    switch (status) {
      case ConnectStatus.disconnected:
        return const Color(0xFF007AFF);
      case ConnectStatus.connecting:
        return const Color(0xFFFF9500);
      case ConnectStatus.connected:
        return const Color(0xFF34C759);
    }
  }

  String get btnText {
    switch (status) {
      case ConnectStatus.disconnected:
        return '连接';
      case ConnectStatus.connecting:
        return '...';
      case ConnectStatus.connected:
        return '已连接';
    }
  }

  Future<void> toggle() async {
    if (status == ConnectStatus.connected) {
      setState(() {
        status = ConnectStatus.disconnected;
        upload = '0 B/s';
        download = '0 B/s';
      });
      return;
    }
    setState(() => status = ConnectStatus.connecting);
    await Future<void>.delayed(const Duration(milliseconds: 800));
    if (!mounted) return;
    setState(() {
      status = ConnectStatus.connected;
      upload = '128 KB/s';
      download = '1.2 MB/s';
    });
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
        body: SafeArea(
          child: Column(
            children: [
              Container(
                width: double.infinity,
                margin: const EdgeInsets.fromLTRB(20, 20, 20, 8),
                padding: const EdgeInsets.symmetric(vertical: 18),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  children: [
                    Text(nodeName, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    const Text('手动添加', style: TextStyle(color: Color(0xFF8E8E93))),
                  ],
                ),
              ),
              Expanded(
                child: Center(
                  child: GestureDetector(
                    onTap: toggle,
                    child: Container(
                      width: 168,
                      height: 168,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: btnColor,
                        boxShadow: [
                          BoxShadow(color: btnColor.withOpacity(0.35), blurRadius: 28, offset: const Offset(0, 10)),
                        ],
                      ),
                      alignment: Alignment.center,
                      child: status == ConnectStatus.connecting
                          ? const CircularProgressIndicator(color: Colors.white)
                          : Text(btnText, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ),
              ),
              Text('↑ $upload    ↓ $download', style: const TextStyle(color: Color(0xFF8E8E93))),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    TextButton(
                      onPressed: () {
                        setState(() {
                          selected = (selected + 1) % nodes.length;
                          nodeName = nodes[selected];
                        });
                      },
                      child: const Text('节点'),
                    ),
                    const TextButton(onPressed: null, child: Text('配置')),
                    const TextButton(onPressed: null, child: Text('设置')),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
