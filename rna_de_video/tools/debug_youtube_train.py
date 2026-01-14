from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


# Allow running as a file: `python rna_de_video/tools/debug_youtube_train.py ...`
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from rna_de_video.core.classifier import PrototypeClassifier
from rna_de_video.core.config import AppConfig, dataset_db_path
from rna_de_video.core.dataset import connect, init_db, ensure_video, set_embedding, set_label_for_segment
from rna_de_video.core.embedding import build_extractor
from rna_de_video.core.embedding_cache import get_or_compute_video_embedding, load_embedding
from rna_de_video.core.train_modes import build_default_registry
from rna_de_video.core.trainer import Trainer
from rna_de_video.core.video_frames import probe_video, read_frames_rgb, sample_frame_indices
from rna_de_video.core.video_sources import resolve_video_reference_to_file


def _segment_indices(info, *, start_ms: int, end_ms: int, config: AppConfig) -> list[int]:
    if start_ms >= 0 and end_ms > start_ms and info.fps > 1e-6 and info.frame_count > 0:
        start_frame = int((start_ms / 1000.0) * info.fps)
        end_frame = int((end_ms / 1000.0) * info.fps)
        start_frame = max(0, min(start_frame, info.frame_count))
        end_frame = max(0, min(end_frame, info.frame_count))
        if end_frame <= start_frame:
            start_frame = 0
            end_frame = info.frame_count

        seg_frame_count = max(0, end_frame - start_frame)
        seg_info = type(info)(
            fps=info.fps,
            frame_count=seg_frame_count,
            duration_s=float(seg_frame_count / info.fps) if info.fps > 1e-6 else 0.0,
        )
        local_idxs = sample_frame_indices(
            seg_info,
            max_frames=config.max_frames_per_video,
            min_step_s=config.min_frame_step_s,
        )
        return [start_frame + int(i) for i in local_idxs]

    return sample_frame_indices(
        info,
        max_frames=config.max_frames_per_video,
        min_step_s=config.min_frame_step_s,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Debug: baixa vídeo (YouTube via yt-dlp), cria embedding, rotula e treina")
    ap.add_argument("--url", required=True)
    ap.add_argument("--label", default="youtube_demo")
    ap.add_argument("--mode", default="appearance")
    ap.add_argument("--start", type=float, default=None)
    ap.add_argument("--end", type=float, default=None)
    args = ap.parse_args(argv)

    config = AppConfig()
    reg = build_default_registry()
    mode_id = str(args.mode).strip() or "appearance"
    mode = reg.get(mode_id)

    start_ms = -1
    end_ms = -1
    if args.start is not None or args.end is not None:
        if args.start is None or args.end is None:
            raise SystemExit("Para trecho, use --start e --end (segundos).")
        if float(args.end) <= float(args.start):
            raise SystemExit("Trecho inválido: --end precisa ser maior que --start")
        start_ms = int(float(args.start) * 1000.0)
        end_ms = int(float(args.end) * 1000.0)

    print("[debug] resolvendo/baixando URL...")
    video_path = resolve_video_reference_to_file(config, str(args.url))
    print(f"[debug] arquivo: {video_path}")

    info = probe_video(video_path)
    idxs = _segment_indices(info, start_ms=start_ms, end_ms=end_ms, config=config)
    frames = read_frames_rgb(video_path, idxs)
    if not frames:
        raise SystemExit("Sem frames lidos do vídeo (codec/arquivo).")

    extractor = build_extractor(config.backbone, config.frame_resize)

    def compute() -> np.ndarray:
        out = mode.compute(
            video_path=video_path,
            frames_rgb=frames,
            appearance_extractor=extractor,
            config=config,
            start_ms=None if start_ms < 0 else int(start_ms),
            end_ms=None if end_ms < 0 else int(end_ms),
        )
        return out.embedding

    print("[debug] calculando embedding...")
    key, emb = get_or_compute_video_embedding(
        config,
        video_path,
        mode=mode_id,
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        compute_fn=compute,
    )

    conn = connect(dataset_db_path(config))
    init_db(conn)
    try:
        rec = ensure_video(conn, path=video_path, duration_s=info.duration_s)
        set_embedding(
            conn,
            video_id=rec.video_id,
            mode=mode_id,
            embedding_key=key,
            n_frames=len(frames),
            start_ms=None if start_ms < 0 else int(start_ms),
            end_ms=None if end_ms < 0 else int(end_ms),
        )
        set_label_for_segment(
            conn,
            video_id=rec.video_id,
            mode=mode_id,
            start_ms=None if start_ms < 0 else int(start_ms),
            end_ms=None if end_ms < 0 else int(end_ms),
            label=str(args.label),
        )

        clf = PrototypeClassifier()
        tr = Trainer(config, clf)
        print("[debug] treinando (centróides)...")
        tr.train_from_db(conn, mode=mode_id, embedding_loader=lambda k: load_embedding(config, k, mode=mode_id))

        pred = clf.predict_open_world(
            emb,
            min_top1_confidence=config.min_top1_confidence,
            min_top1_similarity=config.min_top1_similarity,
            k=5,
        )
        print(f"[debug] predição known={pred.known} reason={pred.reason}")
        for p in pred.topk:
            print(f"  - {p.label} conf={p.confidence:.3f} sim={p.similarity:.3f}")

    finally:
        conn.close()

    print("[debug] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
