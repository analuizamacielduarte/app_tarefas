"""Script para gerar dados de exemplo para o servidor de tarefas com fotos.
Cria o Projeto 001 com Tarefa 1 (Instalação) e Tarefa 2 (Vistoria).
"""
import sys
from pathlib import Path

# Adiciona o diretório do servidor ao path para importar a função de geração
sys.path.insert(0, str(Path(__file__).resolve().parent))
import asyncio
from server import generate_samples

if __name__ == "__main__":
    print("Gerando dados de exemplo...")
    asyncio.run(generate_samples())
    print("Concluído! Pastas criadas em storage/")
