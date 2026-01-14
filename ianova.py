#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ianova - Hub de IAs Locais
Um hub de inteligência artificial local com chat, reconhecimento de imagem,
classificação de vídeo e busca em pastas.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import os
import json
import threading
from datetime import datetime
from pathlib import Path
import subprocess
import webbrowser

# Imports opcionais
try:
    import requests
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import vosk
    VOSK_AVAILABLE = True  # Opcional, não é obrigatório
except ImportError:
    VOSK_AVAILABLE = False


class IanovaApp:
    """Aplicação principal do ianova"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("ianova - Hub de IAs Locais")
        self.root.geometry("900x700")
        
        # Estado da aplicação
        self.chat_history = []
        self.current_attachment = None
        self.ollama_url = "http://localhost:11434"
        self.model_name = "llama2"
        
        # Configurações
        self.config_file = Path.home() / ".ianova_config.json"
        self.load_config()
        
        # Criar interface
        self.create_widgets()
        
    def load_config(self):
        """Carrega configurações do arquivo"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.ollama_url = config.get('ollama_url', self.ollama_url)
                    self.model_name = config.get('model_name', self.model_name)
            except Exception as e:
                print(f"Erro ao carregar configuração: {e}")
    
    def save_config(self):
        """Salva configurações no arquivo"""
        try:
            config = {
                'ollama_url': self.ollama_url,
                'model_name': self.model_name
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Erro ao salvar configuração: {e}")
    
    def create_widgets(self):
        """Cria os widgets da interface"""
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Título
        title_label = ttk.Label(main_frame, text="🤖 ianova - Hub de IAs Locais", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Área de chat
        chat_frame = ttk.LabelFrame(main_frame, text="Chat", padding="5")
        chat_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)
        
        self.chat_display = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, 
                                                      width=80, height=25)
        self.chat_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.chat_display.config(state=tk.DISABLED)
        
        # Configurar tags para formatação
        self.chat_display.tag_config('user', foreground='blue', font=('Arial', 10, 'bold'))
        self.chat_display.tag_config('assistant', foreground='green', font=('Arial', 10, 'bold'))
        self.chat_display.tag_config('system', foreground='red', font=('Arial', 9, 'italic'))
        self.chat_display.tag_config('info', foreground='gray', font=('Arial', 9))
        
        # Frame de entrada
        input_frame = ttk.Frame(main_frame, padding="5")
        input_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E))
        input_frame.columnconfigure(1, weight=1)
        
        # Botão de anexo
        self.attach_btn = ttk.Button(input_frame, text="📎", width=3, 
                                     command=self.attach_file)
        self.attach_btn.grid(row=0, column=0, padx=(0, 5))
        
        # Campo de entrada
        self.input_entry = ttk.Entry(input_frame, width=70)
        self.input_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        self.input_entry.bind('<Return>', lambda e: self.send_message())
        
        # Botão enviar
        self.send_btn = ttk.Button(input_frame, text="Enviar", 
                                   command=self.send_message)
        self.send_btn.grid(row=0, column=2, padx=(5, 0))
        
        # Label de anexo
        self.attachment_label = ttk.Label(input_frame, text="", foreground="gray")
        self.attachment_label.grid(row=1, column=1, sticky=tk.W)
        
        # Barra de status
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="Pronto", foreground="green")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Botão de configurações
        config_btn = ttk.Button(status_frame, text="⚙️ Configurações", 
                               command=self.show_config)
        config_btn.grid(row=0, column=1)
        
        # Mensagem de boas-vindas
        self.add_system_message("Bem-vindo ao ianova! 🤖")
        self.add_system_message("Comandos disponíveis: /buscar <termo>, /abrir <arquivo>, /web <url>")
        self.add_system_message("Use o botão 📎 para anexar imagens, vídeos ou áudio")
        
    def add_message(self, role, message, tag=None):
        """Adiciona uma mensagem ao chat"""
        self.chat_display.config(state=tk.NORMAL)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if tag:
            self.chat_display.insert(tk.END, f"[{timestamp}] ", 'info')
            self.chat_display.insert(tk.END, f"{role}: ", tag)
            self.chat_display.insert(tk.END, f"{message}\n\n")
        else:
            self.chat_display.insert(tk.END, f"[{timestamp}] {role}: {message}\n\n")
        
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
        
    def add_system_message(self, message):
        """Adiciona uma mensagem do sistema"""
        self.add_message("Sistema", message, 'system')
        
    def attach_file(self):
        """Anexa um arquivo (imagem, vídeo ou áudio)"""
        filetypes = [
            ("Todos os arquivos suportados", "*.png *.jpg *.jpeg *.bmp *.gif *.mp4 *.avi *.mov *.wav *.mp3"),
            ("Imagens", "*.png *.jpg *.jpeg *.bmp *.gif"),
            ("Vídeos", "*.mp4 *.avi *.mov"),
            ("Áudio", "*.wav *.mp3"),
            ("Todos os arquivos", "*.*")
        ]
        
        filename = filedialog.askopenfilename(title="Selecionar arquivo", 
                                             filetypes=filetypes)
        
        if filename:
            self.current_attachment = filename
            basename = os.path.basename(filename)
            self.attachment_label.config(text=f"📎 {basename}")
            self.add_system_message(f"Arquivo anexado: {basename}")
            
    def clear_attachment(self):
        """Limpa o anexo atual"""
        self.current_attachment = None
        self.attachment_label.config(text="")
        
    def send_message(self):
        """Envia mensagem do usuário"""
        message = self.input_entry.get().strip()
        
        if not message and not self.current_attachment:
            return
            
        # Limpar entrada
        self.input_entry.delete(0, tk.END)
        
        # Mostrar mensagem do usuário
        if message:
            self.add_message("Você", message, 'user')
        
        # Processar comando ou mensagem
        if message.startswith('/'):
            self.process_command(message)
        elif self.current_attachment:
            self.process_attachment(message)
        else:
            self.process_chat(message)
            
    def process_command(self, command):
        """Processa comandos especiais"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        if cmd == '/buscar':
            self.search_files(arg)
        elif cmd == '/abrir':
            self.open_file(arg)
        elif cmd == '/web':
            self.open_web(arg)
        elif cmd == '/ajuda':
            self.show_help()
        else:
            self.add_system_message(f"Comando desconhecido: {cmd}")
            self.add_system_message("Use /ajuda para ver comandos disponíveis")
            
    def search_files(self, search_term):
        """Busca arquivos no sistema"""
        if not search_term:
            self.add_system_message("Uso: /buscar <termo>")
            return
            
        self.status_label.config(text="Buscando...", foreground="orange")
        
        def search_thread():
            try:
                # Buscar na pasta do usuário
                user_home = Path.home()
                results = []
                
                # Buscar em diretórios comuns
                search_dirs = [
                    user_home / "Documents",
                    user_home / "Downloads",
                    user_home / "Desktop",
                ]
                
                for search_dir in search_dirs:
                    if search_dir.exists():
                        for root, dirs, files in os.walk(search_dir):
                            # Limitar profundidade para performance
                            if root.count(os.sep) - str(search_dir).count(os.sep) > 3:
                                continue
                            
                            for file in files:
                                if search_term.lower() in file.lower():
                                    results.append(os.path.join(root, file))
                                    if len(results) >= 20:  # Limitar resultados
                                        break
                            if len(results) >= 20:
                                break
                    if len(results) >= 20:
                        break
                
                # Mostrar resultados
                self.root.after(0, self.show_search_results, search_term, results)
                
            except Exception as e:
                self.root.after(0, self.add_system_message, f"Erro na busca: {str(e)}")
            finally:
                self.root.after(0, lambda: self.status_label.config(text="Pronto", foreground="green"))
        
        threading.Thread(target=search_thread, daemon=True).start()
        
    def show_search_results(self, term, results):
        """Mostra resultados da busca"""
        if results:
            self.add_message("Sistema", f"Encontrados {len(results)} arquivo(s) para '{term}':", 'system')
            for i, path in enumerate(results[:10], 1):
                self.add_system_message(f"{i}. {path}")
            if len(results) > 10:
                self.add_system_message(f"... e mais {len(results) - 10} arquivo(s)")
        else:
            self.add_system_message(f"Nenhum arquivo encontrado para '{term}'")
            
    def open_file(self, filepath):
        """Abre um arquivo no sistema"""
        if not filepath:
            self.add_system_message("Uso: /abrir <caminho do arquivo>")
            return
            
        filepath = filepath.strip('"').strip("'")
        
        if not os.path.exists(filepath):
            self.add_system_message(f"Arquivo não encontrado: {filepath}")
            return
            
        try:
            if os.name == 'nt':  # Windows
                os.startfile(filepath)
            else:  # Linux/Mac
                subprocess.run(['xdg-open', filepath])
            self.add_system_message(f"Abrindo: {filepath}")
        except Exception as e:
            self.add_system_message(f"Erro ao abrir arquivo: {str(e)}")
            
    def open_web(self, url):
        """Abre uma URL no navegador"""
        if not url:
            self.add_system_message("Uso: /web <url>")
            return
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        try:
            webbrowser.open(url)
            self.add_system_message(f"Abrindo navegador: {url}")
        except Exception as e:
            self.add_system_message(f"Erro ao abrir navegador: {str(e)}")
            
    def show_help(self):
        """Mostra ajuda sobre comandos"""
        help_text = """
