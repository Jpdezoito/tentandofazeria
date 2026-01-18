from __future__ import annotations


def speak_text(text: str) -> None:
    """Offline TTS via pyttsx3 (optional dependency)."""
    try:
        import pyttsx3
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Para falar em voz alta, instale pyttsx3: pip install pyttsx3") from e

    t = (text or "").strip()
    if not t:
        return

    engine = pyttsx3.init()
    engine.say(t)
    engine.runAndWait()
