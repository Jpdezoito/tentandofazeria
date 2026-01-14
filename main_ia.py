from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import webbrowser
import urllib.parse
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox
from tkinter import filedialog, simpledialog
from tkinter import ttk
from typing import Optional


@dataclass(frozen=True)
class IaHubPaths:
    root: Path
    buscarpastas: Path
    qualquer_imagem: Path
    video: Path
    conversa: Path
    extra_treinos: Path


def default_paths() -> IaHubPaths:
    root = Path(__file__).resolve().parent
    return IaHubPaths(
        root=root,
        buscarpastas=root / "treino_rna_buscarpastas",
        qualquer_imagem=root / "treino_rna_qualquer_imagem",
        video=root / "rna_de_video",
        conversa=root / "rna_de_conversa",
        extra_treinos=root / "ia_treinos",
    )


class IaHubApp(tk.Tk):
    def __init__(self, paths: IaHubPaths):
        super().__init__()
        self.paths = paths

        self._settings_path = self.paths.root / "ia_hub_settings.json"
        self._settings = self._load_settings()
        self._theme = str(self._settings.get("theme", "dark"))  # "dark" | "light"

        self._ui_queue: queue.Queue[str] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._busy = False

        self._last_search_paths: list[Path] = []

        self.title("IA Hub")
        self.minsize(1020, 680)

        self._apply_modern_style(theme=self._theme)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(16, 14, 16, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(header)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)

        left_tools = ttk.Frame(toolbar)
        left_tools.grid(row=0, column=0, sticky="w")

        ttk.Button(left_tools, text="Abrir ia_treinos", command=self.on_open_extra_folder).pack(side=tk.LEFT)
        ttk.Button(left_tools, text="Abrir pasta do projeto", command=self.on_open_project_root).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Separator(toolbar, orient=tk.VERTICAL).grid(row=0, column=1, sticky="ns", padx=12)

        right_tools = ttk.Frame(toolbar)
        right_tools.grid(row=0, column=2, sticky="e")

        self.theme_var = tk.StringVar(value=self._theme)
        ttk.Label(right_tools, text="Tema:", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Radiobutton(
            right_tools,
            text="Escuro",
            value="dark",
            variable=self.theme_var,
            command=self.on_toggle_theme,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Radiobutton(
            right_tools,
            text="Claro",
            value="light",
            variable=self.theme_var,
            command=self.on_toggle_theme,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(right_tools, text="Limpar logs", command=self.on_clear_logs).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(right_tools, text="Copiar logs", command=self.on_copy_logs).pack(side=tk.LEFT, padx=(8, 0))

        title_row = ttk.Frame(header)
        title_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        title_row.columnconfigure(0, weight=1)

        ttk.Label(title_row, text="IA Hub", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_row,
            text="Abrir módulos e importar/treinar treinos extras",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        body = ttk.Frame(self, padding=(16, 0, 16, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        cards = ttk.Frame(body)
        cards.grid(row=0, column=0, sticky="ew")
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        cards.columnconfigure(2, weight=1)

        card_apps = ttk.Labelframe(cards, text="Módulos", padding=12)
        card_apps.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        card_apps.columnconfigure(0, weight=1)

        self.btn_open_buscarpastas = ttk.Button(
            card_apps,
            text="Abrir BuscarPastas",
            command=self.on_open_buscarpastas,
            style="Primary.TButton",
        )
        self.btn_open_buscarpastas.grid(
            row=0, column=0, sticky="ew", pady=(0, 6)
        )

        self._buscarpastas_model_status = tk.StringVar(value="Modelos: padrão")
        buscar_models = ttk.Frame(card_apps)
        buscar_models.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        buscar_models.columnconfigure(0, weight=1)
        ttk.Label(buscar_models, textvariable=self._buscarpastas_model_status, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.btn_open_buscar_models = ttk.Button(
            buscar_models, text="Abrir modelos", command=self.on_open_modelos_buscarpastas
        )
        self.btn_open_buscar_models.grid(row=0, column=2, sticky="e")
        self.btn_open_buscar_active = ttk.Button(
            buscar_models, text="Abrir ativo", command=self.on_open_modelos_buscarpastas_ativo
        )
        self.btn_open_buscar_active.grid(row=0, column=1, sticky="e", padx=(0, 8))

        self.btn_open_qualquer = ttk.Button(
            card_apps,
            text="Abrir QualquerImagem",
            command=self.on_open_qualquer_imagem,
            style="Primary.TButton",
        )
        self.btn_open_qualquer.grid(
            row=2, column=0, sticky="ew", pady=(0, 6)
        )

        self._qualquer_model_status = tk.StringVar(value="Modelos: padrão")
        qualquer_models = ttk.Frame(card_apps)
        qualquer_models.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        qualquer_models.columnconfigure(0, weight=1)
        ttk.Label(qualquer_models, textvariable=self._qualquer_model_status, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.btn_open_qualquer_models = ttk.Button(
            qualquer_models, text="Abrir modelos", command=self.on_open_modelos_qualquer_imagem
        )
        self.btn_open_qualquer_models.grid(row=0, column=2, sticky="e")
        self.btn_open_qualquer_active = ttk.Button(
            qualquer_models, text="Abrir ativo", command=self.on_open_modelos_qualquer_imagem_ativo
        )
        self.btn_open_qualquer_active.grid(row=0, column=1, sticky="e", padx=(0, 8))

        self.btn_open_conversa = ttk.Button(
            card_apps,
            text="Abrir Conversa (texto/áudio/visão)",
            command=self.on_open_conversa,
            style="Primary.TButton",
        )
        self.btn_open_conversa.grid(
            row=4, column=0, sticky="ew", pady=(0, 6)
        )

        self.btn_open_video = ttk.Button(
            card_apps,
            text="Abrir Vídeo (treino/reconhecimento)",
            command=self.on_open_video,
            style="Primary.TButton",
        )
        self.btn_open_video.grid(row=6, column=0, sticky="ew", pady=(10, 6))

        self._conversa_model_status = tk.StringVar(value="Modelos: padrão")
        conversa_models = ttk.Frame(card_apps)
        conversa_models.grid(row=5, column=0, sticky="ew")
        conversa_models.columnconfigure(0, weight=1)
        ttk.Label(conversa_models, textvariable=self._conversa_model_status, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.btn_open_conversa_models = ttk.Button(
            conversa_models, text="Abrir modelos", command=self.on_open_modelos_conversa
        )
        self.btn_open_conversa_models.grid(row=0, column=2, sticky="e")
        self.btn_open_conversa_active = ttk.Button(
            conversa_models, text="Abrir ativo", command=self.on_open_modelos_conversa_ativo
        )
        self.btn_open_conversa_active.grid(row=0, column=1, sticky="e", padx=(0, 8))

        card_extras = ttk.Labelframe(cards, text="Treinos extras", padding=12)
        card_extras.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=(0, 10))
        card_extras.columnconfigure(0, weight=1)

        self.btn_import_images = ttk.Button(card_extras, text="Importar extras (imagens)", command=self.on_import_extras)
        self.btn_import_images.grid(
            row=0, column=0, sticky="ew", pady=(0, 8)
        )

        self.btn_import_chat = ttk.Button(card_extras, text="Importar extras (conversa)", command=self.on_import_conversa_extras)
        self.btn_import_chat.grid(
            row=1, column=0, sticky="ew"
        )

        card_tools = ttk.Labelframe(cards, text="Ações", padding=12)
        card_tools.grid(row=0, column=2, sticky="nsew", pady=(0, 10))
        card_tools.columnconfigure(0, weight=1)

        self.btn_train_images = ttk.Button(card_tools, text="Treinar imagens agora", command=self.on_train_images)
        self.btn_train_images.grid(
            row=0, column=0, sticky="ew"
        )

        assistant = ttk.Labelframe(body, text="Assistente (texto + anexos)", padding=10)
        assistant.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        assistant.columnconfigure(0, weight=1)

        self.assistant_entry_var = tk.StringVar(value="")
        self.assistant_entry = ttk.Entry(assistant, textvariable=self.assistant_entry_var)
        self.assistant_entry.grid(row=0, column=0, sticky="ew")
        self.assistant_entry.bind("<Return>", lambda _e: self.on_assistant_send())

        self.btn_clip = ttk.Button(assistant, text="📎", width=3, command=self.on_clip_menu)
        self.btn_clip.grid(row=0, column=1, padx=(8, 0))

        self.btn_assistant_send = ttk.Button(assistant, text="Enviar", command=self.on_assistant_send)
        self.btn_assistant_send.grid(row=0, column=2, padx=(8, 0))

        self.use_ollama_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(assistant, text="Usar Ollama", variable=self.use_ollama_var).grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Label(assistant, text="Modelo:", style="Muted.TLabel").grid(row=1, column=1, sticky="e", padx=(8, 6), pady=(8, 0))
        self.ollama_model_var = tk.StringVar(value="llama3")
        ttk.Entry(assistant, textvariable=self.ollama_model_var, width=20).grid(row=1, column=2, sticky="e", pady=(8, 0))

        ttk.Label(
            assistant,
            text="Dicas: /buscar texto | /abrir 1 | /web texto | ou use o 📎 para anexar",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        logs = ttk.Labelframe(body, text="Logs", padding=10)
        logs.grid(row=2, column=0, sticky="nsew")
        logs.columnconfigure(0, weight=1)
        logs.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            logs,
            wrap="word",
            height=12,
            padx=10,
            pady=8,
            bd=0,
            highlightthickness=0,
            font=("Consolas", 10),
        )
        self.log_text.configure(state=tk.DISABLED)
        scroll = ttk.Scrollbar(logs, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        status = ttk.Frame(self, padding=(16, 8))
        status.grid(row=2, column=0, sticky="ew")
        status.columnconfigure(2, weight=1)

        ttk.Label(status, text="Status:", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=1, sticky="w", padx=(6, 0))

        self.progress = ttk.Progressbar(status, mode="indeterminate", length=140)
        self.progress.grid(row=0, column=2, sticky="e", padx=(8, 12))

        ttk.Label(status, text=f"Treinos extras: {self.paths.extra_treinos}", style="Muted.TLabel").grid(
            row=0, column=3, sticky="e"
        )

        self.after(80, self._poll)

        self._wire_shortcuts()
        self._wire_log_context_menu()
        self._apply_log_tags()

        self._action_buttons: list[ttk.Widget] = [
            self.btn_open_buscarpastas,
            self.btn_open_buscar_active,
            self.btn_open_buscar_models,
            self.btn_open_qualquer,
            self.btn_open_qualquer_active,
            self.btn_open_qualquer_models,
            self.btn_open_conversa,
            self.btn_open_conversa_active,
            self.btn_open_conversa_models,
            self.btn_import_images,
            self.btn_import_chat,
            self.btn_train_images,
        ]

        self._log("IA Hub pronto.")
        self._log(f"Pasta de treinos extras: {self.paths.extra_treinos}")
        self._log("Estrutura sugerida: ia_treinos/imagens/<ROTULO>/*.jpg")

        self._refresh_model_statuses()

    # -------- pretrained models (UI helpers) --------

    @staticmethod
    def _modelos_pre_treinados_base(project_root: Path) -> Path:
        return project_root / "treinos" / "modelo_treino" / "modelos_pre_treinados"

    @staticmethod
    def _active_pretrained_root(base: Path) -> Path | None:
        marker = base / "ATIVO.txt"
        if marker.exists():
            rel = marker.read_text(encoding="utf-8", errors="replace").strip()
            if rel:
                candidate = (base / rel).resolve()
                if candidate.exists() and candidate.is_dir():
                    return candidate

        candidate = base / "ativo"
        if candidate.exists() and candidate.is_dir():
            return candidate

        return None

    def _status_text_for_project(self, project_root: Path) -> str:
        base = self._modelos_pre_treinados_base(project_root)
        active = self._active_pretrained_root(base)
        if active is None:
            return "Modelos: padrão (treinos/)"

        # Prefer a friendly label for the active bundle
        if active.parent == base:
            return f"Modelos: {active.name}"
        return f"Modelos: {active.name} (ativo)"

    def _refresh_model_statuses(self) -> None:
        try:
            self._buscarpastas_model_status.set(self._status_text_for_project(self.paths.buscarpastas))
            self._qualquer_model_status.set(self._status_text_for_project(self.paths.qualquer_imagem))
            self._conversa_model_status.set(self._status_text_for_project(self.paths.conversa))
        except Exception as e:
            self._log(f"Falhou ao atualizar status de modelos: {e}")

    def _apply_modern_style(self, *, theme: str) -> None:
        style = ttk.Style(self)
        # Prefer a theme that allows styling; fall back to whatever exists.
        preferred = ["clam", "vista", "xpnative"]
        available = set(style.theme_names())
        for name in preferred:
            if name in available:
                try:
                    style.theme_use(name)
                except Exception:
                    pass
                break

        # Basic typography
        base_font = tkfont.nametofont("TkDefaultFont")
        base_font.configure(size=10, family="Segoe UI")

        header_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        subheader_font = tkfont.Font(family="Segoe UI", size=10)

        style.configure("Header.TLabel", font=header_font)
        style.configure("SubHeader.TLabel", font=subheader_font)

        palette = self._palette_for_theme(theme)
        self.configure(background=palette["bg"])

        # General
        style.configure("TFrame", background=palette["bg"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["fg"])
        style.configure("Muted.TLabel", background=palette["bg"], foreground=palette["muted"])

        # Labelframe "cards"
        style.configure(
            "TLabelframe",
            background=palette["card_bg"],
            bordercolor=palette["border"],
            relief="solid",
        )
        style.configure(
            "TLabelframe.Label",
            background=palette["card_bg"],
            foreground=palette["fg"],
            font=("Segoe UI", 10, "bold"),
        )

        # Buttons
        style.configure("TButton", padding=(12, 9))
        style.map(
            "TButton",
            foreground=[("disabled", palette["muted"])],
        )

        style.configure(
            "Primary.TButton",
            padding=(12, 10),
            background=palette["accent"],
            foreground=palette["accent_fg"],
            bordercolor=palette["accent"],
            focusthickness=2,
            focuscolor=palette["accent"],
        )
        style.map(
            "Primary.TButton",
            background=[("active", palette["accent_hover"]), ("disabled", palette["border"])],
            foreground=[("active", palette["accent_fg"]), ("disabled", palette["muted"])],
        )

        # Radiobuttons / separators
        style.configure("TRadiobutton", background=palette["bg"], foreground=palette["fg"])
        style.configure("TSeparator", background=palette["border"])

        # Text widget (non-ttk)
        try:
            self.log_text.configure(
                background=palette["log_bg"],
                foreground=palette["log_fg"],
                insertbackground=palette["log_fg"],
                selectbackground=palette["select_bg"],
                selectforeground=palette["select_fg"],
            )
        except Exception:
            pass

        style.configure("Header.TLabel", font=header_font, background=palette["bg"], foreground=palette["fg"])
        style.configure(
            "SubHeader.TLabel",
            font=subheader_font,
            background=palette["bg"],
            foreground=palette["muted"],
        )

    @staticmethod
    def _palette_for_theme(theme: str) -> dict[str, str]:
        if str(theme).lower().strip() == "light":
            return {
                "bg": "#F6F7FB",
                "fg": "#0F172A",
                "muted": "#475569",
                "card_bg": "#FFFFFF",
                "border": "#E2E8F0",
                "accent": "#2563EB",
                "accent_hover": "#1D4ED8",
                "accent_fg": "#FFFFFF",
                "log_bg": "#0B1220",
                "log_fg": "#E5E7EB",
                "select_bg": "#334155",
                "select_fg": "#FFFFFF",
            }
        return {
            "bg": "#0B1020",
            "fg": "#E5E7EB",
            "muted": "#94A3B8",
            "card_bg": "#0F172A",
            "border": "#1F2937",
            "accent": "#22C55E",
            "accent_hover": "#16A34A",
            "accent_fg": "#0B1020",
            "log_bg": "#050815",
            "log_fg": "#D1D5DB",
            "select_bg": "#1F2937",
            "select_fg": "#FFFFFF",
        }

    def _load_settings(self) -> dict:
        try:
            if self._settings_path.exists():
                return json.loads(self._settings_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_settings(self) -> None:
        try:
            self._settings_path.write_text(json.dumps(self._settings, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _wire_shortcuts(self) -> None:
        self.bind_all("<Control-l>", lambda _e: self.on_clear_logs())
        self.bind_all("<Control-L>", lambda _e: self.on_clear_logs())
        self.bind_all("<Control-Shift-C>", lambda _e: self.on_copy_logs())
        self.bind_all("<F5>", lambda _e: self.on_train_images())

    def _wire_log_context_menu(self) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Copiar tudo", command=self.on_copy_logs)
        menu.add_command(label="Limpar", command=self.on_clear_logs)

        def popup(event) -> None:
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        self.log_text.bind("<Button-3>", popup)

    def _set_busy(self, busy: bool, title: str = "") -> None:
        self._busy = bool(busy)
        for w in getattr(self, "_action_buttons", []):
            try:
                w.configure(state=("disabled" if self._busy else "normal"))
            except Exception:
                pass

        if self._busy:
            if title:
                self.status_var.set(title)
            try:
                self.progress.start(12)
            except Exception:
                pass
        else:
            try:
                self.progress.stop()
            except Exception:
                pass
            self.status_var.set("Pronto")

    def on_toggle_theme(self) -> None:
        theme = str(self.theme_var.get() or "dark")
        self._theme = theme
        self._settings["theme"] = theme
        self._save_settings()
        self._apply_modern_style(theme=theme)
        self._apply_log_tags()

    def on_clear_logs(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._log("Logs limpos.")

    def on_copy_logs(self) -> None:
        txt = self.log_text.get("1.0", tk.END).strip("\n")
        if not txt.strip():
            messagebox.showinfo("IA Hub", "Não há logs para copiar.")
            return
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.update_idletasks()
        messagebox.showinfo("IA Hub", "Logs copiados para a área de transferência.")

    def on_open_extra_folder(self) -> None:
        self.paths.extra_treinos.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.paths.extra_treinos))

    def on_open_project_root(self) -> None:
        os.startfile(str(self.paths.root))

    def _open_folder(self, p: Path) -> None:
        p.mkdir(parents=True, exist_ok=True)
        os.startfile(str(p))

    def _open_models_base(self, project_root: Path) -> None:
        self._open_folder(self._modelos_pre_treinados_base(project_root))
        self._refresh_model_statuses()

    def _open_models_active(self, project_root: Path) -> None:
        base = self._modelos_pre_treinados_base(project_root)
        base.mkdir(parents=True, exist_ok=True)
        active = self._active_pretrained_root(base)
        if active is None:
            active = base / "ativo"
            active.mkdir(parents=True, exist_ok=True)
        self._open_folder(active)
        self._refresh_model_statuses()

    def on_open_modelos_buscarpastas(self) -> None:
        self._open_models_base(self.paths.buscarpastas)

    def on_open_modelos_buscarpastas_ativo(self) -> None:
        self._open_models_active(self.paths.buscarpastas)

    def on_open_modelos_qualquer_imagem(self) -> None:
        self._open_models_base(self.paths.qualquer_imagem)

    def on_open_modelos_qualquer_imagem_ativo(self) -> None:
        self._open_models_active(self.paths.qualquer_imagem)

    def on_open_modelos_conversa(self) -> None:
        self._open_models_base(self.paths.conversa)

    def on_open_modelos_conversa_ativo(self) -> None:
        self._open_models_active(self.paths.conversa)

    # -------- logging --------

    def _apply_log_tags(self) -> None:
        # Basic semantic colors for logs.
        try:
            pal = self._palette_for_theme(self._theme)
            self.log_text.tag_configure("err", foreground="#EF4444")
            self.log_text.tag_configure("ok", foreground=pal.get("accent", "#22C55E"))
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"

        low = (msg or "").lower()
        tag = None
        if "erro" in low or "falhou" in low or "traceback" in low:
            tag = "err"
        elif "exit code=0" in low or " ollama ok" in low:
            tag = "ok"

        self.log_text.configure(state=tk.NORMAL)
        if tag:
            self.log_text.insert(tk.END, line + "\n", tag)
        else:
            self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _post_log(self, msg: str) -> None:
        self._ui_queue.put(msg)

    def _poll(self) -> None:
        try:
            while True:
                msg = self._ui_queue.get_nowait()
                self._log(msg)
        except queue.Empty:
            pass
        self.after(120, self._poll)

    # -------- workers --------

    def _run_subprocess(self, title: str, args: list[str], cwd: Path) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("IA Hub", "Já existe uma operação em andamento.")
            return

        def runner() -> None:
            self.after(0, lambda: self._set_busy(True, title))
            self._post_log(f"== {title} ==")
            self._post_log(" ".join(args))
            try:
                proc = subprocess.Popen(
                    args,
                    cwd=str(cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    self._post_log(line.rstrip("\n"))
                rc = proc.wait()
                self._post_log(f"(exit code={rc})")
            except Exception as e:
                self._post_log(f"Falhou: {e}")
            finally:
                self.after(0, lambda: self._set_busy(False))

        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    def _python_for_tools(self) -> str:
        """Pick a Python interpreter for running sub-tools.

        Default is sys.executable, but can be overridden via ia_hub_settings.json:
        {"python_exe": "C:/Path/To/python.exe"}
        """

        try:
            p = str(self._settings.get("python_exe") or "").strip()
            if p:
                return p
        except Exception:
            pass

        # If user has Python 3.12 installed (recommended for opencv), prefer it.
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
            str(self.paths.root / ".venv312" / "Scripts" / "python.exe"),
        ]
        for c in candidates:
            try:
                if c and Path(c).exists():
                    return c
            except Exception:
                continue

        return sys.executable

    def _run_json_tool(self, title: str, args: list[str], cwd: Path) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("IA Hub", "Já existe uma operação em andamento.")
            return

        def runner() -> None:
            self.after(0, lambda: self._set_busy(True, title))
            self._post_log(f"== {title} ==")
            self._post_log(" ".join(args))
            try:
                proc = subprocess.run(
                    args,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                raw = (proc.stdout or "").strip()
                if proc.returncode != 0:
                    err = (proc.stderr or raw or f"exit={proc.returncode}").strip()
                    self._post_log(f"Erro: {err}")
                    return

                try:
                    obj = json.loads(raw) if raw else {}
                except Exception as e:
                    self._post_log(f"Falha ao ler JSON: {e}")
                    self._post_log(raw)
                    return

                # Pretty print key parts.
                if isinstance(obj, dict):
                    if "results" in obj and isinstance(obj.get("results"), list):
                        res = obj.get("results") or []
                        if not res:
                            self._post_log("(sem resultados)")
                        else:
                            self._last_search_paths = []
                            for i, it in enumerate(res[:25], start=1):
                                if not isinstance(it, dict):
                                    continue
                                p = Path(str(it.get("path") or ""))
                                self._last_search_paths.append(p)
                                score = it.get("score")
                                kind = it.get("kind")
                                reason = it.get("reason")
                                self._post_log(f"{i:02d}. {p} | {kind} | score={score} | {reason}")
                        return

                    if "topk" in obj and isinstance(obj.get("topk"), list):
                        known = obj.get("known")
                        reason = obj.get("reason")
                        self._post_log(f"known={known} reason={reason}")
                        for it in obj.get("topk")[:5]:
                            if not isinstance(it, dict):
                                continue
                            self._post_log(
                                f"- {it.get('label')} conf={float(it.get('confidence') or 0):.3f} sim={float(it.get('similarity') or 0):.3f}"
                            )
                        return

                    if "text" in obj:
                        engine = str(obj.get("engine") or "")
                        dbg = str(obj.get("debug") or "")
                        extra = f" ({engine})" if engine else ""
                        if dbg:
                            extra += f" [{dbg}]"
                        self._post_log(f"IA{extra}: {str(obj.get('text') or '')}")
                        return

                self._post_log(raw)
            except Exception as e:
                self._post_log(f"Falhou: {e}")
            finally:
                self.after(0, lambda: self._set_busy(False))

        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    # -------- actions --------

    def on_open_buscarpastas(self) -> None:
        script = self.paths.buscarpastas / "main.py"
        if not script.exists():
            messagebox.showerror("IA Hub", f"Não achei: {script}")
            return
        # Launch detached (no stdout capture)
        subprocess.Popen([sys.executable, str(script)], cwd=str(self.paths.buscarpastas))
        self._log("Abrindo RNA BuscarPastas...")

    def on_open_qualquer_imagem(self) -> None:
        script = self.paths.qualquer_imagem / "main.py"
        if not script.exists():
            messagebox.showerror("IA Hub", f"Não achei: {script}")
            return
        subprocess.Popen([sys.executable, str(script)], cwd=str(self.paths.qualquer_imagem))
        self._log("Abrindo RNA QualquerImagem...")

    def on_open_conversa(self) -> None:
        script = self.paths.conversa / "main.py"
        if not script.exists():
            messagebox.showerror("IA Hub", f"Não achei: {script}")
            return
        subprocess.Popen([sys.executable, str(script)], cwd=str(self.paths.conversa))
        self._log("Abrindo RNA de Conversa...")

    def on_open_video(self) -> None:
        script = self.paths.video / "main.py"
        if not script.exists():
            messagebox.showerror("IA Hub", f"Não achei: {script}")
            return
        subprocess.Popen([sys.executable, str(script)], cwd=str(self.paths.video))
        self._log("Abrindo RNA de Vídeo...")

    # -------- assistant --------

    def on_clip_menu(self) -> None:
        if self._busy:
            return

        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Adicionar imagem...", command=self.on_attach_image)
        m.add_command(label="Adicionar vídeo...", command=self.on_attach_video)
        m.add_command(label="Adicionar áudio...", command=self.on_attach_audio)
        m.add_separator()
        m.add_command(label="Pesquisar na internet...", command=self.on_web_search_prompt)

        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            m.tk_popup(x, y)
        finally:
            try:
                m.grab_release()
            except Exception:
                pass

    def on_web_search_prompt(self) -> None:
        q = simpledialog.askstring("Internet", "Pesquisar por:")
        if not q:
            return
        self._open_web_search(q)

    def _open_web_search(self, query: str) -> None:
        q = (query or "").strip()
        if not q:
            return
        url = "https://duckduckgo.com/?q=" + urllib.parse.quote_plus(q)
        webbrowser.open(url)
        self._log(f"Web: {q}")

    def on_assistant_send(self) -> None:
        if self._busy:
            return
        text = (self.assistant_entry_var.get() or "").strip()
        if not text:
            return
        self.assistant_entry_var.set("")

        low = text.lower().strip()
        if low.startswith("/web "):
            self._open_web_search(text[5:].strip())
            return
        if low.startswith("web:"):
            self._open_web_search(text.split(":", 1)[1].strip())
            return

        if low.startswith("/abrir "):
            self._assistant_open_index(text[7:].strip())
            return

        if low.startswith("/buscar "):
            self._assistant_buscar(text[8:].strip())
            return
        if low.startswith("buscar:"):
            self._assistant_buscar(text.split(":", 1)[1].strip())
            return

        # Default: chat
        self._assistant_chat(text)

    def _assistant_open_index(self, s: str) -> None:
        try:
            idx = int((s or "").strip()) - 1
        except Exception:
            self._log("Uso: /abrir 1")
            return
        if idx < 0 or idx >= len(self._last_search_paths):
            self._log("Não achei esse número na última busca.")
            return
        p = self._last_search_paths[idx]
        if not p.exists():
            self._log("Arquivo/pasta não existe mais.")
            return
        try:
            os.startfile(str(p))
            self._log(f"Abrindo: {p}")
        except Exception as e:
            self._log(f"Falhou ao abrir: {e}")

    def _assistant_buscar(self, query: str) -> None:
        tool = self.paths.buscarpastas / "tools" / "cli_search.py"
        if not tool.exists():
            self._log(f"Não achei: {tool}")
            return
        py = self._python_for_tools()
        args = [py, str(tool), "--query", str(query)]
        self._run_json_tool("BuscarPastas", args, cwd=self.paths.buscarpastas)

    def _assistant_chat(self, text: str) -> None:
        tool = self.paths.conversa / "tools" / "cli_chat.py"
        if not tool.exists():
            self._log(f"Não achei: {tool}")
            return

        use_ollama = bool(self.use_ollama_var.get())
        model = (self.ollama_model_var.get() or "").strip()

        py = self._python_for_tools()
        args = [py, str(tool), "--text", str(text)]
        if use_ollama:
            args.append("--use-ollama")
        if use_ollama and model:
            args += ["--model", model]
        self._run_json_tool("Conversa", args, cwd=self.paths.conversa)

    def on_attach_image(self) -> None:
        p = filedialog.askopenfilename(
            title="Escolher imagem",
            filetypes=[
                ("Imagens", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp"),
                ("Todos", "*.*"),
            ],
        )
        if not p:
            return
        img = Path(p)

        tool = self.paths.qualquer_imagem / "tools" / "cli_classify.py"
        if not tool.exists():
            self._log(f"Não achei: {tool}")
            return

        py = self._python_for_tools()
        args = [py, str(tool), "--image", str(img)]
        self._run_json_tool("Reconhecer imagem", args, cwd=self.paths.qualquer_imagem)

    def on_attach_video(self) -> None:
        p = filedialog.askopenfilename(
            title="Escolher vídeo",
            filetypes=[
                ("Vídeos", "*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v"),
                ("Todos", "*.*"),
            ],
        )
        if not p:
            return

        mode = (simpledialog.askstring("Vídeo", "Modo (appearance/motion/fusion/scene/audio):", initialvalue="appearance") or "").strip()
        mode = mode or "appearance"

        start_s = (simpledialog.askstring("Vídeo", "Início (segundos) [vazio=todo]:", initialvalue="") or "").strip()
        end_s = (simpledialog.askstring("Vídeo", "Fim (segundos) [vazio=todo]:", initialvalue="") or "").strip()

        tool = self.paths.video / "tools" / "cli_classify.py"

        if not tool.exists():
            self._log(f"Não achei: {tool}")
            return

        py = self._python_for_tools()
        args = [py, str(tool), "--video", str(p), "--mode", str(mode)]
        if start_s or end_s:
            try:
                ss = float(start_s)
                ee = float(end_s)
            except Exception:
                self._log("Trecho inválido. Use números em segundos.")
                return
            args += ["--start", str(ss), "--end", str(ee)]

        self._run_json_tool("Reconhecer vídeo", args, cwd=self.paths.video)

    def on_attach_audio(self) -> None:
        p = filedialog.askopenfilename(
            title="Escolher áudio",
            filetypes=[
                ("Áudios", "*.wav;*.mp3;*.m4a;*.aac;*.ogg;*.flac"),
                ("Todos", "*.*"),
            ],
        )
        if not p:
            return

        tool = self.paths.conversa / "tools" / "cli_chat.py"
        if not tool.exists():
            self._log(f"Não achei: {tool}")
            return

        use_ollama = bool(self.use_ollama_var.get())
        model = (self.ollama_model_var.get() or "").strip()

        py = self._python_for_tools()
        args = [py, str(tool), "--audio", str(p)]
        if use_ollama:
            args.append("--use-ollama")
        if use_ollama and model:
            args += ["--model", model]
        self._run_json_tool("Áudio -> Texto -> Conversa", args, cwd=self.paths.conversa)
    def on_import_extras(self) -> None:
        tool = self.paths.qualquer_imagem / "tools" / "import_extra_treinos.py"
        if not tool.exists():
            messagebox.showerror("IA Hub", f"Não achei: {tool}")
            return
        self.paths.extra_treinos.mkdir(parents=True, exist_ok=True)
        args = [sys.executable, str(tool), "--extra", str(self.paths.extra_treinos)]
        self._run_subprocess("Importar treinos extras", args, cwd=self.paths.qualquer_imagem)

    def on_train_images(self) -> None:
        tool = self.paths.qualquer_imagem / "tools" / "train_from_db.py"
        if not tool.exists():
            messagebox.showerror("IA Hub", f"Não achei: {tool}")
            return
        args = [sys.executable, str(tool)]
        self._run_subprocess("Treinar imagens", args, cwd=self.paths.qualquer_imagem)

    def on_import_conversa_extras(self) -> None:
        tool = self.paths.conversa / "tools" / "import_from_ia_treinos.py"
        if not tool.exists():
            messagebox.showerror("IA Hub", f"Não achei: {tool}")
            return
        self.paths.extra_treinos.mkdir(parents=True, exist_ok=True)
        args = [sys.executable, str(tool), "--extra", str(self.paths.extra_treinos)]
        self._run_subprocess("Importar treinos extras (conversa)", args, cwd=self.paths.conversa)


def main() -> None:
    app = IaHubApp(default_paths())
    app.mainloop()


if __name__ == "__main__":
    main()
