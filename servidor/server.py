"""Servidor FastAPI para sincronização e gestão de tarefas com fotos anexadas.

Suporta:
- Sincronização direta com o app Flutter (POST /upload)
- Painel web interativo completo para navegação por Projeto e Tarefa
- Visualizador de fotos (Lightbox) com zoom e metadados
- Download de projetos e tarefas completos em formato .ZIP
- Gerenciamento de projetos, tarefas e fotos (criar, excluir, upload web)
- Detecção automática de IPs locais para configuração simplificada no telemóvel
"""

import io
import os
import re
import socket
import subprocess
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = (BASE_DIR / "storage").resolve()
STATIC_DIR = (BASE_DIR / "static").resolve()

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Servidor de Gestão de Tarefas e Fotos")

# Habilitar CORS para qualquer origem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sanitize_name(name: str) -> str:
    """Higieniza nomes de pastas preservando acentuação e caracteres amigáveis."""
    if not name:
        return "sem_nome"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(name))
    cleaned = cleaned.strip('. ')
    return cleaned[:100] or "sem_nome"


def safe_resolve(base: Path, *parts: str) -> Path:
    """Resolve caminhos garantindo que não escapem do diretório base."""
    sanitized_parts = [sanitize_name(p) for p in parts if p]
    target = base.joinpath(*sanitized_parts).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Caminho de diretório inválido.")
    return target


def format_bytes(num_bytes: int) -> str:
    """Formata bytes em formato legível (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


PUBLIC_URL: Optional[str] = None
TUNNEL_PROCESS: Optional[subprocess.Popen] = None


def run_cloudflared_tunnel():
    """Inicia o Cloudflare Tunnel para expor o servidor na Internet (4G/5G/qualquer rede)."""
    global PUBLIC_URL, TUNNEL_PROCESS
    cloudflared_bin = BASE_DIR / "cloudflared.exe"
    if not cloudflared_bin.exists():
        return

    cmd = [str(cloudflared_bin), "tunnel", "--url", "http://127.0.0.1:8000"]
    try:
        TUNNEL_PROCESS = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in TUNNEL_PROCESS.stdout:
            m = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
            if m:
                PUBLIC_URL = m.group(0)
                print("\n" + "=" * 60)
                print(f"URL PUBLICA (4G/5G/INTERNET): {PUBLIC_URL}")
                print("=" * 60 + "\n")
                break
    except Exception as e:
        print(f"Aviso: Não foi possível iniciar o Cloudflare Tunnel: {e}")


# Inicia o tunnel em segundo plano
threading.Thread(target=run_cloudflared_tunnel, daemon=True).start()


def get_local_network_info():
    """Detecta os IPs locais e a URL pública (Cloudflare Tunnel) da máquina."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        primary = s.getsockname()[0]
        s.close()
        if primary and not primary.startswith("127."):
            ips.append(primary)
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    if not ips:
        ips = ["127.0.0.1"]

    primary_ip = ips[0]
    best_url = PUBLIC_URL or f"http://{primary_ip}:8000"

    return {
        "ips": ips,
        "primary_ip": primary_ip,
        "port": 8000,
        "public_url": PUBLIC_URL,
        "app_url": best_url,
        "app_urls": ([PUBLIC_URL] if PUBLIC_URL else []) + [f"http://{ip}:8000" for ip in ips]
    }


# ============================================================================
# ENDPOINTS PRINCIPAIS E COMPATIBILIDADE FLUTTER
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve a interface web do servidor."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Servidor ativo. O arquivo index.html não foi encontrado em /static.</h1>")


@app.post("/upload")
async def upload(
    project: str = Form(...),
    task: Optional[str] = Form(None),
    files: List[UploadFile] = File(...)
):
    """
    Endpoint de upload.
    Se 'task' for informado, organiza em: storage/<Projeto>/<Tarefa>/foto_001.jpg
    Se 'task' for omitido, organiza direto em: storage/<Projeto>/foto_001.jpg
    """
    if task and task.strip() and task.strip().lower() not in ["none", "null", "geral", "fotos"]:
        folder = safe_resolve(STORAGE_DIR, project, task)
    else:
        folder = safe_resolve(STORAGE_DIR, project)

    folder.mkdir(parents=True, exist_ok=True)

    # Identifica o maior número existente no padrão foto_XXX para evitar conflitos
    max_n = 0
    for p in folder.iterdir():
        if p.is_file():
            m = re.match(r"^foto_(\d+)", p.name, re.IGNORECASE)
            if m:
                try:
                    max_n = max(max_n, int(m.group(1)))
                except ValueError:
                    pass

    saved = []
    n = max_n
    for f in files:
        n += 1
        ext = Path(f.filename or "").suffix.lower() or ".jpg"
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic"]:
            ext = ".jpg"
        name = f"foto_{n:03d}{ext}"
        content = await f.read()
        (folder / name).write_bytes(content)
        saved.append(name)

    return {
        "saved": saved,
        "count": len(saved),
        "project": sanitize_name(project),
        "task": sanitize_name(task) if task else None
    }


