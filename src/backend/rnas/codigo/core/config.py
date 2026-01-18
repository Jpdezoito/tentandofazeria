from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _env_flag(name: str) -> bool:
    import os

    v = str(os.environ.get(name, "")).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _env_str(name: str, default: str = "") -> str:
    import os

    v = os.environ.get(name)
    return str(v).strip() if v is not None else default


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "RNA_Codigo"

    # Folder policy: everything under treinos/
    project_folder_name: str = "rnas/codigo"
    treinos_dir_name: str = "treinos"

    db_name: str = "codigo.db"
    settings_name: str = "settings.json"

    logs_dir_name: str = "logs"
    import_dir_name: str = "importar"

    # Code generation behavior
    max_length: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    do_sample: bool = True

    # Training parameters
    batch_size: int = 8
    learning_rate: float = 5e-5
    num_epochs: int = 3
    warmup_steps: int = 500

    # Model settings
    model_name: str = "Salesforce/codegen-350M-mono"
    tokenizer_name: str = "Salesforce/codegen-350M-mono"

    # Data settings
    max_code_length: int = 1024
    languages: tuple[str, ...] = ("python", "javascript", "java", "cpp")


def config_from_env() -> AppConfig:
    defaults = AppConfig()
    return AppConfig(
        max_length=int(_env_str("RNA_CODIGO_MAX_LENGTH", str(defaults.max_length))),
        temperature=float(_env_str("RNA_CODIGO_TEMPERATURE", str(defaults.temperature))),
        top_p=float(_env_str("RNA_CODIGO_TOP_P", str(defaults.top_p))),
        do_sample=_env_flag("RNA_CODIGO_DO_SAMPLE") if _env_str("RNA_CODIGO_DO_SAMPLE") else defaults.do_sample,
        batch_size=int(_env_str("RNA_CODIGO_BATCH_SIZE", str(defaults.batch_size))),
        learning_rate=float(_env_str("RNA_CODIGO_LEARNING_RATE", str(defaults.learning_rate))),
        num_epochs=int(_env_str("RNA_CODIGO_NUM_EPOCHS", str(defaults.num_epochs))),
        warmup_steps=int(_env_str("RNA_CODIGO_WARMUP_STEPS", str(defaults.warmup_steps))),
        model_name=_env_str("RNA_CODIGO_MODEL_NAME", defaults.model_name),
        tokenizer_name=_env_str("RNA_CODIGO_TOKENIZER_NAME", defaults.tokenizer_name),
        max_code_length=int(_env_str("RNA_CODIGO_MAX_CODE_LENGTH", str(defaults.max_code_length))),
    )


def _project_root() -> Path:
    # Assume we're in backend/rnas/codigo/core/config.py
    return Path(__file__).resolve().parents[3]


def treinos_dir(cfg: AppConfig) -> Path:
    return Path(_project_root(), *cfg.project_folder_name.split("/"), cfg.treinos_dir_name)


def import_dir(cfg: AppConfig) -> Path:
    return treinos_dir(cfg) / cfg.import_dir_name


def db_path(cfg: AppConfig) -> Path:
    return Path(_project_root(), *cfg.project_folder_name.split("/"), cfg.db_name)


def settings_path(cfg: AppConfig) -> Path:
    return Path(_project_root(), *cfg.project_folder_name.split("/"), cfg.settings_name)


def logs_dir(cfg: AppConfig) -> Path:
    return Path(_project_root(), *cfg.project_folder_name.split("/"), cfg.logs_dir_name)


def modelos_pre_treinados_dir(cfg: AppConfig) -> Path:
    return Path(_project_root(), *cfg.project_folder_name.split("/"), "modelos_pre_treinados")
