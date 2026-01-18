from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.config import AppConfig, treinos_dir
from core.knowledge.retrieval import KnowledgeRetrievalConfig, retrieve_chunks
from core.knowledge.vector_index import retrieve_with_vector_index
from core.knowledge.vector_store import query_chunks
from core.knowledge.store import iter_chunks
from core.memoria.long import add_fact, init_db as init_long_memory_db, search_facts
from core.memoria.profile import load_profile, set_preference
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

        if user_text.lower().startswith("/lembrar "):
            payload = user_text.split(" ", 1)[1].strip()
            key, value = self._parse_memory_payload(payload)
            add_fact(self.conn, key, value, tags="")
            return ReplyResult(text=f"Ok, vou lembrar: {key} = {value}", engine="fallback", debug="memory_add")

        if user_text.lower().startswith("/pref "):
            payload = user_text.split(" ", 1)[1].strip()
            key, value = self._parse_memory_payload(payload)
            set_preference(self.cfg, key, value)
            return ReplyResult(text=f"Preferencia salva: {key} = {value}", engine="fallback", debug="profile_set")

        self.mem.add("user", user_text)
        knowledge_hits = self._retrieve_knowledge(user_text)
        long_hits = self._retrieve_long_memory(user_text)

        if use_ollama and model:
            st = detect_ollama(self.cfg)
            if st.installed and st.running:
                prompt = self._build_prompt_for_ollama_rag(user_text, knowledge_hits, long_hits)
                try:
                    out = ollama_generate(self.cfg, model=model, prompt=prompt)
                    out = out.strip() or "(sem resposta do Ollama)"
                    self.mem.add("assistant", out)
                    dbg = "rag=1" if knowledge_hits else ""
                    return ReplyResult(text=out, engine="ollama", debug=dbg)
                except Exception as e:
                    # Fallback to local model if Ollama fails
                    pass

        # Try local fine-tuned model
        prompt = self._build_prompt_for_ollama_rag(user_text, knowledge_hits, long_hits)
        out = self._generate_with_local_model(prompt)
        if out:
            self.mem.add("assistant", out)
            return ReplyResult(text=out, engine="local_model", debug="finetuned")

        if knowledge_hits:
            best = knowledge_hits[0]
            out = (
                "Encontrei isto nos seus arquivos:\n"
                f"{best.chunk.text}\n\n"
                f"Fonte: {best.chunk.source}"
            )
            self.mem.add("assistant", out)
            dbg = f"rag_hit score={best.score:.3f} chunk_id={best.chunk.chunk_id}"
            return ReplyResult(text=out, engine="fallback", debug=dbg)

        if long_hits:
            best = long_hits[0]
            out = f"Memoria longa: {best.key} = {best.value}"
            self.mem.add("assistant", out)
            return ReplyResult(text=out, engine="fallback", debug="long_memory_hit")

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
        self._log_pending_question(user_text)
        out = (
            "Ainda nao tenho um treino bom pra isso.\n"
            "Voce pode me ensinar: va em 'Treino incremental' e salve um exemplo (pergunta -> resposta).\n"
            f"(exemplos salvos: {n})\n"
            "Salvei sua pergunta para treino futuro."
        )
        self.mem.add("assistant", out)
        return ReplyResult(text=out, engine="fallback", debug="no_hits")

    def _log_pending_question(self, user_text: str) -> None:
        try:
            path = treinos_dir(self.cfg) / "treino_pendentes.jsonl"
            payload = {"messages": [{"role": "user", "content": user_text}]}
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

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
        Otherwise, uses local BLIP model for image captioning.
        """

        user_text = (user_text or "").strip() or f"Descreva a {image_hint}."

        self.mem.add("user", user_text)

        if use_ollama and model:
            st = detect_ollama(self.cfg)
            if st.installed and st.running:
                prompt = self._build_prompt_for_ollama_rag(user_text, [])
                try:
                    out = ollama_generate(self.cfg, model=model, prompt=prompt, images=[image_png])
                    out = out.strip() or "(sem resposta do Ollama)"
                    self.mem.add("assistant", out)
                    return ReplyResult(text=out, engine="ollama", debug="image=1")
                except Exception as e:
                    # Fallback to local vision model if Ollama fails
                    pass

        # Fallback: use local BLIP model for image captioning
        out = self._generate_caption_with_local_model(image_png, user_text)
        if out:
            self.mem.add("assistant", out)
            return ReplyResult(text=out, engine="local_vision", debug="image_caption")

        out = (
            "Recebi a imagem, mas não consegui interpretar (Ollama offline e modelo local falhou).\n"
            "Verifique se o Ollama está rodando ou se há problemas com o modelo de visão."
        )
        self.mem.add("assistant", out)
        return ReplyResult(text=out, engine="fallback", debug="image_no_model")

    def _build_prompt_for_ollama(self, user_text: str) -> str:
        system = (
            "Você é um assistente local. Responda em português. Seja direto e útil. "
            "Se faltar informação, faça perguntas curtas."
        )
        # Include session context
        ctx = self.mem.as_prompt(system_preamble=system)
        return ctx + f"\n[user]\n{user_text}\n\n[assistant]\n"

    def _build_prompt_for_ollama_with_knowledge(self, user_text: str, knowledge_hits) -> str:
        system = (
            "Você é um assistente local. Responda em português. Seja direto e útil. "
            "Se faltar informação, faça perguntas curtas."
        )
        ctx = self.mem.as_prompt(system_preamble=system)
        rag = ""
        if knowledge_hits:
            chunks = "\n\n".join(
                f"[{i+1}] {h.chunk.text}\n(Fonte: {h.chunk.source})" for i, h in enumerate(knowledge_hits)
            )
            rag = "\n\n[contexto]\nUse as evidencias abaixo, sem inventar fatos:\n" + chunks
        return ctx + rag + f"\n\n[user]\n{user_text}\n\n[assistant]\n"

    def _build_prompt_for_ollama_rag(self, user_text: str, knowledge_hits, long_hits) -> str:
        system = (
            "Voce e um assistente local. Responda em portugues. Seja direto e util. "
            "Se faltar informacao, faca perguntas curtas."
        )
        ctx = self.mem.as_prompt(system_preamble=system)
        rag = ""
        if knowledge_hits:
            chunks = "\n\n".join(
                f"[{i+1}] {h.chunk.text}\n(Fonte: {h.chunk.source})" for i, h in enumerate(knowledge_hits)
            )
            rag = "\n\n[contexto]\nUse as evidencias abaixo, sem inventar fatos:\n" + chunks
        profile = load_profile(self.cfg).data
        prof_txt = ""
        if profile:
            prof_txt = "\n\n[perfil]\n" + json.dumps(profile, ensure_ascii=False)
        mem_txt = ""
        if long_hits:
            mem_txt = "\n\n[memoria_longa]\n" + "\n".join(
                f"- {m.key}: {m.value}" for m in long_hits[:5]
            )
        return ctx + rag + prof_txt + mem_txt + f"\n\n[user]\n{user_text}\n\n[assistant]\n"

    def _retrieve_knowledge(self, query: str):
        backend = str(getattr(self.cfg, "knowledge_vector_backend", "tfidf") or "tfidf").lower()
        if backend == "chroma":
            try:
                hits = query_chunks(self.cfg, query)
                if hits:
                    return hits
            except Exception:
                pass

        try:
            hits = retrieve_with_vector_index(query, self.cfg)
            if hits:
                return hits
        except Exception:
            pass

        cfg = KnowledgeRetrievalConfig(
            topk=self.cfg.knowledge_topk,
            min_score=self.cfg.knowledge_min_score,
        )
        chunks = list(iter_chunks(self.conn))
        if not chunks:
            return []
        return retrieve_chunks(query, chunks, cfg)

    def _retrieve_long_memory(self, query: str):
        try:
            init_long_memory_db(self.conn)
        except Exception:
            pass
        return search_facts(self.conn, query, limit=5)

    @staticmethod
    def _parse_memory_payload(payload: str) -> tuple[str, str]:
        if "=" in payload:
            k, v = payload.split("=", 1)
            return k.strip(), v.strip()
        return "nota", payload.strip()

    def _generate_with_local_model(self, prompt: str) -> str:
        """Generate response using local fine-tuned model if available."""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel
        except ImportError:
            return ""

        model_path = Path(__file__).resolve().parents[2] / "models" / "conversa_finetuned"
        if not model_path.exists():
            return ""

        try:
            # Load base model (assuming GPT-2)
            base_model_name = "gpt2"
            tokenizer = AutoTokenizer.from_pretrained(str(model_path))
            base_model = AutoModelForCausalLM.from_pretrained(base_model_name)
            model = PeftModel.from_pretrained(base_model, str(model_path))
            model.eval()
            print("Modelo local carregado com sucesso")  # Debug

            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=100,
                    do_sample=True,
                    temperature=0.7,
                    pad_token_id=tokenizer.eos_token_id
                )
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Remove the prompt from response
            if response.startswith(prompt):
                response = response[len(prompt):].strip()
            return response
        except Exception:
            return ""

    def _generate_caption_with_local_model(self, image_png: bytes, user_text: str) -> str:
        """Generate image caption using local BLIP model."""
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            from PIL import Image
            import io
        except ImportError:
            return ""

        try:
            # Load model (cached locally)
            processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            model.eval()

            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_png)).convert("RGB")

            # Process based on user_text
            if "descreva" in user_text.lower() or "describe" in user_text.lower():
                # Generate caption
                inputs = processor(image, return_tensors="pt")
                out = model.generate(**inputs, max_new_tokens=50)
                caption = processor.decode(out[0], skip_special_tokens=True)
                return f"A imagem mostra: {caption}"
            else:
                # For other queries, generate a relevant caption
                inputs = processor(image, text=user_text, return_tensors="pt")
                out = model.generate(**inputs, max_new_tokens=50)
                caption = processor.decode(out[0], skip_special_tokens=True)
                return caption
        except Exception as e:
            return f"Erro ao processar imagem localmente: {str(e)}"

