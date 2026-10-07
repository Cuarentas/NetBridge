package com.netbridge.netbridge

import android.app.Activity
import android.content.Intent
import android.net.VpnService
import android.os.Build
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

object VpnPlugin {
    private const val CHANNEL = "com.netbridge/vpn"
    private const val REQ_VPN = 0x701

    fun register(activity: Activity, engine: FlutterEngine) {
        MethodChannel(engine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "prepare" -> {
                    val intent = VpnService.prepare(activity)
                    if (intent != null) {
                        activity.startActivityForResult(intent, REQ_VPN)
                        // 简化：返回 true，用户需再次点连接；生产可挂起 result
                        result.success(true)
                    } else {
                        result.success(true)
                    }
                }
                "start" -> {
                    val core = call.argument<String>("core") ?: "sing-box"
                    val config = call.argument<String>("config") ?: "{}"
                    val i = Intent(activity, NetBridgeVpnService::class.java)
                    i.action = NetBridgeVpnService.ACTION_START
                    i.putExtra("core", core)
                    i.putExtra("config", config)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        activity.startForegroundService(i)
                    } else {
                        activity.startService(i)
                    }
                    result.success("vpn-started")
                }
                "stop" -> {
                    val i = Intent(activity, NetBridgeVpnService::class.java)
                    i.action = NetBridgeVpnService.ACTION_STOP
                    activity.startService(i)
                    result.success(null)
                }
                "status" -> {
                    result.success(if (NetBridgeVpnService.running) "running" else "stopped")
                }
                "corePath" -> {
                    val core = call.argument<String>("core") ?: "sing-box"
                    val name = if (core == "xray") "xray" else "sing-box"
                    result.success(File(activity.filesDir, "core/$name").absolutePath)
                }
                else -> result.notImplemented()
            }
        }
    }
}
