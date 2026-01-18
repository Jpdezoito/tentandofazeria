import os
import subprocess

def open_file(file_path: str) -> bool:
    """Abre um arquivo usando o programa padrao do sistema."""
    try:
        if os.name == 'nt':  # Windows
            os.startfile(file_path)
        elif os.name == 'posix':  # macOS/Linux
            subprocess.run(['xdg-open', file_path], check=True)
        else:
            print("Sistema operacional nao suportado")
            return False
        return True
    except Exception as e:
        print(f"Erro ao abrir arquivo {file_path}: {e}")
        return False

# Simular _do_play para música local
music_files = []
music_dir = os.path.expanduser("~/Music")

# Procurar em múltiplas pastas possíveis
possible_dirs = [
    os.path.expanduser("~/Music"),
    os.path.expanduser("~/Música"),  # Com acento
    os.path.expanduser("~/My Music"),  # Inglês antigo
    os.path.expanduser("~/Documents/Music"),
    os.path.expanduser("~/Downloads"),
    "C:\\Users\\Public\\Music",
]
# Adicionar drives se existirem
for drive in ['D:', 'E:', 'F:']:
    if os.path.exists(f"{drive}\\Music"):
        possible_dirs.append(f"{drive}\\Music")

best_dir = None
max_files = 0
for d in possible_dirs:
    if os.path.exists(d):
        temp_files = []
        for root, dirs, files in os.walk(d):
            for file in files:
                if file.lower().endswith(('.mp3', '.wav', '.flac', '.mp4', '.avi', '.m4a')):
                    temp_files.append(os.path.join(root, file))
            if len(temp_files) > 50:  # limitar busca
                break
        if len(temp_files) > max_files:
            max_files = len(temp_files)
            music_files = temp_files
            best_dir = d

if music_files:
    music_dir = best_dir