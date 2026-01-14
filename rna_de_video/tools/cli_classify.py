from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from rna_de_video.core.classifier import PrototypeClassifier
from rna_de_video.core.config import AppConfig, model_dir, thresholds_path
from rna_de_video.core.embedding import build_extractor
from rna_de_video.core.embedding_cache import get_or_compute_video_embedding
from rna_de_video.core.thresholds import Thresholds, load_thresholds
from rna_de_video.core.train_modes import build_default_registry
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
    ap = argparse.ArgumentParser(description="Classifica um vídeo usando modelos treinados em rna_de_video/treinos/model")
    ap.add_argument("--video", required=True, help="Caminho do vídeo (ou URL http(s) direta)")
    ap.add_argument("--mode", default="appearance", help="Modo: appearance|motion|fusion|scene|audio")
    ap.add_argument("--start", type=float, default=None, help="Início do trecho em segundos")
    ap.add_argument("--end", type=float, default=None, help="Fim do trecho em segundos")
    args = ap.parse_args(argv)

    config = AppConfig()

    try:
        ref = str(args.video)
        video_path = resolve_video_reference_to_file(config, ref)
        if not video_path.exists():
            raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")

        mode_id = str(args.mode).strip() or "appearance"
        reg = build_default_registry()
        mode = reg.get(mode_id)

        start_ms = -1
        end_ms = -1
        if args.start is not None or args.end is not None:
            if args.start is None or args.end is None:
                raise ValueError("Para usar trecho, informe --start e --end (segundos).")
            if float(args.end) <= float(args.start):
                raise ValueError("Trecho inválido: --end precisa ser maior que --start.")
            start_ms = int(float(args.start) * 1000.0)
            end_ms = int(float(args.end) * 1000.0)

        info = probe_video(video_path)
        idxs = _segment_indices(info, start_ms=start_ms, end_ms=end_ms, config=config)
        frames = read_frames_rgb(video_path, idxs)
        if not frames:
            raise RuntimeError("Sem frames lidos do vídeo (codec/arquivo).")

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

        _key, emb = get_or_compute_video_embedding(
            config,
            video_path,
            mode=mode_id,
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            compute_fn=compute,
        )

        # Load model trained under treinos/model
        clf = PrototypeClassifier()
        safe_mode = "".join(ch for ch in str(mode_id) if ch.isalnum() or ch in {"-", "_"}) or "mode"
        model_path = model_dir(config) / f"centroids_{safe_mode}.json"
        clf.load(model_path)

        thr = load_thresholds(
            thresholds_path(config),
            Thresholds(min_top1_confidence=config.min_top1_confidence, min_top1_similarity=config.min_top1_similarity),
        )

        pred = clf.predict_open_world(
            emb,
            min_top1_confidence=thr.min_top1_confidence,
            min_top1_similarity=thr.min_top1_similarity,
            k=5,
        )

        out = {
            "known": bool(pred.known),
            "reason": str(pred.reason),
            "mode": mode_id,
            "segment": {
                "start_s": None if start_ms < 0 else (start_ms / 1000.0),
                "end_s": None if end_ms < 0 else (end_ms / 1000.0),
            },
            "model_path": str(model_path),
            "topk": [
                {
                    "label": p.label,
                    "confidence": float(p.confidence),
                    "similarity": float(p.similarity),
                }
                for p in pred.topk
            ],
        }

        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0

    except Exception as e:
        # Write a compact error to stderr so caller sees it.
        sys.stderr.write(str(e))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
