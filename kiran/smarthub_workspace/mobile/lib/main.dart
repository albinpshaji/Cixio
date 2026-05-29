import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'screens/auth_screen.dart';
import 'screens/main_layout.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Check for existing session
  final prefs = await SharedPreferences.getInstance();
  final String? token = prefs.getString('jwt_token');

  runApp(SmartHubApp(initialToken: token));
}

class SmartHubApp extends StatelessWidget {
  final String? initialToken;
  const SmartHubApp({super.key, this.initialToken});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SmartHub',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.light,
        scaffoldBackgroundColor: const Color(0xFFF8FAFC), // Light slate background
        primaryColor: const Color(0xFF0F172A), // Executive dark navy
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: Color(0xFF0F172A),
          elevation: 0.5,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: Color(0xFF0F172A), 
            fontSize: 20, 
            fontWeight: FontWeight.w600,
            letterSpacing: -0.5,
          ),
        ),
        fontFamily: 'Roboto', // Clean default sans-serif
      ),
      home: initialToken != null 
          ? MainLayout(token: initialToken!) 
          : const AuthScreen(),
    );
  }
}