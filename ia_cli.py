from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ia_core.config import resolve_paths
from ia_core.eval_runner import run_eval
from ia_core.dataset_registry import build_entry, register_dataset
from ia_core.extractors import index_image, index_video
from ia_core.logging import append_event
from ia_core.orchestrator import route_assistant
from ia_core.registry import ModelEntry, register_model, utc_now_iso


def _root_dir() -> Path:
    return Path(__file__).resolve().parent


def _run(cmd: list[str], *, cwd: Path) -> int:
    proc = subprocess.run(cmd, cwd=str(cwd))
    return int(proc.returncode)


def _run_capture_json(cmd: list[str], *, cwd: Path) -> dict:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or raw or f"exit={proc.returncode}").strip())
    if not raw:
        return {}
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    root = _root_dir()
    cfg_path = root / "configs" / "app.json"
    paths = resolve_paths(root, cfg_path)

    ap = argparse.ArgumentParser(description="CLI unica do ianova")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_assistant = sub.add_parser("assistant", help="Assistente (roteia para chat/busca/imagem/video)")
    p_assistant.add_argument("--text", required=True)
    p_assistant.add_argument("--use-ollama", action="store_true")
    p_assistant.add_argument("--model", default="")

    p_chat = sub.add_parser("chat", help="Conversa (texto)")
    p_chat.add_argument("--text", required=True)
    p_chat.add_argument("--use-ollama", action="store_true")
    p_chat.add_argument("--model", default="")

    p_ingest = sub.add_parser("ingest", help="Indexar arquivos para RAG")
    p_ingest.add_argument("--path", required=True)
    p_ingest.add_argument("--max-files", type=int, default=0)
    p_ingest.add_argument("--chunk-tokens", type=int, default=0)
    p_ingest.add_argument("--chunk-overlap", type=int, default=0)

    p_search = sub.add_parser("search", help="BuscarPastas")
    p_search.add_argument("--query", required=True)

    p_image = sub.add_parser("image", help="Classificar imagem")
    p_image.add_argument("--path", required=True)

    p_index_image = sub.add_parser("index-image", help="Indexar imagem como conhecimento")
    p_index_image.add_argument("--path", required=True)

    p_video = sub.add_parser("video", help="Classificar video")
    p_video.add_argument("--path", required=True)
    p_video.add_argument("--mode", default="appearance")
    p_video.add_argument("--start", default="")
    p_video.add_argument("--end", default="")

    p_index_video = sub.add_parser("index-video", help="Indexar video como conhecimento")
    p_index_video.add_argument("--path", required=True)
    p_index_video.add_argument("--mode", default="appearance")

    p_train_img = sub.add_parser("train-images", help="Treinar imagens")

    p_import = sub.add_parser("import-conversa", help="Importar treinos extras (conversa)")

    p_eval = sub.add_parser("eval", help="Rodar avaliacao simples")
    p_eval.add_argument("--questions", default=str(paths.eval_dir / "questions.jsonl"))
    p_eval.add_argument("--out", default=str(paths.eval_dir / "results.jsonl"))

    p_reg_ds = sub.add_parser("register-dataset", help="Registrar dataset no index")
    p_reg_ds.add_argument("--name", required=True)
    p_reg_ds.add_argument("--path", required=True)
    p_reg_ds.add_argument("--meta", default="{}")

    p_lora = sub.add_parser("finetune-lora", help="Fine-tuning LoRA/QLoRA (script)")
    p_lora.add_argument("--model", required=True)
    p_lora.add_argument("--data", required=True)
    p_lora.add_argument("--output", required=True)
    p_lora.add_argument("--qlora", action="store_true")
    p_lora.add_argument("--epochs", type=int, default=1)
    p_lora.add_argument("--batch", type=int, default=1)
    p_lora.add_argument("--lr", type=float, default=2e-4)

    p_reg = sub.add_parser("register-model", help="Registrar modelo no index")
    p_reg.add_argument("--name", required=True)
    p_reg.add_argument("--task", required=True)
    p_reg.add_argument("--data-version", required=True)
    p_reg.add_argument("--path", required=True)
    p_reg.add_argument("--metrics", default="{}")

    args = ap.parse_args(argv)

    if args.cmd == "assistant":
        reply = route_assistant(
            args.text,
            paths=paths,
            config_path=cfg_path,
            use_ollama=bool(args.use_ollama),
            model=str(args.model or ""),
        )
        append_event(paths.logs / "ops.jsonl", {"cmd": "assistant", "kind": reply.kind})
        print(json.dumps({"ok": True, "kind": reply.kind, "data": reply.data}, ensure_ascii=False))
        return 0

    if args.cmd == "chat":
        tool = paths.conversa / "tools" / "cli_chat.py"
        cmd = [sys.executable, str(tool), "--text", args.text]
        if args.use_ollama:
            cmd.append("--use-ollama")
        if args.model:
            cmd += ["--model", args.model]
        return _run(cmd, cwd=paths.conversa)

    if args.cmd == "ingest":
        tool = paths.conversa / "tools" / "cli_ingest.py"
        cmd = [
            sys.executable,
            str(tool),
            "--path",
            args.path,
            "--max-files",
            str(args.max_files),
            "--chunk-tokens",
            str(args.chunk_tokens),
            "--chunk-overlap",
            str(args.chunk_overlap),
        ]
        rc = _run(cmd, cwd=paths.conversa)
        append_event(paths.logs / "ops.jsonl", {"cmd": "ingest", "path": args.path, "rc": rc})
        return rc

    if args.cmd == "search":
        tool = paths.buscarpastas / "tools" / "cli_search.py"
        return _run([sys.executable, str(tool), "--query", args.query], cwd=paths.buscarpastas)

    if args.cmd == "image":
        tool = paths.qualquer_imagem / "tools" / "cli_classify.py"
        return _run([sys.executable, str(tool), "--image", args.path], cwd=paths.qualquer_imagem)

    if args.cmd == "index-image":
        res = index_image(Path(args.path), tool_root=paths.qualquer_imagem)
        append_event(paths.logs / "ops.jsonl", {"cmd": "index-image", "source": res.source})
        print(json.dumps({"ok": True, "source": res.source, "summary": res.summary}, ensure_ascii=False))
        return 0

    if args.cmd == "video":
        tool = paths.video / "tools" / "cli_classify.py"
        cmd = [sys.executable, str(tool), "--video", args.path, "--mode", args.mode]
        if args.start or args.end:
            cmd += ["--start", str(args.start), "--end", str(args.end)]
        return _run(cmd, cwd=paths.video)

    if args.cmd == "index-video":
        res = index_video(Path(args.path), tool_root=paths.video, mode=str(args.mode))
        append_event(paths.logs / "ops.jsonl", {"cmd": "index-video", "source": res.source, "mode": args.mode})
        print(json.dumps({"ok": True, "source": res.source, "summary": res.summary}, ensure_ascii=False))
        return 0

    if args.cmd == "train-images":
        tool = paths.qualquer_imagem / "tools" / "train_from_db.py"
        rc = _run([sys.executable, str(tool)], cwd=paths.qualquer_imagem)
        append_event(paths.logs / "ops.jsonl", {"cmd": "train-images", "rc": rc})
        return rc

    if args.cmd == "import-conversa":
        tool = paths.conversa / "tools" / "import_from_ia_treinos.py"
        rc = _run([sys.executable, str(tool), "--extra", str(paths.treinos)], cwd=paths.conversa)
        append_event(paths.logs / "ops.jsonl", {"cmd": "import-conversa", "rc": rc})
        return rc

    if args.cmd == "eval":
        questions = Path(str(args.questions)).expanduser().resolve()
        out = Path(str(args.out)).expanduser().resolve()
        chat_cli = paths.conversa / "tools" / "cli_chat.py"
        try:
            from rna_de_conversa.core.config import config_from_env, db_path

            knowledge_db = db_path(config_from_env())
        except Exception:
            knowledge_db = None
        run_eval(questions, chat_cli, cwd=paths.conversa, out_path=out, knowledge_db=knowledge_db)
        append_event(paths.logs / "ops.jsonl", {"cmd": "eval", "out": str(out)})
        print(json.dumps({"ok": True, "out": str(out)}, ensure_ascii=False))
        return 0

    if args.cmd == "register-dataset":
        meta = json.loads(args.meta)
        index_path = paths.data / "datasets.json"
        entry = build_entry(args.name, Path(args.path), utc_now_iso(), meta=meta)
        register_dataset(index_path, entry)
        append_event(paths.logs / "ops.jsonl", {"cmd": "register-dataset", "name": args.name})
        print(json.dumps({"ok": True, "index": str(index_path)}, ensure_ascii=False))
        return 0

    if args.cmd == "finetune-lora":
        tool = root / "train" / "finetune_lora.py"
        cmd = [
            sys.executable,
            str(tool),
            "--model",
            args.model,
            "--data",
            args.data,
            "--output",
            args.output,
            "--epochs",
            str(args.epochs),
            "--batch",
            str(args.batch),
            "--lr",
            str(args.lr),
        ]
        if args.qlora:
            cmd.append("--qlora")
        rc = _run(cmd, cwd=root)
        append_event(paths.logs / "ops.jsonl", {"cmd": "finetune-lora", "rc": rc})
        return rc

    if args.cmd == "register-model":
        metrics = json.loads(args.metrics)
        entry = ModelEntry(
            name=args.name,
            task=args.task,
            data_version=args.data_version,
            path=args.path,
            metrics=metrics,
            created_at=utc_now_iso(),
        )
        index_path = paths.models / "index.json"
        register_model(index_path, entry)
        append_event(paths.logs / "ops.jsonl", {"cmd": "register-model", "name": args.name, "task": args.task})
        print(json.dumps({"ok": True, "index": str(index_path)}, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
