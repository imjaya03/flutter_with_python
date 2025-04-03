import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:serious_python/serious_python.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// Finds a free port on the local machine
Future<int> findFreePort() async {
  // Create a server socket binding to an ephemeral port (0)
  final serverSocket = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
  final port = serverSocket.port;
  // Close the socket so the port becomes available for use
  await serverSocket.close();
  return port;
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const PythonServerApp());
}

class PythonServerApp extends StatelessWidget {
  const PythonServerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Python Server Controller',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        brightness: Brightness.light,
      ),
      darkTheme: ThemeData(
        primarySwatch: Colors.blue,
        brightness: Brightness.dark,
      ),
      themeMode: ThemeMode.system,
      home: const ServerControlPage(),
    );
  }
}

class ServerControlPage extends StatefulWidget {
  const ServerControlPage({super.key});

  @override
  State<ServerControlPage> createState() => _ServerControlPageState();
}

class _ServerControlPageState extends State<ServerControlPage> {
  int? _port;
  int? _wsPort; // WebSocket port
  bool _isServerRunning = false;
  String _serverStatus = "Server not started";
  bool _isKeyboardTracking = false;
  List<dynamic> _keyboardEvents = [];
  Timer? _eventPollingTimer;
  WebSocketChannel? _webSocketChannel;
  StreamSubscription? _wsSubscription;
  bool _webSocketAvailable = false;
  String _connectionStatus = "WebSocket not connected";

  @override
  void initState() {
    super.initState();
    _initializePort();
  }

  @override
  void dispose() {
    _disconnectWebSocket();
    _eventPollingTimer?.cancel();
    super.dispose();
  }

  Future<void> _initializePort() async {
    final port = await findFreePort();
    setState(() {
      _port = port;
      _wsPort = port + 1; // WebSocket port is HTTP port + 1
    });
  }

  void _startServer() async {
    if (_port == null || _isServerRunning) return;

    setState(() {
      _isServerRunning = true;
      _serverStatus = "Starting server...";
    });

    // Run the Python application with the free port
    try {
      SeriousPython.run(
        "app/app.zip", // This should match where your zip file is created
        appFileName: "my_app.py",
        environmentVariables: {
          "PORT": _port.toString(),
          "DEBUG": "True",
          "OPEN_BROWSER": "False", // Prevent automatic browser opening
        },
      );

      setState(() {
        _serverStatus = "Server running on port $_port";
      });

      // Wait for the server to start
      await Future.delayed(const Duration(seconds: 2));

      // Check if WebSocket is available
      await _checkServerStatus();
    } catch (e) {
      setState(() {
        _isServerRunning = false;
        _serverStatus = "Error starting server: ${e.toString()}";
      });
    }
  }

  Future<void> _checkServerStatus() async {
    if (!_isServerRunning || _port == null) return;

    try {
      final response = await http
          .get(Uri.parse('http://localhost:$_port/api/keyboard/status'))
          .timeout(const Duration(seconds: 5));

      print("Server status response: ${response.statusCode}");

      if (response.statusCode == 200 && response.body.isNotEmpty) {
        try {
          final data = jsonDecode(response.body);

          setState(() {
            _webSocketAvailable = data['websocketAvailable'] ?? false;
            if (data['websocketPort'] != null) {
              _wsPort = data['websocketPort'];
            }
          });

          if (_webSocketAvailable) {
            _connectionStatus = "WebSocket available on port $_wsPort";
            print("WebSocket available on port $_wsPort");
          } else {
            _connectionStatus = "WebSocket not available, using HTTP fallback";
            print("WebSocket not available, using HTTP fallback");
          }
        } catch (e) {
          print("Error parsing server status: $e");
          setState(() {
            _connectionStatus = "Error parsing server status";
            _webSocketAvailable = false;
          });
        }
      } else {
        print(
          "Unexpected server status response: ${response.statusCode}, body: ${response.body}",
        );
        setState(() {
          _connectionStatus =
              "Error checking server status: ${response.statusCode}";
        });
      }
    } catch (e) {
      print('Error checking server status: $e');
      setState(() {
        _connectionStatus = "Error connecting to server";
        _webSocketAvailable = false;
      });
    }
  }

