from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.rna_de_conversa.core.config import config_from_env, db_path
from src.rna_de_conversa.core.memoria.store import connect, iter_all, init_db

def main():
    cfg = config_from_env()
    conn = connect(db_path(cfg))
    init_db(conn)

    output_path = _ROOT / "treinos" / "conversa_finetune.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for ex in iter_all(conn):
            obj = {
                "instruction": ex.user_text,
                "output": ex.assistant_text,
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    conn.close()
    print(f"Exportados {output_path}")

if __name__ == "__main__":
    main()