import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const App());
}

/// Modelo de Projeto (fotos diretamente no projeto, sem tarefas)
class Project {
  String name;
  List<String> photos;
  int sentCount;

  Project(this.name, {List<String>? photos, this.sentCount = 0})
      : photos = photos ?? [];

  List<String> get pending =>
      photos.sublist(sentCount > photos.length ? photos.length : sentCount);

  Map<String, dynamic> toJson() => {
        'name': name,
        'photos': photos,
        'sentCount': sentCount,
      };

  factory Project.fromJson(Map<String, dynamic> j) {
    List<String> loadedPhotos = [];
    int loadedSentCount = 0;

    if (j['photos'] != null) {
      loadedPhotos = List<String>.from(j['photos']);
      loadedSentCount = j['sentCount'] ?? 0;
    } else if (j['tasks'] != null) {
      for (final t in j['tasks']) {
        if (t['photos'] != null) {
          loadedPhotos.addAll(List<String>.from(t['photos']));
          loadedSentCount += (t['sentCount'] as int? ?? 0);
        }
      }
    }

    return Project(
      j['name'] ?? 'Sem nome',
      photos: loadedPhotos,
      sentCount: loadedSentCount,
    );
  }
}

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Projetos',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
      ),
      home: const ProjectsScreen(),
    );
  }
}

/// 1. TELA DE PROJETOS (Lista simples sem distrações)
class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({super.key});

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  List<Project> projects = [Project('Projeto 001')];
  String server = 'http://192.168.1.8:8000';
  SharedPreferences? prefs;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    prefs = await SharedPreferences.getInstance();
    final raw = prefs!.getString('projects_data');
    final srv = prefs!.getString('server_url') ?? server;

    List<Project> loadedProjects;
    if (raw != null && raw.isNotEmpty && raw != '[]') {
      try {
        loadedProjects = (jsonDecode(raw) as List)
            .map((e) => Project.fromJson(e))
            .toList();
      } catch (_) {
        loadedProjects = [Project('Projeto 001')];
      }
    } else {
      loadedProjects = [Project('Projeto 001')];
    }

    if (mounted) {
      setState(() {
        server = srv;
        projects = loadedProjects;
      });
    }

    // Ajusta caminhos das fotos se houver
    final hasPhotos = loadedProjects.any((p) => p.photos.isNotEmpty);
    if (hasPhotos) {
      try {
        final docsDir = (await getApplicationDocumentsDirectory()
                .timeout(const Duration(milliseconds: 500)))
            .path;
        for (final pjt in loadedProjects) {
          for (var i = 0; i < pjt.photos.length; i++) {
            pjt.photos[i] = p.join(docsDir, p.basename(pjt.photos[i]));
          }
        }
      } catch (_) {}
    }
  }

  Future<void> _save() async {
    await prefs?.setString('server_url', server);
    await prefs?.setString(
      'projects_data',
      jsonEncode(projects.map((p) => p.toJson()).toList()),
    );
  }

  Future<void> _addProject() async {
    final c = TextEditingController(text: 'Projeto ${projects.length + 1}');
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Novo Projeto'),
        content: TextField(
          controller: c,
          autofocus: true,
          decoration: const InputDecoration(hintText: 'Nome do Projeto'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(ctx, c.text.trim()), child: const Text('Criar')),
        ],
      ),
    );

    if (name != null && name.isNotEmpty) {
      final pjt = Project(name);
      setState(() => projects.add(pjt));
      await _save();
      if (!mounted) return;
      // Vai direto colocar fotos no projeto criado!
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ProjectPhotosScreen(project: pjt, server: server, onChanged: _save),
        ),
      );
      setState(() {});
    }
  }

  Future<void> _deleteProject(Project project) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Excluir Projeto?'),
        content: Text('Excluir "${project.name}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Excluir'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      for (final path in project.photos) {
        try { await File(path).delete(); } catch (_) {}
      }
      setState(() => projects.remove(project));
      await _save();
    }
  }

  Future<void> _configServer() async {
    final c = TextEditingController(text: server);
    final url = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('URL do Servidor'),
        content: TextField(
          controller: c,
          autofocus: true,
          decoration: const InputDecoration(hintText: 'http://... ou https://...'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(ctx, c.text.trim()), child: const Text('Salvar')),
        ],
      ),
    );

    if (url != null && url.isNotEmpty) {
      setState(() => server = url);
      await _save();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Projetos'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: _configServer,
          ),
        ],
      ),
      body: projects.isEmpty
          ? const Center(child: Text('Sem projetos'))
          : ListView.separated(
              itemCount: projects.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (ctx, i) {
                final pjt = projects[i];
                return ListTile(
                  title: Text(pjt.name, style: const TextStyle(fontSize: 16)),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline, color: Colors.red),
                    onPressed: () => _deleteProject(pjt),
                  ),
                  onTap: () async {
                    // Clica no projeto e vai DIRETO para as fotos!
                    await Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => ProjectPhotosScreen(project: pjt, server: server, onChanged: _save),
                      ),
                    );
                    setState(() {});
                  },
                );
              },
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addProject,
        child: const Icon(Icons.add),
      ),
    );
  }
}