# ============================================================================
# API DE DADOS PARA A INTERFACE WEB
# ============================================================================

@app.get("/api/network-info")
async def api_network_info():
    """Retorna informações de rede e URLs para o app Flutter."""
    return get_local_network_info()


@app.get("/api/stats")
async def api_stats():
    """Retorna estatísticas globais do servidor."""
    projects_count = 0
    tasks_count = 0
    photos_count = 0
    total_size = 0

    if STORAGE_DIR.exists():
        for proj in STORAGE_DIR.iterdir():
            if proj.is_dir() and not proj.name.startswith("."):
                projects_count += 1
                for item in proj.iterdir():
                    if item.is_file() and not item.name.startswith("."):
                        photos_count += 1
                        try:
                            total_size += item.stat().st_size
                        except Exception:
                            pass
                    elif item.is_dir() and not item.name.startswith("."):
                        tasks_count += 1
                        for photo in item.iterdir():
                            if photo.is_file() and not photo.name.startswith("."):
                                photos_count += 1
                                try:
                                    total_size += photo.stat().st_size
                                except Exception:
                                    pass

    return {
        "projects_count": projects_count,
        "tasks_count": tasks_count,
        "photos_count": photos_count,
        "total_size_bytes": total_size,
        "total_size_formatted": format_bytes(total_size)
    }


@app.get("/api/projects")
async def list_projects():
    """Retorna a lista de projetos com totais de fotos."""
    projects = []
    if STORAGE_DIR.exists():
        for proj_dir in sorted(STORAGE_DIR.iterdir(), key=lambda p: p.name.lower()):
            if proj_dir.is_dir() and not proj_dir.name.startswith("."):
                t_count = 0
                p_count = 0
                size = 0
                latest_mtime = proj_dir.stat().st_mtime

                for item in proj_dir.iterdir():
                    if item.is_file() and not item.name.startswith("."):
                        p_count += 1
                        try:
                            st = item.stat()
                            size += st.st_size
                            latest_mtime = max(latest_mtime, st.st_mtime)
                        except Exception:
                            pass
                    elif item.is_dir() and not item.name.startswith("."):
                        t_count += 1
                        latest_mtime = max(latest_mtime, item.stat().st_mtime)
                        for photo in item.iterdir():
                            if photo.is_file() and not photo.name.startswith("."):
                                p_count += 1
                                try:
                                    st = photo.stat()
                                    size += st.st_size
                                    latest_mtime = max(latest_mtime, st.st_mtime)
                                except Exception:
                                    pass

                projects.append({
                    "name": proj_dir.name,
                    "tasks_count": t_count,
                    "photos_count": p_count,
                    "total_size_bytes": size,
                    "total_size_formatted": format_bytes(size),
                    "updated_at": datetime.fromtimestamp(latest_mtime).strftime("%d/%m/%Y %H:%M")
                })
    return projects


