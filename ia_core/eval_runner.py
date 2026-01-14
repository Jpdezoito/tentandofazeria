from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter


@dataclass(frozen=True)
class EvalResult:
    question: str
    answer: str
    engine: str
    elapsed_ms: float
    has_source: bool
    answer_len: int
    answer_tokens: int
    contains_uncertainty: bool
    support_score: float
    support_hit: bool
    created_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _token_overlap(a: str, b: str) -> float:
    at = set((a or "").lower().split())
    bt = set((b or "").lower().split())
    if not at or not bt:
        return 0.0
    inter = len(at & bt)
    union = len(at | bt)
    return float(inter / union) if union else 0.0


def _support_from_knowledge(question: str, answer: str, knowledge_db: Path | None) -> tuple[float, bool]:
    if not knowledge_db or not knowledge_db.exists():
        return 0.0, False

    try:
        import sqlite3

        from rna_de_conversa.core.config import AppConfig
        from rna_de_conversa.core.knowledge.retrieval import KnowledgeRetrievalConfig, retrieve_chunks
        from rna_de_conversa.core.knowledge.store import iter_chunks
    except Exception:
        return 0.0, False

    try:
        conn = sqlite3.connect(str(knowledge_db))
        conn.row_factory = sqlite3.Row
    except Exception:
        return 0.0, False

    try:
        cfg = AppConfig()
        chunks = list(iter_chunks(conn))
        if not chunks:
            return 0.0, False
        hits = retrieve_chunks(
            question,
            chunks,
            KnowledgeRetrievalConfig(topk=cfg.knowledge_topk, min_score=cfg.knowledge_min_score),
        )
        if not hits:
            return 0.0, False
        best = hits[0].chunk.text
        score = _token_overlap(answer, best)
        return float(score), bool(score >= 0.08)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_eval(
    questions_path: Path,
    chat_cli: Path,
    *,
    cwd: Path,
    out_path: Path,
    knowledge_db: Path | None = None,
) -> list[EvalResult]:
    if not questions_path.exists():
        raise FileNotFoundError(f"Nao achei: {questions_path}")

    results: list[EvalResult] = []
    lines = questions_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        s = (line or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            obj = {"question": s}
        q = str(obj.get("question") or "").strip()
        if not q:
            continue

        t0 = perf_counter()
        proc = subprocess.run(
            [sys.executable, str(chat_cli), "--text", q],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        elapsed_ms = (perf_counter() - t0) * 1000.0
        raw = (proc.stdout or "").strip()
        answer = ""
        engine = ""
        if proc.returncode == 0 and raw:
            try:
                data = json.loads(raw)
                answer = str(data.get("text") or "")
                engine = str(data.get("engine") or "")
            except Exception:
                answer = raw
        has_source = "Fonte:" in answer
        answer_len = len(answer or "")
        answer_tokens = len((answer or "").split())
        lower = (answer or "").lower()
        contains_uncertainty = any(
            p in lower
            for p in [
                "nao sei",
                "não sei",
                "talvez",
                "posso estar errado",
                "posso estar enganado",
                "nao tenho certeza",
                "não tenho certeza",
            ]
        )
        support_score, support_hit = _support_from_knowledge(q, answer, knowledge_db)
        results.append(
            EvalResult(
                question=q,
                answer=answer,
                engine=engine,
                elapsed_ms=float(elapsed_ms),
                has_source=bool(has_source),
                answer_len=int(answer_len),
                answer_tokens=int(answer_tokens),
                contains_uncertainty=bool(contains_uncertainty),
                support_score=float(support_score),
                support_hit=bool(support_hit),
                created_at=utc_now_iso(),
            )
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "question": r.question,
                        "answer": r.answer,
                        "engine": r.engine,
                        "elapsed_ms": r.elapsed_ms,
                        "has_source": r.has_source,
                        "answer_len": r.answer_len,
                        "answer_tokens": r.answer_tokens,
                        "contains_uncertainty": r.contains_uncertainty,
                        "support_score": r.support_score,
                        "support_hit": r.support_hit,
                        "created_at": r.created_at,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return results
