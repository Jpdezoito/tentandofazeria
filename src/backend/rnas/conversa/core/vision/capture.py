from __future__ import annotations

import base64
from dataclasses import dataclass


@dataclass(frozen=True)
class CapturedImage:
    kind: str  # "screen" | "webcam"
    png_bytes: bytes


def png_bytes_to_tk_photo_data(png_bytes: bytes) -> str:
    """Return base64 string usable by tkinter.PhotoImage(data=...)."""
    return base64.b64encode(png_bytes).decode("ascii")


def capture_screen_png() -> CapturedImage:
    """Capture a screenshot and return PNG bytes.

    Requires Pillow (PIL). If missing, raises RuntimeError with instructions.
    """
    try:
        from PIL import ImageGrab  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Para capturar a tela, instale Pillow: pip install pillow") from e

    try:
        img = ImageGrab.grab(all_screens=True)
        img = img.convert("RGB")
        from io import BytesIO

        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return CapturedImage(kind="screen", png_bytes=buf.getvalue())
    except Exception as e:
        raise RuntimeError(f"Falha ao capturar a tela: {e}") from e


def capture_webcam_png(camera_index: int = 0) -> CapturedImage:
    """Capture a single frame from webcam and return PNG bytes.

    Requires opencv-python (cv2). If missing, raises RuntimeError with instructions.
    """
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Para capturar webcam, instale opencv-python: pip install opencv-python") from e

    cap = None
    try:
        # No Windows, CAP_DSHOW costuma ser mais estável/rápido para algumas webcams.
        backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0
        cap = cv2.VideoCapture(int(camera_index), backend)

        if not cap.isOpened():
            raise RuntimeError(f"Não consegui abrir a webcam (camera_index={camera_index}).")

        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError("Falha ao ler frame da webcam.")

        # Encode PNG (mantém BGR; é suficiente para PNG)
        ok2, png = cv2.imencode(".png", frame)
        if not ok2:
            raise RuntimeError("Falha ao codificar frame em PNG.")

        return CapturedImage(kind="webcam", png_bytes=bytes(png))
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
