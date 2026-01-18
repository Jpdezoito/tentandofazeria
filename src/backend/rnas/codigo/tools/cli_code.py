from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a file
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import config_from_env  # noqa: E402
from core.models import CodeModel  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="RNA Código CLI - Geração de código")
    ap.add_argument("--prompt", required=True, help="Prompt para geração de código")
    ap.add_argument("--max-length", type=int, default=200, help="Comprimento máximo da geração")
    ap.add_argument("--model-path", default=None, help="Caminho para modelo treinado (opcional)")
    args = ap.parse_args(argv)

    cfg = config_from_env()
    model = CodeModel(cfg)

    if args.model_path:
        # Carregar modelo treinado
        model.model = AutoModelForCausalLM.from_pretrained(args.model_path)
        model.tokenizer = AutoTokenizer.from_pretrained(args.model_path)

    generated = model.generate(args.prompt, max_length=args.max_length)

    # Output JSON
    result = {
        "prompt": args.prompt,
        "generated": generated,
        "model": cfg.model_name,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