/// 2. TELA DE FOTOS DO PROJETO (Direto para por as fotos, sem tarefas)
class ProjectPhotosScreen extends StatefulWidget {
  final Project project;
  final String server;
  final Future<void> Function() onChanged;

  const ProjectPhotosScreen({
    super.key,
    required this.project,
    required this.server,
    required this.onChanged,
  });

  @override
  State<ProjectPhotosScreen> createState() => _ProjectPhotosScreenState();
}

class _ProjectPhotosScreenState extends State<ProjectPhotosScreen> {
  final picker = ImagePicker();
  bool sending = false;

  Future<String> _keep(XFile x) async {
    final dir = await getApplicationDocumentsDirectory();
    final dest = p.join(
      dir.path,
      '${DateTime.now().microsecondsSinceEpoch}${p.extension(x.path)}',
    );
    await File(x.path).copy(dest);
    return dest;
  }

  Future<void> _add(List<XFile> files) async {
    for (final f in files) {
      widget.project.photos.add(await _keep(f));
    }
    await widget.onChanged();
    if (mounted) setState(() {});
  }

  Future<void> _camera() async {
    final x = await picker.pickImage(source: ImageSource.camera, imageQuality: 80, maxWidth: 2048);
    if (x != null) await _add([x]);
  }

  Future<void> _gallery() async =>
      _add(await picker.pickMultiImage(imageQuality: 80, maxWidth: 2048));

  Future<void> _delete(int i) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Excluir foto?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Excluir'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      if (i < widget.project.sentCount) widget.project.sentCount--;
      final path = widget.project.photos.removeAt(i);
      try { await File(path).delete(); } catch (_) {}
      await widget.onChanged();
      setState(() {});
    }
  }

  Future<void> _send() async {
    final pending = widget.project.pending;
    if (pending.isEmpty) return;

    setState(() => sending = true);

    try {
      // Envia direto para o projeto, sem criar tarefa
      final req = http.MultipartRequest('POST', Uri.parse('${widget.server}/upload'))
        ..fields['project'] = widget.project.name;

      for (final path in pending) {
        req.files.add(await http.MultipartFile.fromPath('files', path));
      }

      final res = await req.send().timeout(const Duration(minutes: 5));
      if (res.statusCode != 200) throw Exception('${res.statusCode}');

      widget.project.sentCount += pending.length;
      await widget.onChanged();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Enviado com sucesso!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erro: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pjt = widget.project;
    final pendingCount = pjt.pending.length;

    return Scaffold(
      appBar: AppBar(
        title: Text(pjt.name),
      ),
      body: pjt.photos.isEmpty
          ? const Center(child: Text('Sem fotos'))
          : GridView.builder(
              padding: const EdgeInsets.all(6),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                crossAxisSpacing: 6,
                mainAxisSpacing: 6,
              ),
              itemCount: pjt.photos.length,
              itemBuilder: (ctx, i) {
                final isSent = i < pjt.sentCount;
                return GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => PhotoViewer(
                          photos: pjt.photos,
                          initialIndex: i,
                          onDelete: (idx) async {
                            Navigator.pop(context);
                            await _delete(idx);
                          },
                        ),
                      ),
                    );
                  },
                  onLongPress: () => _delete(i),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.file(File(pjt.photos[i]), fit: BoxFit.cover, cacheWidth: 300),
                      if (isSent)
                        const Positioned(
                          top: 4,
                          right: 4,
                          child: Icon(Icons.check_circle, color: Colors.green, size: 20),
                        ),
                    ],
                  ),
                );
              },
            ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (pendingCount > 0) ...[
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    style: FilledButton.styleFrom(
                      backgroundColor: Colors.green,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: sending ? null : _send,
                    icon: sending
                        ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Icon(Icons.cloud_upload),
                    label: Text(sending ? 'A enviar...' : 'Enviar ($pendingCount fotos)'),
                  ),
                ),
                const SizedBox(height: 8),
              ],
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _gallery,
                      icon: const Icon(Icons.photo_library),
                      label: const Text('Galeria'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: _camera,
                      icon: const Icon(Icons.photo_camera),
                      label: const Text('Câmera'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 3. VISUALIZADOR EM TELA CHEIA
class PhotoViewer extends StatelessWidget {
  final List<String> photos;
  final int initialIndex;
  final void Function(int) onDelete;

  const PhotoViewer({
    super.key,
    required this.photos,
    required this.initialIndex,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final pageController = PageController(initialPage: initialIndex);

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline, color: Colors.red),
            onPressed: () => onDelete(pageController.page?.round() ?? initialIndex),
          ),
        ],
      ),
      body: PageView.builder(
        controller: pageController,
        itemCount: photos.length,
        itemBuilder: (ctx, i) => InteractiveViewer(
          child: Center(
            child: Image.file(File(photos[i])),
          ),
        ),
      ),
    );
  }
}