@app.get("/api/projects/{project}/tasks")
async def list_project_tasks(project: str):
    """Retorna fotos diretas do projeto ou tarefas com fotos."""
    proj_dir = safe_resolve(STORAGE_DIR, project)
    if not proj_dir.exists() or not proj_dir.is_dir():
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    tasks = []

    # 1. Fotos diretas no projeto
    direct_photos = [f.name for f in sorted(proj_dir.iterdir(), key=lambda p: p.name.lower()) if f.is_file() and not f.name.startswith(".")]
    if direct_photos:
        size = sum(f.stat().st_size for f in proj_dir.iterdir() if f.is_file() and not f.name.startswith("."))
        previews = [f"/api/photos/{quote(proj_dir.name)}/{quote(name)}" for name in direct_photos[:4]]
        tasks.append({
            "name": "Fotos",
            "photos_count": len(direct_photos),
            "preview_photos": previews,
            "total_size_bytes": size,
            "total_size_formatted": format_bytes(size),
            "updated_at": datetime.fromtimestamp(proj_dir.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        })

    # 2. Tarefas em subpastas
    for task_dir in sorted(proj_dir.iterdir(), key=lambda p: p.name.lower()):
        if task_dir.is_dir() and not task_dir.name.startswith("."):
            photos = []
            size = 0
            latest_mtime = task_dir.stat().st_mtime

            for photo in sorted(task_dir.iterdir(), key=lambda p: p.name.lower()):
                if photo.is_file() and not photo.name.startswith("."):
                    try:
                        st = photo.stat()
                        size += st.st_size
                        latest_mtime = max(latest_mtime, st.st_mtime)
                        photos.append(photo.name)
                    except Exception:
                        pass

            previews = [
                f"/api/photos/{quote(proj_dir.name)}/{quote(task_dir.name)}/{quote(name)}"
                for name in photos[:4]
            ]

            tasks.append({
                "name": task_dir.name,
                "photos_count": len(photos),
                "preview_photos": previews,
                "total_size_bytes": size,
                "total_size_formatted": format_bytes(size),
                "updated_at": datetime.fromtimestamp(latest_mtime).strftime("%d/%m/%Y %H:%M")
            })

    return tasks


@app.get("/api/projects/{project}/tasks/{task}")
async def get_task_details(project: str, task: str):
    """Retorna detalhes da tarefa e todas as fotos com metadados."""
    task_dir = safe_resolve(STORAGE_DIR, project, task)
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    photos = []
    total_size = 0
    for photo in sorted(task_dir.iterdir(), key=lambda p: p.name.lower()):
        if photo.is_file() and not photo.name.startswith("."):
            st = photo.stat()
            total_size += st.st_size
            photos.append({
                "name": photo.name,
                "url": f"/api/photos/{quote(project)}/{quote(task)}/{quote(photo.name)}",
                "size_bytes": st.st_size,
                "size_formatted": format_bytes(st.st_size),
                "created_at": datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
            })

    return {
        "project": project,
        "task": task,
        "photos_count": len(photos),
        "total_size_bytes": total_size,
        "total_size_formatted": format_bytes(total_size),
        "photos": photos
    }


@app.get("/api/photos/{project}/{filename:path}")
async def get_photo(project: str, filename: str):
    """Entrega a foto (direta no projeto ou em subpasta de tarefa)."""
    file_path = safe_resolve(STORAGE_DIR, project, filename)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    return FileResponse(file_path)


# ============================================================================
# EXPORTAÇÃO EM ARQUIVO ZIP
# ============================================================================

@app.get("/api/download/task/{project}/{task}")
async def download_task_zip(project: str, task: str):
    """Gera um arquivo ZIP com todas as fotos de uma tarefa."""
    task_dir = safe_resolve(STORAGE_DIR, project, task)
    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(task_dir.iterdir()):
            if file_path.is_file() and not file_path.name.startswith("."):
                zf.write(file_path, arcname=file_path.name)
    zip_buffer.seek(0)

    zip_name = f"{project}_{task}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(zip_name)}"}
    )


@app.get("/api/download/project/{project}")
async def download_project_zip(project: str):
    """Gera um arquivo ZIP com todo o projeto organizado por pastas de tarefas."""
    proj_dir = safe_resolve(STORAGE_DIR, project)
    if not proj_dir.exists() or not proj_dir.is_dir():
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(proj_dir):
            for file in sorted(files):
                if file.startswith("."):
                    continue
                full_path = Path(root) / file
                rel_path = full_path.relative_to(proj_dir)
                zf.write(full_path, arcname=str(rel_path))
    zip_buffer.seek(0)

    zip_name = f"{project}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(zip_name)}"}
    )


# ============================================================================
# GESTÃO (CRIAÇÃO E EXCLUSÃO)
# ============================================================================

class ProjectCreate(BaseModel):
    name: str

class TaskCreate(BaseModel):
    project: str
    name: str


@app.post("/api/projects")
async def create_project(data: ProjectCreate):
    """Cria uma nova pasta de projeto."""
    proj_dir = safe_resolve(STORAGE_DIR, data.name)
    proj_dir.mkdir(parents=True, exist_ok=True)
    return {"message": "Projeto criado com sucesso", "name": proj_dir.name}


@app.post("/api/tasks")
async def create_task(data: TaskCreate):
    """Cria uma nova tarefa dentro de um projeto."""
    task_dir = safe_resolve(STORAGE_DIR, data.project, data.name)
    task_dir.mkdir(parents=True, exist_ok=True)
    return {"message": "Tarefa criada com sucesso", "project": data.project, "name": task_dir.name}


