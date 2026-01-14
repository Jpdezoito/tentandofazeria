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


def _format_example(obj: dict) -> str:
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
    ap.add_argument("--model", required=True, help="Modelo base (ex: meta-llama/...)" )
    ap.add_argument("--data", required=True, help="JSONL com instruction/input/output")
    ap.add_argument("--output", required=True, help="Pasta de saida")
    ap.add_argument("--qlora", action="store_true")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-4)
    args = ap.parse_args(argv)

    data_path = Path(args.data).expanduser().resolve()
    if not data_path.exists():
        raise FileNotFoundError(f"Nao achei: {data_path}")

    rows = _load_jsonl(data_path)
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
        return tokenizer(batch["text"], truncation=True, max_length=2048)

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
