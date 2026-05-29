import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:file_picker/file_picker.dart';
import 'dart:convert';

class DocumentScreen extends StatefulWidget {
  final String token;
  final VoidCallback onUnauthorized;

  const DocumentScreen({super.key, required this.token, required this.onUnauthorized});

  @override
  State<DocumentScreen> createState() => _DocumentScreenState();
}

class _DocumentScreenState extends State<DocumentScreen> {
  final String apiUrl = 'http://localhost:8000/api/v1';
  List<dynamic> documents = [];
  bool isLoading = true;
  bool isUploading = false;

  @override
  void initState() {
    super.initState();
    _fetchDocuments();
  }

  Future<void> _fetchDocuments() async {
    setState(() => isLoading = true);
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/documents'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );

      if (response.statusCode == 200) {
        setState(() => documents = json.decode(response.body));
      } else if (response.statusCode == 401) {
        widget.onUnauthorized();
      }
    } catch (e) {
      debugPrint("Error fetching documents: $e");
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> _uploadFile() async {
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'docx', 'txt', 'png', 'jpg'], // Supported by backend
    );

    if (result != null) {
      setState(() => isUploading = true);
      try {
        var request = http.MultipartRequest('POST', Uri.parse('$apiUrl/documents/upload'));
        request.headers['Authorization'] = 'Bearer ${widget.token}';
        request.files.add(await http.MultipartFile.fromPath('file', result.files.single.path!));

        var response = await request.send();
        if (response.statusCode == 201) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Document uploaded!')));
          _fetchDocuments(); // Refresh the list
        }
      } catch (e) {
        debugPrint("Upload failed: $e");
      } finally {
        setState(() => isUploading = false);
      }
    }
  }

  Future<void> _deleteDocument(String id) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/documents/$id'),
        headers: {'Authorization': 'Bearer ${widget.token}'},
      );

      if (response.statusCode == 200) {
        _fetchDocuments(); // Refresh the list
      }
    } catch (e) {
      debugPrint("Delete failed: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text('My Documents', style: TextStyle(fontSize: 18)),
        elevation: 0,
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF0F172A)))
          : documents.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.folder_open, size: 64, color: Colors.grey.shade300),
                      const SizedBox(height: 16),
                      Text("No documents uploaded yet.", style: TextStyle(color: Colors.grey.shade500)),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: documents.length,
                  itemBuilder: (context, index) {
                    final doc = documents[index];
                    return Card(
                      elevation: 0,
                      margin: const EdgeInsets.only(bottom: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                        side: BorderSide(color: Colors.grey.shade200),
                      ),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: doc['processed'] == true ? Colors.green.shade50 : Colors.blue.shade50,
                          child: Icon(
                            doc['file_type'] == 'pdf'
                                ? Icons.picture_as_pdf
                                : doc['file_type'] == 'txt'
                                    ? Icons.text_snippet
                                    : doc['file_type'] == 'image'
                                        ? Icons.image
                                        : Icons.description,
                            color: doc['processed'] == true ? Colors.green.shade700 : Colors.blue.shade700,
                          ),
                        ),
                        title: Text(doc['filename'], style: const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Text(
                          doc['processed'] == true
                              ? "Indexed for AI · ${doc['chunk_count'] ?? 0} chunks"
                              : "Pending indexing",
                          style: TextStyle(
                            color: doc['processed'] == true ? Colors.green.shade700 : Colors.orange.shade700,
                            fontSize: 12,
                          ),
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                          onPressed: () => _deleteDocument(doc['id']),
                        ),
                      ),
                    );
                  },
                ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: isUploading ? null : _uploadFile,
        backgroundColor: const Color(0xFF0F172A),
        icon: isUploading
            ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
            : const Icon(Icons.upload_file, color: Colors.white),
        label: Text(isUploading ? "Uploading..." : "Upload File", style: const TextStyle(color: Colors.white)),
      ),
    );
  }
}