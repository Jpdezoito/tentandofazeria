from __future__ import annotations

from dataclasses import dataclass

from core.config import AppConfig
from core.memoria.short import SessionMemory
from core.memoria.store import count_examples, iter_all
from core.ollama.client import detect as detect_ollama
from core.ollama.client import generate as ollama_generate
from core.retrieval.retriever import RetrievalConfig, retrieve


@dataclass(frozen=True)
class ReplyResult:
    text: str
    engine: str  # "ollama" | "fallback"
    debug: str = ""


class ChatRuntime:
    def __init__(self, cfg: AppConfig, conn):
        self.cfg = cfg
        self.conn = conn
        self.mem = SessionMemory(max_turns=cfg.session_max_turns)

    def clear_session(self) -> None:
        self.mem.clear()

    def reply(self, user_text: str, *, use_ollama: bool, model: str | None) -> ReplyResult:
        user_text = (user_text or "").strip()
        if not user_text:
            return ReplyResult(text="", engine="fallback")

        self.mem.add("user", user_text)

        if use_ollama and model:
            st = detect_ollama(self.cfg)
            if st.installed and st.running:
                prompt = self._build_prompt_for_ollama(user_text)
                out = ollama_generate(self.cfg, model=model, prompt=prompt)
                out = out.strip() or "(sem resposta do Ollama)"
                self.mem.add("assistant", out)
                return ReplyResult(text=out, engine="ollama")

        # Fallback: retrieval over local examples
        cfg = RetrievalConfig(topk=self.cfg.retrieval_topk, min_score=self.cfg.retrieval_min_score)
        examples = list(iter_all(self.conn))
        hits = retrieve(user_text, examples, cfg)

        if hits:
            best = hits[0]
            out = best.example.assistant_text
            dbg = f"retrieval_hit score={best.score:.3f} ex_id={best.example.example_id}"
            self.mem.add("assistant", out)
            return ReplyResult(text=out, engine="fallback", debug=dbg)

        n = count_examples(self.conn)
        out = (
            "Ainda não tenho um treino bom pra isso.\n"
            "Você pode me ensinar: vá em 'Treino incremental' e salve um exemplo (pergunta -> resposta).\n"
            f"(exemplos salvos: {n})"
        )
        self.mem.add("assistant", out)
        return ReplyResult(text=out, engine="fallback", debug="no_hits")

    def reply_with_image(
        self,
        user_text: str,
        *,
        image_png: bytes,
        use_ollama: bool,
        model: str | None,
        image_hint: str = "imagem",
    ) -> ReplyResult:
        """Reply using an attached image.

        If Ollama is available and selected, sends the image to /api/generate.
        Otherwise, returns a local fallback message (offline retrieval can't "see" images).
        """

        user_text = (user_text or "").strip() or f"Descreva a {image_hint}."

        self.mem.add("user", user_text)

        if use_ollama and model:
            st = detect_ollama(self.cfg)
            if st.installed and st.running:
                prompt = self._build_prompt_for_ollama(user_text)
                out = ollama_generate(self.cfg, model=model, prompt=prompt, images=[image_png])
                out = out.strip() or "(sem resposta do Ollama)"
                self.mem.add("assistant", out)
                return ReplyResult(text=out, engine="ollama", debug="image=1")

        out = (
            "Recebi a imagem, mas no modo local (sem Ollama) eu não consigo interpretar imagens ainda.\n"
            "Se você instalar o Ollama e usar um modelo multimodal (ex.: llava), eu consigo descrever a tela/webcam."
        )
        self.mem.add("assistant", out)
        return ReplyResult(text=out, engine="fallback", debug="image_no_ollama")

    def _build_prompt_for_ollama(self, user_text: str) -> str:
        system = (
            "Você é um assistente local. Responda em português. Seja direto e útil. "
            "Se faltar informação, faça perguntas curtas."
        )
        # Include session context
        ctx = self.mem.as_prompt(system_preamble=system)
        return ctx + f"\n[user]\n{user_text}\n\n[assistant]\n"