  void _connectWebSocket() {
    if (_webSocketChannel != null || _wsPort == null || !_webSocketAvailable) {
      return;
    }

    try {
      // Fix WebSocket URL format - ensure pure WebSocket URL without fragments
      final wsUrl = 'ws://localhost:$_wsPort/';
      print("Connecting to WebSocket at: $wsUrl");

      // Create WebSocket connection with longer timeout
      _webSocketChannel = IOWebSocketChannel.connect(
        wsUrl,
        pingInterval: const Duration(seconds: 5),
      );

      setState(() {
        _connectionStatus = "Connecting to WebSocket...";
      });

      _wsSubscription = _webSocketChannel!.stream.listen(
        (dynamic message) {
          try {
            final data = jsonDecode(message.toString());

            if (data['type'] == 'status') {
              setState(() {
                _isKeyboardTracking = data['isTracking'] ?? false;
                _connectionStatus = "Connected to WebSocket";
              });
              print("WebSocket connected and received status");
            } else if (data['type'] == 'init_events' &&
                data['events'] != null) {
              setState(() {
                _keyboardEvents = List.from(data['events']);
              });
              print("Received initial events: ${data['events'].length}");
            } else if (data['type'] == 'command_response') {
              if (data['command'] == 'start_tracking') {
                setState(() {
                  _isKeyboardTracking = data['success'];
                });
                ScaffoldMessenger.of(
                  context,
                ).showSnackBar(SnackBar(content: Text(data['message'])));
              } else if (data['command'] == 'stop_tracking') {
                setState(() {
                  _isKeyboardTracking = !data['success'];
                });
                ScaffoldMessenger.of(
                  context,
                ).showSnackBar(SnackBar(content: Text(data['message'])));
              }
            } else if (data['type'] == 'press' || data['type'] == 'release') {
              // Direct keyboard event from server
              setState(() {
                _keyboardEvents.add(data);
              });
              print("Received real-time keyboard event: ${data['key']}");
            }
          } catch (e) {
            print("Error processing WebSocket message: $e");
          }
        },
        onError: (error) {
          print("WebSocket error: $error");
          setState(() {
            _connectionStatus = "WebSocket error: $error";
          });
          _disconnectWebSocket();
        },
        onDone: () {
          print("WebSocket connection closed");
          setState(() {
            _connectionStatus = "WebSocket connection closed";
          });
          _disconnectWebSocket();
        },
      );

      print("WebSocket connection established");
    } catch (e) {
      print("Error connecting to WebSocket: $e");
      setState(() {
        _connectionStatus = "Error connecting to WebSocket: $e";
        _webSocketAvailable =
            false; // Mark WebSocket as unavailable after failed connection
      });

      // Fall back to HTTP polling on WebSocket failure
      if (_isKeyboardTracking) {
        _startEventPolling();
      }
    }
  }

  void _disconnectWebSocket() {
    _wsSubscription?.cancel();
    _wsSubscription = null;
    _webSocketChannel?.sink.close();
    _webSocketChannel = null;

    print("WebSocket disconnected");
  }

  void _stopServer() {
    // Disconnect WebSocket if connected ff
    _disconnectWebSocket();

    // Stop the keyboard tracking if it's active
    if (_isKeyboardTracking) {
      _toggleKeyboardTracking();
    }

    // Stop event polling
    _eventPollingTimer?.cancel();
    _eventPollingTimer = null;

    // This is a placeholder - serious_python might not have a direct way to stop the server
    setState(() {
      _isServerRunning = false;
      _serverStatus = "Server stopped";
      _keyboardEvents = [];
      _webSocketAvailable = false;
      _connectionStatus = "WebSocket not connected";
    });
  }

