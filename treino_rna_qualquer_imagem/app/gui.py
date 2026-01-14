from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import ttk
from typing import Optional

import numpy as np
from PIL import Image, ImageTk

from core.classifier import PrototypeClassifier
from core.config import AppConfig, dataset_db_path, thresholds_path
from core.dataset import (
    add_image,
    assign_cluster_label,
    connect,
    ensure_cluster,
    init_db,
    list_images_by_cluster,
    list_labels,
    list_unlabeled_clusters,
    name_cluster,
    set_cluster,
    set_label,
)
from core.embedding import build_extractor
from core.embedding_cache import get_or_compute_embedding, load_embedding
from core.image_sources import resolve_image_reference_to_file
from core.models import ClusterSummary, ImageRecord, PredictResult
from core.thresholds import Thresholds, load_thresholds
from core.trainer import Trainer
from core.unknown_clusters import UnknownClusterer


@dataclass(frozen=True)
class UiMsg:
    kind: str
    text: str = ""
    image_id: Optional[int] = None


class RnaImageApp(tk.Tk):
    """Tkinter GUI for open-world incremental image learning."""

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

        self._ui_queue: queue.Queue[UiMsg] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._cancel = threading.Event()

        self._conn = connect(dataset_db_path(config))
        init_db(self._conn)

        self._extractor = build_extractor(config.backbone, config.image_size)
        self._classifier = PrototypeClassifier()
        self._trainer = Trainer(config, self._classifier)
        self._trainer.try_load()

        self._thresholds = load_thresholds(
            thresholds_path(config),
            Thresholds(min_top1_confidence=config.min_top1_confidence, min_top1_similarity=config.min_top1_similarity),
        )

        self._clusterer = UnknownClusterer(threshold=float(config.unknown_cluster_similarity))

        self._current_image: Optional[ImageRecord] = None
        self._current_embedding: Optional[np.ndarray] = None
        self._current_pred: Optional[PredictResult] = None

        self._build_ui()
        self.after(60, self._poll_queue)

        info = self._extractor.info()
        self._log(f"Embeddings backend: {info.name} | pretrained={info.pretrained} | {info.note}")

        self._refresh_clusters()
        self._refresh_labels()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        self.btn_add = ttk.Button(top, text="Adicionar imagens", command=self.on_add_images)
        self.btn_add.grid(row=0, column=0, padx=(0, 8))

        self.btn_add_url = ttk.Button(top, text="Adicionar por URL/endereço", command=self.on_add_image_url)
        self.btn_add_url.grid(row=0, column=1, padx=(0, 8))

        self.btn_train = ttk.Button(top, text="Treinar agora", command=self.on_train)
        self.btn_train.grid(row=0, column=2, padx=(0, 8))

        self.btn_cancel = ttk.Button(top, text="Cancelar", command=self.on_cancel)
        self.btn_cancel.grid(row=0, column=3)

        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(top, textvariable=self.status_var).grid(row=0, column=4, padx=(12, 0), sticky="w")

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.tabs = ttk.Notebook(left)
        self.tabs.grid(row=0, column=0, sticky="nsew")

        self._tab_predict = ttk.Frame(self.tabs, padding=8)
        self._tab_clusters = ttk.Frame(self.tabs, padding=8)
        self._tab_metrics = ttk.Frame(self.tabs, padding=8)

        self.tabs.add(self._tab_predict, text="Predição")
        self.tabs.add(self._tab_clusters, text="Clusters")
        self.tabs.add(self._tab_metrics, text="Métricas")

        self._build_predict_tab()
        self._build_clusters_tab()
        self._build_metrics_tab()

        body.add(left, weight=2)

        logs = ttk.Labelframe(body, text="Logs ao vivo", padding=8)
        logs.columnconfigure(0, weight=1)
        logs.rowconfigure(0, weight=1)
        self.log_text = tk.Text(logs, wrap="word", height=10)
        self.log_text.configure(state=tk.DISABLED)
        scroll = ttk.Scrollbar(logs, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        body.add(logs, weight=1)

    def _build_predict_tab(self) -> None:
        frame = self._tab_predict
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        ttk.Label(frame, text="Preview").grid(row=0, column=0, sticky="w")
        self.preview = ttk.Label(frame)
        self.preview.grid(row=1, column=0, rowspan=3, sticky="nw", padx=(0, 12))

        ttk.Label(frame, text="Top-5 palpites").grid(row=0, column=1, sticky="w")
        self.pred_list = tk.Listbox(frame, height=6)
        self.pred_list.grid(row=1, column=1, sticky="ew")

        self.unknown_frame = ttk.Labelframe(frame, text="Se for DESCONHECIDO", padding=8)
        self.unknown_frame.grid(row=2, column=1, sticky="ew", pady=(8, 0))

        self.unknown_frame.columnconfigure(1, weight=1)

        ttk.Button(self.unknown_frame, text="Criar nova classe", command=self.on_create_new_class).grid(
            row=0, column=0, padx=(0, 8)
        )

        ttk.Button(self.unknown_frame, text="Adicionar a classe existente", command=self.on_add_to_existing).grid(
            row=0, column=1, padx=(0, 8)
        )

        ttk.Button(self.unknown_frame, text="Enviar para cluster provisório", command=self.on_send_to_cluster).grid(
            row=0, column=2
        )

        ttk.Label(frame, text="Detalhes").grid(row=3, column=1, sticky="w", pady=(10, 0))
        self.details = tk.Text(frame, height=10, wrap="word")
        self.details.grid(row=4, column=0, columnspan=2, sticky="nsew")

    def _build_clusters_tab(self) -> None:
        frame = self._tab_clusters
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(frame, text="Clusters de desconhecidos").grid(row=0, column=0, sticky="w")
        self.cluster_list = tk.Listbox(frame, height=12)
        self.cluster_list.grid(row=1, column=0, sticky="ns")
        self.cluster_list.bind("<<ListboxSelect>>", lambda _e: self.on_select_cluster())

        right = ttk.Frame(frame)
        right.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self.cluster_title = ttk.Label(right, text="Selecione um cluster")
        self.cluster_title.grid(row=0, column=0, sticky="w")

        self.cluster_images = tk.Listbox(right)
        self.cluster_images.grid(row=1, column=0, sticky="nsew")

        btns = ttk.Frame(right)
        btns.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(btns, text="Nomear cluster", command=self.on_name_cluster).pack(side=tk.LEFT)
        ttk.Button(btns, text="Rotular cluster (aprender)", command=self.on_label_cluster).pack(side=tk.LEFT, padx=(8, 0))

    def _build_metrics_tab(self) -> None:
        frame = self._tab_metrics
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.metrics_text = tk.Text(frame, wrap="word")
        self.metrics_text.grid(row=0, column=0, sticky="nsew")
        self.metrics_text.insert(tk.END, "Métricas básicas serão mostradas após treinos com dados rotulados.\n")

    # ---------------- Thread helpers ----------------

    def _set_busy(self, busy: bool, status: str) -> None:
        self.status_var.set(status)
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_add.configure(state=state)
        self.btn_train.configure(state=state)
        self.btn_cancel.configure(state=tk.NORMAL if busy else tk.DISABLED)

    def _log(self, msg: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _post_log(self, msg: str) -> None:
        self._ui_queue.put(UiMsg(kind="log", text=msg))

    def _poll_queue(self) -> None:
        try:
            while True:
                m = self._ui_queue.get_nowait()
                if m.kind == "log":
                    self._log(m.text)
                elif m.kind == "done":
                    self._set_busy(False, "Pronto")
                elif m.kind == "error":
                    self._set_busy(False, "Erro")
                    messagebox.showerror("RNA", m.text)
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _run_worker(self, name: str, fn) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("RNA", "Já existe uma operação em andamento. Use Cancelar.")
            return

        self._cancel = threading.Event()
        cancel = self._cancel

        def runner() -> None:
            try:
                self._post_log(f"== {name} ==")
                fn(cancel)
                self._ui_queue.put(UiMsg(kind="done"))
            except Exception as e:
                self._ui_queue.put(UiMsg(kind="error", text=f"{name} falhou: {e}"))

        self._worker = threading.Thread(target=runner, daemon=True)
        self._set_busy(True, f"{name}...")
        self._worker.start()

    # ---------------- Actions ----------------

    def on_cancel(self) -> None:
        self._cancel.set()
        self._post_log("Cancelamento solicitado.")

    def on_add_images(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Selecione imagens",
            filetypes=[("Imagens", "*.png;*.jpg;*.jpeg;*.bmp;*.webp"), ("Todos", "*.*")],
        )
        if not paths:
            return

        def task(cancel: threading.Event) -> None:
            conn = connect(dataset_db_path(self.config))
            init_db(conn)
            try:
                for p in paths:
                    if cancel.is_set():
                        return
                    path = Path(p)
                    self._post_log(f"Processando: {path.name}")

                    key, emb = get_or_compute_embedding(self.config, self._extractor, path)
                    rec = add_image(conn, path=path, embedding_key=key)

                    pred = self._classifier.predict_open_world(
                        emb,
                        min_top1_confidence=self._thresholds.min_top1_confidence,
                        min_top1_similarity=self._thresholds.min_top1_similarity,
                        k=5,
                    )

                    if pred.known:
                        self._post_log(f"Conhecido: {pred.topk[0].label} (conf={pred.topk[0].confidence:.2f})")
                    else:
                        self._post_log(f"DESCONHECIDO ({pred.reason}). Use botões para rotular/cluster.")

                    # Keep last item as current in UI (lightweight)
                    self._current_image = rec
                    self._current_embedding = emb
                    self._current_pred = pred
                    self._ui_queue.put(UiMsg(kind="log", text=f"Atual: image_id={rec.image_id}"))

                    self.after(0, self._render_current)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        self._run_worker("Adicionar imagens", task)

    def on_add_image_url(self) -> None:
        url = multiline_prompt(
            self,
            title="Adicionar por URL/endereço",
            prompt=(
                "Cole uma URL (http/https), uma data URL (data:image/...;base64,...)\n"
                "ou um endereço/caminho local (ex: C:\\pasta\\foto.jpg).\n"
                "Dica: para strings base64 grandes, cole aqui (não no terminal)."
            ),
        )
        if not url:
            return

        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return

            self._post_log("Resolvendo URL/endereço...")
            path = resolve_image_reference_to_file(self.config, url)
            self._post_log(f"Imagem selecionada: {path.name}")

            if cancel.is_set():
                return

            key, emb = get_or_compute_embedding(self.config, self._extractor, path)
            conn = connect(dataset_db_path(self.config))
            init_db(conn)
            try:
                rec = add_image(conn, path=path, embedding_key=key)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            pred = self._classifier.predict_open_world(
                emb,
                min_top1_confidence=self._thresholds.min_top1_confidence,
                min_top1_similarity=self._thresholds.min_top1_similarity,
                k=5,
            )

            if pred.known:
                self._post_log(f"Conhecido: {pred.topk[0].label} (conf={pred.topk[0].confidence:.2f})")
            else:
                self._post_log(f"DESCONHECIDO ({pred.reason}). Use botões para rotular/cluster.")

            self._current_image = rec
            self._current_embedding = emb
            self._current_pred = pred
            self._ui_queue.put(UiMsg(kind="log", text=f"Atual: image_id={rec.image_id}"))
            self.after(0, self._render_current)

        self._run_worker("Adicionar por URL/endereço", task)

    def on_train(self) -> None:
        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return

            def loader(key: str):
                return load_embedding(self.config, key)

            conn = connect(dataset_db_path(self.config))
            init_db(conn)
            try:
                report = self._trainer.train_from_db(conn, embedding_loader=loader, log=self._post_log)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            self._post_log(f"Treino: classes={report.n_classes} | rotuladas={report.n_labeled}")
            self.after(0, self._refresh_labels)

        self._run_worker("Treinar", task)

    def on_create_new_class(self) -> None:
        if not self._ensure_current_unknown():
            return

        name = simple_prompt(self, "Nova classe", "Nome da classe:")
        if not name:
            return
        set_label(self._conn, self._current_image.image_id, name)
        self._post_log(f"Rotulado como nova classe: {name}")
        self._refresh_labels()

    def on_add_to_existing(self) -> None:
        if not self._ensure_current_unknown():
            return

        labels = list_labels(self._conn)
        if not labels:
            messagebox.showinfo("RNA", "Ainda não existem classes. Use 'Criar nova classe'.")
            return

        choice = ChoiceDialog(self, "Selecionar classe", "Escolha uma classe:", labels).run()
        if not choice:
            return
        set_label(self._conn, self._current_image.image_id, choice)
        self._post_log(f"Rotulado como: {choice}")
        self._refresh_labels()

    def on_send_to_cluster(self) -> None:
        if self._current_image is None or self._current_embedding is None:
            messagebox.showinfo("RNA", "Adicione uma imagem primeiro.")
            return

        cid = self._clusterer.assign(self._current_embedding)
        ensure_cluster(self._conn, cid)
        set_cluster(self._conn, self._current_image.image_id, cid)
        self._post_log(f"Enviado para cluster provisório: {cid}")
        self._refresh_clusters()

    def on_select_cluster(self) -> None:
        sel = self.cluster_list.curselection()
        if not sel:
            return
        text = self.cluster_list.get(sel[0])
        cluster_id = text.split(" ", 1)[0]

        imgs = list_images_by_cluster(self._conn, cluster_id)
        self.cluster_title.configure(text=f"{cluster_id} | {len(imgs)} imagem(ns)")
        self.cluster_images.delete(0, tk.END)
        for rec in imgs[:200]:
            self.cluster_images.insert(tk.END, f"{rec.image_id}: {rec.path.name}")

    def on_name_cluster(self) -> None:
        sel = self.cluster_list.curselection()
        if not sel:
            return
        text = self.cluster_list.get(sel[0])
        cluster_id = text.split(" ", 1)[0]

        name = simple_prompt(self, "Nomear cluster", f"Nome para {cluster_id}:")
        if not name:
            return
        name_cluster(self._conn, cluster_id, name)
        self._post_log(f"Cluster {cluster_id} nomeado: {name}")
        self._refresh_clusters()

    def on_label_cluster(self) -> None:
        sel = self.cluster_list.curselection()
        if not sel:
            return
        text = self.cluster_list.get(sel[0])
        cluster_id = text.split(" ", 1)[0]

        label = simple_prompt(self, "Rotular cluster", f"Rótulo definitivo para {cluster_id}:")
        if not label:
            return

        n = assign_cluster_label(self._conn, cluster_id, label)
        self._post_log(f"Cluster {cluster_id} -> label '{label}' ({n} imagem(ns))")
        self._refresh_clusters()
        self._refresh_labels()

    # ---------------- UI rendering ----------------

    def _ensure_current_unknown(self) -> bool:
        if self._current_image is None or self._current_embedding is None or self._current_pred is None:
            messagebox.showinfo("RNA", "Adicione uma imagem primeiro.")
            return False
        if self._current_pred.known:
            messagebox.showinfo("RNA", "Esta imagem já foi considerada conhecida; você ainda pode rotular manualmente.")
        return True

    def _render_current(self) -> None:
        if self._current_image is None or self._current_pred is None:
            return

        # Preview
        try:
            img = Image.open(self._current_image.path).convert("RGB")
            img.thumbnail((380, 380))
            self._tk_img = ImageTk.PhotoImage(img)
            self.preview.configure(image=self._tk_img)
        except Exception:
            self.preview.configure(image="")

        # Predictions
        self.pred_list.delete(0, tk.END)
        for p in self._current_pred.topk[:5]:
            self.pred_list.insert(tk.END, f"{p.label} | conf={p.confidence:.2f} | sim={p.similarity:.2f}")

        # Details
        self.details.delete("1.0", tk.END)
        self.details.insert(
            tk.END,
            f"image_id: {self._current_image.image_id}\n"
            f"arquivo: {self._current_image.path}\n"
            f"resultado: {'CONHECIDO' if self._current_pred.known else 'DESCONHECIDO'}\n"
            f"motivo: {self._current_pred.reason}\n",
        )

    def _refresh_clusters(self) -> None:
        clusters = list_unlabeled_clusters(self._conn)
        self.cluster_list.delete(0, tk.END)
        for c in clusters:
            name = f" ({c.name})" if c.name else ""
            self.cluster_list.insert(tk.END, f"{c.cluster_id} | {c.count} img{name}")

    def _refresh_labels(self) -> None:
        labels = list_labels(self._conn)
        self.metrics_text.delete("1.0", tk.END)
        self.metrics_text.insert(tk.END, f"Classes aprendidas: {len(labels)}\n")
        for l in labels[:200]:
            self.metrics_text.insert(tk.END, f"- {l}\n")


def simple_prompt(parent: tk.Tk, title: str, prompt: str) -> Optional[str]:
    d = tk.Toplevel(parent)
    d.title(title)
    d.resizable(False, False)
    d.grab_set()

    ttk.Label(d, text=prompt).grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")
    entry = ttk.Entry(d, width=40)
    entry.grid(row=1, column=0, padx=10, pady=(0, 10))
    entry.focus_set()

    val: dict[str, Optional[str]] = {"v": None}

    def ok() -> None:
        v = entry.get().strip()
        val["v"] = v or None
        d.destroy()

    def cancel() -> None:
        val["v"] = None
        d.destroy()

    btns = ttk.Frame(d)
    btns.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="e")
    ttk.Button(btns, text="OK", command=ok).pack(side=tk.LEFT)
    ttk.Button(btns, text="Cancelar", command=cancel).pack(side=tk.LEFT, padx=(8, 0))

    d.bind("<Return>", lambda _e: ok())
    d.bind("<Escape>", lambda _e: cancel())

    parent.wait_window(d)
    return val["v"]


def multiline_prompt(parent: tk.Tk, title: str, prompt: str) -> Optional[str]:
    d = tk.Toplevel(parent)
    d.title(title)
    d.resizable(True, True)
    d.grab_set()

    ttk.Label(d, text=prompt).grid(row=0, column=0, padx=10, pady=(10, 6), sticky="w")
    txt = tk.Text(d, height=8, width=90, wrap="word")
    txt.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
    d.columnconfigure(0, weight=1)
    d.rowconfigure(1, weight=1)

    # Try to prefill from clipboard (best-effort)
    try:
        clip = parent.clipboard_get()
        if clip and isinstance(clip, str):
            txt.insert("1.0", clip)
            txt.mark_set(tk.INSERT, "1.0")
    except Exception:
        pass

    val: dict[str, Optional[str]] = {"v": None}

    def ok() -> None:
        v = txt.get("1.0", tk.END).strip()
        val["v"] = v or None
        d.destroy()

    def cancel() -> None:
        val["v"] = None
        d.destroy()

    btns = ttk.Frame(d)
    btns.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="e")
    ttk.Button(btns, text="OK", command=ok).pack(side=tk.LEFT)
    ttk.Button(btns, text="Cancelar", command=cancel).pack(side=tk.LEFT, padx=(8, 0))

    d.bind("<Escape>", lambda _e: cancel())
    parent.wait_window(d)
    return val["v"]


class ChoiceDialog:
    def __init__(self, parent: tk.Tk, title: str, prompt: str, options: list[str]):
        self.parent = parent
        self.title = title
        self.prompt = prompt
        self.options = options
        self.value: Optional[str] = None

    def run(self) -> Optional[str]:
        d = tk.Toplevel(self.parent)
        d.title(self.title)
        d.resizable(False, False)
        d.grab_set()

        ttk.Label(d, text=self.prompt).grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")
        lb = tk.Listbox(d, height=min(12, max(3, len(self.options))))
        lb.grid(row=1, column=0, padx=10, pady=(0, 10))
        for opt in self.options:
            lb.insert(tk.END, opt)

        def ok() -> None:
            sel = lb.curselection()
            if not sel:
                return
            self.value = str(lb.get(sel[0]))
            d.destroy()

        def cancel() -> None:
            self.value = None
            d.destroy()

        btns = ttk.Frame(d)
        btns.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="e")
        ttk.Button(btns, text="OK", command=ok).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancelar", command=cancel).pack(side=tk.LEFT, padx=(8, 0))

        d.bind("<Return>", lambda _e: ok())
        d.bind("<Escape>", lambda _e: cancel())

        self.parent.wait_window(d)
        return self.value
