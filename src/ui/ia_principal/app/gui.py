"""
Interface principal da aplicação IA Principal com design de chat moderno.
"""

from __future__ import annotations

import os
import re
import threading
import tkinter as tk
from tkinter import filedialog
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import logging
import webbrowser
from urllib.parse import urlparse
import subprocess

import customtkinter as ctk
from PIL import Image, ImageTk

from src.ui.ia_principal.core.clients import BuscarPastasClient, RnaConversaClient, RnaVideoClient, RnaCodigoClient, SubprocessResult
from src.ui.ia_principal.core.router import decide_route
from src.core.ui_components import (
    ChatBubble, ChatBubbleWithAttachment, AttachmentPreview, VoiceRecorder, AttachmentMenu, SettingsMenu
)
# Media utils removed in simplification - basic implementations below

def open_file(path):
    """Basic file opener using system default"""
    import os
    try:
        os.startfile(path)
        return True
    except:
        return False

def create_image_thumbnail(path, size=(100, 100)):
    """Basic image thumbnail - returns None for now"""
    return None

def create_video_thumbnail(path, size=(100, 100)):
    """Basic video thumbnail - returns None for now"""
    return None

def get_video_metadata(path):
    """Basic video metadata - returns empty dict for now"""
    return {}

def play_audio(path):
    """Basic audio player - returns False for now"""
    return False

class ImageViewer:
    """Basic image viewer placeholder"""
    def __init__(self, parent, path):
        pass

class VideoViewer:
    """Basic video viewer placeholder"""
    def __init__(self, parent, path, vlc_instance=None):
        pass

logger = logging.getLogger(__name__)

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import vlc
except Exception:
    vlc = None

@dataclass
class SearchHit:
    path: str
    score: float
    kind: str
    reason: str
    source: str = ""
    display_name: str = ""

@dataclass
class ChatMessage:
    text: str
    is_user: bool
    timestamp: str
    attachments: list[dict] = None

    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []


def is_url(string: str) -> bool:
    """Verifica se a string é uma URL válida."""
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


