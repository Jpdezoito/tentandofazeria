from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk
from typing import Optional

from core.config import AppConfig, db_path, import_dir, load_settings, save_settings
from core.memoria.store import add_example, connect, count_examples, init_db
from core.ollama.client import OllamaStatus, detect
from core.runtime.orchestrator import ChatRuntime
from core.treino.importer import import_folder
from core.vision.capture import CapturedImage, capture_screen_png, capture_webcam_png, png_bytes_to_tk_photo_data
from core.audio.record import record_wav_to_file
from core.audio.stt_vosk import transcribe_wav_vosk
from core.audio.tts import speak_text


@dataclass(frozen=True)
class UiMsg:
    kind: str
    text: str = ""


class RnaConversaApp(tk.Tk):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg

        self._ui_queue: queue.Queue[UiMsg] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._cancel = threading.Event()

        self._conn = connect(db_path(cfg))
        init_db(self._conn)
        self._runtime = ChatRuntime(cfg, self._conn)

        self._settings = load_settings(cfg)

        self._ollama_status = OllamaStatus(installed=False, running=False, models=[], note="")

        self._last_assistant_text: str = ""
        self._last_image: Optional[CapturedImage] = None

        self._build_ui()
        self.after(80, self._poll)

        self._refresh_ollama(initial=True)
        self._refresh_counts()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(9, weight=1)

        self.use_ollama_var = tk.BooleanVar(value=bool(self._settings.get("use_ollama", False)))
        self.model_var = tk.StringVar(value=str(self._settings.get("ollama_model", "")))

        self.chk_ollama = ttk.Checkbutton(top, text="Usar Ollama (local)", variable=self.use_ollama_var)
        self.chk_ollama.grid(row=0, column=0, padx=(0, 10))

        ttk.Label(top, text="Modelo:").grid(row=0, column=1, sticky="w")
        self.cmb_models = ttk.Combobox(top, textvariable=self.model_var, values=[], width=28, state="readonly")
        self.cmb_models.grid(row=0, column=2, padx=(6, 10))

        ttk.Button(top, text="Atualizar modelos", command=self.on_refresh_models).grid(row=0, column=3, padx=(0, 10))
        ttk.Button(top, text="Limpar sessão", command=self.on_clear_session).grid(row=0, column=4, padx=(0, 10))

        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(top, textvariable=self.status_var).grid(row=0, column=5, sticky="w")

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        self.tabs = ttk.Notebook(left)
        self.tabs.grid(row=0, column=0, sticky="nsew")

        self.tab_chat = ttk.Frame(self.tabs, padding=8)
        self.tab_train = ttk.Frame(self.tabs, padding=8)
        self.tab_audio = ttk.Frame(self.tabs, padding=8)
        self.tab_vision = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.tab_chat, text="Conversa")
        self.tabs.add(self.tab_train, text="Treino incremental")
        self.tabs.add(self.tab_audio, text="Áudio")
        self.tabs.add(self.tab_vision, text="Visão")

        self._build_chat_tab()
        self._build_train_tab()
        self._build_audio_tab()
        self._build_vision_tab()

        body.add(left, weight=2)

        logs = ttk.Labelframe(body, text="Logs", padding=8)
        logs.columnconfigure(0, weight=1)
        logs.rowconfigure(0, weight=1)
        self.log_text = tk.Text(logs, wrap="word", height=10)
        self.log_text.configure(state=tk.DISABLED)
        scroll = ttk.Scrollbar(logs, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        body.add(logs, weight=1)

    def _build_chat_tab(self) -> None:
        f = self.tab_chat
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        self.chat_text = tk.Text(f, wrap="word")
        self.chat_text.grid(row=0, column=0, columnspan=3, sticky="nsew")

        self.entry_var = tk.StringVar(value="")
        self.entry = ttk.Entry(f, textvariable=self.entry_var)
        self.entry.grid(row=1, column=0, sticky="ew", pady=(8, 0), padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self.on_send())

        ttk.Button(f, text="Enviar", command=self.on_send).grid(row=1, column=1, pady=(8, 0), padx=(0, 8))
        ttk.Button(f, text="Cancelar", command=self.on_cancel).grid(row=1, column=2, pady=(8, 0))

        ttk.Button(f, text="Falar última resposta", command=self.on_speak_last).grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )

    def _build_train_tab(self) -> None:
        f = self.tab_train
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Pergunta (user)").grid(row=0, column=0, sticky="w")
        ttk.Label(f, text="Resposta (assistant)").grid(row=0, column=1, sticky="w")

        self.train_q = tk.Text(f, height=10, wrap="word")
        self.train_a = tk.Text(f, height=10, wrap="word")
        self.train_q.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.train_a.grid(row=1, column=1, sticky="nsew")

        btns = ttk.Frame(f)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        ttk.Button(btns, text="Salvar exemplo", command=self.on_save_example).pack(side=tk.LEFT)
        ttk.Button(btns, text="Importar pasta treinos/importar", command=self.on_import_folder).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(btns, text="Importar de ia_treinos", command=self.on_import_ia_treinos).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        self.train_stats_var = tk.StringVar(value="Exemplos: 0")
        ttk.Label(btns, textvariable=self.train_stats_var).pack(side=tk.RIGHT)

    def _build_audio_tab(self) -> None:
        f = self.tab_audio
        f.columnconfigure(0, weight=1)

        ttk.Label(
            f,
            text=(
                "Áudio (opcional, offline):\n"
                "- Para gravar: sounddevice + numpy\n"
                "- Para transcrever: vosk + modelo Vosk em rna_de_conversa/treinos/vosk_model\n"
                "- Para falar (TTS): pyttsx3\n"
            ),
        ).grid(row=0, column=0, sticky="w")

        cfg = ttk.Frame(f)
        cfg.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        cfg.columnconfigure(7, weight=1)

        self.audio_seconds_var = tk.StringVar(value=str(self._settings.get("audio_seconds", 4.0)))
        ttk.Label(cfg, text="Duração (s):").grid(row=0, column=0, sticky="w")
        ttk.Entry(cfg, textvariable=self.audio_seconds_var, width=8).grid(row=0, column=1, padx=(6, 12))

        ttk.Button(cfg, text="Gravar e transcrever (enviar)", command=self.on_record_and_send).grid(
            row=0, column=2, padx=(0, 8)
        )
        ttk.Button(cfg, text="Só falar última resposta", command=self.on_speak_last).grid(row=0, column=3)

        self.audio_note = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.audio_note).grid(row=2, column=0, sticky="w", pady=(10, 0))

    def _build_vision_tab(self) -> None:
        f = self.tab_vision
        f.columnconfigure(1, weight=1)
        f.rowconfigure(2, weight=1)

        ttk.Label(
            f,
            text=(
                "Visão (tela/webcam):\n"
                "- Capturar tela: requer Pillow\n"
                "- Capturar webcam: requer opencv-python\n"
                "- Para descrever a imagem: use Ollama com modelo multimodal (ex.: llava)\n"
            ),
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        btns = ttk.Frame(f)
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        ttk.Button(btns, text="Capturar tela", command=self.on_capture_screen).pack(side=tk.LEFT)
        ttk.Button(btns, text="Capturar webcam", command=self.on_capture_webcam).pack(side=tk.LEFT, padx=(8, 0))

        self.vision_prompt_var = tk.StringVar(value="Descreva o que você vê.")
        ttk.Entry(btns, textvariable=self.vision_prompt_var, width=50).pack(side=tk.LEFT, padx=(12, 8))
        ttk.Button(btns, text="Enviar imagem", command=self.on_send_image).pack(side=tk.LEFT)

        ttk.Label(f, text="Preview").grid(row=2, column=0, sticky="nw", padx=(0, 10))
        self.img_preview = ttk.Label(f)
        self.img_preview.grid(row=3, column=0, sticky="nw", padx=(0, 10))

        ttk.Label(f, text="Status").grid(row=2, column=1, sticky="nw")
        self.vision_status = tk.Text(f, height=12, wrap="word")
        self.vision_status.grid(row=3, column=1, sticky="nsew")

    # ---------------- helpers ----------------

    def _log(self, msg: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _chat_append(self, who: str, msg: str) -> None:
        self.chat_text.insert(tk.END, f"{who}: {msg}\n\n")
        self.chat_text.see(tk.END)

        if who == "IA":
            self._last_assistant_text = msg

    def _post(self, kind: str, text: str = "") -> None:
        self._ui_queue.put(UiMsg(kind=kind, text=text))

    def _poll(self) -> None:
        try:
            while True:
                m = self._ui_queue.get_nowait()
                if m.kind == "log":
                    self._log(m.text)
                elif m.kind == "chat_user":
                    self._chat_append("Você", m.text)
                elif m.kind == "chat_assistant":
                    self._chat_append("IA", m.text)
                elif m.kind == "status":
                    self.status_var.set(m.text)
                elif m.kind == "done":
                    self.status_var.set("Pronto")
                elif m.kind == "error":
                    self.status_var.set("Erro")
                    messagebox.showerror("RNA", m.text)
        except queue.Empty:
            pass
        self.after(120, self._poll)

    def _run_worker(self, title: str, fn) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("RNA", "Já existe uma operação em andamento.")
            return

        self._cancel = threading.Event()
        cancel = self._cancel
        self._post("status", f"{title}...")

        def runner() -> None:
            try:
                self._post("log", f"== {title} ==")
                fn(cancel)
                self._post("done")
            except Exception as e:
                self._post("error", f"{title} falhou: {e}")

        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    def _refresh_counts(self) -> None:
        n = count_examples(self._conn)
        self.train_stats_var.set(f"Exemplos: {n}")

    def _refresh_ollama(self, *, initial: bool = False) -> None:
        st = detect(self.cfg)
        self._ollama_status = st

        if st.models:
            self.cmb_models.configure(values=st.models, state="readonly")
        else:
            self.cmb_models.configure(values=[], state="disabled")

        if initial and not self.model_var.get() and st.models:
            self.model_var.set(st.models[0])

        note = st.note
        if st.installed and st.running:
            self._log(f"Ollama OK. Modelos: {len(st.models)}")
        elif st.installed and not st.running:
            self._log(f"Ollama instalado, mas não está rodando. {note}")
        else:
            self._log("Ollama não encontrado. Usando fallback local.")

        # If not running, force disable checkbox in UI
        if not (st.installed and st.running):
            self.use_ollama_var.set(False)

        self._save_settings()

    def _save_settings(self) -> None:
        data = {
            "use_ollama": bool(self.use_ollama_var.get()),
            "ollama_model": str(self.model_var.get() or ""),
            "audio_seconds": float(self._safe_float(self.audio_seconds_var.get(), 4.0))
            if hasattr(self, "audio_seconds_var")
            else float(self._settings.get("audio_seconds", 4.0)),
        }
        save_settings(self.cfg, data)

    # ---------------- actions ----------------

    def on_cancel(self) -> None:
        self._cancel.set()
        self._post("log", "Cancelamento solicitado.")

    def on_clear_session(self) -> None:
        self._runtime.clear_session()
        self.chat_text.delete("1.0", tk.END)
        self._log("Sessão limpa.")

    def on_refresh_models(self) -> None:
        self._refresh_ollama(initial=False)

    def on_send(self) -> None:
        text = (self.entry_var.get() or "").strip()
        if not text:
            return
        self.entry_var.set("")

        use_ollama = bool(self.use_ollama_var.get())
        model = (self.model_var.get() or "").strip() or None

        if use_ollama and not (self._ollama_status.installed and self._ollama_status.running):
            messagebox.showinfo("RNA", "Ollama não está disponível. Desmarque 'Usar Ollama'.")
            return
        if use_ollama and not model:
            messagebox.showinfo("RNA", "Selecione um modelo do Ollama.")
            return

        self._post("chat_user", text)

        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            res = self._runtime.reply(text, use_ollama=use_ollama, model=model)
            if cancel.is_set():
                return
            self._post("log", f"engine={res.engine} {res.debug}".strip())
            self._post("chat_assistant", res.text)
            self._save_settings()

        self._run_worker("Responder", task)

    def on_speak_last(self) -> None:
        txt = (self._last_assistant_text or "").strip()
        if not txt:
            messagebox.showinfo("RNA", "Ainda não há resposta para falar.")
            return

        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            speak_text(txt)

        self._run_worker("TTS (falar)", task)

    def on_save_example(self) -> None:
        q = self.train_q.get("1.0", tk.END).strip()
        a = self.train_a.get("1.0", tk.END).strip()
        if not q or not a:
            messagebox.showinfo("RNA", "Preencha pergunta e resposta.")
            return

        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            _ = add_example(self._conn, q, a)
            self._post("log", "Exemplo salvo no treino.")
            self.after(0, self._refresh_counts)

        self._run_worker("Salvar exemplo", task)

    def on_import_folder(self) -> None:
        folder = import_dir(self.cfg)
        folder.mkdir(parents=True, exist_ok=True)

        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            n, errs = import_folder(self._conn, folder)
            self._post("log", f"Importados: {n}")
            for e in errs[:30]:
                self._post("log", f"ERRO: {e}")
            self.after(0, self._refresh_counts)

        self._run_worker("Importar pasta", task)

    def on_import_ia_treinos(self) -> None:
        # Workspace root is parent of rna_de_conversa/
        ws_root = Path(__file__).resolve().parents[2]
        base = ws_root / "ia_treinos" / "conversa"
        folder = (base / "importar") if (base / "importar").exists() else base

        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            if not folder.exists():
                self._post("log", f"Nada para importar (não existe): {folder}")
                return
            n, errs = import_folder(self._conn, folder)
            self._post("log", f"Importados de ia_treinos: {n} | fonte={folder}")
            for e in errs[:30]:
                self._post("log", f"ERRO: {e}")
            self.after(0, self._refresh_counts)

        self._run_worker("Importar ia_treinos", task)

    def on_record_and_send(self) -> None:
        seconds = self._safe_float(self.audio_seconds_var.get(), 4.0)

        use_ollama = bool(self.use_ollama_var.get())
        model = (self.model_var.get() or "").strip() or None

        if use_ollama and not (self._ollama_status.installed and self._ollama_status.running):
            messagebox.showinfo("RNA", "Ollama não está disponível. Desmarque 'Usar Ollama'.")
            return
        if use_ollama and not model:
            messagebox.showinfo("RNA", "Selecione um modelo do Ollama.")
            return

        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            self._post("log", f"Gravando {seconds:.1f}s...")

            wav_path = (Path(db_path(self.cfg)).parent / "audio") / "last.wav"
            rec = record_wav_to_file(wav_path, seconds=seconds, sample_rate=16000, channels=1)

            if cancel.is_set():
                return

            model_dir = Path(db_path(self.cfg)).parent / "vosk_model"
            tr = transcribe_wav_vosk(rec.path, model_dir=model_dir)
            text = (tr.text or "").strip()
            if not text:
                self._post("log", "Transcrição vazia.")
                return

            self._post("chat_user", text)
            res = self._runtime.reply(text, use_ollama=use_ollama, model=model)
            self._post("log", f"engine={res.engine} {res.debug}".strip())
            self._post("chat_assistant", res.text)
            self._save_settings()

        self._run_worker("Áudio -> Texto", task)

    def on_capture_screen(self) -> None:
        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            img = capture_screen_png()
            self._last_image = img
            self._post("log", "Tela capturada.")
            self.after(0, self._render_last_image)

        self._run_worker("Capturar tela", task)

    def on_capture_webcam(self) -> None:
        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            img = capture_webcam_png(0)
            self._last_image = img
            self._post("log", "Webcam capturada.")
            self.after(0, self._render_last_image)

        self._run_worker("Capturar webcam", task)

    def on_send_image(self) -> None:
        if self._last_image is None:
            messagebox.showinfo("RNA", "Capture a tela ou webcam primeiro.")
            return

        prompt = (self.vision_prompt_var.get() or "").strip()
        use_ollama = bool(self.use_ollama_var.get())
        model = (self.model_var.get() or "").strip() or None

        if use_ollama and not (self._ollama_status.installed and self._ollama_status.running):
            messagebox.showinfo("RNA", "Ollama não está disponível. Desmarque 'Usar Ollama'.")
            return
        if use_ollama and not model:
            messagebox.showinfo("RNA", "Selecione um modelo do Ollama.")
            return

        # Log user intent into chat
        self._post("chat_user", f"[imagem:{self._last_image.kind}] {prompt or ''}".strip())

        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return
            res = self._runtime.reply_with_image(
                prompt,
                image_png=self._last_image.png_bytes,
                use_ollama=use_ollama,
                model=model,
                image_hint=self._last_image.kind,
            )
            if cancel.is_set():
                return
            self._post("log", f"engine={res.engine} {res.debug}".strip())
            self._post("chat_assistant", res.text)
            self._save_settings()

        self._run_worker("Responder com imagem", task)

    def _render_last_image(self) -> None:
        if self._last_image is None:
            return
        try:
            data = png_bytes_to_tk_photo_data(self._last_image.png_bytes)
            self._tk_img = tk.PhotoImage(data=data)
            self.img_preview.configure(image=self._tk_img)
            self.vision_status.delete("1.0", tk.END)
            self.vision_status.insert(tk.END, f"Última imagem: {self._last_image.kind}\n")
            self.vision_status.insert(tk.END, f"Tamanho: {len(self._last_image.png_bytes)} bytes\n")
        except Exception as e:
            self.vision_status.delete("1.0", tk.END)
            self.vision_status.insert(tk.END, f"Falha ao renderizar preview: {e}\n")

    @staticmethod
    def _safe_float(v: str, default: float) -> float:
        try:
            return float(str(v).strip().replace(",", "."))
        except Exception:
            return float(default)
