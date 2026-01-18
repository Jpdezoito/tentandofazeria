from __future__ import annotations

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from datasets import Dataset
from pathlib import Path
from typing import Any

from .config import AppConfig


class CodeModel:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.model = None
        self.tokenizer = None

    def load_model(self):
        """Carrega o modelo e tokenizer."""
        self.tokenizer = AutoTokenizer.from_pretrained(self.cfg.tokenizer_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(self.cfg.model_name)

    def tokenize_function(self, examples: dict[str, Any]) -> dict[str, Any]:
        """Tokeniza os exemplos."""
        return self.tokenizer(
            examples["text"],
            truncation=True,
            padding="max_length",
            max_length=self.cfg.max_code_length,
        )

    def prepare_dataset(self, texts: list[str]) -> Dataset:
        """Prepara o dataset para treinamento."""
        dataset = Dataset.from_dict({"text": texts})
        tokenized_dataset = dataset.map(
            self.tokenize_function,
            batched=True,
            remove_columns=["text"]
        )
        return tokenized_dataset

    def train(self, train_texts: list[str], output_dir: Path):
        """Treina o modelo."""
        if self.model is None:
            self.load_model()

        train_dataset = self.prepare_dataset(train_texts)

        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False,
        )

        training_args = TrainingArguments(
            output_dir=str(output_dir),
            overwrite_output_dir=True,
            num_train_epochs=self.cfg.num_epochs,
            per_device_train_batch_size=self.cfg.batch_size,
            save_steps=10_000,
            save_total_limit=2,
            learning_rate=self.cfg.learning_rate,
            warmup_steps=self.cfg.warmup_steps,
            logging_dir=str(output_dir / "logs"),
            logging_steps=100,
            eval_strategy="no",
            load_best_model_at_end=False,
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            data_collator=data_collator,
            train_dataset=train_dataset,
        )

        trainer.train()
        trainer.save_model(str(output_dir))

    def generate(self, prompt: str, max_length: int = 100) -> str:
        """Gera código a partir de um prompt."""
        if self.model is None:
            self.load_model()

        inputs = self.tokenizer(prompt, return_tensors="pt")
        input_len = int(inputs["input_ids"].shape[1])
        max_new = max(1, int(max_length) - input_len)
        with torch.no_grad():
            gen_kwargs = {
                "max_new_tokens": max_new,
                "do_sample": bool(self.cfg.do_sample),
                "pad_token_id": self.tokenizer.eos_token_id,
            }
            if self.cfg.do_sample:
                gen_kwargs.update(
                    {
                        "temperature": float(self.cfg.temperature),
                        "top_p": float(self.cfg.top_p),
                    }
                )
            outputs = self.model.generate(**inputs, **gen_kwargs)

        new_tokens = outputs[0][input_len:]
        if len(new_tokens) == 0:
            return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)
