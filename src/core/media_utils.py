"""
Utilitarios para manipulacao de midia (audio, video, imagens).
"""

import os
import subprocess
import logging
from typing import Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

def open_file(file_path: str) -> bool:
    """Abre um arquivo usando o programa padrao do sistema."""
    try:
        if os.name == 'nt':  # Windows
            os.startfile(file_path)
        elif os.name == 'posix':  # macOS/Linux
            subprocess.run(['xdg-open', file_path], check=True)
        else:
            messagebox.showerror("Erro", "Sistema operacional nao suportado para abertura de arquivos.")
            return False
        return True
    except Exception as e:
        logger.error(f"Erro ao abrir arquivo {file_path}: {e}")
        messagebox.showerror("Erro", f"Nao foi possivel abrir o arquivo: {e}")
        return False

def create_image_thumbnail(image_path: str, size: tuple = (100, 100)) -> Optional[ImageTk.PhotoImage]:
    """Cria um thumbnail de imagem."""
    try:
        img = Image.open(image_path)
        img.thumbnail(size)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        logger.error(f"Erro ao criar thumbnail: {e}")
        return None

class ImageViewer(ctk.CTkToplevel):
    """Visualizador de imagem simples."""

    def __init__(self, master, image_path: str, **kwargs):
        super().__init__(master, **kwargs)
        self.title(f"Visualizar: {os.path.basename(image_path)}")
        self.geometry("600x600")

        try:
            img = Image.open(image_path)
            # Redimensionar mantendo proporcao
            img.thumbnail((580, 580))
            self.photo = ImageTk.PhotoImage(img)

            label = tk.Label(self, image=self.photo)
            label.pack(expand=True, fill="both", padx=10, pady=10)

            # Botao fechar
            close_btn = ctk.CTkButton(self, text="Fechar", command=self.destroy)
            close_btn.pack(pady=10)

        except Exception as e:
            messagebox.showerror("Erro", f"Nao foi possivel carregar a imagem: {e}")
            self.destroy()


class VideoViewer(ctk.CTkToplevel):
    """Visualizador de vídeo usando VLC."""

    def __init__(self, master, video_path: str, vlc_instance=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title(f"Reproduzir: {os.path.basename(video_path)}")
        self.geometry("800x600")

        try:
            import vlc
            if vlc_instance is None:
                vlc_instance = vlc.Instance()
            self.player = vlc_instance.media_player_new()
            
            # Frame para o vídeo
            self.video_frame = tk.Frame(self, bg="black")
            self.video_frame.pack(expand=True, fill="both", padx=10, pady=10)
            
            # Configurar player
            media = vlc_instance.media_new(str(video_path))
            self.player.set_media(media)
            self.player.set_hwnd(self.video_frame.winfo_id())
            
            # Controles
            controls_frame = ctk.CTkFrame(self)
            controls_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            self.play_btn = ctk.CTkButton(controls_frame, text="▶️", width=50, command=self._play_pause)
            self.play_btn.pack(side="left", padx=5)
            
            self.stop_btn = ctk.CTkButton(controls_frame, text="⏹️", width=50, command=self._stop)
            self.stop_btn.pack(side="left", padx=5)
            
            close_btn = ctk.CTkButton(controls_frame, text="Fechar", command=self._close)
            close_btn.pack(side="right", padx=5)
            
            # Bind para fechar
            self.protocol("WM_DELETE_WINDOW", self._close)
            
            # Iniciar reprodução
            self.player.play()
            
        except Exception as e:
            logger.error(f"Erro ao carregar vídeo {video_path}: {e}")
            messagebox.showerror("Erro", f"Nao foi possivel carregar o vídeo: {e}")
            self.destroy()

    def _play_pause(self):
        if self.player.is_playing():
            self.player.pause()
            self.play_btn.configure(text="▶️")
        else:
            self.player.play()
            self.play_btn.configure(text="⏸️")

    def _stop(self):
        self.player.stop()
        self.play_btn.configure(text="▶️")

    def _close(self):
        if hasattr(self, 'player'):
            self.player.stop()
        self.destroy()


def play_audio(audio_path: str) -> bool:
    """Toca um arquivo de audio."""
    try:
        if os.name == 'nt':
            os.startfile(audio_path)
        else:
            subprocess.run(['xdg-open', audio_path], check=True)
        return True
    except Exception as e:
        logger.error(f"Erro ao tocar audio {audio_path}: {e}")
        messagebox.showerror("Erro", f"Nao foi possivel tocar o audio: {e}")
        return False

def get_file_size_mb(file_path: str) -> float:
    """Retorna o tamanho do arquivo em MB."""
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception:
        return 0.0

def get_video_metadata(video_path: str) -> dict:
    """Extrai metadados básicos do vídeo usando ffprobe se disponível."""
    try:
        import json
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', video_path],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            format_info = data.get('format', {})
            streams = data.get('streams', [])
            
            # Procurar stream de vídeo
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
            
            metadata = {
                'duration': float(format_info.get('duration', 0)),
                'size_mb': get_file_size_mb(video_path),
                'codec': video_stream.get('codec_name', 'unknown'),
                'width': video_stream.get('width', 0),
                'height': video_stream.get('height', 0),
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                'bitrate': int(format_info.get('bit_rate', 0)) // 1000 if format_info.get('bit_rate') else 0
            }
            return metadata
    except Exception as e:
        logger.error(f"Erro ao extrair metadados do vídeo {video_path}: {e}")
    
    # Fallback: apenas tamanho do arquivo
    return {
        'size_mb': get_file_size_mb(video_path),
        'error': 'Não foi possível extrair metadados detalhados. ffprobe não disponível.'
    }

def create_video_thumbnail(video_path: str, size: tuple = (100, 100)) -> Optional[ImageTk.PhotoImage]:
    """Cria um thumbnail do vídeo extraindo o primeiro frame."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # Converter BGR para RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img.thumbnail(size)
                return ImageTk.PhotoImage(img)
        cap.release()
    except Exception as e:
        logger.error(f"Erro ao criar thumbnail do vídeo {video_path}: {e}")
    
    return None