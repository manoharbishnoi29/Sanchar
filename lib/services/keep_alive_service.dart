import 'dart:async';
import 'package:flutter/foundation.dart';

class KeepAliveService {
  static final KeepAliveService _instance = KeepAliveService._internal();
  factory KeepAliveService() => _instance;
  KeepAliveService._internal();

  Timer? _heartbeatTimer;
  bool _isAlive = false;

  /// Service ko start/initialize karne ke liye method
  void startKeepAlive() {
    if (_isAlive) return;
    _isAlive = true;

    if (kDebugMode) {
      print("KeepAliveService: Service Started successfully.");
    }

    // Har 30 seconds mein background heartbeat/ping chalega
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
      _sendHeartbeat();
    });
  }

  /// Periodic Heartbeat check (State ko fresh aur active rakhne ke liye)
  void _sendHeartbeat() {
    if (!_isAlive) return;
    
    // Yahan aap local storage refresh ya server ping call kar sakte hain
    if (kDebugMode) {
      print("KeepAliveService: Ping sent - App State Alive at ${DateTime.now()}");
    }
  }

  /// App close ya service stop karne par cleanup ke liye
  void stopKeepAlive() {
    _isAlive = false;
    _heartbeatTimer?.cancel();
    if (kDebugMode) {
      print("KeepAliveService: Service Stopped.");
    }
  }
}
