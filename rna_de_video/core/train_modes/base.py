from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class ModeComputeResult:
    embedding: np.ndarray
    preview_rgb: np.ndarray
    n_frames: int


class TrainMode(Protocol):
    mode_id: str
    display_name: str

    def compute(
        self,
        *,
        video_path,
        frames_rgb: list[np.ndarray],
        appearance_extractor,
        config,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> ModeComputeResult:
        ...


class ModeRegistry:
    def __init__(self) -> None:
        self._modes: dict[str, TrainMode] = {}

    def register(self, mode: TrainMode) -> None:
        self._modes[str(mode.mode_id)] = mode

    def get(self, mode_id: str) -> TrainMode:
        if mode_id not in self._modes:
            raise KeyError(f"Modo não encontrado: {mode_id}")
        return self._modes[mode_id]

    def list(self) -> list[TrainMode]:
        # Preserve registration order (dict insertion order)
        return list(self._modes.values())

    def ids(self) -> list[str]:
        return [m.mode_id for m in self.list()]

    def display_names(self) -> list[str]:
        return [m.display_name for m in self.list()]

    def id_by_display(self, display_name: str) -> str:
        for m in self.list():
            if m.display_name == display_name:
                return m.mode_id
        raise KeyError("display_name inválido")
