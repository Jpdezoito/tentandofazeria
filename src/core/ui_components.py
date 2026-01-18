"""
UI Components para a aplicacao IA Principal.
Componentes reutilizaveis para chat, anexos e midia.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import os
import threading
import time
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ChatBubble(ctk.CTkFrame):
    """Bolha de chat para mensagens."""

    def __init__(self, master, text: str, is_user: bool = False, timestamp: str = None, **kwargs):
        super().__init__(master, **kwargs)
        self.is_user = is_user

        # Configurar cores baseado no tipo
        if is_user:
            bg_color = "#0078D4"
            fg_color = "white"
            anchor = "e"  # direita
        else:
            bg_color = "#F3F2F1"
            fg_color = "black"
            anchor = "w"  # esquerda
        self.anchor = anchor
        self.timestamp = timestamp

        # Label para o texto
        self.text_label = ctk.CTkLabel(
            self,
            text=text,
            wraplength=400,
            justify="left",
            fg_color=bg_color,
            text_color=fg_color,
            corner_radius=15,
            padx=15,
            pady=10
        )
        self.text_label.pack(anchor=anchor, padx=10, pady=5)

        # Timestamp
        if timestamp:
            time_label = ctk.CTkLabel(
                self,
                text=timestamp,
                font=ctk.CTkFont(size=8),
                text_color="gray"
            )
            time_label.pack(anchor=anchor, padx=10)


class ChatBubbleWithAttachment(ctk.CTkFrame):
    """Bolha de chat com anexo visual."""

    def __init__(self, master, text: str, thumbnail: ImageTk.PhotoImage, attachment_type: str, file_path: str, is_user: bool = False, timestamp: str = None, **kwargs):
        super().__init__(master, **kwargs)
        self.is_user = is_user
        self.file_path = file_path
        self.attachment_type = attachment_type

        # Configurar cores baseado no tipo
        if is_user:
            bg_color = "#0078D4"
            fg_color = "white"
            anchor = "e"  # direita
        else:
            bg_color = "#F3F2F1"
            fg_color = "black"
            anchor = "w"  # esquerda

        # Frame para conteúdo
        content_frame = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=15)
        content_frame.pack(anchor=anchor, padx=10, pady=5)

        # Thumbnail
        if thumbnail:
            thumb_label = tk.Label(content_frame, image=thumbnail, bg=bg_color)
            thumb_label.image = thumbnail  # Manter referência
            thumb_label.pack(side="left", padx=10, pady=10)

        # Texto
        text_label = ctk.CTkLabel(
            content_frame,
            text=text,
            wraplength=300,
            justify="left",
            fg_color="transparent",
            text_color=fg_color,
            padx=10,
            pady=10
        )
        text_label.pack(side="left", fill="both", expand=True)

        # Botão para abrir
        open_btn = ctk.CTkButton(
            content_frame,
            text="▶️" if attachment_type == "video" else "👁️",
            width=30,
            height=30,
            command=self._open_attachment
        )
        open_btn.pack(side="right", padx=10, pady=10)

        # Timestamp
        if timestamp:
            time_label = ctk.CTkLabel(
                self,
                text=timestamp,
                font=ctk.CTkFont(size=8),
                text_color="gray"
            )
            time_label.pack(anchor=anchor, padx=10)

    def _open_attachment(self):
        """Abre o anexo."""
        from media_utils import open_file, ImageViewer, VideoViewer
        if self.attachment_type == "image":
            ImageViewer(self, self.file_path).focus()
        elif self.attachment_type == "video":
            VideoViewer(self, self.file_path).focus()
        else:
            open_file(self.file_path)
        if self.timestamp and not hasattr(self, "time_label"):
            self.time_label = ctk.CTkLabel(
                self,
                text=self.timestamp,
                font=ctk.CTkFont(size=10),
                text_color="gray"
            )
            self.time_label.pack(anchor=self.anchor, padx=10)

class AttachmentPreview(ctk.CTkFrame):
    """Preview para anexos (imagem, video, arquivo)."""

    def __init__(self, master, file_path: str, file_type: str, on_open: Callable = None, **kwargs):
        super().__init__(master, **kwargs)
        self.file_path = file_path
        self.file_type = file_type
        self.on_open = on_open

        filename = os.path.basename(file_path)

        if file_type == "image":
            # Thumbnail da imagem
            try:
                img = Image.open(file_path)
                img.thumbnail((100, 100))
                self.photo = ImageTk.PhotoImage(img)
                self.img_label = tk.Label(self, image=self.photo, cursor="hand2")
                self.img_label.pack(pady=5)
                self.img_label.bind("<Button-1>", lambda e: self._open())
            except Exception as e:
                logger.error(f"Erro ao carregar imagem: {e}")
                self._fallback_icon("🖼️")

        elif file_type == "video":
            # Card para video
            self._create_video_card(filename)

        else:
            # Icone para arquivo
            self._create_file_card(filename)

    def _fallback_icon(self, icon: str):
        self.icon_label = ctk.CTkLabel(self, text=icon, font=ctk.CTkFont(size=48))
        self.icon_label.pack(pady=5)

    def _create_video_card(self, filename: str):
        card = ctk.CTkFrame(self, corner_radius=10)
        card.pack(pady=5, padx=10)

        icon_label = ctk.CTkLabel(card, text="🎥", font=ctk.CTkFont(size=24))
        icon_label.pack(side="left", padx=10)

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=10)

        name_label = ctk.CTkLabel(info_frame, text=filename, font=ctk.CTkFont(weight="bold"))
        name_label.pack(anchor="w")

        open_btn = ctk.CTkButton(card, text="Abrir", width=60, command=self._open)
        open_btn.pack(side="right", padx=10)

    def _create_file_card(self, filename: str):
        card = ctk.CTkFrame(self, corner_radius=10)
        card.pack(pady=5, padx=10)

        icon_label = ctk.CTkLabel(card, text="📎", font=ctk.CTkFont(size=24))
        icon_label.pack(side="left", padx=10)

        name_label = ctk.CTkLabel(card, text=filename, wraplength=300)
        name_label.pack(side="left", fill="x", expand=True, padx=10)

        open_btn = ctk.CTkButton(card, text="Abrir", width=60, command=self._open)
        open_btn.pack(side="right", padx=10)

    def _open(self):
        if self.on_open:
            self.on_open(self.file_path)
        else:
            try:
                os.startfile(self.file_path)
            except Exception as e:
                messagebox.showerror("Erro", f"Nao foi possivel abrir o arquivo: {e}")

class VoiceRecorder(ctk.CTkFrame):
    """Componente para gravacao de voz."""

    def __init__(self, master, on_record_complete: Callable[[str], None], **kwargs):
        super().__init__(master, **kwargs)
        self.on_record_complete = on_record_complete
        self.is_recording = False
        self.start_time = None
        self.recording_thread = None

        # Botao de gravacao
        self.record_btn = ctk.CTkButton(
            self,
            text="🎙️ Gravar",
            command=self._toggle_recording,
            fg_color="red" if self.is_recording else "gray"
        )
        self.record_btn.pack(side="left", padx=5)

        # Label de duracao
        self.duration_label = ctk.CTkLabel(self, text="00:00")
        self.duration_label.pack(side="left", padx=5)

        # Botao enviar
        self.send_btn = ctk.CTkButton(
            self,
            text="Enviar Audio",
            command=self._send_audio,
            state="disabled"
        )
        self.send_btn.pack(side="right", padx=5)

        self.audio_path = None

    def _toggle_recording(self):
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        try:
            import sounddevice as sd
            import scipy.io.wavfile as wav
            import numpy as np
        except ImportError:
            messagebox.showerror("Erro", "Bibliotecas de audio nao instaladas. Instale sounddevice e scipy.")
            return

        self.is_recording = True
        self.record_btn.configure(text="⏹️ Parar", fg_color="red")
        self.start_time = time.time()
        self.audio_path = f"temp_audio_{int(time.time())}.wav"

        def record():
            fs = 44100  # Sample rate
            duration = 300  # Max 5 minutes
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype=np.int16)
            sd.wait()

            # Save as WAV file
            wav.write(self.audio_path, fs, recording)

        self.recording_thread = threading.Thread(target=record, daemon=True)
        self.recording_thread.start()

        # Update duration
        self._update_duration()

    def _stop_recording(self):
        self.is_recording = False
        self.record_btn.configure(text="🎙️ Gravar", fg_color="gray")
        self.send_btn.configure(state="normal")

    def _update_duration(self):
        if self.is_recording:
            elapsed = int(time.time() - self.start_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.duration_label.configure(text=f"{minutes:02d}:{seconds:02d}")
            self.after(1000, self._update_duration)

    def _send_audio(self):
        if self.audio_path and os.path.exists(self.audio_path):
            self.on_record_complete(self.audio_path)
            self.send_btn.configure(state="disabled")
            self.duration_label.configure(text="00:00")

class AttachmentMenu(ctk.CTkToplevel):
    """Menu popup para selecao de anexos."""

    def __init__(self, master, on_file_select: Callable[[str, str], None], **kwargs):
        super().__init__(master, **kwargs)
        self.on_file_select = on_file_select
        self.title("Anexar")
        self.geometry("200x150")
        self.resizable(False, False)

        # Botoes de anexo
        ctk.CTkButton(self, text="📄 Arquivo", command=lambda: self._select_file("file")).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(self, text="🖼️ Imagem", command=lambda: self._select_file("image")).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(self, text="🎥 Video", command=lambda: self._select_file("video")).pack(pady=5, padx=20, fill="x")

    def _select_file(self, file_type: str):
        filetypes = {
            "file": [("Todos os arquivos", "*.*")],
            "image": [("Imagens", "*.png *.jpg *.jpeg *.webp")],
            "video": [("Videos", "*.mp4 *.mov *.mkv *.avi")]
        }

        filename = filedialog.askopenfilename(filetypes=filetypes[file_type])
        if filename:
            self.on_file_select(filename, file_type)
        self.destroy()

class SettingsMenu(ctk.CTkToplevel):
    """Menu de configuracoes simples."""

    def __init__(self, master, current_model: str, voice_enabled: bool, use_ollama: bool, on_save: Callable[[str, bool, bool], None], **kwargs):
        super().__init__(master, **kwargs)
        self.on_save = on_save
        self.title("Configuracoes")
        self.geometry("300x250")
        self.resizable(False, False)

        # Modelo
        ctk.CTkLabel(self, text="Modelo:").pack(pady=5)
        self.model_var = tk.StringVar(value=current_model)
        model_entry = ctk.CTkEntry(self, textvariable=self.model_var)
        model_entry.pack(pady=5, padx=20, fill="x")

        # Voz
        self.voice_var = tk.BooleanVar(value=voice_enabled)
        voice_check = ctk.CTkCheckBox(self, text="Habilitar voz", variable=self.voice_var)
        voice_check.pack(pady=10)

        # Ollama
        self.ollama_var = tk.BooleanVar(value=use_ollama)
        ollama_check = ctk.CTkCheckBox(self, text="Usar Ollama", variable=self.ollama_var)
        ollama_check.pack(pady=10)

        # Botao salvar
        ctk.CTkButton(self, text="Salvar", command=self._save).pack(pady=10)

    def _save(self):
        self.on_save(self.model_var.get(), self.voice_var.get(), self.ollama_var.get())
        self.destroy()
