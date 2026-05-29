import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class NotificationsScreen extends StatefulWidget {
  final String token;
  final VoidCallback onUnauthorized;

  const NotificationsScreen({super.key, required this.token, required this.onUnauthorized});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool isLoading = true;
  List<dynamic> notifications = [];

  @override
  void initState() {
    super.initState();
    _fetchUserNotifications();
  }

  Future<void> _fetchUserNotifications() async {
    // Note: Since a specific GET /notifications endpoint wasn't in the base PDF API list,
    // this simulates fetching personal alerts (Chat replies, Todo reminders, System alerts).
    // You can wire this up to a real endpoint once you build it, or keep the mock data for the demo!
    
    await Future.delayed(const Duration(milliseconds: 800)); // Simulate network delay
    
    if (mounted) {
      setState(() {
        notifications = [
          {
            "id": "1",
            "type": "chat",
            "title": "New AI Response",
            "message": "SmartHub has finished generating a summary for your document.",
            "is_read": false,
            "time": "Just now"
          },
          {
            "id": "2",
            "type": "todo",
            "title": "Task Reminder",
            "message": "Your task 'Submit Frontend Build' is due tomorrow.",
            "is_read": false,
            "time": "2 hours ago"
          },
          {
            "id": "3",
            "type": "system",
            "title": "Security Alert",
            "message": "A new login was detected on a Web Browser.",
            "is_read": true,
            "time": "Yesterday"
          }
        ];
        isLoading = false;
      });
    }
  }

  void _markAllAsRead() {
    setState(() {
      for (var notif in notifications) {
        notif['is_read'] = true;
      }
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('All notifications marked as read.')),
    );
  }

  IconData _getIconForType(String type) {
    switch (type) {
      case 'chat': return Icons.chat_bubble_outline;
      case 'todo': return Icons.check_box_outlined;
      case 'system': return Icons.security_outlined;
      default: return Icons.notifications_none;
    }
  }

  Color _getColorForType(String type) {
    switch (type) {
      case 'chat': return Colors.blueAccent;
      case 'todo': return Colors.green.shade600;
      case 'system': return Colors.orange.shade700;
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text('My Notifications', style: TextStyle(fontSize: 18)),
        actions: [
          TextButton(
            onPressed: _markAllAsRead,
            child: const Text("Mark All Read", style: TextStyle(color: Colors.blueAccent)),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF0F172A)))
          : notifications.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.notifications_off_outlined, size: 64, color: Colors.grey.shade300),
                      const SizedBox(height: 16),
                      Text("No new notifications.", style: TextStyle(color: Colors.grey.shade500)),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: notifications.length,
                  itemBuilder: (context, index) {
                    final notif = notifications[index];
                    final bool isRead = notif['is_read'];
                    
                    return Card(
                      elevation: 0,
                      margin: const EdgeInsets.only(bottom: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                        side: BorderSide(color: isRead ? Colors.transparent : Colors.blue.shade100, width: 1.5),
                      ),
                      color: isRead ? Colors.white : Colors.blue.shade50.withOpacity(0.3),
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: _getColorForType(notif['type']).withOpacity(0.1),
                                shape: BoxShape.circle,
                              ),
                              child: Icon(
                                _getIconForType(notif['type']), 
                                color: _getColorForType(notif['type']),
                                size: 24
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        notif['title'], 
                                        style: TextStyle(
                                          fontWeight: isRead ? FontWeight.w600 : FontWeight.w800, 
                                          color: const Color(0xFF0F172A),
                                          fontSize: 15,
                                        )
                                      ),
                                      Text(
                                        notif['time'], 
                                        style: TextStyle(color: Colors.grey.shade500, fontSize: 11)
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    notif['message'], 
                                    style: TextStyle(
                                      color: Colors.black87, 
                                      height: 1.4,
                                      fontWeight: isRead ? FontWeight.normal : FontWeight.w500
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}