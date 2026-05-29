import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;

class ProfileScreen extends StatefulWidget {
  final String token;
  final VoidCallback onUnauthorized;

  const ProfileScreen({super.key, required this.token, required this.onUnauthorized});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  // Ensure this matches your FastAPI server port
  final String apiUrl = 'http://localhost:8000/api/v1';
  final String baseImageUrl = 'http://localhost:8000';
  
  bool isLoading = true;
  String? avatarUrl;
  String email = "";
  
  final TextEditingController nameController = TextEditingController();
  final TextEditingController phoneController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _fetchProfile();
  }

  Future<void> _fetchProfile() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/auth/profile'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (mounted) {
          setState(() {
            email = data['email'];
            nameController.text = data['full_name'];
            phoneController.text = data['phone'] ?? '';
            // Store the relative path (e.g., /static/avatars/...)
            avatarUrl = data['avatar_url'];
            isLoading = false;
          });
        }
      } else if (response.statusCode == 401) {
        widget.onUnauthorized();
      }
    } catch (e) {
      debugPrint("Error fetching profile: $e");
    }
  }

  Future<void> _updateProfile() async {
    try {
      final response = await http.put(
        Uri.parse('$apiUrl/auth/profile'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${widget.token}',
        },
        body: json.encode({
          'full_name': nameController.text.trim(),
          'phone': phoneController.text.trim(),
        }),
      );

      if (response.statusCode == 200) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profile updated!'), backgroundColor: Colors.green));
      } else if (response.statusCode == 401) {
        widget.onUnauthorized();
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Network error.'), backgroundColor: Colors.red));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) return const Center(child: CircularProgressIndicator(color: Color(0xFF0F172A)));
final String imageUrl = (avatarUrl != null && avatarUrl!.isNotEmpty) 
    ? '$baseImageUrl$avatarUrl' 
    : '';
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        children: [
          // Secure Avatar implementation to prevent Codec/Namespace errors
          // 1. Remove the CachedNetworkImage block and use this instead:


// 2. Build the Avatar
CircleAvatar(
  radius: 50,
  backgroundColor: Colors.transparent,
  child: ClipOval(
    child: (imageUrl.isEmpty)
        ? const Icon(Icons.person, size: 50, color: Colors.blueAccent)
        : Image.network(
            imageUrl,
            fit: BoxFit.cover,
            width: 100,
            height: 100,
            // Key Fix: Use headers to hint the browser this is a standard network request
            headers: {'Access-Control-Allow-Origin': '*'},
            errorBuilder: (context, error, stackTrace) {
              return const Icon(Icons.error, size: 50, color: Colors.red);
            },
            // This forces the image to load as a simple HTML <img> tag on web
            frameBuilder: (context, child, frame, wasSynchronouslyLoaded) {
              return child;
            },
          ),
  ),
),
          const SizedBox(height: 24),
          Text(email, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 32),
          TextField(
            controller: nameController,
            decoration: const InputDecoration(labelText: 'Full Name', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 24),
          TextField(
            controller: phoneController,
            decoration: const InputDecoration(labelText: 'Phone Number', border: OutlineInputBorder()),
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF0F172A),
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              onPressed: _updateProfile,
              child: const Text("SAVE CHANGES", style: TextStyle(color: Colors.white)),
            ),
          ),
        ],
      ),
    );
  }
}