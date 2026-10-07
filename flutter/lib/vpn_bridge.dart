import 'package:flutter/services.dart';

/// 与各平台原生层通信：启动/停止核心与 VPN
class VpnBridge {
  static const _ch = MethodChannel('com.netbridge/vpn');

  static Future<bool> prepare() async {
    try {
      final r = await _ch.invokeMethod<bool>('prepare');
      return r ?? true;
    } catch (_) {
      return true;
    }
  }

  static Future<String> start({
    required String core, // sing-box | xray
    required String configJson,
  }) async {
    final r = await _ch.invokeMethod<String>('start', {
      'core': core,
      'config': configJson,
    });
    return r ?? 'ok';
  }

  static Future<void> stop() async {
    await _ch.invokeMethod<void>('stop');
  }

  static Future<String> status() async {
    try {
      return await _ch.invokeMethod<String>('status') ?? 'stopped';
    } catch (_) {
      return 'unknown';
    }
  }

  static Future<String> corePath(String core) async {
    try {
      return await _ch.invokeMethod<String>('corePath', {'core': core}) ?? '';
    } catch (_) {
      return '';
    }
  }
}
