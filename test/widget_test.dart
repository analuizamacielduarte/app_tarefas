import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:app_tarefas/main.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({
      'server_url': 'http://192.168.1.8:8000',
    });
  });

  group('Testes Unitários do Modelo Project', () {
    test('Criação inicial e fotos pendentes no Project', () {
      final project = Project('Projeto 001');
      expect(project.name, 'Projeto 001');
      expect(project.photos, isEmpty);
      expect(project.sentCount, 0);
      expect(project.pending, isEmpty);

      // Adiciona 3 fotos
      project.photos.addAll(['/doc/foto1.jpg', '/doc/foto2.jpg', '/doc/foto3.jpg']);
      expect(project.pending.length, 3);

      // Simula envio de 2 fotos
      project.sentCount = 2;
      expect(project.pending.length, 1);
      expect(project.pending, ['/doc/foto3.jpg']);

      // Todas enviadas
      project.sentCount = 3;
      expect(project.pending, isEmpty);
    });

    test('Serialização e Deserialização do Project', () {
      final project = Project(
        'Projeto Alpha',
        photos: ['/foto1.jpg', '/foto2.jpg'],
        sentCount: 1,
      );

      final json = project.toJson();
      expect(json['name'], 'Projeto Alpha');
      expect((json['photos'] as List).length, 2);
      expect(json['sentCount'], 1);

      final decoded = Project.fromJson(json);
      expect(decoded.name, 'Projeto Alpha');
      expect(decoded.photos.length, 2);
      expect(decoded.sentCount, 1);
      expect(decoded.pending, ['/foto2.jpg']);
    });
  });

  group('Testes de Interface do Mobile (Projetos e Fotos Diretas)', () {
    testWidgets('Renderiza lista de projetos e botão de adicionar', (WidgetTester tester) async {
      await tester.pumpWidget(const App());
      await tester.pumpAndSettle();

      // Verifica título, presença do projeto inicial e botão +
      expect(find.text('Projetos'), findsOneWidget);
      expect(find.text('Projeto 001'), findsOneWidget);
      expect(find.byIcon(Icons.add), findsOneWidget);
    });

    testWidgets('Adiciona um novo projeto e vai direto para as fotos', (WidgetTester tester) async {
      await tester.pumpWidget(const App());
      await tester.pumpAndSettle();

      // Toca no botão +
      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      // Diálogo aberto
      expect(find.byType(AlertDialog), findsOneWidget);
      expect(find.text('Novo Projeto'), findsOneWidget);

      // Digita o nome do projeto
      await tester.enterText(find.byType(TextField), 'Reforma do Prédio B');
      await tester.tap(find.text('Criar'));
      await tester.pumpAndSettle();

      // Entra DIRETAMENTE na tela de fotos do projeto recém-criado
      expect(find.text('Reforma do Prédio B'), findsOneWidget);
      expect(find.text('Sem fotos'), findsOneWidget);
      expect(find.text('Câmera'), findsOneWidget);
      expect(find.text('Galeria'), findsOneWidget);
    });

    testWidgets('Exclui um projeto diretamente pelo mobile', (WidgetTester tester) async {
      await tester.pumpWidget(const App());
      await tester.pumpAndSettle();

      // Verifica que Projeto 001 existe
      expect(find.text('Projeto 001'), findsOneWidget);

      // Toca no botão de exclusão
      final deleteIcons = find.byIcon(Icons.delete_outline);
      expect(deleteIcons, findsWidgets);
      await tester.tap(deleteIcons.first);
      await tester.pumpAndSettle();

      // Diálogo de confirmação
      expect(find.text('Excluir Projeto?'), findsOneWidget);
      await tester.tap(find.text('Excluir'));
      await tester.pumpAndSettle();

      // Verifica que o projeto foi removido
      expect(find.text('Projeto 001'), findsNothing);
      expect(find.text('Sem projetos'), findsOneWidget);
    });

    testWidgets('Clica no projeto e abre diretamente a tela de fotos', (WidgetTester tester) async {
      await tester.pumpWidget(const App());
      await tester.pumpAndSettle();

      // Clica diretamente no Projeto 001
      await tester.tap(find.text('Projeto 001'));
      await tester.pumpAndSettle();

      // Abre diretamente a tela de fotos do projeto
      expect(find.text('Projeto 001'), findsOneWidget);
      expect(find.text('Sem fotos'), findsOneWidget);
      expect(find.text('Câmera'), findsOneWidget);
      expect(find.text('Galeria'), findsOneWidget);
    });

    testWidgets('Configura URL do servidor para acesso local ou 4G', (WidgetTester tester) async {
      await tester.pumpWidget(const App());
      await tester.pumpAndSettle();

      // Toca no ícone de configuração do servidor
      await tester.tap(find.byIcon(Icons.settings));
      await tester.pumpAndSettle();

      // Verifica diálogo do servidor
      expect(find.text('URL do Servidor'), findsOneWidget);

      // Insere uma URL remota / Cloudflare
      await tester.enterText(find.byType(TextField), 'https://meu-servidor-4g.trycloudflare.com');
      await tester.tap(find.text('Salvar'));
      await tester.pumpAndSettle();

      expect(find.byType(AlertDialog), findsNothing);
    });
  });
}
