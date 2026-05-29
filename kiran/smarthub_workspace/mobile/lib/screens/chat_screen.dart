import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

class ChatScreen extends StatefulWidget {
  final String token;
  final VoidCallback onUnauthorized;

  const ChatScreen({super.key, required this.token, required this.onUnauthorized});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final String apiUrl = 'http://localhost:8000/api/v1';
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  
  String? activeSessionId;
  bool isLoadingSession = true;

  List<Map<String, dynamic>> messages = [];
  List<dynamic> _sessions = [];
  List<String> processingLogs = [];
  List<Map<String, dynamic>> currentSources = [];
  String currentAiMessage = "";
  bool isAiThinking = false;
  bool isUploadingFile = false;

  @override
  void initState() {
    super.initState();
    _initSession();
  }

  /// Create or fetch the most recent chat session
  Future<void> _initSession() async {
    setState(() => isLoadingSession = true);
    try {
      // Try to fetch existing sessions
      final response = await http.get(
        Uri.parse('$apiUrl/chat/sessions'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );

      if (response.statusCode == 200) {
        final sessions = json.decode(response.body) as List;
        setState(() {
          _sessions = sessions;
        });
        if (sessions.isNotEmpty) {
          // Use the most recent session
          setState(() {
            activeSessionId = sessions[0]['id'];
            isLoadingSession = false;
          });
          _loadHistory();
          return;
        }
      } else if (response.statusCode == 401) {
        widget.onUnauthorized();
        return;
      }

      // No sessions found — create a new one
      await _createNewSession();
    } catch (e) {
      debugPrint("Error initializing session: $e");
      setState(() => isLoadingSession = false);
    }
  }

  Future<void> _fetchSessions() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/chat/sessions'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );
      if (response.statusCode == 200) {
        setState(() {
          _sessions = json.decode(response.body) as List;
        });
      }
    } catch (e) {
      debugPrint("Error fetching sessions: $e");
    }
  }

  Future<void> _pickAndUploadFile() async {
    if (activeSessionId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select or start a chat session first.'),
          backgroundColor: Color(0xFFDC2626),
        ),
      );
      return;
    }

    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'txt'],
      );

      if (result == null || result.files.single.path == null) {
        return;
      }

      final filePath = result.files.single.path!;
      final fileName = result.files.single.name;

      setState(() {
        isUploadingFile = true;
      });

      // Show uploading snackbar
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text('Uploading & vector indexing "$fileName"...'),
              ),
            ],
          ),
          duration: const Duration(days: 1), // Indefinite until closed
          key: const ValueKey('uploading_snackbar'),
        ),
      );

      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$apiUrl/documents/upload'),
      );
      request.headers.addAll({
        'Authorization': 'Bearer ${widget.token}',
      });
      request.fields['session_id'] = activeSessionId!;
      request.files.add(
        await http.MultipartFile.fromPath('file', filePath),
      );

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      // Hide the uploading snackbar
      ScaffoldMessenger.of(context).removeCurrentSnackBar();

      setState(() {
        isUploadingFile = false;
      });

      if (response.statusCode == 201) {
        final parsed = json.decode(response.body);
        final chunks = parsed['chunk_count'] ?? 0;

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('"$fileName" uploaded and indexed successfully!'),
            backgroundColor: const Color(0xFF16A34A),
          ),
        );

        // Add a system feedback message inside the chat view
        setState(() {
          messages.add({
            "role": "assistant",
            "content": "📁 **Document uploaded successfully for this session:** _${fileName}_\nIndexed into **$chunks** chunks. SmartHub AI is now grounded in this document for this chat session.",
          });
        });
        _scrollToBottom();
      } else {
        final errorMsg = json.decode(response.body)['detail'] ?? 'Upload failed';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Upload failed: $errorMsg'),
            backgroundColor: const Color(0xFFDC2626),
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).removeCurrentSnackBar();
      setState(() {
        isUploadingFile = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error picking/uploading file: $e'),
          backgroundColor: const Color(0xFFDC2626),
        ),
      );
    }
  }

  Future<void> _createNewSession() async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/chat/sessions'),
        headers: {
          'Authorization': 'Bearer ${widget.token}',
          'Content-Type': 'application/json',
        },
        body: json.encode({'title': 'New Chat'}),
      );

      if (response.statusCode == 201) {
        final session = json.decode(response.body);
        setState(() {
          activeSessionId = session['id'];
          messages.clear();
          isLoadingSession = false;
        });
        await _fetchSessions();
      }
    } catch (e) {
      debugPrint("Error creating session: $e");
      setState(() => isLoadingSession = false);
    }
  }

  Future<void> _deleteSession(String id) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/chat/sessions/$id'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );

      if (response.statusCode == 200) {
        await _fetchSessions();
        if (activeSessionId == id) {
          if (_sessions.isNotEmpty) {
            setState(() {
              activeSessionId = _sessions[0]['id'];
            });
            _loadHistory();
          } else {
            await _createNewSession();
          }
        }
      }
    } catch (e) {
      debugPrint("Error deleting session: $e");
    }
  }

  Future<void> _loadHistory() async {
    if (activeSessionId == null) return;
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/chat/sessions/$activeSessionId/messages'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );
      if (response.statusCode == 200) {
        final history = json.decode(response.body) as List;
        setState(() {
          messages = history.map<Map<String, dynamic>>((m) => {
            "role": m['role'],
            "content": m['content'],
            "sources": List<Map<String, dynamic>>.from(m['sources'] ?? []),
          }).toList();
        });
        WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
      }
    } catch (e) {
      debugPrint("Error loading history: $e");
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || activeSessionId == null) return;

    setState(() {
      messages.add({"role": "user", "content": text});
      _controller.clear();
      processingLogs.clear();
      currentSources.clear();
      currentAiMessage = "";
      isAiThinking = true;
    });
    
    _scrollToBottom();

    final request = http.Request('POST', Uri.parse('$apiUrl/chat/sessions/$activeSessionId/messages'));
    request.headers.addAll({
      'Authorization': 'Bearer ${widget.token}',
      'Content-Type': 'application/json'
    });
    request.body = json.encode({'content': text});

    try {
      final client = http.Client();
      final response = await client.send(request);

      response.stream.transform(utf8.decoder).listen((data) {
        // Handle multiple SSE events in one chunk
        final lines = data.split('\n');
        for (final line in lines) {
          if (line.startsWith('data: ')) {
            final jsonString = line.substring(6).trim();
            if (jsonString.isNotEmpty) {
              try {
                final parsed = json.decode(jsonString);

                setState(() {
                  if (parsed['type'] == 'log') {
                    processingLogs.add(parsed['message']);
                  } else if (parsed['type'] == 'content') {
                    currentAiMessage += parsed['content'];
                  } else if (parsed['type'] == 'sources') {
                    // Store RAG source citations
                    currentSources = List<Map<String, dynamic>>.from(parsed['sources'] ?? []);
                  } else if (parsed['type'] == 'done') {
                    isAiThinking = false;
                    messages.add({
                      "role": "assistant",
                      "content": currentAiMessage,
                      "sources": List<Map<String, dynamic>>.from(currentSources),
                    });
                    currentAiMessage = "";
                    currentSources.clear();
                    processingLogs.clear();
                  } else if (parsed['type'] == 'error') {
                    isAiThinking = false;
                    messages.add({
                      "role": "assistant",
                      "content": parsed['message'] ?? "An error occurred.",
                    });
                  }
                  _scrollToBottom();
                });
              } catch (_) {
                // Skip malformed JSON chunks
              }
            }
          }
        }
      });
    } catch (e) {
      setState(() {
        isAiThinking = false;
        messages.add({"role": "assistant", "content": "Error connecting to AI server."});
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text(
          'SmartHub AI',
          style: TextStyle(
            fontSize: 18, 
            fontWeight: FontWeight.w700, 
            color: Colors.white,
            letterSpacing: -0.5,
          ),
        ),
        elevation: 1,
        backgroundColor: const Color(0xFF0F172A),
        foregroundColor: Colors.white,
        leading: Builder(
          builder: (context) => IconButton(
            icon: const Icon(Icons.view_sidebar_outlined, size: 22), 
            tooltip: 'Chat History',
            onPressed: () {
              Scaffold.of(context).openDrawer(); 
            },
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_comment_outlined, size: 22, color: Colors.white),
            tooltip: 'New Chat',
            onPressed: () async {
              await _createNewSession();
            },
          ),
        ],
      ),
      drawer: Drawer(
        child: Container(
          color: const Color(0xFFF8FAFC),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DrawerHeader(
                decoration: const BoxDecoration(
                  color: Color(0xFF0F172A),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    const Icon(Icons.hub, size: 40, color: Colors.blueAccent),
                    const SizedBox(height: 12),
                    const Text(
                      'SmartHub AI Chats',
                      style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${_sessions.length} historical sessions',
                      style: TextStyle(color: Colors.grey.shade400, fontSize: 12),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(12),
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF0F172A),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () async {
                    Navigator.pop(context); // close drawer
                    await _createNewSession();
                  },
                  icon: const Icon(Icons.add, color: Colors.white),
                  label: const Text('New Chat', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              ),
              Expanded(
                child: _sessions.isEmpty
                    ? const Center(
                        child: Text('No past sessions', style: TextStyle(color: Colors.grey)),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        itemCount: _sessions.length,
                        itemBuilder: (context, index) {
                          final session = _sessions[index];
                          final isSelected = session['id'] == activeSessionId;
                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            decoration: BoxDecoration(
                              color: isSelected ? Colors.blueAccent.withOpacity(0.1) : Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: isSelected ? Colors.blueAccent.withOpacity(0.3) : Colors.grey.shade200,
                              ),
                            ),
                            child: Material(
                              color: Colors.transparent,
                              borderRadius: BorderRadius.circular(8),
                              child: ListTile(
                                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                                leading: Icon(
                                  Icons.chat_bubble_outline,
                                  color: isSelected ? Colors.blueAccent : Colors.grey.shade600,
                                  size: 20,
                                ),
                                title: Text(
                                  session['title'] ?? 'Chat Session',
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                    color: isSelected ? Colors.blueAccent.shade700 : const Color(0xFF0F172A),
                                  ),
                                ),
                                trailing: IconButton(
                                  icon: const Icon(Icons.delete_outline, size: 18, color: Colors.redAccent),
                                  onPressed: () async {
                                    final confirm = await showDialog<bool>(
                                      context: context,
                                      builder: (context) => AlertDialog(
                                        title: const Text('Delete Chat?'),
                                        content: const Text('Are you sure you want to delete this chat session?'),
                                        actions: [
                                          TextButton(
                                            onPressed: () => Navigator.pop(context, false),
                                            child: const Text('Cancel', style: TextStyle(color: Colors.grey)),
                                          ),
                                          TextButton(
                                            onPressed: () => Navigator.pop(context, true),
                                            child: const Text('Delete', style: TextStyle(color: Colors.redAccent)),
                                          ),
                                        ],
                                      ),
                                    );
                                    if (confirm == true) {
                                      await _deleteSession(session['id']);
                                    }
                                  },
                                ),
                                onTap: () {
                                  Navigator.pop(context); // close drawer
                                  if (!isSelected) {
                                    setState(() {
                                      activeSessionId = session['id'];
                                    });
                                    _loadHistory();
                                  }
                                },
                              ),
                            ),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
      body: isLoadingSession
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF0F172A)))
          : Column(
              children: [
                Expanded(
                  child: SelectionArea(
                    child: messages.isEmpty && !isAiThinking
                        ? _buildGeminiGreetingScreen()
                        : ListView.builder(
                            controller: _scrollController,
                            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                            itemCount: messages.length + (isAiThinking ? 1 : 0),
                            itemBuilder: (context, index) {
                              if (index == messages.length && isAiThinking) {
                                return _buildActiveStreamBubble();
                              }

                              final msg = messages[index];
                              final isUser = msg['role'] == 'user';
                              final sources = msg['sources'] as List<Map<String, dynamic>>?;
                              final hasSources = sources != null && sources.isNotEmpty;

                              if (isUser) {
                                return Padding(
                                  padding: const EdgeInsets.only(bottom: 16),
                                  child: Align(
                                    alignment: Alignment.centerRight,
                                    child: Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                                      constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                                      decoration: const BoxDecoration(
                                        color: Color(0xFFF1F5F9),
                                        borderRadius: BorderRadius.only(
                                          topLeft: Radius.circular(20),
                                          topRight: Radius.circular(20),
                                          bottomLeft: Radius.circular(20),
                                          bottomRight: Radius.circular(4),
                                        ),
                                      ),
                                      child: Text(
                                        msg['content'],
                                        style: const TextStyle(
                                          color: Color(0xFF0F172A), 
                                          fontSize: 15, 
                                          height: 1.4,
                                          fontWeight: FontWeight.w400,
                                        ),
                                      ),
                                    ),
                                  ),
                                );
                              } else {
                                // AI Assistant message (Simplistic Style - No Bubble, Raw Flow)
                                return Padding(
                                  padding: const EdgeInsets.only(bottom: 24),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          const Icon(Icons.smart_toy_outlined, color: Color(0xFF64748B), size: 16),
                                          const SizedBox(width: 8),
                                          const Text(
                                            'SmartHub AI',
                                            style: TextStyle(
                                              fontSize: 13,
                                              fontWeight: FontWeight.w600,
                                              color: Color(0xFF475569),
                                            ),
                                          ),
                                          const Spacer(),
                                          IconButton(
                                            icon: const Icon(Icons.copy_all_outlined, size: 16, color: Color(0xFF94A3B8)),
                                            padding: EdgeInsets.zero,
                                            constraints: const BoxConstraints(),
                                            splashRadius: 16,
                                            tooltip: 'Copy message',
                                            onPressed: () {
                                              Clipboard.setData(ClipboardData(text: msg['content'] ?? ''));
                                              ScaffoldMessenger.of(context).showSnackBar(
                                                const SnackBar(
                                                  content: Text('Copied to clipboard'),
                                                  duration: Duration(seconds: 1),
                                                ),
                                              );
                                            },
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 8),
                                      Padding(
                                        padding: const EdgeInsets.only(left: 24),
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            MarkdownBody(
                                              data: msg['content'] ?? '',
                                              styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                                                p: const TextStyle(
                                                  color: Color(0xFF334155),
                                                  fontSize: 15,
                                                  height: 1.5,
                                                ),
                                                listBullet: const TextStyle(
                                                  color: Color(0xFF334155),
                                                  fontSize: 15,
                                                ),
                                              ),
                                            ),
                                            if (hasSources) ...[
                                              const SizedBox(height: 12),
                                              GestureDetector(
                                                onTap: () => _showSourcesDialog(sources),
                                                child: Container(
                                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                                  decoration: BoxDecoration(
                                                    color: const Color(0xFFF1F5F9),
                                                    borderRadius: BorderRadius.circular(20),
                                                    border: Border.all(color: const Color(0xFFE2E8F0)),
                                                  ),
                                                  child: Row(
                                                    mainAxisSize: MainAxisSize.min,
                                                    children: [
                                                      const Icon(Icons.auto_stories_outlined, size: 14, color: Color(0xFF475569)),
                                                      const SizedBox(width: 6),
                                                      Text(
                                                        'Grounded on ${sources.length} document source${sources.length > 1 ? 's' : ''}',
                                                        style: const TextStyle(
                                                          fontSize: 11, 
                                                          color: Color(0xFF475569), 
                                                          fontWeight: FontWeight.w600,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                ),
                                              ),
                                            ],
                                          ],
                                        ),
                                      ),
                                    ],
                                  ),
                                );
                              }
                            },
                          ),
                  ),
                ),
                
                // Floating Pill-Shaped Input Area
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  child: Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFFF1F5F9),
                      borderRadius: BorderRadius.circular(28),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                    child: Row(
                      children: [
                        isUploadingFile
                            ? const SizedBox(
                                width: 24,
                                height: 24,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF0F172A)),
                              )
                            : IconButton(
                                icon: Icon(Icons.add_circle_outline, color: Colors.grey.shade600, size: 24),
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(),
                                tooltip: 'Upload document for this chat',
                                onPressed: isAiThinking ? null : _pickAndUploadFile,
                              ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextField(
                            controller: _controller,
                            enabled: !isAiThinking,
                            style: const TextStyle(fontSize: 15, color: Color(0xFF0F172A)),
                            decoration: InputDecoration(
                              hintText: "Ask SmartHub...",
                              hintStyle: TextStyle(color: Colors.grey.shade500, fontSize: 15),
                              border: InputBorder.none,
                              contentPadding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                            onSubmitted: (_) => _sendMessage(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        GestureDetector(
                          onTap: isAiThinking ? null : _sendMessage,
                          child: CircleAvatar(
                            radius: 18,
                            backgroundColor: isAiThinking ? Colors.grey.shade400 : const Color(0xFF0F172A),
                            child: const Icon(Icons.arrow_upward, color: Colors.white, size: 18),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }

  /// Show a bottom sheet with the retrieved RAG source chunks
  void _showSourcesDialog(List<Map<String, dynamic>> sources) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.5,
        maxChildSize: 0.85,
        minChildSize: 0.3,
        expand: false,
        builder: (context, scrollController) => Column(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(color: Colors.grey.shade200)),
              ),
              child: Row(
                children: [
                  Icon(Icons.auto_stories, color: Colors.green.shade700),
                  const SizedBox(width: 8),
                  Text(
                    'Retrieved Sources (${sources.length})',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView.builder(
                controller: scrollController,
                padding: const EdgeInsets.all(16),
                itemCount: sources.length,
                itemBuilder: (context, index) {
                  final source = sources[index];
                  final similarity = (source['similarity'] as num?)?.toStringAsFixed(3) ?? '?';
                  final metadata = source['metadata'] as Map<String, dynamic>?;
                  final sourceName = metadata?['source'] ?? 'pasted text';
                  final page = metadata?['page'];

                  return Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.grey.shade50,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.grey.shade200),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: Colors.blue.shade50,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                'Source ${index + 1}',
                                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.blue.shade700),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'similarity: $similarity',
                              style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                            ),
                            if (page != null) ...[
                              const SizedBox(width: 8),
                              Text(
                                'page $page',
                                style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          sourceName.toString(),
                          style: TextStyle(fontSize: 12, color: Colors.grey.shade500, fontStyle: FontStyle.italic),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          source['content'] ?? '',
                          style: const TextStyle(fontSize: 13, height: 1.5),
                          maxLines: 6,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  // The sleek UI block showing the AI's internal process and live text
  Widget _buildActiveStreamBubble() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.smart_toy_outlined, color: Color(0xFF64748B), size: 16),
              const SizedBox(width: 8),
              const Text(
                'SmartHub AI',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF475569),
                ),
              ),
              const SizedBox(width: 8),
              const SizedBox(
                width: 10,
                height: 10,
                child: CircularProgressIndicator(strokeWidth: 1.5, color: Color(0xFF64748B)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.only(left: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Processing Logs
                if (processingLogs.isNotEmpty && currentAiMessage.isEmpty)
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: processingLogs.map((log) => Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.chevron_right, size: 14, color: Colors.grey.shade400),
                          const SizedBox(width: 4),
                          Text(
                            log, 
                            style: TextStyle(
                              fontSize: 13, 
                              color: Colors.grey.shade500, 
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ),
                    )).toList(),
                  ),
                  
                // Live Streamed Content
                if (currentAiMessage.isNotEmpty)
                  MarkdownBody(
                    data: currentAiMessage,
                    styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                      p: const TextStyle(
                        color: Color(0xFF334155),
                        fontSize: 15,
                        height: 1.5,
                      ),
                      listBullet: const TextStyle(
                        color: Color(0xFF334155),
                        fontSize: 15,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGeminiGreetingScreen() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.smart_toy_outlined, color: Color(0xFF0F172A), size: 40),
            const SizedBox(height: 20),
            
            const Text(
              'Hello there.',
              style: TextStyle(
                fontSize: 32, 
                fontWeight: FontWeight.w700, 
                color: Color(0xFF0F172A),
                letterSpacing: -1.0,
              ),
            ),
            
            const Text(
              'How can I help you today?',
              style: TextStyle(
                fontSize: 24, 
                fontWeight: FontWeight.w600, 
                color: Color(0xFF64748B),
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 36),
            
            const Text(
              'Get started with suggestions:',
              style: TextStyle(
                fontSize: 12, 
                fontWeight: FontWeight.w600, 
                color: Color(0xFF94A3B8),
                letterSpacing: 1.0,
              ),
            ),
            const SizedBox(height: 12),
            
            // Cards Grid/Row
            _buildSuggestionCard(
              icon: Icons.article_outlined,
              title: 'Summarize my documents',
              prompt: 'Please provide a clear executive summary of all my uploaded PDF files.',
            ),
            _buildSuggestionCard(
              icon: Icons.checklist_outlined,
              title: 'Brainstorm my tasks',
              prompt: 'Help me draft and prioritize a new to-do list for my current project tasks.',
            ),
            _buildSuggestionCard(
              icon: Icons.lightbulb_outline,
              title: 'Explain standard architectures',
              prompt: 'Explain what a RAG (Retrieval-Augmented Generation) pipeline is and how it functions.',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionCard({
    required IconData icon,
    required String title,
    required String prompt,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          leading: CircleAvatar(
            backgroundColor: const Color(0xFFF1F5F9),
            child: Icon(icon, color: const Color(0xFF475569), size: 20),
          ),
          title: Text(
            title,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF334155)),
          ),
          trailing: const Icon(Icons.arrow_forward_ios, size: 14, color: Colors.grey),
          onTap: () {
            _controller.text = prompt;
            _sendMessage();
          },
        ),
      ),
    );
  }
}