import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:io';
import 'main_layout.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  bool isLogin = true;
  bool isLoading = false;
  
  final TextEditingController emailController = TextEditingController();
  final TextEditingController passwordController = TextEditingController();
  final TextEditingController nameController = TextEditingController();
  final TextEditingController phoneController = TextEditingController();
  
  final String apiUrl = 'http://localhost:8000/api/v1';
  final String simulatedDeviceToken = "fcm_token_pixel_8_pro_dummy_123";

  File? _profileImage;
  final ImagePicker _picker = ImagePicker();

  Future<void> _pickImage() async {
    final XFile? image = await _picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      setState(() => _profileImage = File(image.path));
    }
  }

  void _showNotification(String message, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message, style: const TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: isError ? Colors.redAccent.shade700 : Colors.green.shade800,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    );
  }

  // --- NEW: FORGOT PASSWORD DIALOG ---
  Future<void> _showForgotPasswordDialog() async {
    final TextEditingController resetEmailController = TextEditingController();
    
    // Pre-fill if they already typed something
    if (emailController.text.isNotEmpty) {
      resetEmailController.text = emailController.text;
    }

    await showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Reset Password', style: TextStyle(color: Color(0xFF0F172A), fontWeight: FontWeight.bold)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Enter your registered email address to receive a password reset link.', style: TextStyle(fontSize: 13, color: Colors.black54)),
              const SizedBox(height: 16),
              TextField(
                controller: resetEmailController,
                decoration: const InputDecoration(labelText: 'Email Address', border: OutlineInputBorder()),
                keyboardType: TextInputType.emailAddress,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('CANCEL', style: TextStyle(color: Colors.grey)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0F172A)),
              onPressed: () async {
                final email = resetEmailController.text.trim();
                if (email.isEmpty) return;
                
                Navigator.pop(context); // Close dialog immediately
                
                try {
                  final response = await http.post(
                    Uri.parse('$apiUrl/auth/forgot-password'),
                    headers: {'Content-Type': 'application/json'},
                    body: json.encode({'email': email}),
                  );
                  
                  if (response.statusCode == 200) {
                    _showNotification('If that email is registered, a reset link has been sent.');
                  } else {
                    _showNotification('Failed to send reset request.', isError: true);
                  }
                } catch (e) {
                  _showNotification('Network error.', isError: true);
                }
              },
              child: const Text('SEND LINK', style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }

  Future<void> submitAuth() async {
    if (emailController.text.trim().isEmpty || passwordController.text.trim().isEmpty) {
      _showNotification('Please fill in all mandatory fields (*)', isError: true);
      return;
    }

    setState(() => isLoading = true);
    
    try {
      if (isLogin) {
        final response = await http.post(
          Uri.parse('$apiUrl/auth/login'),
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: {
            'username': emailController.text.trim(),
            'password': passwordController.text.trim(),
            'device_token': simulatedDeviceToken,
          },
        ).timeout(const Duration(seconds: 15));

        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          final String token = data['access_token'];
          
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString('jwt_token', token);
          
          if (mounted) {
            Navigator.pushReplacement(context, MaterialPageRoute(builder: (context) => MainLayout(token: token)));
          }
        } else {
          _showNotification('Invalid email or password.', isError: true);
        }
      } else {
        if (nameController.text.trim().isEmpty) {
          _showNotification('Full Name is mandatory (*)', isError: true);
          setState(() => isLoading = false);
          return;
        }

        var request = http.MultipartRequest('POST', Uri.parse('$apiUrl/auth/register'));
        request.fields['email'] = emailController.text.trim();
        request.fields['full_name'] = nameController.text.trim();
        request.fields['password'] = passwordController.text.trim();
        request.fields['device_token'] = simulatedDeviceToken;
        
        if (phoneController.text.trim().isNotEmpty) {
          request.fields['phone'] = phoneController.text.trim();
        }

        if (_profileImage != null) {
          request.files.add(await http.MultipartFile.fromPath('avatar', _profileImage!.path));
        }

        var streamedResponse = await request.send().timeout(const Duration(seconds: 20));
        var response = await http.Response.fromStream(streamedResponse);

        if (response.statusCode == 201) {
          setState(() {
            isLogin = true;
            passwordController.clear();
            _profileImage = null; 
          });
          _showNotification('Registration successful! You can now log in.');
        } else if (response.statusCode == 400) {
          _showNotification('An account with this email already exists.', isError: true);
        } else {
          _showNotification('Failed to create account.', isError: true);
        }
      }
    } catch (e) {
      _showNotification('Network error. Ensure the server is running.', isError: true);
    } finally {
      if (mounted) setState(() => isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (!isLogin) ...[
                GestureDetector(
                  onTap: _pickImage,
                  child: CircleAvatar(
                    radius: 45,
                    backgroundColor: Colors.blueAccent.withOpacity(0.1),
                    backgroundImage: _profileImage != null ? FileImage(_profileImage!) : null,
                    child: _profileImage == null
                        ? const Icon(Icons.add_a_photo, size: 30, color: Colors.blueAccent)
                        : null,
                  ),
                ),
                const SizedBox(height: 8),
                const Text("Upload Photo (Optional)", textAlign: TextAlign.center, style: TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 24),
              ] else ...[
                const Icon(Icons.hub, size: 80, color: Colors.blueAccent),
                const SizedBox(height: 24),
              ],
              
              Text(
                isLogin ? 'SYSTEM LOGIN' : 'INITIALIZE ACCOUNT',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, letterSpacing: 1.5, color: Color(0xFF0F172A)),
              ),
              const SizedBox(height: 32),
              
              if (!isLogin) ...[
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(labelText: 'Full Name *', border: OutlineInputBorder()),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: phoneController,
                  decoration: const InputDecoration(labelText: 'Phone Number (Optional)', border: OutlineInputBorder()),
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 16),
              ],
              
              TextField(
                controller: emailController,
                decoration: InputDecoration(labelText: isLogin ? 'Email Address' : 'Email Address *', border: const OutlineInputBorder()),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 16),
              
              TextField(
                controller: passwordController,
                decoration: InputDecoration(labelText: isLogin ? 'Password' : 'Password *', border: const OutlineInputBorder()),
                obscureText: true,
              ),
              
              if (isLogin)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: _showForgotPasswordDialog, // <-- HOOKED UP HERE
                    child: const Text('Forgot Password?', style: TextStyle(color: Colors.blueAccent)),
                  ),
                )
              else ...[
                const SizedBox(height: 24),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.orange.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.orange.shade200)
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.lock_outline, color: Colors.orange.shade800, size: 20),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          "SECURITY LOCK: Your Email Address cannot be changed after registration. Profile photo, name, and phone number can be updated later.",
                          style: TextStyle(fontSize: 12, color: Colors.orange.shade900, height: 1.4),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
              ],

              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.all(16), 
                  backgroundColor: const Color(0xFF0F172A),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))
                ),
                onPressed: isLoading ? null : submitAuth,
                child: isLoading
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : Text(isLogin ? 'AUTHENTICATE' : 'REGISTER', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, letterSpacing: 1)),
              ),
              
              const SizedBox(height: 16),
              TextButton(
                onPressed: () {
                  setState(() {
                    isLogin = !isLogin;
                    passwordController.clear();
                  });
                },
                child: Text(isLogin ? 'Need an account? Register here' : 'Already have an account? Login here', style: const TextStyle(color: Colors.grey)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}