class IaPrincipalApp(ctk.CTk):
    """Aplicação principal com interface de chat moderno."""

    def __init__(self, project_root: Path):
        super().__init__()

        # Configurações da aplicação
        self.project_root = project_root
        self.title("IA Principal - Chat Moderno")
        self.geometry("1200x800")
        self.minsize(800, 600)

        # Configurações de tema
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Estado da aplicação
        self.conversa = RnaConversaClient(project_root)
        self.buscar = BuscarPastasClient(project_root)
        self.video = RnaVideoClient(project_root)
        self.codigo = RnaCodigoClient(project_root)

        self._busy = False
        self._pending_action = None
        self._music_files = None
        self._music_dir = None
        self._last_hits: list[SearchHit] = []
        self._pending_files: list[Path] = []
        self._recent_attachments: list[dict] = []
        self._chat_messages: list[ChatMessage] = []
        self._voice_enabled = False
        self._use_ollama = True
        self._current_model = "llama3" if self._use_ollama else "claude-3-5-sonnet-20241022"
        self._retreino_ativo = False
        self._retreino_thread = None

        # VLC para vídeo
        self._vlc_instance = None
        self._vlc_player = None
        self._current_video_path = None
        self._audio_list_player = None
        self._audio_list = None

        # Componentes de UI
        self._build_ui()
        self._init_vlc()
        self._start_ollama()

        # Mensagem inicial
        self._add_message(
            "IA Principal pronta! 💬\n\n"
            "Dicas de uso:\n"
            "• Digite mensagens normalmente para conversar\n"
            "• Use /buscar <termo> para pesquisar arquivos\n"
            "• Use /abrir <número> para abrir resultados\n"
            "• Anexe arquivos, imagens ou vídeos com 📎\n"
            "• Grave áudio com 🎙️",
            is_user=False
        )

    def _build_ui(self):
        """Constrói a interface principal."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header (Topo)
        self._build_header()

        # Chat Area (Centro)
        self._build_chat_area()

        # Input Area (Rodapé)
        self._build_input_area()

    def _build_header(self):
        """Constrói o cabeçalho com título, status e modelo."""
        header = ctk.CTkFrame(self, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        # Título
        title_label = ctk.CTkLabel(
            header,
            text="🤖 IA Principal",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=10)

        # Status
        self.status_label = ctk.CTkLabel(
            header,
            text="Pronto",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_label.grid(row=0, column=1, padx=20, pady=10)

        # Modelo atual
        self.model_label = ctk.CTkLabel(
            header,
            text=f"Modelo: {self._current_model}",
            font=ctk.CTkFont(size=12),
            text_color="lightblue"
        )
        self.model_label.grid(row=0, column=2, padx=20, pady=10)

        # Controles de audio (playlist)
        audio_controls = ctk.CTkFrame(header, fg_color="transparent")
        audio_controls.grid(row=0, column=3, padx=10, pady=10)
        ctk.CTkButton(audio_controls, text="Play", width=50, command=self._audio_play).pack(side="left", padx=2)
        ctk.CTkButton(audio_controls, text="Pause", width=60, command=self._audio_pause).pack(side="left", padx=2)
        ctk.CTkButton(audio_controls, text="Stop", width=50, command=self._audio_stop).pack(side="left", padx=2)
        ctk.CTkButton(audio_controls, text="Prev", width=50, command=self._audio_prev).pack(side="left", padx=2)
        ctk.CTkButton(audio_controls, text="Next", width=50, command=self._audio_next).pack(side="left", padx=2)

        # Botão configurações
        settings_btn = ctk.CTkButton(
            header,
            text="⚙️",
            width=40,
            height=40,
            command=self._show_settings
        )
        settings_btn.grid(row=0, column=4, padx=10, pady=10)

        # Botão copiar conversa
        copy_btn = ctk.CTkButton(
            header,
            text="📋",
            width=40,
            height=40,
            command=self._copy_conversation
        )
        copy_btn.grid(row=0, column=5, padx=10, pady=10)

        # Toggle retreino
        self.retreino_var = tk.BooleanVar(value=False)
        retreino_toggle = ctk.CTkSwitch(
            header,
            text="🔄 Retreino",
            variable=self.retreino_var,
            command=self._toggle_retreino
        )
        retreino_toggle.grid(row=0, column=6, padx=10, pady=10)

    def _build_chat_area(self):
        """Constrói a área de chat com scroll."""
        chat_frame = ctk.CTkFrame(self)
        chat_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        chat_frame.grid_columnconfigure(0, weight=1)
        chat_frame.grid_rowconfigure(0, weight=1)

        # Canvas para scroll
        self.chat_canvas = tk.Canvas(
            chat_frame,
            bg=self.cget("fg_color")[1] if isinstance(self.cget("fg_color"), list) else self.cget("fg_color"),
            highlightthickness=0
        )
        self.chat_canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbar
        scrollbar = ctk.CTkScrollbar(
            chat_frame,
            orientation="vertical",
            command=self.chat_canvas.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.chat_canvas.configure(yscrollcommand=scrollbar.set)

        # Frame interno para mensagens
        self.messages_frame = ctk.CTkFrame(self.chat_canvas, fg_color="transparent")
        self.chat_canvas.create_window((0, 0), window=self.messages_frame, anchor="nw")

        # Bind para scroll
        self.messages_frame.bind("<Configure>", self._on_frame_configure)
        self.chat_canvas.bind("<Configure>", self._on_canvas_configure)

    def _build_input_area(self):
        """Constrói a área de input com botões."""
        input_frame = ctk.CTkFrame(self, height=120)
        input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        input_frame.grid_propagate(False)
        input_frame.grid_columnconfigure(0, weight=1)

        # Frame para controles superiores
        controls_frame = ctk.CTkFrame(input_frame, fg_color="transparent", height=40)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        controls_frame.grid_columnconfigure(1, weight=1)

        # Botão anexar
        self.attach_btn = ctk.CTkButton(
            controls_frame,
            text="📎",
            width=40,
            height=40,
            command=self._show_attachment_menu
        )
        self.attach_btn.grid(row=0, column=0, padx=(0, 5))

        # Gravador de voz
        self.voice_recorder = VoiceRecorder(
            controls_frame,
            on_record_complete=self._on_voice_recorded
        )
        self.voice_recorder.grid(row=0, column=1, sticky="ew", padx=5)

        # Menu de anexos (inicialmente oculto)
        self.attachment_menu_frame = ctk.CTkFrame(self, fg_color="white", border_width=1, width=120, height=120)
        self.attachment_menu_frame.place(x=0, y=0)
        self.attachment_menu_frame.place_forget()  # Oculto inicialmente

        # Botões do menu
        ctk.CTkButton(
            self.attachment_menu_frame,
            text="📄 Arquivo",
            command=lambda: self._select_attachment("file"),
            width=100
        ).pack(pady=2)
        ctk.CTkButton(
            self.attachment_menu_frame,
            text="🖼️ Imagem",
            command=lambda: self._select_attachment("image"),
            width=100
        ).pack(pady=2)
        ctk.CTkButton(
            self.attachment_menu_frame,
            text="🎥 Vídeo",
            command=lambda: self._select_attachment("video"),
            width=100
        ).pack(pady=2)
        text_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        text_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        text_frame.grid_columnconfigure(0, weight=1)

        # Campo de texto
        self.text_input = ctk.CTkTextbox(
            text_frame,
            height=60,
            wrap="word"
        )
        self.text_input.grid(row=0, column=0, sticky="ew")

        # Bind Enter para enviar
        self.text_input.bind("<Return>", self._on_enter_pressed)
        self.text_input.bind("<Shift-Return>", lambda e: None)  # Shift+Enter quebra linha

        # Botão enviar
        self.send_btn = ctk.CTkButton(
            text_frame,
            text="Enviar",
            width=80,
            height=60,
            command=self._send_message
        )
        self.send_btn.grid(row=0, column=1, padx=(10, 0))

    def _on_frame_configure(self, event=None):
        """Ajusta o scroll quando o frame muda."""
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        """Ajusta a largura do frame interno."""
        self.chat_canvas.itemconfig(
            self.chat_canvas.find_withtag("all")[0],
            width=event.width
        )

    def _add_message(self, text: str, is_user: bool = False, attachments: list[dict] = None):
        """Adiciona uma mensagem ao chat."""
        if attachments is None:
            attachments = []

        timestamp = datetime.now().strftime("%H:%M")
        message = ChatMessage(text, is_user, timestamp, attachments)
        self._chat_messages.append(message)

        # Cria bolha de chat
        bubble = ChatBubble(self.messages_frame, text, is_user, timestamp)
        bubble.pack(anchor="e" if is_user else "w", fill="x", padx=10, pady=5)
        self.update_idletasks()

        # Adiciona anexos
        for attachment in attachments:
            preview = AttachmentPreview(
                self.messages_frame,
                attachment["path"],
                attachment["type"],
                on_open=self._open_attachment
            )
            preview.pack(anchor="e" if is_user else "w", padx=10, pady=5)
            self.update_idletasks()

        # Scroll para o final
        self.after(100, lambda: self.chat_canvas.yview_moveto(1.0))

    def _add_message_with_attachment(self, text: str, thumbnail: ImageTk.PhotoImage, attachment_type: str, file_path: str, is_user: bool = False):
        """Adiciona uma mensagem com anexo visual."""
        timestamp = datetime.now().strftime("%H:%M")
        message = ChatMessage(text, is_user, timestamp, [{"path": file_path, "type": attachment_type, "name": os.path.basename(file_path)}])
        self._chat_messages.append(message)

        # Cria bolha de chat com thumbnail
        bubble = ChatBubbleWithAttachment(self.messages_frame, text, thumbnail, attachment_type, file_path, is_user, timestamp)
        bubble.pack(anchor="e" if is_user else "w", fill="x", padx=10, pady=5)

        # Scroll para o final
        self.after(100, lambda: self.chat_canvas.yview_moveto(1.0))

    def _send_message(self):
        """Envia a mensagem atual."""
        if self._busy:
            return

        text = self.text_input.get("1.0", "end-1c").strip()
        if not text and not self._pending_files:
            return

        # Coleta anexos pendentes
        attachments = []
        for file_path in self._pending_files:
            file_type = self._get_file_type(file_path)
            attachments.append({
                "path": str(file_path),
                "type": file_type,
                "name": os.path.basename(file_path)
            })

        # Adiciona à lista de recentes
        self._recent_attachments.extend(attachments)
        if len(self._recent_attachments) > 20:
            self._recent_attachments = self._recent_attachments[-20:]

        # Limpa input
        self.text_input.delete("1.0", "end")
        self._pending_files.clear()

        # Adiciona mensagem do usuário
        self._add_message(text, is_user=True, attachments=attachments)

        # Processa a mensagem
        self._process_message(text, attachments)

    def _process_message(self, text: str, attachments: list[dict]):
        """Processa a mensagem e decide a ação."""
        self._set_busy(True, "Processando...")

        def process():
            try:
                if self._pending_action == "choose_music":
                    choice = text.lower().strip()
                    if choice == "vc decide":
                        import random
                        chosen = random.choice(self._music_files)
                        open_file(chosen)
                        self.after(0, lambda: self._add_message(f"Escolhi aleatoriamente: {os.path.basename(chosen)}", is_user=False))
                    elif choice == "tocar todas":
                        if self._play_music_list(self._music_files):
                            self.after(0, lambda: self._add_message("Tocando todas as musicas em sequencia.", is_user=False))
                        else:
                            self.after(0, lambda: self._add_message("Nao foi possivel tocar todas em sequencia. VLC nao disponivel.", is_user=False))
                    else:
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(self._music_files):
                                chosen = self._music_files[idx]
                                open_file(chosen)
                                self.after(0, lambda: self._add_message(f"Abrindo: {os.path.basename(chosen)}", is_user=False))
                            else:
                                self.after(0, lambda: self._add_message("Número inválido. Tente novamente.", is_user=False))
                                return
                        except ValueError:
                            self.after(0, lambda: self._add_message("Diga o número da música, 'vc decide' ou 'tocar todas'.", is_user=False))
                            return
                    self._pending_action = None
                    self._music_files = None
                    self._music_dir = None
                    self._set_busy(False)
                    return

                decision = decide_route(text)

                # Verifica URLs do YouTube
                yt_urls = self._extract_youtube_urls(text)
                if yt_urls:
                    self._do_youtube(yt_urls[0], False)
                    return

                # Processa comandos especiais
                if decision.kind == "abrir":
                    self._handle_open(decision.payload)
                elif decision.kind == "buscar_abrir":
                    q = decision.payload.strip() or text
                    if is_url(q):
                        try:
                            webbrowser.open(q)
                            self._add_message(f"Abrindo no navegador: {q}", is_user=False)
                        except Exception as e:
                            self._add_message(f"Erro ao abrir URL: {e}", is_user=False)
                    else:
                        # Atalhos para sites comuns
                        shortcuts = {
                            "youtube": "https://www.youtube.com",
                            "google": "https://www.google.com",
                            "gmail": "https://mail.google.com",
                            "spotify": "https://www.spotify.com",
                            "netflix": "https://www.netflix.com",
                        }
                        url = shortcuts.get(q.lower())
                        if url:
                            try:
                                webbrowser.open(url)
                                self._add_message(f"Abrindo {q}: {url}", is_user=False)
                            except Exception as e:
                                self._add_message(f"Erro ao abrir {q}: {e}", is_user=False)
                        elif not self._open_from_recent(q):
                            self._do_search(q, True)
                elif decision.kind == "tocar":
                    self._do_play(decision.payload)
                elif decision.kind in ["yt", "ytvideo"]:
                    url = decision.payload.strip()
                    if url:
                        self._do_youtube(url, decision.kind == "ytvideo")
                    else:
                        self._add_message("Use /yt <url> ou /ytvideo <url>", is_user=False)
                elif decision.kind == "buscar":
                    q = decision.payload.strip() or text
                    if not self._open_from_recent(q):
                        self._do_search(q, False)
                elif decision.kind == "codigo":
                    prompt = decision.payload.strip() or text
                    self._do_code(prompt)
                else:
                    # Conversa normal
                    self._do_chat(text, attachments)

            except Exception as e:
                logger.error(f"Erro ao processar mensagem: {e}")
                self._add_message(f"Erro: {str(e)}", is_user=False)
            finally:
                self._set_busy(False)

        threading.Thread(target=process, daemon=True).start()

    def _do_chat(self, text: str, attachments: list[dict]):
        """Realiza conversa com a IA."""
        use_ollama = getattr(self, '_use_ollama', False)

        if attachments:
            # Conversa com imagem
            image_path = None
            video_path = None
            for att in attachments:
                if att["type"] == "image":
                    image_path = Path(att["path"])
                    break
                elif att["type"] == "video":
                    video_path = Path(att["path"])
                    break

            if image_path:
                result = self.conversa.reply_with_image(text, image_path, use_ollama=use_ollama, model=self._current_model)
            elif video_path:
                # Para vídeo, extrair metadados e usar na conversa
                metadata = get_video_metadata(str(video_path))
                video_info = f"Informações do vídeo anexado:\n"
                video_info += f"- Duração: {metadata.get('duration', 'N/A'):.1f} segundos\n"
                video_info += f"- Tamanho: {metadata.get('size_mb', 0):.1f} MB\n"
                video_info += f"- Codec: {metadata.get('codec', 'N/A')}\n"
                video_info += f"- Resolução: {metadata.get('width', 0)}x{metadata.get('height', 0)}\n"
                video_info += f"- FPS: {metadata.get('fps', 0):.1f}\n"
                if metadata.get('bitrate'):
                    video_info += f"- Bitrate: {metadata.get('bitrate')} kbps\n"
                if 'error' in metadata:
                    video_info += f"- Nota: {metadata['error']}\n"
                
                # Combinar com o texto do usuário
                combined_text = f"{text}\n\n{video_info}"
                result = self.conversa.reply(combined_text, use_ollama=use_ollama, model=self._current_model)
            else:
                result = self.conversa.reply(text, use_ollama=use_ollama, model=self._current_model)
        else:
            result = self.conversa.reply(text, use_ollama=use_ollama, model=self._current_model)

        if result.ok:
            self.after(0, lambda: self._add_message(result.data.get("text", "Sem resposta"), is_user=False))
        else:
            self.after(0, lambda: self._add_message(f"Erro: {result.error}", is_user=False))

    def _do_code(self, prompt: str):
        """Gera código usando RNA Código."""
        result = self.codigo.generate_code(prompt)
        if result.ok:
            generated = result.data.get("generated", "")
            self.after(0, lambda: self._add_message(f"```python\n{generated}\n```", is_user=False))
        else:
            self.after(0, lambda: self._add_message(f"Erro na geração de código: {result.error}", is_user=False))

    def _do_play(self, query: str):
        """Toca música ou mídia."""
        q = query.lower().strip()
        if q in ["musica", "música", "music"]:
            import tkinter.messagebox as messagebox
            choice = messagebox.askquestion("Tocar Música", "Você quer tocar música online (YouTube Music)?\n\nSim = Online\nNão = Local")
            if choice == "yes":
                webbrowser.open("https://music.youtube.com")
                self.after(0, lambda: self._add_message("Abrindo YouTube Music.", is_user=False))
            else:
                # Buscar música local
                music_files = []
                import os
                music_dir = r"C:\Users\José Paulo Siqueira\Music"
                if os.path.exists(music_dir):
                    for root, dirs, files in os.walk(music_dir):
                        for file in files:
                            if file.lower().endswith(('.mp3', '.wav', '.flac', '.mp4', '.avi', '.m4a')):
                                music_files.append(os.path.join(root, file))
                        if len(music_files) > 20:  # limitar
                            break
                if music_files:
                    if len(music_files) == 1:
                        first_file = music_files[0]
                        open_file(first_file)
                        self.after(0, lambda: self._add_message(f"Abrindo: {os.path.basename(first_file)}", is_user=False))
                    else:
                        # Mostrar lista
                        response = "Músicas encontradas:\n"
                        for i, f in enumerate(music_files[:10], 1):
                            response += f"{i}. {os.path.basename(f)}\n"
                        if len(music_files) > 10:
                            response += f"... e mais {len(music_files) - 10} músicas.\n"
                        response += "\nDiga o número da música, 'vc decide' para escolher aleatoriamente, ou 'tocar todas' para tocar todas as músicas."
                        self.after(0, lambda: self._add_message(response, is_user=False))
                        self._pending_action = "choose_music"
                        self._music_files = music_files
                        self._music_dir = music_dir
                else:
                    self.after(0, lambda: self._add_message("Nenhum arquivo de música encontrado na pasta Música do usuário.", is_user=False))
        else:
            play_shortcuts = {
                "spotify": "https://www.spotify.com",
            }
            url = play_shortcuts.get(q)
            if url:
                try:
                    webbrowser.open(url)
                    self.after(0, lambda: self._add_message(f"Tocando {query}: {url}", is_user=False))
                except Exception as e:
                    self.after(0, lambda: self._add_message(f"Erro ao tocar {query}: {e}", is_user=False))
            else:
                # Para músicas específicas, buscar no YouTube
                search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
                try:
                    webbrowser.open(search_url)
                    self.after(0, lambda: self._add_message(f"Buscando e tocando '{query}' no YouTube", is_user=False))
                except Exception as e:
                    self.after(0, lambda: self._add_message(f"Erro ao buscar {query}: {e}", is_user=False))

    def _play_music_list(self, files: list[str]) -> bool:
        if not vlc:
            return False
        try:
            if self._vlc_instance is None:
                self._init_vlc()
            if self._vlc_instance is None:
                return False
            if self._audio_list_player is not None:
                self._audio_list_player.stop()
            media_list = self._vlc_instance.media_list_new(files)
            list_player = self._vlc_instance.media_list_player_new()
            list_player.set_media_list(media_list)
            list_player.play()
            self._audio_list_player = list_player
            self._audio_list = media_list
            return True
        except Exception as e:
            logger.error(f"Erro ao tocar lista de musicas: {e}")
            return False

    def _audio_play(self):
        if self._audio_list_player is None:
            self._add_message("No playlist audio active.", is_user=False)
            return
        try:
            self._audio_list_player.play()
        except Exception as e:
            logger.error(f"Erro ao dar play na playlist: {e}")
            self._add_message(f"Audio play failed: {e}", is_user=False)

    def _audio_pause(self):
        if self._audio_list_player is None:
            self._add_message("No playlist audio active.", is_user=False)
            return
        try:
            self._audio_list_player.pause()
        except Exception as e:
            logger.error(f"Erro ao pausar a playlist: {e}")
            self._add_message(f"Audio pause failed: {e}", is_user=False)

    def _audio_stop(self):
        if self._audio_list_player is None:
            self._add_message("No playlist audio active.", is_user=False)
            return
        try:
            self._audio_list_player.stop()
        except Exception as e:
            logger.error(f"Erro ao parar a playlist: {e}")
            self._add_message(f"Audio stop failed: {e}", is_user=False)

    def _audio_next(self):
        if self._audio_list_player is None:
            self._add_message("No playlist audio active.", is_user=False)
            return
        try:
            self._audio_list_player.next()
        except Exception as e:
            logger.error(f"Erro ao avancar a playlist: {e}")
            self._add_message(f"Audio next failed: {e}", is_user=False)

    def _audio_prev(self):
        if self._audio_list_player is None:
            self._add_message("No playlist audio active.", is_user=False)
            return
        try:
            self._audio_list_player.previous()
        except Exception as e:
            logger.error(f"Erro ao voltar na playlist: {e}")
            self._add_message(f"Audio prev failed: {e}", is_user=False)

    def _do_search(self, query: str, open_first: bool):
        """Realiza busca de arquivos."""
        result = self.buscar.search(query)
        if result.ok:
            hits = result.data.get("results", [])
            self._last_hits = [SearchHit(**hit) for hit in hits]

            if hits:
                response = f"Encontrei {len(hits)} resultado(s):\n\n"
                for i, hit in enumerate(hits[:10], 1):
                    response += f"{i}. {hit['path']} ({hit['kind']})\n"

                if len(hits) > 10:
                    response += f"\n... e mais {len(hits) - 10} resultados"

                self.after(0, lambda: self._add_message(response, is_user=False))

                if open_first and hits:
                    self._open_result_index(0)
            else:
                self.after(0, lambda: self._add_message("Nenhum resultado encontrado.", is_user=False))
        else:
            self.after(0, lambda: self._add_message(f"Erro na busca: {result.error}", is_user=False))

    def _do_youtube(self, url: str, video_only: bool):
        """Processa vídeo do YouTube."""
        result = self.conversa.youtube(url, video_only=video_only)
        if result.ok:
            data = result.data
            response = f"Vídeo processado: {data.get('title', 'Título desconhecido')}\n\n"

            if data.get("summary"):
                response += f"Resumo: {data['summary']}\n\n"

            if data.get("transcript_path"):
                response += f"Transcrição salva em: {data['transcript_path']}\n"

            self.after(0, lambda: self._add_message(response, is_user=False))

            # Se há vídeo, oferece para abrir
            if data.get("video_path"):
                video_path = data["video_path"]
                self.after(0, lambda: self._add_message(
                    f"Vídeo baixado: {os.path.basename(video_path)}",
                    is_user=False,
                    attachments=[{
                        "path": video_path,
                        "type": "video",
                        "name": os.path.basename(video_path)
                    }]
                ))
        else:
            self.after(0, lambda: self._add_message(f"Erro ao processar vídeo: {result.error}", is_user=False))

    def _handle_open(self, num_str: str):
        """Abre um resultado de busca pelo número."""
        try:
            idx = int(num_str) - 1
            self._open_result_index(idx)
        except ValueError:
            self.after(0, lambda: self._add_message("Uso: /abrir <número>", is_user=False))

    def _open_result_index(self, idx: int):
        """Abre um resultado específico."""
        if idx < 0 or idx >= len(self._last_hits):
            self.after(0, lambda: self._add_message("Número inválido.", is_user=False))
            return

        path = self._last_hits[idx].path
        if open_file(path):
            self.after(0, lambda: self._add_message(f"Abrindo: {path}", is_user=False))
        else:
            self.after(0, lambda: self._add_message("Erro ao abrir o arquivo.", is_user=False))

    def _open_from_recent(self, query: str) -> bool:
        """Tenta abrir um arquivo recente pela consulta."""
        q = query.lower().strip()
        for att in self._recent_attachments:
            name = att["name"].lower()
            if q in name:
                if open_file(att["path"]):
                    self.after(0, lambda: self._add_message(f"Abrindo (recente): {att['name']}", is_user=False))
                    return True
        return False

    def _show_attachment_menu(self):
        """Mostra menu de anexos sobre o botão."""
        print("Opening attachment menu")
        if self.attachment_menu_frame.winfo_ismapped():
            self.attachment_menu_frame.place_forget()
            return

        # Posicionar sobre o botão
        btn_x = self.attach_btn.winfo_rootx() - self.winfo_rootx()
        btn_y = self.attach_btn.winfo_rooty() - self.winfo_rooty() + self.attach_btn.winfo_height()
        print(f"Button position: {btn_x}, {btn_y}")
        self.attachment_menu_frame.place(x=btn_x, y=btn_y)
        self.attachment_menu_frame.lift()  # Trazer para frente

    def _on_attachment_selected(self, file_path: str, file_type: str):
        """Callback quando um anexo é selecionado."""
        self._pending_files.append(Path(file_path))
        filename = os.path.basename(file_path)

        # Adiciona preview da mensagem com thumbnail se for imagem/vídeo
        if file_type == "image":
            thumbnail = create_image_thumbnail(file_path, size=(100, 100))
            if thumbnail:
                self._add_message_with_attachment(f"🖼️ Imagem: {filename}", thumbnail, "image", file_path, is_user=True)
            else:
                self._add_message(f"🖼️ Imagem anexada: {filename}", is_user=True)
        elif file_type == "video":
            # Para vídeo, tenta criar thumbnail do primeiro frame
            thumbnail = self._create_video_thumbnail(file_path)
            if thumbnail:
                self._add_message_with_attachment(f"🎥 Vídeo: {filename}", thumbnail, "video", file_path, is_user=True)
            else:
                self._add_message(f"🎥 Vídeo anexado: {filename}", is_user=True)
        else:
            self._add_message(f"📎 Arquivo anexado: {filename}", is_user=True)

    def _select_attachment(self, file_type: str):
        """Seleciona arquivo do tipo especificado."""
        filetypes = {
            "file": [("Todos os arquivos", "*.*")],
            "image": [("Imagens", "*.png *.jpg *.jpeg *.webp")],
            "video": [("Vídeos", "*.mp4 *.mov *.mkv *.avi")]
        }

        filename = filedialog.askopenfilename(filetypes=filetypes[file_type])
        if filename:
            self._on_attachment_selected(filename, file_type)
        # Ocultar menu
        self.attachment_menu_frame.place_forget()

    def _create_video_thumbnail(self, video_path: str):
        """Cria thumbnail do vídeo."""
        return create_video_thumbnail(video_path, size=(100, 100))

    def _on_voice_recorded(self, audio_path: str):
        """Callback quando áudio é gravado."""
        filename = os.path.basename(audio_path)
        self._add_message(
            f"🎵 Áudio gravado: {filename}",
            is_user=True,
            attachments=[{
                "path": audio_path,
                "type": "audio",
                "name": filename
            }]
        )

    def _open_attachment(self, file_path: str):
        """Abre um anexo."""
        file_type = self._get_file_type(Path(file_path))

        if file_type == "image":
            viewer = ImageViewer(self, file_path)
            viewer.focus()
        elif file_type == "video":
            viewer = VideoViewer(self, file_path, vlc_instance=self._vlc_instance)
            viewer.focus()
        elif file_type == "audio":
            if not play_audio(file_path):
                self._add_message("Erro ao tocar áudio.", is_user=False)
        else:
            open_file(file_path)

    def _show_settings(self):
        """Mostra menu de configurações."""
        menu = SettingsMenu(
            self,
            self._current_model,
            self._voice_enabled,
            self._use_ollama,
            self._on_settings_saved
        )
        menu.focus()

    def _on_settings_saved(self, model: str, voice_enabled: bool, use_ollama: bool):
        """Callback quando configurações são salvas."""
        self._current_model = model
        self._voice_enabled = voice_enabled
        self._use_ollama = use_ollama
        # Ajustar modelo se necessário
        if use_ollama and not model.startswith(("llama", "mistral", "qwen", "gemma")):
            self._current_model = "llama3"
            self.model_label.configure(text=f"Modelo: llama3 (ajustado para Ollama)")
        else:
            self.model_label.configure(text=f"Modelo: {self._current_model}")
        self._add_message(f"Configurações atualizadas: Modelo={self._current_model}, Voz={'Habilitada' if voice_enabled else 'Desabilitada'}", is_user=False)

    def _on_enter_pressed(self, event):
        """Handle Enter key press."""
        if event.state & 0x0001:  # Shift+Enter
            return  # Allow new line
        else:
            self._send_message()
            return "break"

    def _set_busy(self, busy: bool, status: str = ""):
        """Define estado ocupado da interface."""
        self._busy = busy

        state = "disabled" if busy else "normal"
        self.send_btn.configure(state=state)
        self.attach_btn.configure(state=state)
        self.text_input.configure(state=state)

        if status:
            self.status_label.configure(text=status)
        elif not busy:
            self.status_label.configure(text="Pronto")

    def _get_file_type(self, file_path: Path) -> str:
        """Determina o tipo de arquivo."""
        ext = file_path.suffix.lower()
        if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']:
            return "image"
        elif ext in ['.mp4', '.mov', '.mkv', '.avi', '.wmv', '.flv']:
            return "video"
        elif ext in ['.wav', '.mp3', '.ogg', '.flac']:
            return "audio"
        else:
            return "file"

    def _extract_youtube_urls(self, text: str) -> list[str]:
        """Extrai URLs do YouTube do texto."""
        pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
        matches = re.findall(pattern, text)
        return [f"https://www.youtube.com/watch?v={match}" for match in matches]

    def _init_vlc(self):
        """Inicializa VLC para reprodução de vídeo."""
        if vlc:
            try:
                self._vlc_instance = vlc.Instance()
                self._vlc_player = self._vlc_instance.media_player_new()
            except Exception as e:
                logger.warning(f"Erro ao inicializar VLC: {e}")

    def _start_ollama(self):
        """Inicia o Ollama se não estiver rodando."""
        try:
            # Verificar se já está rodando
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self._add_message("Ollama já está rodando.", is_user=False)
            else:
                # Tenta iniciar ollama serve em background
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._add_message("Ollama iniciado automaticamente.", is_user=False)
            # Tentar detectar modelo disponível
            self._detect_ollama_model()
        except FileNotFoundError:
            self._add_message("Ollama não encontrado. Instale o Ollama para usar modelos locais.", is_user=False)
        except Exception as e:
            logger.warning(f"Erro ao iniciar Ollama: {e}")

    def _detect_ollama_model(self):
        """Detecta um modelo Ollama disponível e ajusta se necessário."""
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Header + models
                    models = [line.split()[0] for line in lines[1:] if line.strip()]
                    # Preferir modelos de chat: gemma, llama, mistral, qwen
                    preferred = [m for m in models if any(p in m.lower() for p in ['gemma', 'llama', 'mistral', 'qwen'])]
                    chosen = preferred[0] if preferred else models[0]
                    if self._use_ollama and not self._current_model.startswith(("llama", "mistral", "qwen", "gemma")):
                        self._current_model = chosen
                        self.model_label.configure(text=f"Modelo: {chosen} (Ollama detectado)")
                        self._add_message(f"Modelo Ollama detectado: {chosen}", is_user=False)
        except Exception as e:
            logger.warning(f"Erro ao detectar modelos Ollama: {e}")

    def _copy_conversation(self):
        """Copia a conversa atual para o clipboard."""
        if pyperclip is None:
            self._add_message("pyperclip não instalado. Instale com: pip install pyperclip", is_user=False)
            return
        conversation_text = ""
        for msg in self._chat_messages:
            sender = "Usuário" if msg.is_user else "IA"
            conversation_text += f"[{msg.timestamp}] {sender}: {msg.text}\n"
        pyperclip.copy(conversation_text)
        self._add_message("Conversa copiada para o clipboard!", is_user=False)

    def _toggle_retreino(self):
        """Ativa/desativa o retreino em background."""
        self._retreino_ativo = self.retreino_var.get()
        if self._retreino_ativo:
            self._start_retreino_thread()
            self._add_message("Retreino ativado. Treinando em background.", is_user=False)
        else:
            self._stop_retreino_thread()
            self._add_message("Retreino desativado.", is_user=False)

    def _start_retreino_thread(self):
        """Inicia thread de retreino."""
        if self._retreino_thread and self._retreino_thread.is_alive():
            return
        self._retreino_thread = threading.Thread(target=self._retreino_loop, daemon=True)
        self._retreino_thread.start()

    def _stop_retreino_thread(self):
        """Para thread de retreino."""
        self._retreino_ativo = False
        if self._retreino_thread:
            self._retreino_thread.join(timeout=1)

    def _retreino_loop(self):
        """Loop de retreino em background."""
        import time
        while self._retreino_ativo:
            try:
                # Simula treino: aqui você pode integrar com o sistema de treino da RNA
                # Por exemplo, chamar self.conversa.treinar() ou similar
                # Para demonstração, apenas log
                logger.info("Executando retreino em background...")
                time.sleep(60)  # Treina a cada 1 minuto, ajuste conforme necessário
            except Exception as e:
                logger.error(f"Erro no retreino: {e}")
                break

    def clear_chat(self):
        """Limpa o chat."""
        """Limpa o chat."""
        for widget in self.messages_frame.winfo_children():
            widget.destroy()
        self._chat_messages.clear()
        self._add_message("Chat limpo! 🧹", is_user=False)
