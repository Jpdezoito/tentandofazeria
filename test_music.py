import os

# Testar o caminho da pasta Música
music_dir = os.path.expanduser("~/Music")
print(f"Caminho da pasta Música: {music_dir}")
print(f"Existe: {os.path.exists(music_dir)}")

if os.path.exists(music_dir):
    files = []
    for root, dirs, files_in_dir in os.walk(music_dir):
        for file in files_in_dir:
            if file.lower().endswith(('.mp3', '.wav', '.flac', '.mp4', '.avi', '.m4a')):
                files.append(os.path.join(root, file))
        if len(files) > 5:  # limitar para teste
            break
    print(f"Arquivos de música encontrados: {len(files)}")
    for f in files[:5]:
        print(f"  {os.path.basename(f)}")
else:
    print("Pasta Música não existe. Verificando outras possibilidades...")

    # Verificar outras pastas comuns
    possible_dirs = [
        os.path.expanduser("~/Música"),  # Com acento
        os.path.expanduser("~/My Music"),  # Inglês antigo
        "C:\\Users\\Public\\Music",
        "D:\\Music",  # Se houver D:
    ]
    for d in possible_dirs:
        if os.path.exists(d):
            print(f"Encontrei pasta alternativa: {d}")
            music_dir = d
            break
    else:
        print("Nenhuma pasta de música encontrada.")

# Testar abrir a pasta
if os.path.exists(music_dir):
    import subprocess
    try:
        subprocess.run(["explorer", music_dir])
        print("Pasta aberta com sucesso.")
    except Exception as e:
        print(f"Erro ao abrir pasta: {e}")
else:
    print("Não foi possível abrir a pasta.")