@app.delete("/api/photos/{project}/{task}/{filename}")
async def delete_photo(project: str, task: str, filename: str):
    """Exclui uma foto específica."""
    file_path = safe_resolve(STORAGE_DIR, project, task, filename)
    if file_path.exists() and file_path.is_file():
        file_path.unlink()
        return {"message": "Foto excluída com sucesso"}
    raise HTTPException(status_code=404, detail="Foto não encontrada")


@app.delete("/api/tasks/{project}/{task}")
async def delete_task(project: str, task: str):
    """Exclui uma tarefa inteira com suas fotos."""
    task_dir = safe_resolve(STORAGE_DIR, project, task)
    if task_dir.exists() and task_dir.is_dir():
        import shutil
        shutil.rmtree(task_dir)
        return {"message": "Tarefa excluída com sucesso"}
    raise HTTPException(status_code=404, detail="Tarefa não encontrada")


@app.delete("/api/projects/{project}")
async def delete_project(project: str):
    """Exclui um projeto inteiro com todas as suas tarefas e fotos."""
    proj_dir = safe_resolve(STORAGE_DIR, project)
    if proj_dir.exists() and proj_dir.is_dir():
        import shutil
        shutil.rmtree(proj_dir)
        return {"message": "Projeto excluído com sucesso"}
    raise HTTPException(status_code=404, detail="Projeto não encontrado")


# ============================================================================
# GERADOR DE DADOS DE EXEMPLO (DEMONSTRAÇÃO)
# ============================================================================

def create_sample_png_bytes(text: str, color_hex: str = "#4f46e5", width: int = 400, height: int = 300) -> bytes:
    """Gera um PNG válido e visualmente agradável usando zlib em Python puro."""
    import struct
    import zlib

    # Converte cor hex para RGB
    color_hex = color_hex.lstrip('#')
    r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))

    # Cria pixels com gradiente e moldura
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # filter type 0 (None)
        for x in range(width):
            # Gradiente sutil e borda
            if x < 4 or x >= width - 4 or y < 4 or y >= height - 4:
                raw_data.extend([30, 41, 59])  # moldura escura
            elif y < 50:
                raw_data.extend([min(255, r + 20), min(255, g + 20), min(255, b + 20)])
            else:
                factor = 0.8 + 0.2 * (y / height)
                raw_data.extend([int(r * factor), int(g * factor), int(b * factor)])

    compressed = zlib.compress(bytes(raw_data))

    png = bytearray()
    png.extend(b"\x89PNG\r\n\x1a\n")  # PNG Header

    # IHDR Chunk
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    png.extend(struct.pack(">I", len(ihdr_data)))
    png.extend(b"IHDR")
    png.extend(ihdr_data)
    png.extend(struct.pack(">I", ihdr_crc))

    # IDAT Chunk
    idat_crc = zlib.crc32(b"IDAT" + compressed)
    png.extend(struct.pack(">I", len(compressed)))
    png.extend(b"IDAT")
    png.extend(compressed)
    png.extend(struct.pack(">I", idat_crc))

    # IEND Chunk
    iend_crc = zlib.crc32(b"IEND")
    png.extend(struct.pack(">I", 0))
    png.extend(b"IEND")
    png.extend(struct.pack(">I", iend_crc))

    return bytes(png)


@app.post("/api/generate-samples")
async def generate_samples():
    """Gera dados de demonstração (Projeto 001 com Tarefas e Fotos)."""
    samples = [
        {
            "project": "Projeto 001",
            "task": "Tarefa 1 – Instalação do Equipamento",
            "photos": [
                ("foto_001.png", "#2563eb"),
                ("foto_002.png", "#0284c7"),
                ("foto_003.png", "#0d9488"),
                ("foto_004.png", "#16a34a"),
            ]
        },
        {
            "project": "Projeto 001",
            "task": "Tarefa 2 – Vistoria Elétrica",
            "photos": [
                ("foto_001.png", "#d97706"),
                ("foto_002.png", "#ea580c"),
                ("foto_003.png", "#dc2626"),
            ]
        },
        {
            "project": "Projeto 002 - Reforma Predial",
            "task": "Tarefa 1 – Inspeção de Fachada",
            "photos": [
                ("foto_001.png", "#7c3aed"),
                ("foto_002.png", "#9333ea"),
            ]
        }
    ]

    for item in samples:
        folder = safe_resolve(STORAGE_DIR, item["project"], item["task"])
        folder.mkdir(parents=True, exist_ok=True)
        for filename, color in item["photos"]:
            file_path = folder / filename
            if not file_path.exists():
                file_path.write_bytes(create_sample_png_bytes(filename, color))

    return {"message": "Dados de exemplo gerados com sucesso!"}