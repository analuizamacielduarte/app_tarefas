@echo off
chcp 65001 > nul
title Servidor de Tarefas e Fotos
echo ========================================================
echo   Iniciando Servidor de Gestao de Tarefas e Fotos
echo ========================================================
echo.
cd /d "%~dp0"

echo Verificando dependencias Python...
python -m pip install fastapi uvicorn python-multipart > nul 2>&1

echo.
echo Servidor disponivel em:
echo   - Computador Local: http://localhost:8000
echo   - Internet / 4G:    URL publica gerada automaticamente abaixo (Cloudflare)
echo.
echo Dica: Cole a URL https://....trycloudflare.com no app mobile.
echo Nao precisa estar no mesmo Wi-Fi!
echo.
echo Pressione CTRL+C para encerrar o servidor.
echo.

start "" "http://localhost:8000"

python -m uvicorn server:app --host 0.0.0.0 --port 8000
pause
