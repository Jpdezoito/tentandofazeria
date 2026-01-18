from __future__ import annotations

from rna_de_video.core.train_modes.base import ModeRegistry, TrainMode
from rna_de_video.core.train_modes.appearance import AppearanceMode
from rna_de_video.core.train_modes.motion import MotionMode
from rna_de_video.core.train_modes.fusion import FusionMode
from rna_de_video.core.train_modes.scene import SceneMode
from rna_de_video.core.train_modes.audio import AudioMode


def build_default_registry() -> ModeRegistry:
    reg = ModeRegistry()
    reg.register(AppearanceMode())
    reg.register(MotionMode())
    reg.register(FusionMode())
    reg.register(SceneMode())
    reg.register(AudioMode())
    return reg
