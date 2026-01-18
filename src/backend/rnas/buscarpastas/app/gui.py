from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk
from typing import Callable, Optional

from core.config import AppConfig
from core.index_db import connect, init_db, item_count
from core.indexer import index_all
from core.models import ParsedCommand, SearchResult
from core.opener import open_result
from core.parser import parse_command
from core.quick_search import QuickSearchParams, quick_search
from core.limited_search import LimitedSearchConfig, limited_search
from core.search import SearchParams, search
from core.storage import PreferenceStore


@dataclass(frozen=True)
class UiMsg:
    kind: str
    text: str = ""
    results: Optional[list[SearchResult]] = None
    command: Optional[ParsedCommand] = None


class RnaApp(tk.Tk):
    """Tkinter GUI for RNA.

    Threading model:
    - GUI thread runs Tk mainloop.
    - Worker thread runs indexing/search.
    - A Queue transports log + results + status messages.
    - A threading.Event provides cancellation.
    """

    def __init__(self, config: AppConfig, store: PreferenceStore, db_path: Path):
        super().__init__()
        self.config = config
        self.store = store
        self.db_path = db_path

        self._ui_queue: queue.Queue[UiMsg] = queue.Queue()
        self._cancel_event: Optional[threading.Event] = None
        self._worker: Optional[threading.Thread] = None

        self._last_command: Optional[ParsedCommand] = None
        self._pending_search_after_index: Optional[ParsedCommand] = None
        self._last_results: list[SearchResult] = []

        self._build_widgets()
        self._set_busy(False)

        # Start polling UI queue.
        self.after(50, self._poll_queue)

        # IMPORTANT: No automatic full indexing on startup.
        self._post_log("Pronto. Dica: use 'Executar' para busca sob demanda; 'Indexar/Reindexar' faz indexação completa.")

    # ------------------------- UI layout -------------------------

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1)

        self.entry = ttk.Entry(top)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.insert(0, "abrir chrome")
        self.entry.bind("<Return>", lambda _e: self.on_execute())

        self.btn_execute = ttk.Button(top, text="Executar", command=self.on_execute)
        self.btn_execute.grid(row=0, column=1, padx=(0, 6))

        self.btn_index = ttk.Button(top, text="Indexar/Reindexar", command=self.on_reindex)
        self.btn_index.grid(row=0, column=2, padx=(0, 6))

        self.btn_cancel = ttk.Button(top, text="Cancelar busca", command=self.on_cancel)
        self.btn_cancel.grid(row=0, column=3)

        status = ttk.Frame(self, padding=(10, 0, 10, 10))
        status.grid(row=1, column=0, sticky="ew")
        status.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Pronto")
        self.status_label = ttk.Label(status, textvariable=self.status_var)
        self.status_label.grid(row=0, column=0, sticky="w")

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Left: results
        results_frame = ttk.Labelframe(body, text="Resultados", padding=8)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        columns = ("name", "source", "score", "path")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=10)
        self.tree.heading("name", text="Nome")
        self.tree.heading("source", text="Fonte")
        self.tree.heading("score", text="Score")
        self.tree.heading("path", text="Caminho")

        self.tree.column("name", width=240, anchor=tk.W)
        self.tree.column("source", width=140, anchor=tk.W)
        self.tree.column("score", width=70, anchor=tk.E)
        self.tree.column("path", width=420, anchor=tk.W)

        yscroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<Double-1>", lambda _e: self.on_open_selected())

        btns = ttk.Frame(results_frame)
        btns.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.btn_open = ttk.Button(btns, text="Abrir selecionado", command=self.on_open_selected)
        self.btn_open.pack(side=tk.LEFT)

        self.btn_clear = ttk.Button(btns, text="Limpar lista", command=self._clear_results)
        self.btn_clear.pack(side=tk.LEFT, padx=(8, 0))

        body.add(results_frame, weight=1)

        # Right: logs
        logs_frame = ttk.Labelframe(body, text="Logs ao vivo", padding=8)
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)

        self.logs = tk.Text(logs_frame, wrap="word", height=10)
        self.logs.configure(state=tk.DISABLED)
        log_scroll = ttk.Scrollbar(logs_frame, orient=tk.VERTICAL, command=self.logs.yview)
        self.logs.configure(yscrollcommand=log_scroll.set)

        self.logs.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

        body.add(logs_frame, weight=1)

    # ------------------------- Helpers -------------------------

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_execute.configure(state=state)
        self.btn_index.configure(state=state)
        self.btn_open.configure(state=state)
        self.btn_clear.configure(state=state)
        self.entry.configure(state=state)
        self.btn_cancel.configure(state=tk.NORMAL if busy else tk.DISABLED)

    def _log(self, msg: str) -> None:
        self.logs.configure(state=tk.NORMAL)
        self.logs.insert(tk.END, msg + "\n")
        self.logs.see(tk.END)
        self.logs.configure(state=tk.DISABLED)

    def _post_log(self, msg: str) -> None:
        self._ui_queue.put(UiMsg(kind="log", text=msg))

    def _post_status(self, msg: str) -> None:
        self._ui_queue.put(UiMsg(kind="status", text=msg))

    def _poll_queue(self) -> None:
        try:
            while True:
                m = self._ui_queue.get_nowait()
                if m.kind == "log":
                    self._log(m.text)
                elif m.kind == "status":
                    self.status_var.set(m.text)
                elif m.kind == "results":
                    self._render_results(m.results or [])
                elif m.kind == "done":
                    self._set_busy(False)
                    self.status_var.set(m.text or "Pronto")
                    self._worker = None
                    self._cancel_event = None

                    # If we queued a search after indexing, run it now.
                    if self._pending_search_after_index is not None:
                        cmd = self._pending_search_after_index
                        self._pending_search_after_index = None
                        self._start_search(cmd)

                elif m.kind == "ask_index":
                    # Ask user permission to run full indexing.
                    cmd = m.command
                    if cmd is None:
                        continue
                    ok = messagebox.askyesno(
                        "RNA",
                        "Não encontrei nas camadas rápidas/limitadas.\n\nDeseja fazer indexação completa agora?",
                    )
                    if ok:
                        self._pending_search_after_index = cmd
                        self.on_reindex()
                    else:
                        self.status_var.set("Pronto")
                        self._post_log("Usuário recusou indexação completa.")

                elif m.kind == "error":
                    self._set_busy(False)
                    self._worker = None
                    self._cancel_event = None
                    self.status_var.set("Erro")
                    messagebox.showerror("RNA", m.text)
        except queue.Empty:
            pass

        self.after(80, self._poll_queue)

    def _clear_results(self) -> None:
        self._last_results = []
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _render_results(self, results: list[SearchResult]) -> None:
        self._clear_results()
        self._last_results = list(results)

        if not results:
            self._post_log("(sem resultados)")
            return

        # Auto-open if exactly 1 result.
        if len(results) == 1 and self._last_command is not None:
            self._post_log("1 resultado: abrindo automaticamente.")
            self._open_and_learn(results[0])
            return

        for idx, r in enumerate(results):
            self.tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(r.display_name, r.source, f"{r.score:.1f}", str(r.path)),
            )

        self._post_log("Selecione um resultado e dê duplo clique ou use 'Abrir selecionado'.")

    def _open_and_learn(self, result: SearchResult) -> None:
        if self._last_command is None:
            raise RuntimeError("Sem comando atual.")

        try:
            open_result(result, action=self._last_command.action, config=self.config)
            self.store.record_open(str(result.path))
            # Training: save preference for this query.
            self.store.set_preference_for_query(self._last_command.query_norm, str(result.path))
            self._post_log(f"Aberto: {result.path}")
        except Exception as e:
            messagebox.showerror("RNA", f"Falha ao abrir: {e}")

    def _run_worker(self, name: str, fn: Callable[[threading.Event], None]) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("RNA", "Já existe uma operação em andamento. Use Cancelar.")
            return

        self._cancel_event = threading.Event()
        cancel = self._cancel_event

        def runner() -> None:
            self._ui_queue.put(UiMsg(kind="status", text=f"{name}..."))
            t0 = time.perf_counter()
            try:
                fn(cancel)
                elapsed = time.perf_counter() - t0
                self._ui_queue.put(UiMsg(kind="done", text=f"{name} OK ({elapsed:.1f}s)"))
            except Exception as e:
                self._ui_queue.put(UiMsg(kind="error", text=f"{name} falhou: {e}"))

        self._worker = threading.Thread(target=runner, daemon=True)
        self._set_busy(True)
        self._worker.start()

    # ------------------------- Button handlers -------------------------

    def on_cancel(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self._post_log("Cancelamento solicitado.")

    def on_reindex(self) -> None:
        self._clear_results()

        def task(cancel: threading.Event) -> None:
            conn = connect(self.db_path)
            try:
                self._post_log("Preparando banco do índice...")
                init_db(conn)
                self._post_log("Indexando (pode demorar; logs mostram diretórios visitados)...")
                index_all(conn, self.config, cancel_event=cancel, log=self._post_log)
            finally:
                conn.close()

        self._run_worker("Indexação", task)

    def _start_search(self, cmd: ParsedCommand) -> None:
        self._clear_results()
        self._last_command = cmd

        def task(cancel: threading.Event) -> None:
            conn = connect(self.db_path)
            try:
                init_db(conn)
                params = SearchParams(query_text=cmd.query_text, query_norm=cmd.query_norm, action=cmd.action)
                results = search(conn, self.store, self.config, params, cancel_event=cancel, log=self._post_log)
                self._ui_queue.put(UiMsg(kind="results", results=results))
            finally:
                conn.close()

        self._run_worker("Busca", task)

    def _start_layered_search(self, cmd: ParsedCommand) -> None:
        """Run Camada 1 (quick) then Camada 2 (limited), then optionally Camada 3 (index)."""

        self._clear_results()
        self._last_command = cmd

        def task(cancel: threading.Event) -> None:
            # Camada 1
            r1 = quick_search(
                store=self.store,
                config=self.config,
                params=QuickSearchParams(query_text=cmd.query_text, query_norm=cmd.query_norm, action=cmd.action),
                log=self._post_log,
            )
            if cancel.is_set():
                return
            if r1:
                self._ui_queue.put(UiMsg(kind="results", results=r1))
                return

            # Camada 2
            r2 = limited_search(
                config=self.config,
                query_text=cmd.query_text,
                query_norm=cmd.query_norm,
                cancel_event=cancel,
                log=self._post_log,
                limits=LimitedSearchConfig(
                    max_depth=self.config.limited_max_depth,
                    timeout_seconds=self.config.limited_timeout_seconds,
                    max_entries=self.config.limited_max_entries,
                ),
            )
            if cancel.is_set():
                return
            if r2:
                self._ui_queue.put(UiMsg(kind="results", results=r2))
                return

            # If nothing found, optionally use existing full index if present.
            self._post_log("Camada 3: (opcional) índice completo só por autorização.")

            # If there is already an index, we can try it without reindexing.
            conn = None
            try:
                conn = connect(self.db_path)
                init_db(conn)
                n = item_count(conn)
                if n > 0:
                    self._post_log("Camada 3: tentando índice existente (sem reindexar)...")
                    params = SearchParams(query_text=cmd.query_text, query_norm=cmd.query_norm, action=cmd.action)
                    r3 = search(conn, self.store, self.config, params, cancel_event=cancel, log=self._post_log)
                    if r3:
                        self._ui_queue.put(UiMsg(kind="results", results=r3))
                        return
                else:
                    self._post_log("Camada 3: índice ainda não existe.")
            except Exception as e:
                self._post_log(f"Camada 3: falha ao usar índice existente: {e}")
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

            self._ui_queue.put(UiMsg(kind="ask_index", command=cmd))

        self._run_worker("Busca", task)

    def on_execute(self) -> None:
        text = self.entry.get().strip()
        self._clear_results()

        try:
            cmd = parse_command(text)
        except Exception as e:
            messagebox.showwarning("RNA", str(e))
            return

        # New behavior: never auto-index. First try Camada 1/2 on demand.
        self._start_layered_search(cmd)

    def on_open_selected(self) -> None:
        if self._last_command is None:
            messagebox.showinfo("RNA", "Primeiro faça uma busca.")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("RNA", "Selecione um resultado.")
            return

        iid = selection[0]
        try:
            idx = int(iid)
        except ValueError:
            messagebox.showerror("RNA", "Seleção inválida.")
            return

        if idx < 0 or idx >= len(self._last_results):
            messagebox.showerror("RNA", "Seleção fora da lista.")
            return

        self._open_and_learn(self._last_results[idx])
