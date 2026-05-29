import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class TodoScreen extends StatefulWidget {
  final String token;
  final VoidCallback onUnauthorized;

  const TodoScreen({super.key, required this.token, required this.onUnauthorized});

  @override
  State<TodoScreen> createState() => _TodoScreenState();
}

class _TodoScreenState extends State<TodoScreen> {
  final String apiUrl = 'http://localhost:8000/api/v1';
  List<dynamic> todos = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchTodos();
  }

  Future<void> _fetchTodos() async {
    setState(() => isLoading = true);
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/todos'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );

      if (response.statusCode == 200) {
        setState(() {
          todos = json.decode(response.body);
          // Sort: Incomplete first, then by creation date
          todos.sort((a, b) {
            if (a['completed'] == b['completed']) return 0;
            return a['completed'] ? 1 : -1;
          });
          isLoading = false;
        });
      } else if (response.statusCode == 401) {
        widget.onUnauthorized();
      }
    } catch (e) {
      debugPrint("Error fetching todos: $e");
      setState(() => isLoading = false);
    }
  }

  Future<void> _addTodo(String title) async {
    if (title.trim().isEmpty) return;
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/todos'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${widget.token}',
        },
        body: json.encode({'title': title.trim()}),
      );

      if (response.statusCode == 201) {
        _fetchTodos();
      }
    } catch (e) {
      debugPrint("Error adding todo: $e");
    }
  }

  Future<void> _toggleTodo(String id) async {
    // Optimistic UI update
    final index = todos.indexWhere((t) => t['id'] == id);
    if (index != -1) {
      setState(() {
        todos[index]['completed'] = !todos[index]['completed'];
      });
    }

    try {
      final response = await http.put(
        Uri.parse('$apiUrl/todos/$id/complete'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );
      if (response.statusCode != 200) _fetchTodos(); // Revert on failure
    } catch (e) {
      _fetchTodos();
    }
  }

  Future<void> _deleteTodo(String id) async {
    setState(() {
      todos.removeWhere((t) => t['id'] == id);
    });

    try {
      await http.delete(
        Uri.parse('$apiUrl/todos/$id'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );
    } catch (e) {
      _fetchTodos();
    }
  }

  void _showAddDialog() {
    final TextEditingController titleController = TextEditingController();
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('New Task', style: TextStyle(color: Color(0xFF0F172A), fontWeight: FontWeight.bold)),
          content: TextField(
            controller: titleController,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Task Title', border: OutlineInputBorder()),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('CANCEL', style: TextStyle(color: Colors.grey)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0F172A)),
              onPressed: () {
                _addTodo(titleController.text);
                Navigator.pop(context);
              },
              child: const Text('ADD TASK', style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF0F172A)))
          : todos.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.check_circle_outline, size: 64, color: Colors.grey.shade300),
                      const SizedBox(height: 16),
                      Text("You're all caught up!", style: TextStyle(color: Colors.grey.shade600, fontSize: 16)),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: todos.length,
                  itemBuilder: (context, index) {
                    final todo = todos[index];
                    final bool isCompleted = todo['completed'];
                    return Card(
                      elevation: 0,
                      margin: const EdgeInsets.only(bottom: 8),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                        side: BorderSide(color: isCompleted ? Colors.transparent : Colors.black12),
                      ),
                      color: isCompleted ? Colors.grey.shade100 : Colors.white,
                      child: ListTile(
                        leading: Checkbox(
                          value: isCompleted,
                          activeColor: const Color(0xFF0F172A),
                          onChanged: (_) => _toggleTodo(todo['id']),
                        ),
                        title: Text(
                          todo['title'],
                          style: TextStyle(
                            fontWeight: FontWeight.w500,
                            color: isCompleted ? Colors.grey : const Color(0xFF0F172A),
                            decoration: isCompleted ? TextDecoration.lineThrough : null,
                          ),
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
                          onPressed: () => _deleteTodo(todo['id']),
                        ),
                      ),
                    );
                  },
                ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFF0F172A),
        onPressed: _showAddDialog,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }
}