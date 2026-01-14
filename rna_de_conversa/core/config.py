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
    app_name: str = "RNA_Conversa"

    # Folder policy: everything under treinos/
    project_folder_name: str = "rna_de_conversa"
    treinos_dir_name: str = "treinos"

    db_name: str = "conversa.db"
    settings_name: str = "settings.json"

    logs_dir_name: str = "logs"
    import_dir_name: str = "importar"

    # Conversation behavior
    session_max_turns: int = 12
    retrieval_topk: int = 3
    retrieval_min_score: float = 0.18

    # Knowledge / RAG behavior
    knowledge_topk: int = 4
    knowledge_min_score: float = 0.16
    knowledge_chunk_tokens: int = 420
    knowledge_chunk_overlap: int = 60
    knowledge_build_index: bool = True
    knowledge_index_name: str = "knowledge_index.pkl"
    knowledge_index_max_features: int = 50000
    knowledge_vector_backend: str = "tfidf"  # tfidf | chroma
    knowledge_chroma_dir_name: str = "knowledge_chroma"
    knowledge_chroma_collection: str = "knowledge_chunks"
    knowledge_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_s: float = 30.0


def config_from_env() -> AppConfig:
    """Build config with safe defaults when debugging."""

    backend = _env_str("IANOVA_VECTOR_BACKEND", "").strip().lower()
    emb_model = _env_str("IANOVA_EMBEDDING_MODEL", "").strip()

    if not _env_flag("IANOVA_SAFE_DEBUG"):
        if backend or emb_model:
            return AppConfig(
                knowledge_vector_backend=backend or AppConfig.knowledge_vector_backend,
                knowledge_embedding_model=emb_model or AppConfig.knowledge_embedding_model,
            )
        return AppConfig()

    return AppConfig(
        session_max_turns=6,
        retrieval_topk=2,
        ollama_timeout_s=10.0,
        knowledge_vector_backend=backend or AppConfig.knowledge_vector_backend,
        knowledge_embedding_model=emb_model or AppConfig.knowledge_embedding_model,
    )


def project_root() -> Path:
    # Directory containing this module (rna_de_conversa/core)
    return Path(__file__).resolve().parents[1]


def assistant_base_dir(config: AppConfig) -> Path:
    root = project_root()
    if root.name.lower() == config.project_folder_name.lower():
        return root

    candidate = root / config.project_folder_name
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def treinos_dir(config: AppConfig) -> Path:
    d = assistant_base_dir(config) / config.treinos_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def knowledge_index_path(config: AppConfig) -> Path:
    d = treinos_dir(config)
    return d / config.knowledge_index_name


def knowledge_chroma_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.knowledge_chroma_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def modelo_treino_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / "modelo_treino"
    d.mkdir(parents=True, exist_ok=True)
    return d


def modelos_pre_treinados_dir(config: AppConfig) -> Path:
    d = modelo_treino_dir(config) / "modelos_pre_treinados"
    d.mkdir(parents=True, exist_ok=True)
    return d


def active_pretrained_root(config: AppConfig) -> Path | None:
    """Return the active pretrained bundle folder if configured.

    Rules (first match wins):
    - treinos/modelo_treino/modelos_pre_treinados/ATIVO.txt containing a relative folder name
    - treinos/modelo_treino/modelos_pre_treinados/ativo (directory)

    The active folder can contain files like conversa.db, settings.json, etc.
    """

    base = modelos_pre_treinados_dir(config)
    marker = base / "ATIVO.txt"
    if marker.exists():
        rel = marker.read_text(encoding="utf-8", errors="replace").strip()
        if rel:
            candidate = (base / rel).resolve()
            if candidate.exists() and candidate.is_dir():
                return candidate

    candidate = base / "ativo"
    if candidate.exists() and candidate.is_dir():
        return candidate

    return None


def _prefer_pretrained_file(config: AppConfig, filename: str) -> Path | None:
    active = active_pretrained_root(config)
    if not active:
        return None
    p = active / filename
    return p if p.exists() and p.is_file() else None


def db_path(config: AppConfig) -> Path:
    return _prefer_pretrained_file(config, config.db_name) or (treinos_dir(config) / config.db_name)


def settings_path(config: AppConfig) -> Path:
    # Keep settings local by default (user preferences), unless a pretrained settings file exists.
    return _prefer_pretrained_file(config, config.settings_name) or (treinos_dir(config) / config.settings_name)


def logs_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.logs_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def import_dir(config: AppConfig) -> Path:
    d = treinos_dir(config) / config.import_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_settings(config: AppConfig) -> dict[str, Any]:
    p = settings_path(config)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def save_settings(config: AppConfig, data: dict[str, Any]) -> None:
    p = settings_path(config)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
