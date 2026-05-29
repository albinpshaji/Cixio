import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'queue_dashboard.dart';
import 'profile_screen.dart';
import 'auth_screen.dart';
import 'todo_screen.dart';
import 'notification_screen.dart';
import 'chat_screen.dart';
import 'document_screen.dart';
class MainLayout extends StatefulWidget {
  final String token;
  const MainLayout({super.key, required this.token});

  @override
  State<MainLayout> createState() => _MainLayoutState();
}

class _MainLayoutState extends State<MainLayout> {
  int _currentIndex = 0;

  void _logout() async {
    // Clear session cache
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('jwt_token');
    
    if (mounted) {
      Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(builder: (context) => const AuthScreen()),
        (route) => false, // Destroy all previous routes to prevent back-button loopholes
      );
    }
  }

  // Define the screens for the sidebar
  late final List<Widget> _screens = [
    QueueDashboard(token: widget.token, onUnauthorized: _logout),      // Index 0
    ProfileScreen(token: widget.token, onUnauthorized: _logout),       // Index 1
    ChatScreen(token: widget.token, onUnauthorized: _logout),          // Index 2 (NEW)
    DocumentScreen(token: widget.token, onUnauthorized: _logout),      // Index 3 (NEW)
    TodoScreen(token: widget.token, onUnauthorized: _logout),          // Index 4
    NotificationsScreen(token: widget.token, onUnauthorized: _logout), // Index 5
  ];

  Widget _buildDummyScreen(String title) {
    return Center(
      child: Text(
        title,
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 18, color: Colors.black54, fontWeight: FontWeight.w500),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SmartHub'),
      ),
      drawer: Drawer(
        backgroundColor: Colors.white,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            const DrawerHeader(
              decoration: BoxDecoration(color: Color(0xFF0F172A)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Icon(Icons.hub, color: Colors.white, size: 40),
                  SizedBox(height: 12),
                  Text('SmartHub Workspace', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                ],
              ),
            ),
            _buildDrawerItem(Icons.person, 'My Profile', 0),
            _buildDrawerItem(Icons.queue, 'Notification Queue', 1),
            
            const Divider(),
            const Padding(
              padding: EdgeInsets.only(left: 16, top: 8, bottom: 8),
              child: Text("OTHER MODULES", style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.black38)),
            ),
            _buildDrawerItem(Icons.chat_bubble_outline, 'SmartHub AI', 2), // Points to ChatScreen
            _buildDrawerItem(Icons.folder_shared_outlined, 'My Documents', 3),
            const Divider(color: Colors.white12, height: 32),
            
            const Padding(
              padding: EdgeInsets.only(left: 24, bottom: 8),
              child: Text('TOOLS', style: TextStyle(color: Colors.white54, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
            ),
            _buildDrawerItem(Icons.check_box_outlined, 'Todos', 4),
            _buildDrawerItem(Icons.notifications_outlined, 'My Inbox', 5), // <-- ADD THIS
            
            const Divider(),
            ListTile(
              leading: const Icon(Icons.logout, color: Colors.redAccent),
              title: const Text('Secure Logout', style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.w500)),
              onTap: _logout,
            ),
          ],
        ),
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
    );
  }

  Widget _buildDrawerItem(IconData icon, String title, int index) {
    final isSelected = _currentIndex == index;
    return ListTile(
      leading: Icon(icon, color: isSelected ? const Color(0xFF0F172A) : Colors.black54),
      title: Text(
        title, 
        style: TextStyle(
          color: isSelected ? const Color(0xFF0F172A) : Colors.black87,
          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal
        )
      ),
      selected: isSelected,
      selectedTileColor: Colors.grey[100],
      onTap: () {
        setState(() => _currentIndex = index);
        Navigator.pop(context); // Close drawer
      },
    );
  }
}