from __future__ import annotations

import argparse
import json
from pathlib import Path


def _require_train_deps():
    try:
        import importlib

        importlib.import_module("torch")
        importlib.import_module("transformers")
        importlib.import_module("datasets")
        importlib.import_module("peft")
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Dependencias de treino nao instaladas. "
            "Instale transformers, datasets, peft, accelerate e torch."
        ) from e


def _load_jsonl(path: Path) -> list[dict]:
    data: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = (line or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        data.append(obj)
    return data


def _collect_jsonl_files(data_path: Path | None, data_dir: Path | None) -> list[Path]:
    files: list[Path] = []
    if data_path:
        if not data_path.exists():
            raise FileNotFoundError(f"Nao achei: {data_path}")
        files.append(data_path)

    if data_dir:
        if not data_dir.exists():
            raise FileNotFoundError(f"Nao achei: {data_dir}")
        for p in sorted(data_dir.glob("**/*.jsonl")):
            if p.is_file():
                files.append(p)

    # Remove duplicates preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in files:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        unique.append(p)
    return unique


def _format_example(obj: dict) -> str:
    messages = obj.get("messages")
    if isinstance(messages, list):
        system_parts: list[str] = []
        cleaned: list[tuple[str, str]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "").strip().lower()
            content = str(msg.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
                continue
            if role in {"user", "assistant"}:
                cleaned.append((role, content))

        last_assistant_idx = -1
        for i in range(len(cleaned) - 1, -1, -1):
            if cleaned[i][0] == "assistant":
                last_assistant_idx = i
                break
        if last_assistant_idx == -1:
            return ""

        instruction = "\n".join(system_parts).strip()
        input_msgs = cleaned[:last_assistant_idx]
        output = cleaned[last_assistant_idx][1].strip()

        dialogue_lines: list[str] = []
        for role, content in input_msgs:
            label = "Usuario" if role == "user" else "Assistente"
            dialogue_lines.append(f"{label}: {content}")
        inp = "\n".join(dialogue_lines).strip()

        parts = []
        if instruction:
            parts.append(f"### Instrucao:\n{instruction}")
        if inp:
            parts.append(f"### Entrada:\n{inp}")
        if output:
            parts.append(f"### Resposta:\n{output}")
        return "\n\n".join(parts).strip()

    instruction = str(obj.get("instruction") or obj.get("question") or "").strip()
    inp = str(obj.get("input") or "").strip()
    output = str(obj.get("output") or obj.get("answer") or "").strip()
    parts = []
    if instruction:
        parts.append(f"### Instrução:\n{instruction}")
    if inp:
        parts.append(f"### Entrada:\n{inp}")
    if output:
        parts.append(f"### Resposta:\n{output}")
    return "\n\n".join(parts).strip()


def main(argv: list[str] | None = None) -> int:
    _require_train_deps()

    import importlib

    torch = importlib.import_module("torch")
    Dataset = importlib.import_module("datasets").Dataset
    peft_mod = importlib.import_module("peft")
    transformers = importlib.import_module("transformers")

    LoraConfig = peft_mod.LoraConfig
    get_peft_model = peft_mod.get_peft_model
    prepare_model_for_kbit_training = peft_mod.prepare_model_for_kbit_training

    AutoModelForCausalLM = transformers.AutoModelForCausalLM
    AutoTokenizer = transformers.AutoTokenizer
    TrainingArguments = transformers.TrainingArguments
    Trainer = transformers.Trainer

    ap = argparse.ArgumentParser(description="Fine-tuning LoRA/QLoRA (minimo)")
    ap.add_argument("--model", required=True, help="Modelo base (ex: meta-llama/... )" )
    ap.add_argument("--data", default="", help="JSONL com instruction/input/output")
    ap.add_argument("--data-dir", default="", help="Pasta com JSONL (usa todos)")
    ap.add_argument("--output", required=True, help="Pasta de saida")
    ap.add_argument("--qlora", action="store_true")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-4)
    args = ap.parse_args(argv)

    data_path = Path(args.data).expanduser().resolve() if args.data else None
    data_dir = Path(args.data_dir).expanduser().resolve() if args.data_dir else None

    files = _collect_jsonl_files(data_path, data_dir)
    if not files:
        raise RuntimeError("Informe --data ou --data-dir com JSONL.")

    rows: list[dict] = []
    for p in files:
        rows.extend(_load_jsonl(p))
    texts = [t for t in (_format_example(r) for r in rows) if t]
    if not texts:
        raise RuntimeError("Dataset vazio ou invalido.")

    ds = Dataset.from_dict({"text": texts})

    quant_config = None
    if args.qlora:
        try:
            BitsAndBytesConfig = transformers.BitsAndBytesConfig
        except Exception as e:  # pragma: no cover
            raise ImportError("bitsandbytes necessario para QLoRA") from e
        quant_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        device_map="auto",
        quantization_config=quant_config,
    )

    if args.qlora:
        model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)

    def tokenize_fn(batch):
        enc = tokenizer(batch["text"], truncation=True, max_length=2048)
        enc["labels"] = enc["input_ids"].copy()
        return enc

    tokenized = ds.map(tokenize_fn, batched=True, remove_columns=["text"])

    args_train = TrainingArguments(
        output_dir=str(Path(args.output).expanduser().resolve()),
        per_device_train_batch_size=int(args.batch),
        num_train_epochs=int(args.epochs),
        learning_rate=float(args.lr),
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        report_to=[],
    )

    trainer = Trainer(model=model, args=args_train, train_dataset=tokenized)
    trainer.train()

    model.save_pretrained(args_train.output_dir)
    tokenizer.save_pretrained(args_train.output_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
