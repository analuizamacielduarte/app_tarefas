# Gestão de Tarefas com Fotos Anexadas 📱📸

Sistema composto por um **aplicativo móvel em Flutter** (simples, direto ao ponto, com gestão de múltiplos projetos) e um **servidor central em FastAPI** com visualização web e suporte a conexão remota (4G/Internet sem precisar estar no mesmo Wi-Fi).

---

## 🚀 1. Iniciar o Servidor

Dê dois cliques no arquivo:
```
iniciar_servidor.bat
```
Ao iniciar, o servidor exibirá duas URLs:
- **Computador Local:** `http://localhost:8000` (abre o painel web)
- **Internet / 4G (Remoto):** Uma URL pública segura `https://...trycloudflare.com` gerada automaticamente.

> **Sem precisar do mesmo Wi-Fi:** Cole a URL pública `https://...trycloudflare.com` no aplicativo do celular. Ele funcionará em qualquer lugar (4G, 5G ou redes Wi-Fi externas).

---

## 📱 2. Interface Mobile Direta (Flutter)

A interface foi simplificada ao máximo, sem textos tutoriais ou tutoriais longos:

1. **Tela de Projetos:**
   - Mostra a lista de projetos criados (`Projeto 001`, `Reforma`, etc.).
   - Botão **"Novo Projeto"** (+) para criar novos projetos diretamente pelo celular.
   - Ícone de lixeira para excluir projetos diretamente pelo celular.
   - Ícone no topo para colar a URL do servidor (Local ou 4G).
2. **Tela de Tarefas:**
   - Ao tocar em um projeto, abre a lista de tarefas daquele projeto.
   - Botão **"Nova Tarefa"** (+) para criar tarefas.
   - Botão **"Enviar Fotos"** (aparece na barra inferior se houver fotos pendentes).
3. **Tela de Fotos:**
   - Grade limpa com fotos tiradas.
   - Botões diretos: **Câmera** (fotografar) e **Galeria** (selecionar várias).
   - Toque para ver em tela cheia (zoom interativo).
   - Pressione para excluir foto.

---

## 🖥️ 3. Painel Web do Computador

- Acesse `http://localhost:8000` no computador.
- Fotos recebidas são salvas em:
  `servidor/storage/<Projeto>/<Tarefa>/foto_001.jpg`, `foto_002.jpg`...
- Visualizador com fotos em alta resolução, galeria por tarefa e download de projetos e tarefas inteiros em `.ZIP`.
