from __future__ import annotations

import os
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import ttk

from ia_principal.core.clients import BuscarPastasClient, QualquerImagemClient, RnaConversaClient, RnaVideoClient
from ia_principal.core.router import decide_route


@dataclass
class SearchHit:
    path: str
    score: float
    kind: str
    reason: str


class IaPrincipalApp(tk.Tk):
    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root

        self.conversa = RnaConversaClient(project_root)
        self.buscar = BuscarPastasClient(project_root)
        self.imagem = QualquerImagemClient(project_root)
        self.video = RnaVideoClient(project_root)

        self._busy = False
        self._last_hits: list[SearchHit] = []

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=(12, 10))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        left = ttk.Frame(top)
        left.grid(row=0, column=0, sticky="w")

        ttk.Button(left, text="Imagem...", command=self.on_pick_image).pack(side=tk.LEFT)
        ttk.Button(left, text="Vídeo...", command=self.on_pick_video).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(left, text="Limpar", command=self.on_clear).pack(side=tk.LEFT, padx=(8, 0))

        right = ttk.Frame(top)
        right.grid(row=0, column=1, sticky="e")

        ttk.Label(right, text="Vídeo modo:").pack(side=tk.LEFT, padx=(0, 6))
        self.video_mode_var = tk.StringVar(value="appearance")
        ttk.Combobox(
            right,
            textvariable=self.video_mode_var,
            values=["appearance", "motion", "fusion", "scene", "audio"],
            state="readonly",
            width=10,
        ).pack(side=tk.LEFT)

        ttk.Label(right, text="Início(s):").pack(side=tk.LEFT, padx=(10, 6))
        self.video_start_var = tk.StringVar(value="")
        ttk.Entry(right, textvariable=self.video_start_var, width=6).pack(side=tk.LEFT)

        ttk.Label(right, text="Fim(s):").pack(side=tk.LEFT, padx=(10, 6))
        self.video_end_var = tk.StringVar(value="")
        ttk.Entry(right, textvariable=self.video_end_var, width=6).pack(side=tk.LEFT)

        self.use_ollama_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(right, text="Usar Ollama", variable=self.use_ollama_var).pack(side=tk.LEFT)
        ttk.Label(right, text="Modelo:").pack(side=tk.LEFT, padx=(10, 0))
        self.model_var = tk.StringVar(value="llama3")
        ttk.Entry(right, textvariable=self.model_var, width=18).pack(side=tk.LEFT)

        mid = ttk.Frame(self, padding=(12, 0, 12, 8))
        mid.grid(row=1, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)

        self.chat = tk.Text(mid, wrap="word", height=20)
        self.chat.configure(state=tk.DISABLED)
        self.chat.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self.chat.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.chat.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(self, padding=(12, 6, 12, 12))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(bottom, textvariable=self.entry_var)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _e: self.on_send())

        self.btn_send = ttk.Button(bottom, text="Enviar", command=self.on_send)
        self.btn_send.grid(row=0, column=1, padx=(10, 0))

        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(bottom, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(6, 0))

        self._append("IA Principal pronta. Dicas:\n- buscar: texto  (ou /buscar texto)\n- /abrir 1  (abre o resultado 1 da última busca)\n")

        self.entry.focus_set()

    def _append(self, text: str) -> None:
        self.chat.configure(state=tk.NORMAL)
        self.chat.insert(tk.END, text)
        self.chat.see(tk.END)
        self.chat.configure(state=tk.DISABLED)

    def _set_busy(self, busy: bool, status: str = "") -> None:
        self._busy = busy
        self.btn_send.configure(state=("disabled" if busy else "normal"))
        self.entry.configure(state=("disabled" if busy else "normal"))
        self.status_var.set(status or ("Ocupado" if busy else "Pronto"))

    def on_clear(self) -> None:
        self.chat.configure(state=tk.NORMAL)
        self.chat.delete("1.0", tk.END)
        self.chat.configure(state=tk.DISABLED)
        self._append("(limpo)\n")

    def on_send(self) -> None:
        if self._busy:
            return

        text = (self.entry_var.get() or "").strip()
        if not text:
            return
        self.entry_var.set("")

        decision = decide_route(text)
        self._append(f"\n[Você] {text}\n")

        if decision.kind == "abrir":
            self._handle_open(decision.payload)
            return

        if decision.kind == "buscar":
            q = decision.payload.strip() or text
            self._run_async(self._do_search, q)
            return

        self._run_async(self._do_chat, decision.payload)

    def _handle_open(self, num_str: str) -> None:
        try:
            idx = int(num_str) - 1
        except Exception:
            self._append("[IA] Uso: /abrir 1\n")
            return

        if idx < 0 or idx >= len(self._last_hits):
            self._append("[IA] Não achei esse número na última busca.\n")
            return

        p = Path(self._last_hits[idx].path)
        if not p.exists():
            self._append("[IA] O arquivo/pasta não existe mais.\n")
            return

        try:
            os.startfile(str(p))
            self._append(f"[IA] Abrindo: {p}\n")
        except Exception as e:
            self._append(f"[IA] Falhou ao abrir: {e}\n")

    def on_pick_image(self) -> None:
        if self._busy:
            return

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
        self._append(f"\n[Você] (imagem) {img}\n")
        self._run_async(self._do_classify, img)

    def on_pick_video(self) -> None:
        if self._busy:
            return

        p = filedialog.askopenfilename(
            title="Escolher vídeo",
            filetypes=[
                ("Vídeos", "*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v"),
                ("Todos", "*.*"),
            ],
        )
        if not p:
            return

        vid = Path(p)
        self._append(f"\n[Você] (vídeo) {vid}\n")
        self._run_async(self._do_classify_video, vid)

    def _run_async(self, fn, *args) -> None:
        def runner() -> None:
            self.after(0, lambda: self._set_busy(True, "Processando..."))
            try:
                fn(*args)
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=runner, daemon=True).start()

    def _do_chat(self, text: str) -> None:
        use_ollama = bool(self.use_ollama_var.get())
        model = (self.model_var.get() or "").strip() or None
        r = self.conversa.reply(text, use_ollama=use_ollama, model=model)
        if not r.ok:
            self.after(0, lambda: self._append(f"[IA] Erro (conversa): {r.error}\n"))
            return

        out = str((r.data or {}).get("text") or "")
        engine = str((r.data or {}).get("engine") or "")
        dbg = str((r.data or {}).get("debug") or "")

        extra = f" ({engine})" if engine else ""
        if dbg:
            extra += f" [{dbg}]"

        self.after(0, lambda: self._append(f"[IA]{extra} {out}\n"))

    def _do_search(self, query: str) -> None:
        r = self.buscar.search(query)
        if not r.ok:
            self.after(0, lambda: self._append(f"[IA] Erro (buscar): {r.error}\n"))
            return

        hits_raw = (r.data or {}).get("results") or []
        hits: list[SearchHit] = []
        for item in hits_raw:
            if not isinstance(item, dict):
                continue
            hits.append(
                SearchHit(
                    path=str(item.get("path") or ""),
                    score=float(item.get("score") or 0.0),
                    kind=str(item.get("kind") or ""),
                    reason=str(item.get("reason") or ""),
                )
            )

        self._last_hits = hits

        if not hits:
            self.after(0, lambda: self._append("[IA] Nenhum resultado.\n"))
            return

        def render() -> None:
            self._append("[IA] Resultados:\n")
            for i, h in enumerate(hits[:10], start=1):
                self._append(f"  {i}. {h.kind} | {h.path}\n")
            self._append("Use /abrir 1 para abrir um item.\n")

        self.after(0, render)

    def _do_classify(self, image_path: Path) -> None:
        if not image_path.exists():
            self.after(0, lambda: self._append("[IA] A imagem não existe.\n"))
            return

        r = self.imagem.classify(image_path)
        if not r.ok:
            self.after(0, lambda: self._append(f"[IA] Erro (imagem): {r.error}\n"))
            return

        known = bool((r.data or {}).get("known"))
        reason = str((r.data or {}).get("reason") or "")
        topk = (r.data or {}).get("topk") or []

        def render() -> None:
            self._append(f"[IA] Imagem: {'conhecida' if known else 'desconhecida'} ({reason})\n")
            if isinstance(topk, list):
                for p in topk[:5]:
                    if not isinstance(p, dict):
                        continue
                    label = p.get("label")
                    conf = p.get("confidence")
                    sim = p.get("similarity")
                    self._append(f"  - {label} | conf={conf:.3f} | sim={sim:.3f}\n")

        self.after(0, render)

    def _parse_float_opt(self, s: str) -> float | None:
        t = (s or "").strip()
        if not t:
            return None
        return float(t.replace(",", "."))

    def _do_classify_video(self, video_path: Path) -> None:
        if not video_path.exists():
            self.after(0, lambda: self._append("[IA] O vídeo não existe.\n"))
            return

        mode = (self.video_mode_var.get() or "appearance").strip() or "appearance"

        try:
            start_s = self._parse_float_opt(self.video_start_var.get())
            end_s = self._parse_float_opt(self.video_end_var.get())
        except Exception:
            self.after(0, lambda: self._append("[IA] Início/Fim inválidos. Use segundos (ex: 12.5).\n"))
            return

        if (start_s is None) != (end_s is None):
            self.after(0, lambda: self._append("[IA] Para trecho, preencha Início e Fim.\n"))
            return

        r = self.video.classify(str(video_path), mode=mode, start_s=start_s, end_s=end_s)
        if not r.ok:
            self.after(0, lambda: self._append(f"[IA] Erro (vídeo): {r.error}\n"))
            return

        known = bool((r.data or {}).get("known"))
        reason = str((r.data or {}).get("reason") or "")
        topk = (r.data or {}).get("topk") or []
        model_path = str((r.data or {}).get("model_path") or "")

        def render() -> None:
            seg = (r.data or {}).get("segment") or {}
            ss = seg.get("start_s")
            es = seg.get("end_s")
            if ss is not None and es is not None:
                seg_txt = f" trecho={ss:.2f}-{es:.2f}s"
            else:
                seg_txt = ""

            self._append(f"[IA] Vídeo: {'conhecido' if known else 'desconhecido'} ({reason}) | modo={mode}{seg_txt}\n")
            if model_path:
                self._append(f"[IA] Modelo: {model_path}\n")
            if isinstance(topk, list):
                for p in topk[:5]:
                    if not isinstance(p, dict):
                        continue
                    label = p.get("label")
                    conf = float(p.get("confidence") or 0.0)
                    sim = float(p.get("similarity") or 0.0)
                    self._append(f"  - {label} | conf={conf:.3f} | sim={sim:.3f}\n")

        self.after(0, render)