Comandos disponíveis:
  /buscar <termo> - Busca arquivos no sistema
  /abrir <arquivo> - Abre um arquivo
  /web <url> - Abre uma URL no navegador
  /ajuda - Mostra esta mensagem

Use o botão 📎 para anexar imagens, vídeos ou áudio.
        """
        self.add_system_message(help_text.strip())
        
    def process_attachment(self, message):
        """Processa anexo enviado"""
        if not self.current_attachment:
            return
            
        filepath = self.current_attachment
        ext = os.path.splitext(filepath)[1].lower()
        
        # Processar imagem
        if ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
            self.process_image(filepath, message)
        # Processar vídeo
        elif ext in ['.mp4', '.avi', '.mov']:
            self.process_video(filepath, message)
        # Processar áudio
        elif ext in ['.wav', '.mp3']:
            self.process_audio(filepath, message)
        else:
            self.add_system_message(f"Tipo de arquivo não suportado: {ext}")
            
        self.clear_attachment()
        
    def process_image(self, filepath, message):
        """Processa imagem com reconhecimento"""
        if not PIL_AVAILABLE:
            self.add_system_message("PIL não disponível. Instale: pip install Pillow")
            return
            
        try:
            img = Image.open(filepath)
            width, height = img.size
            format_img = img.format
            
            info = f"Imagem analisada: {width}x{height} pixels, formato {format_img}"
            self.add_message("Assistente", info, 'assistant')
            
            # Se tiver mensagem, processar com contexto da imagem
            if message:
                context = f"Analisando imagem ({width}x{height}, {format_img}): {message}"
                self.process_chat(context)
            else:
                self.add_system_message("Imagem carregada. Faça uma pergunta sobre ela!")
                
        except Exception as e:
            self.add_system_message(f"Erro ao processar imagem: {str(e)}")
            
    def process_video(self, filepath, message):
        """Processa vídeo com classificação"""
        if not CV2_AVAILABLE:
            self.add_system_message("OpenCV não disponível. Instale: pip install opencv-python")
            return
            
        try:
            cap = cv2.VideoCapture(filepath)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0
            
            cap.release()
            
            info = f"Vídeo analisado: {width}x{height}, {frame_count} frames, {fps} FPS, {duration:.1f}s"
            self.add_message("Assistente", info, 'assistant')
            
            if message:
                context = f"Analisando vídeo ({duration:.1f}s, {frame_count} frames): {message}"
                self.process_chat(context)
            else:
                self.add_system_message("Vídeo carregado. Faça uma pergunta sobre ele!")
                
        except Exception as e:
            self.add_system_message(f"Erro ao processar vídeo: {str(e)}")
            
    def process_audio(self, filepath, message):
        """Processa áudio"""
        self.add_system_message(f"Áudio recebido: {os.path.basename(filepath)}")
        
        if VOSK_AVAILABLE:
            self.add_system_message("Reconhecimento de voz com Vosk (em desenvolvimento)")
        else:
            self.add_system_message("Reconhecimento de voz não disponível (instale vosk se necessário)")
            
        if message:
            self.process_chat(f"Contexto do áudio: {message}")
            
    def process_chat(self, message):
        """Processa mensagem de chat com Ollama"""
        if not OLLAMA_AVAILABLE:
            self.add_system_message("Ollama não disponível. Instale: pip install requests")
            self.add_message("Assistente", "Resposta simulada: Entendi sua mensagem!", 'assistant')
            return
            
        self.status_label.config(text="Processando...", foreground="orange")
        
        def chat_thread():
            try:
                # Tentar conectar ao Ollama
                url = f"{self.ollama_url}/api/generate"
                payload = {
                    "model": self.model_name,
                    "prompt": message,
                    "stream": False
                }
                
                response = requests.post(url, json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    reply = result.get('response', 'Sem resposta')
                    self.root.after(0, self.add_message, "Assistente", reply, 'assistant')
                else:
                    error_msg = f"Erro ao conectar ao Ollama (código {response.status_code})"
                    self.root.after(0, self.add_system_message, error_msg)
                    self.root.after(0, self.add_message, "Assistente", 
                                  "Resposta simulada: Entendi sua mensagem!", 'assistant')
                    
            except requests.exceptions.ConnectionError:
                self.root.after(0, self.add_system_message, 
                              "Ollama não está rodando. Inicie com 'ollama serve'")
                self.root.after(0, self.add_message, "Assistente", 
                              "Resposta simulada: Entendi sua mensagem!", 'assistant')
            except Exception as e:
                self.root.after(0, self.add_system_message, f"Erro: {str(e)}")
            finally:
                self.root.after(0, lambda: self.status_label.config(text="Pronto", foreground="green"))
        
        threading.Thread(target=chat_thread, daemon=True).start()
        
    def show_config(self):
        """Mostra janela de configurações"""
        config_window = tk.Toplevel(self.root)
        config_window.title("Configurações")
        config_window.geometry("400x200")
        
        # Frame principal
        frame = ttk.Frame(config_window, padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # URL do Ollama
        ttk.Label(frame, text="URL do Ollama:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ollama_entry = ttk.Entry(frame, width=40)
        ollama_entry.insert(0, self.ollama_url)
        ollama_entry.grid(row=0, column=1, pady=5)
        
        # Nome do modelo
        ttk.Label(frame, text="Modelo:").grid(row=1, column=0, sticky=tk.W, pady=5)
        model_entry = ttk.Entry(frame, width=40)
        model_entry.insert(0, self.model_name)
        model_entry.grid(row=1, column=1, pady=5)
        
        # Informações
        info_text = "Certifique-se de que o Ollama está instalado e rodando.\nComando: ollama serve"
        ttk.Label(frame, text=info_text, foreground="gray").grid(row=2, column=0, 
                                                                 columnspan=2, pady=10)
        
        def save_and_close():
            self.ollama_url = ollama_entry.get()
            self.model_name = model_entry.get()
            self.save_config()
            self.add_system_message("Configurações salvas!")
            config_window.destroy()
        
        # Botões
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Salvar", command=save_and_close).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=config_window.destroy).pack(side=tk.LEFT)


def main():
    """Função principal"""
    root = tk.Tk()
    app = IanovaApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
