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

from rna_de_video.core.classifier import PrototypeClassifier
from rna_de_video.core.config import AppConfig, dataset_db_path, thresholds_path
from rna_de_video.core.dataset import (
    assign_cluster_label,
    connect,
    ensure_cluster,
    ensure_video,
    init_db,
    list_labels,
    list_unlabeled_clusters,
    list_videos_by_cluster,
    name_cluster,
    set_cluster,
    set_cluster_for_segment,
    set_embedding,
    set_label,
    set_label_for_segment,
)
from rna_de_video.core.embedding import build_extractor
from rna_de_video.core.embedding_cache import get_or_compute_video_embedding, load_embedding
from rna_de_video.core.models import ClusterSummary, PredictResult, VideoRecord
from rna_de_video.core.thresholds import Thresholds, load_thresholds
from rna_de_video.core.trainer import Trainer
from rna_de_video.core.unknown_clusters import UnknownClusterer
from rna_de_video.core.video_frames import probe_video, read_frames_rgb, sample_frame_indices
from rna_de_video.core.video_sources import list_videos_in_folder, resolve_video_reference_to_file
from rna_de_video.core.train_modes import build_default_registry


@dataclass(frozen=True)
class UiMsg:
    kind: str
    text: str = ""


class RnaVideoApp(tk.Tk):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

        self._ui_queue: queue.Queue[UiMsg] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._cancel = threading.Event()

        self._conn = connect(dataset_db_path(config))
        init_db(self._conn)

        self._registry = build_default_registry()
        modes = self._registry.list()
        self._mode_id = modes[0].mode_id if modes else "appearance"
        self._mode_display_names = [m.display_name for m in modes] or ["Aparência (frames)"]
        self._runtimes: dict[str, tuple[PrototypeClassifier, Trainer]] = {}

        self._extractor = build_extractor(config.backbone, config.frame_resize)

        # Initialize runtime for default mode
        self._get_runtime(self._mode_id)

        self._thresholds = load_thresholds(
            thresholds_path(config),
            Thresholds(min_top1_confidence=config.min_top1_confidence, min_top1_similarity=config.min_top1_similarity),
        )

        self._clusterer = UnknownClusterer(threshold=0.55)

        self._current_video: Optional[VideoRecord] = None
        self._current_embedding: Optional[np.ndarray] = None
        self._current_pred: Optional[PredictResult] = None
        self._current_seg_start_ms: int = -1
        self._current_seg_end_ms: int = -1
        self._current_mode_id: str = self._mode_id
        self._current_preview_imgtk: Optional[ImageTk.PhotoImage] = None

        self._build_ui()
        self.after(60, self._poll_queue)

        info = self._extractor.info()
        self._log(f"Embeddings backend: {info.name} | pretrained={info.pretrained} | {info.note}")
        self._log(f"Modo atual: {self._mode_id}")

        self._refresh_clusters()
        self._refresh_labels()

    def _parse_segment_ms(self) -> tuple[int, int]:
        """Returns (start_ms, end_ms) using -1 sentinel when not set."""

        def parse_s(v: str) -> float | None:
            t = (v or "").strip()
            if not t:
                return None
            return float(t.replace(",", "."))

        try:
            start_s = parse_s(getattr(self, "seg_start_var", tk.StringVar()).get())
            end_s = parse_s(getattr(self, "seg_end_var", tk.StringVar()).get())
        except Exception:
            raise ValueError("Início/Fim inválidos. Use segundos (ex: 12.5).")

        if start_s is None and end_s is None:
            return -1, -1

        if start_s is None:
            start_s = 0.0

        if end_s is None:
            raise ValueError("Se definir Início, defina também o Fim (em segundos).")

        if start_s < 0 or end_s <= 0 or end_s <= start_s:
            raise ValueError("Trecho inválido: Fim precisa ser maior que Início.")

        return int(start_s * 1000.0), int(end_s * 1000.0)

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")

        self.btn_add = ttk.Button(top, text="Adicionar vídeos", command=self.on_add_videos)
        self.btn_add.grid(row=0, column=0, padx=(0, 8))

        self.btn_add_folder = ttk.Button(top, text="Importar pasta", command=self.on_import_folder)
        self.btn_add_folder.grid(row=0, column=1, padx=(0, 8))

        self.btn_add_url = ttk.Button(top, text="Adicionar por URL", command=self.on_add_video_url)
        self.btn_add_url.grid(row=0, column=2, padx=(0, 8))

        ttk.Label(top, text="Modo:").grid(row=0, column=3, padx=(10, 4), sticky="w")
        self.mode_var = tk.StringVar(value=self._registry.get(self._mode_id).display_name)
        self.mode_combo = ttk.Combobox(
            top,
            textvariable=self.mode_var,
            values=self._mode_display_names,
            state="readonly",
            width=22,
        )
        self.mode_combo.grid(row=0, column=4, padx=(0, 8), sticky="w")
        self.mode_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_change_mode())

        ttk.Label(top, text="Início(s):").grid(row=0, column=5, padx=(10, 4), sticky="w")
        self.seg_start_var = tk.StringVar(value="")
        self.seg_start_entry = ttk.Entry(top, textvariable=self.seg_start_var, width=7)
        self.seg_start_entry.grid(row=0, column=6, padx=(0, 6), sticky="w")

        ttk.Label(top, text="Fim(s):").grid(row=0, column=7, padx=(0, 4), sticky="w")
        self.seg_end_var = tk.StringVar(value="")
        self.seg_end_entry = ttk.Entry(top, textvariable=self.seg_end_var, width=7)
        self.seg_end_entry.grid(row=0, column=8, padx=(0, 10), sticky="w")

        self.btn_train = ttk.Button(top, text="Treinar agora", command=self.on_train)
        self.btn_train.grid(row=0, column=9, padx=(0, 8))

        self.btn_cancel = ttk.Button(top, text="Cancelar", command=self.on_cancel)
        self.btn_cancel.grid(row=0, column=10)

        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(top, textvariable=self.status_var).grid(row=0, column=11, padx=(12, 0), sticky="w")

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.tabs = ttk.Notebook(left)
        self.tabs.grid(row=0, column=0, sticky="nsew")

        self._tab_predict = ttk.Frame(self.tabs, padding=8)
        self._tab_clusters = ttk.Frame(self.tabs, padding=8)

        self.tabs.add(self._tab_predict, text="Predição")
        self.tabs.add(self._tab_clusters, text="Clusters")

        self._build_predict_tab()
        self._build_clusters_tab()

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

        ttk.Label(frame, text="Preview (1 frame)").grid(row=0, column=0, sticky="w")
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
        self.btn_save_segment = ttk.Button(
            self.unknown_frame,
            text="Salvar trecho do vídeo atual",
            command=self.on_save_current_segment,
        )
        self.btn_save_segment.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))

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

        self.cluster_videos = tk.Listbox(right)
        self.cluster_videos.grid(row=1, column=0, sticky="nsew")

        btns = ttk.Frame(right)
        btns.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(btns, text="Nomear cluster", command=self.on_name_cluster).pack(side=tk.LEFT)
        ttk.Button(btns, text="Rotular cluster (aprender)", command=self.on_label_cluster).pack(side=tk.LEFT, padx=(8, 0))

    # ---------------- Thread helpers ----------------

    def _set_busy(self, busy: bool, status: str) -> None:
        self.status_var.set(status)
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_add.configure(state=state)
        self.btn_add_folder.configure(state=state)
        try:
            self.btn_add_url.configure(state=state)
        except Exception:
            pass
        self.btn_train.configure(state=state)
        try:
            self.mode_combo.configure(state="disabled" if busy else "readonly")
        except Exception:
            pass
        try:
            self.seg_start_entry.configure(state=tk.DISABLED if busy else tk.NORMAL)
            self.seg_end_entry.configure(state=tk.DISABLED if busy else tk.NORMAL)
        except Exception:
            pass
        self.btn_cancel.configure(state=tk.NORMAL if busy else tk.DISABLED)
        try:
            self.btn_save_segment.configure(state=state)
        except Exception:
            pass

    def _get_runtime(self, mode_id: str) -> tuple[PrototypeClassifier, Trainer]:
        if mode_id in self._runtimes:
            return self._runtimes[mode_id]

        clf = PrototypeClassifier()
        tr = Trainer(self.config, clf)
        tr.try_load(mode=mode_id)
        self._runtimes[mode_id] = (clf, tr)
        return clf, tr

    def on_change_mode(self) -> None:
        name = (self.mode_var.get() or "").strip()
        try:
            mode_id = self._registry.id_by_display(name)
        except Exception:
            return
        if mode_id == self._mode_id:
            return
        self._mode_id = mode_id
        self._get_runtime(mode_id)
        self._post_log(f"Modo alterado: {mode_id}")

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

    def on_add_videos(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Selecione vídeos",
            filetypes=[("Vídeos", "*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v"), ("Todos", "*.*")],
        )
        if not paths:
            return

        self._add_videos_worker([Path(p) for p in paths], title="Adicionar vídeos")

    def on_save_current_segment(self) -> None:
        if not self._current_video:
            messagebox.showinfo("RNA", "Nenhum vídeo atual. Adicione um vídeo primeiro.")
            return

        p = Path(self._current_video.path)
        if not p.exists():
            messagebox.showinfo("RNA", "Arquivo do vídeo atual não existe mais no disco.")
            return

        self._add_videos_worker([p], title="Salvar trecho atual")

    def on_import_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecione uma pasta")
        if not folder:
            return
        videos = list_videos_in_folder(Path(folder))
        if not videos:
            messagebox.showinfo("RNA", "Não encontrei vídeos nessa pasta.")
            return
        self._add_videos_worker(videos, title=f"Importar pasta ({len(videos)} vídeos)")

    def on_add_video_url(self) -> None:
        url_text = multiline_prompt(
            self,
            title="Adicionar vídeo por URL",
            prompt=(
                "Cole uma ou mais URLs http(s) diretas para arquivo de vídeo (mp4/mkv/avi/mov/webm/m4v).\n"
                "Dica: 1 por linha. O arquivo será baixado para rna_de_video/treinos/imported_videos/."
            ),
        )
        if not url_text:
            return

        urls = [ln.strip() for ln in url_text.splitlines() if ln.strip()]
        if not urls:
            return

        def task(cancel: threading.Event) -> None:
            paths: list[Path] = []
            for u in urls:
                if cancel.is_set():
                    return
                self._post_log(f"Baixando/resolvendo: {u}")
                p = resolve_video_reference_to_file(self.config, u)
                paths.append(p)
                self._post_log(f"OK: {p.name}")

            if cancel.is_set():
                return
            # Reuse the same pipeline for local files
            self.after(0, lambda: self._add_videos_worker(paths, title=f"Adicionar URL ({len(paths)} vídeos)"))

        self._run_worker("Baixar URLs", task)

    def _add_videos_worker(self, videos: list[Path], *, title: str) -> None:
        try:
            seg_start_ms, seg_end_ms = self._parse_segment_ms()
        except Exception as e:
            messagebox.showinfo("RNA", str(e))
            return

        def task(cancel: threading.Event) -> None:
            conn = connect(dataset_db_path(self.config))
            init_db(conn)
            try:
                for p in videos:
                    if cancel.is_set():
                        return

                    try:
                        self._post_log(f"Processando: {p.name}")
                        info = probe_video(p)

                        # Segment-aware frame sampling
                        if seg_start_ms >= 0 and seg_end_ms > seg_start_ms and info.fps > 1e-6:
                            start_frame = int((seg_start_ms / 1000.0) * info.fps)
                            end_frame = int((seg_end_ms / 1000.0) * info.fps)
                            start_frame = max(0, min(start_frame, info.frame_count))
                            end_frame = max(0, min(end_frame, info.frame_count))
                            if end_frame <= start_frame:
                                self._post_log("Trecho resultou em 0 frames; usando vídeo inteiro.")
                                start_frame = 0
                                end_frame = info.frame_count

                            seg_info = type(info)(
                                fps=info.fps,
                                frame_count=max(0, end_frame - start_frame),
                                duration_s=float(max(0, end_frame - start_frame) / info.fps),
                            )
                            local_idxs = sample_frame_indices(
                                seg_info,
                                max_frames=self.config.max_frames_per_video,
                                min_step_s=self.config.min_frame_step_s,
                            )
                            idxs = [start_frame + int(i) for i in local_idxs]
                        else:
                            idxs = sample_frame_indices(
                                info,
                                max_frames=self.config.max_frames_per_video,
                                min_step_s=self.config.min_frame_step_s,
                            )

                        frames = read_frames_rgb(p, idxs)
                        if not frames:
                            self._post_log("(sem frames lidos; pulando)")
                            continue

                        mode = self._registry.get(self._mode_id)

                        def compute() -> np.ndarray:
                            out = mode.compute(
                                video_path=p,
                                frames_rgb=frames,
                                appearance_extractor=self._extractor,
                                config=self.config,
                                start_ms=None if seg_start_ms < 0 else int(seg_start_ms),
                                end_ms=None if seg_end_ms < 0 else int(seg_end_ms),
                            )
                            self._last_preview_rgb = out.preview_rgb
                            self._last_n_frames = out.n_frames
                            return out.embedding

                        key, emb = get_or_compute_video_embedding(
                            self.config,
                            p,
                            mode=self._mode_id,
                            start_ms=int(seg_start_ms),
                            end_ms=int(seg_end_ms),
                            compute_fn=compute,
                        )

                        rec = ensure_video(conn, path=p, duration_s=info.duration_s)
                        set_embedding(
                            conn,
                            video_id=rec.video_id,
                            mode=self._mode_id,
                            embedding_key=key,
                            n_frames=int(getattr(self, "_last_n_frames", len(frames))),
                            start_ms=None if seg_start_ms < 0 else int(seg_start_ms),
                            end_ms=None if seg_end_ms < 0 else int(seg_end_ms),
                        )

                        clf, _tr = self._get_runtime(self._mode_id)
                        pred = clf.predict_open_world(
                            emb,
                            min_top1_confidence=self._thresholds.min_top1_confidence,
                            min_top1_similarity=self._thresholds.min_top1_similarity,
                            k=5,
                        )

                        if pred.known:
                            self._post_log(
                                f"Conhecido: {pred.topk[0].label} (conf={pred.topk[0].confidence:.2f})"
                            )
                        else:
                            self._post_log(f"DESCONHECIDO ({pred.reason}). Use botões para rotular/cluster.")

                        self._current_video = rec
                        self._current_embedding = emb
                        self._current_pred = pred
                        self._current_seg_start_ms = int(seg_start_ms)
                        self._current_seg_end_ms = int(seg_end_ms)
                        self._current_mode_id = str(self._mode_id)

                        preview_rgb = getattr(self, "_last_preview_rgb", frames[0])
                        self.after(0, lambda rgb=preview_rgb: self._render_current(rgb))

                    except Exception as e:
                        self._post_log(f"Erro ao processar {p.name}: {e}")
                        continue
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        self._run_worker(title, task)

    def on_train(self) -> None:
        def task(cancel: threading.Event) -> None:
            if cancel.is_set():
                return

            conn = connect(dataset_db_path(self.config))
            init_db(conn)
            try:
                _clf, tr = self._get_runtime(self._mode_id)
                tr.train_from_db(
                    conn,
                    mode=self._mode_id,
                    embedding_loader=lambda k: load_embedding(self.config, k, mode=self._mode_id),
                    log=self._post_log,
                )
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            self.after(0, self._refresh_labels)

        self._run_worker("Treinar", task)

    # ---------------- Labeling / unknowns ----------------

    def on_create_new_class(self) -> None:
        if not self._current_video or self._current_video.video_id is None:
            messagebox.showinfo("RNA", "Nenhum vídeo atual.")
            return
        if self._current_embedding is None:
            messagebox.showinfo("RNA", "Sem embedding atual.")
            return

        label = simple_prompt(self, "Nova classe", "Digite o nome da nova classe:")
        if not label:
            return

        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            set_label_for_segment(
                conn,
                video_id=self._current_video.video_id,
                mode=self._current_mode_id,
                start_ms=None if self._current_seg_start_ms < 0 else int(self._current_seg_start_ms),
                end_ms=None if self._current_seg_end_ms < 0 else int(self._current_seg_end_ms),
                label=label,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._post_log(f"Rotulado como nova classe: {label}")
        self._refresh_labels()

    def on_add_to_existing(self) -> None:
        if not self._current_video:
            messagebox.showinfo("RNA", "Nenhum vídeo atual.")
            return

        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            labels = list_labels(conn)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if not labels:
            messagebox.showinfo("RNA", "Ainda não existe nenhuma classe. Use 'Criar nova classe'.")
            return

        choice = ChoiceDialog(self, "Escolher classe", "Selecione uma classe:", labels).run()
        if not choice:
            return

        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            set_label_for_segment(
                conn,
                video_id=self._current_video.video_id,
                mode=self._current_mode_id,
                start_ms=None if self._current_seg_start_ms < 0 else int(self._current_seg_start_ms),
                end_ms=None if self._current_seg_end_ms < 0 else int(self._current_seg_end_ms),
                label=choice,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._post_log(f"Adicionado à classe: {choice}")
        self._refresh_labels()

    def on_send_to_cluster(self) -> None:
        if not self._current_video or self._current_embedding is None:
            messagebox.showinfo("RNA", "Nenhum vídeo/embedding atual.")
            return

        assign = self._clusterer.assign(self._current_embedding)
        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            ensure_cluster(conn, assign.cluster_id)
            set_cluster_for_segment(
                conn,
                video_id=self._current_video.video_id,
                mode=self._current_mode_id,
                start_ms=None if self._current_seg_start_ms < 0 else int(self._current_seg_start_ms),
                end_ms=None if self._current_seg_end_ms < 0 else int(self._current_seg_end_ms),
                cluster_id=assign.cluster_id,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._post_log(f"Enviado para cluster: {assign.cluster_id} (sim={assign.similarity:.2f})")
        self._refresh_clusters()

    # ---------------- Cluster tab ----------------

    def _refresh_clusters(self) -> None:
        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            clusters = list_unlabeled_clusters(conn)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._clusters = clusters
        self.cluster_list.delete(0, tk.END)
        for c in clusters:
            name = c.name or c.cluster_id
            self.cluster_list.insert(tk.END, f"{name} ({c.count})")

    def _refresh_labels(self) -> None:
        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            labels = list_labels(conn)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._labels = labels
        self._post_log(f"Classes: {len(labels)}")

    def on_select_cluster(self) -> None:
        sel = self.cluster_list.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(getattr(self, "_clusters", [])):
            return

        cluster: ClusterSummary = self._clusters[idx]
        self.cluster_title.configure(text=f"Cluster: {cluster.name or cluster.cluster_id}")

        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            vids = list_videos_by_cluster(conn, cluster.cluster_id)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._cluster_selected = cluster
        self.cluster_videos.delete(0, tk.END)
        for path, mode, s_ms, e_ms in vids:
            if s_ms >= 0 and e_ms > s_ms:
                seg = f"{s_ms/1000.0:.2f}-{e_ms/1000.0:.2f}s"
            else:
                seg = "(todo)"
            self.cluster_videos.insert(tk.END, f"{path.name} | {mode} | {seg}")

    def on_name_cluster(self) -> None:
        cluster = getattr(self, "_cluster_selected", None)
        if not cluster:
            messagebox.showinfo("RNA", "Selecione um cluster.")
            return
        name = simple_prompt(self, "Nomear cluster", "Digite um nome para esse cluster:")
        if not name:
            return

        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            name_cluster(conn, cluster.cluster_id, name)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._post_log(f"Cluster nomeado: {name}")
        self._refresh_clusters()

    def on_label_cluster(self) -> None:
        cluster = getattr(self, "_cluster_selected", None)
        if not cluster:
            messagebox.showinfo("RNA", "Selecione um cluster.")
            return

        label = simple_prompt(self, "Rotular cluster", "Qual rótulo/classe esse cluster representa?")
        if not label:
            return

        conn = connect(dataset_db_path(self.config))
        init_db(conn)
        try:
            n = assign_cluster_label(conn, cluster.cluster_id, label)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._post_log(f"Cluster rotulado como '{label}' (itens={n})")
        self._refresh_clusters()
        self._refresh_labels()

    # ---------------- Rendering ----------------

    def _render_current(self, preview_rgb: np.ndarray) -> None:
        self.pred_list.delete(0, tk.END)

        if self._current_pred:
            for p in self._current_pred.topk:
                self.pred_list.insert(tk.END, f"{p.label} | conf={p.confidence:.2f} | sim={p.similarity:.2f}")

        img = Image.fromarray(preview_rgb.astype(np.uint8), mode="RGB")
        img.thumbnail((420, 320))
        self._current_preview_imgtk = ImageTk.PhotoImage(img)
        self.preview.configure(image=self._current_preview_imgtk)

        self.details.delete("1.0", tk.END)
        if self._current_video:
            self.details.insert(tk.END, f"Arquivo: {self._current_video.path}\n")
            self.details.insert(tk.END, f"Duração: {self._current_video.duration_s:.1f}s\n")
            if self._current_seg_start_ms >= 0 and self._current_seg_end_ms > self._current_seg_start_ms:
                self.details.insert(
                    tk.END,
                    f"Trecho: {self._current_seg_start_ms/1000.0:.2f}–{self._current_seg_end_ms/1000.0:.2f}s\n",
                )
            nf = getattr(self, "_last_n_frames", None)
            if nf is not None:
                self.details.insert(tk.END, f"Frames amostrados: {nf}\n")
            self.details.insert(tk.END, f"Modo: {self._mode_id}\n")
            if self._current_pred:
                self.details.insert(tk.END, f"Status: {'CONHECIDO' if self._current_pred.known else 'DESCONHECIDO'} ({self._current_pred.reason})\n")


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
