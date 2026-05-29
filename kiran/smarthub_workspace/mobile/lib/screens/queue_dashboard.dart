import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';

class QueueDashboard extends StatefulWidget {
  final String token;
  final VoidCallback onUnauthorized;
  
  const QueueDashboard({super.key, required this.token, required this.onUnauthorized});

  @override
  State<QueueDashboard> createState() => _QueueDashboardState();
}

class _QueueDashboardState extends State<QueueDashboard> {
  // Use 10.0.2.2 for Android emulator, or localhost for web/iOS simulator
  final String apiUrl = 'http://localhost:8000/api/v1'; 
  List<Map<String, dynamic>> jobs = [];
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) => _pollJobStatus());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> triggerJob(String channel) async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/notify/bulk'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${widget.token}', 
        },
        body: json.encode({'channel': channel, 'total': 50}), 
      );

      if (response.statusCode == 202) {
        final data = json.decode(response.body);
        setState(() {
          jobs.insert(0, {
            'id': data['job_id'],
            'channel': channel,
            'progress': 0.0,
            'status': 'queued',
            'failed': 0,
          });
        });
      } else if (response.statusCode == 401) {
        widget.onUnauthorized(); 
      }
    } catch (e) {
      debugPrint('Error triggering job: $e');
    }
  }

  Future<void> _pollJobStatus() async {
    for (int i = 0; i < jobs.length; i++) {
      if (jobs[i]['progress'] >= 1.0) continue;

      try {
        final response = await http.get(
          Uri.parse('$apiUrl/notify/jobs/${jobs[i]['id']}'),
          headers: {'Authorization': 'Bearer ${widget.token}'}
        );
        
        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          
          double totalProcessed = data['sent'] + data['failed'] + (data['retrying'] * 0.2);
          double progress = data['total'] > 0 ? totalProcessed / data['total'] : 0.0;
          
          if (progress > 0.95 && (data['sent'] + data['failed'] < data['total'])) {
            progress = 0.95; 
          }

          setState(() {
            jobs[i]['progress'] = progress;
            jobs[i]['failed'] = data['failed']; 
            jobs[i]['status'] = (data['sent'] + data['failed'] >= data['total']) ? 'completed' : 'processing';
          });
        }
      } catch (e) {
        debugPrint('Error polling job: $e');
      }
    }
  }

  // Helper widget to keep the button code clean
  Widget _buildDispatchButton(String title, IconData icon, Color color, String channel) {
    return Expanded(
      child: ElevatedButton.icon(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.all(16), 
          backgroundColor: Colors.white,
          foregroundColor: const Color(0xFF0F172A),
          elevation: 0,
          side: const BorderSide(color: Colors.black12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))
        ),
        onPressed: () => triggerJob(channel),
        icon: Icon(icon, color: color),
        label: Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'SUBMIT DISPATCH JOB', 
            style: TextStyle(color: Colors.black45, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1.2)
          ),
          const SizedBox(height: 16),
          
          // --- THE NEW 2x2 GRID FOR ALL 4 CHANNELS ---
          Row(
            children: [
              _buildDispatchButton('Bulk Email', Icons.email_outlined, Colors.blueAccent, 'email'),
              const SizedBox(width: 16),
              _buildDispatchButton('Bulk SMS', Icons.message_outlined, Colors.purpleAccent, 'sms'),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _buildDispatchButton('Push Alert', Icons.notifications_active_outlined, Colors.teal, 'push'),
              const SizedBox(width: 16),
              _buildDispatchButton('WhatsApp', Icons.chat_outlined, Colors.green.shade600, 'whatsapp'),
            ],
          ),
          // --------------------------------------------

          const SizedBox(height: 40),
          const Text(
            'ACTIVE QUEUE', 
            style: TextStyle(color: Colors.black45, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1.2)
          ),
          const SizedBox(height: 16),
          Expanded(
            child: jobs.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.inbox_outlined, size: 48, color: Colors.grey.shade300),
                        const SizedBox(height: 16),
                        Text('System idle. Awaiting tasks.', style: TextStyle(color: Colors.grey.shade500)),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: jobs.length,
                    itemBuilder: (context, index) {
                      final job = jobs[index];
                      return Card(
                        color: Colors.white,
                        elevation: 0,
                        margin: const EdgeInsets.only(bottom: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                          side: const BorderSide(color: Colors.black12),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(20.0),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    '${job['channel'].toString().toUpperCase()} DISPATCH', 
                                    style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFF0F172A))
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: job['status'] == 'completed' 
                                          ? ((job['failed'] ?? 0) > 0 ? Colors.orange.shade50 : Colors.green.shade50) 
                                          : Colors.blue.shade50,
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      job['status'] == 'completed' 
                                          ? ((job['failed'] ?? 0) > 0 ? 'COMPLETED (${job['failed']} FAILED)' : 'COMPLETED')
                                          : job['status'].toString().toUpperCase(),
                                      style: TextStyle(
                                        color: job['status'] == 'completed' 
                                            ? ((job['failed'] ?? 0) > 0 ? Colors.orange.shade800 : Colors.green.shade700) 
                                            : Colors.blue.shade700,
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                      )
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text('ID: ${job['id']}', style: const TextStyle(color: Colors.black38, fontSize: 11, fontFamily: 'monospace')),
                              const SizedBox(height: 16),
                              LinearProgressIndicator(
                                value: job['progress'],
                                backgroundColor: Colors.grey.shade100,
                                color: const Color(0xFF0F172A), 
                                minHeight: 6,
                                borderRadius: BorderRadius.circular(4),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}