  void _refreshPort() async {
    if (_isServerRunning) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Stop the server before changing port')),
      );
      return;
    }

    await _initializePort();
  }

  // Add method to launch URL in browser
  Future<void> _launchURL(String url) async {
    final Uri uri = Uri.parse(url);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Could not launch $url')));
    }
  }

  // Toggle keyboard tracking using WebSocket if available, fallback to HTTP
  Future<void> _toggleKeyboardTracking() async {
    if (!_isServerRunning) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Start the server before tracking keyboard'),
        ),
      );
      return;
    }

    // If WebSocket is available, use it
    if (_webSocketAvailable && _webSocketChannel == null) {
      try {
        _connectWebSocket();
        // Wait a bit for the connection to establish
        await Future.delayed(const Duration(milliseconds: 500));
      } catch (e) {
        print("Failed to establish WebSocket connection: $e");
        // Mark WebSocket as unavailable if we can't connect
        _webSocketAvailable = false;
      }
    }

    // If WebSocket connected successfully, send command through WebSocket
    if (_webSocketAvailable && _webSocketChannel != null) {
      try {
        final command =
            _isKeyboardTracking ? 'stop_tracking' : 'start_tracking';
        _webSocketChannel!.sink.add(jsonEncode({'command': command}));
        return;
      } catch (e) {
        print("Error sending WebSocket command: $e");
        // Fall back to HTTP on failure
      }
    }

    // Fallback to HTTP API if WebSocket failed or is not available
    try {
      final url =
          'http://localhost:$_port/api/keyboard/${_isKeyboardTracking ? 'stop' : 'start'}';
      final response = await http.post(Uri.parse(url));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        setState(() {
          _isKeyboardTracking = !_isKeyboardTracking;
          if (_isKeyboardTracking) {
            _keyboardEvents = [];
            _startEventPolling();
          } else {
            _eventPollingTimer?.cancel();
          }
        });

        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(data['message'])));
      } else {
        throw Exception(
          'Failed to ${_isKeyboardTracking ? 'stop' : 'start'} keyboard tracking',
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Error: ${e.toString()}')));
    }
  }

  // Start polling for keyboard events (fallback for when WebSocket is not available)
  void _startEventPolling() {
    if (_webSocketAvailable) return; // Don't poll if WebSocket is available

    _eventPollingTimer?.cancel();
    _eventPollingTimer = Timer.periodic(const Duration(seconds: 2), (timer) {
      if (_isServerRunning && _isKeyboardTracking) {
        _fetchKeyboardEvents();
      } else if (!_isServerRunning) {
        timer.cancel();
      }
    });
  }

  // Fetch keyboard events from server via HTTP (fallback method)
  Future<void> _fetchKeyboardEvents() async {
    if (!_isServerRunning || !_isKeyboardTracking) return;

    try {
      final response = await http.get(
        Uri.parse('http://localhost:$_port/api/keyboard/events'),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _keyboardEvents = data['events'];
        });
      }
    } catch (e) {
      print('Error fetching keyboard events: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Python Server Controller")),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Card(
                elevation: 4,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      const Icon(Icons.computer, size: 50),
                      const SizedBox(height: 16),
                      Text(
                        "Server Port: ${_port ?? 'Finding free port...'}",
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color:
                              _isServerRunning
                                  ? Colors.green.shade100
                                  : Colors.grey.shade200,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          _serverStatus,
                          style: TextStyle(
                            color:
                                _isServerRunning
                                    ? Colors.green.shade900
                                    : Colors.grey.shade800,
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      // Show WebSocket status
                      if (_isServerRunning)
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color:
                                _webSocketAvailable
                                    ? Colors.blue.shade100
                                    : Colors.orange.shade100,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            _connectionStatus,
                            style: TextStyle(
                              color:
                                  _webSocketAvailable
                                      ? Colors.blue.shade900
                                      : Colors.orange.shade900,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  ElevatedButton.icon(
                    onPressed: _isServerRunning ? null : _startServer,
                    icon: const Icon(Icons.play_arrow),
                    label: const Text("Start Server"),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  ElevatedButton.icon(
                    onPressed: _isServerRunning ? _stopServer : null,
                    icon: const Icon(Icons.stop),
                    label: const Text("Stop Server"),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 12,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  TextButton.icon(
                    onPressed: _refreshPort,
                    icon: const Icon(Icons.refresh),
                    label: const Text("Find New Port"),
                  ),
                  const SizedBox(width: 16),
                  ElevatedButton.icon(
                    onPressed:
                        _isServerRunning ? _toggleKeyboardTracking : null,
                    icon: Icon(
                      _isKeyboardTracking
                          ? Icons.keyboard_hide
                          : Icons.keyboard,
                    ),
                    label: Text(
                      _isKeyboardTracking
                          ? "Stop Tracking"
                          : "Start Keyboard Tracking",
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          _isKeyboardTracking ? Colors.amber : Colors.blue,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              ),
              if (_isServerRunning &&
                  _webSocketAvailable &&
                  _webSocketChannel == null)
                Padding(
                  padding: const EdgeInsets.only(top: 12.0),
                  child: ElevatedButton.icon(
                    onPressed: _connectWebSocket,
                    icon: const Icon(Icons.wifi),
                    label: const Text("Connect WebSocket"),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.purple,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
              if (_port != null)
                Padding(
                  padding: const EdgeInsets.only(top: 20.0),
                  child: InkWell(
                    onTap: () => _launchURL("http://localhost:$_port"),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          "Server URL: http://localhost:$_port",
                          style: const TextStyle(
                            fontSize: 16,
                            color: Colors.blue,
                            decoration: TextDecoration.underline,
                          ),
                        ),
                        const SizedBox(width: 8),
                        const Icon(Icons.open_in_browser, size: 16),
                      ],
                    ),
                  ),
                ),

              // Keyboard events display
              if (_isServerRunning && _keyboardEvents.isNotEmpty)
                Expanded(
                  child: Card(
                    margin: const EdgeInsets.only(top: 20),
                    child: Column(
                      children: [
                        Padding(
                          padding: const EdgeInsets.all(8.0),
                          child: Row(
                            children: [
                              const Icon(Icons.keyboard_alt_outlined),
                              const SizedBox(width: 8),
                              Text(
                                "Keyboard Events (${_keyboardEvents.length})",
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const Spacer(),
                              IconButton(
                                icon: const Icon(Icons.clear_all),
                                onPressed:
                                    () => setState(() => _keyboardEvents = []),
                                tooltip: "Clear events",
                              ),
                            ],
                          ),
                        ),
                        const Divider(height: 1),
                        Expanded(
                          child: ListView.separated(
                            padding: const EdgeInsets.all(8),
                            itemCount: _keyboardEvents.length,
                            separatorBuilder:
                                (context, index) => const Divider(height: 1),
                            itemBuilder: (context, index) {
                              final event =
                                  _keyboardEvents[_keyboardEvents.length -
                                      1 -
                                      index];
                              return ListTile(
                                dense: true,
                                leading: Icon(
                                  event['type'] == 'press'
                                      ? Icons.arrow_downward
                                      : Icons.arrow_upward,
                                  color:
                                      event['type'] == 'press'
                                          ? Colors.green
                                          : Colors.red,
                                ),
                                title: Text("Key: ${event['key']}"),
                                subtitle: Text("Type: ${event['type']}"),
                                trailing: Text(
                                  DateTime.fromMillisecondsSinceEpoch(
                                    (event['timestamp'] * 1000).round(),
                                  ).toString().substring(11, 23),
                                ),
                              );
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
