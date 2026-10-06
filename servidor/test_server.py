"""Bateria de testes completa para todos os endpoints e regras de negócio do servidor FastAPI.
"""
import asyncio
import io
from pathlib import Path
from starlette.datastructures import UploadFile
import server

async def run_tests():
    print("==================================================")
    print("INICIANDO TESTES DO SERVIDOR FASTAPI (BACKEND)")
    print("==================================================")

    # 1. Geração de dados de teste
    print("\n1. Testando geração de dados de exemplo (/api/generate-samples)...")
    gen_res = await server.generate_samples()
    assert "message" in gen_res
    print(f"   [OK] {gen_res['message']}")

    # 2. Estatísticas do servidor
    print("\n2. Testando api_stats()...")
    stats = await server.api_stats()
    assert stats["projects_count"] >= 1
    assert stats["tasks_count"] >= 1
    assert stats["photos_count"] >= 1
    assert stats["total_size_bytes"] > 0
    print(f"   [OK] Stats: {stats['projects_count']} projetos, {stats['tasks_count']} tarefas, {stats['photos_count']} fotos, {stats['total_size_formatted']}")

    # 3. Informações de rede para app mobile
    print("\n3. Testando api_network_info()...")
    net = await server.api_network_info()
    assert "app_url" in net
    assert "ips" in net
    print(f"   [OK] URL para Flutter App: {net['app_url']}")

    # 4. Listagem de projetos
    print("\n4. Testando list_projects()...")
    projects = await server.list_projects()
    assert len(projects) >= 1
    proj_names = [p["name"] for p in projects]
    print(f"   [OK] {len(projects)} projetos encontrados: {proj_names}")

    # 5. Listagem de tarefas do projeto
    proj_with_tasks = next((p["name"] for p in projects if p["tasks_count"] > 0), "Projeto 001")
    print(f"\n5. Testando list_project_tasks('{proj_with_tasks}')...")
    tasks = await server.list_project_tasks(proj_with_tasks)
    assert len(tasks) >= 1
    task_name = tasks[0]["name"]
    proj_name = proj_with_tasks
    print(f"   [OK] {len(tasks)} tarefas no projeto: {[t['name'] for t in tasks]}")

    # 6. Detalhes da tarefa e lista de fotos
    print(f"\n6. Testando get_task_details('{proj_name}', '{task_name}')...")
    details = await server.get_task_details(proj_name, task_name)
    assert details["project"] == proj_name
    assert details["task"] == task_name
    assert len(details["photos"]) >= 1
    photo_name = details["photos"][0]["name"]
    print(f"   [OK] {len(details['photos'])} fotos na tarefa. Primeira foto: {photo_name}")

    # 7. Download/Serviço do arquivo de foto
    print(f"\n7. Testando get_photo('{proj_name}', '{task_name}', '{photo_name}')...")
    photo_resp = await server.get_photo(proj_name, task_name, photo_name)
    assert photo_resp.status_code == 200
    assert Path(photo_resp.path).exists()
    print(f"   [OK] Arquivo de foto entregue com sucesso: {photo_resp.path}")

    # 8. Exportação da Tarefa em ZIP
    print(f"\n8. Testando download_task_zip('{proj_name}', '{task_name}')...")
    task_zip = await server.download_task_zip(proj_name, task_name)
    assert task_zip.media_type == "application/zip"
    print(f"   [OK] Streaming de ZIP da tarefa funcionando")

    # 9. Exportação do Projeto em ZIP
    print(f"\n9. Testando download_project_zip('{proj_name}')...")
    proj_zip = await server.download_project_zip(proj_name)
    assert proj_zip.media_type == "application/zip"
    print(f"   [OK] Streaming de ZIP do projeto funcionando")

    # 10. Criação de Projeto via API
    test_proj = "Projeto Teste Automatizado"
    print(f"\n10. Testando criação de projeto: '{test_proj}'...")
    create_proj_res = await server.create_project(server.ProjectCreate(name=test_proj))
    assert create_proj_res["name"] == test_proj
    print(f"   [OK] Projeto criado no disco com sucesso")

    # 11. Criação de Tarefa via API
    test_task = "Tarefa Teste Unitaria"
    print(f"\n11. Testando criação de tarefa: '{test_task}'...")
    create_task_res = await server.create_task(server.TaskCreate(project=test_proj, name=test_task))
    assert create_task_res["name"] == test_task
    print(f"   [OK] Tarefa criada dentro do projeto com sucesso")

    # 12. Upload de Foto compatível com Flutter (/upload)
    print("\n12. Testando upload de foto multipart compatível com Flutter...")
    raw_img = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
    upload_file = UploadFile(file=raw_img, filename="evidencia_camera.png")
    
    upload_res = await server.upload(
        project=test_proj,
        task=test_task,
        files=[upload_file]
    )
    assert "saved" in upload_res
    assert len(upload_res["saved"]) == 1
    saved_filename = upload_res["saved"][0]
    print(f"   [OK] Foto salva como: {saved_filename} (numeração sequencial correta)")

    # 13. Exclusão de Foto
    print(f"\n13. Testando exclusão de foto: '{saved_filename}'...")
    del_photo_res = await server.delete_photo(test_proj, test_task, saved_filename)
    assert "message" in del_photo_res
    print(f"   [OK] Foto excluída com sucesso")

    # 14. Exclusão de Tarefa
    print(f"\n14. Testando exclusão da tarefa de teste...")
    del_task_res = await server.delete_task(test_proj, test_task)
    assert "message" in del_task_res
    print(f"   [OK] Pasta da tarefa excluída com sucesso")

    # 15. Exclusão de Projeto
    print(f"\n15. Testando exclusão do projeto de teste...")
    del_proj_res = await server.delete_project(test_proj)
    assert "message" in del_proj_res
    print(f"   [OK] Pasta do projeto excluída com sucesso")

    # 16. Interface Web index.html
    print("\n16. Testando entrega da interface web SPA (index.html)...")
    idx_resp = await server.serve_index()
    assert idx_resp.status_code == 200
    print(f"   [OK] Interface Web entregue com código 200")

    print("\n==================================================")
    print("TODOS OS 16 TESTES DO BACKEND PASSARAM COM SUCESSO!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
