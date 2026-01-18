from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


SYSTEM_PROMPTS = [
    "Você é uma assistente de IA útil, objetiva e educada.",
    "Responda em português brasileiro, com tom amigável e claro.",
    "Ajude o usuário a usar o app, com passos curtos quando necessário.",
    "Priorize respostas curtas e práticas, com linguagem simples.",
    "Evite inventar resultados; se algo depende de busca, diga que vai buscar.",
]


def _pick(rng: random.Random, items: list[str]) -> str:
    return items[rng.randrange(len(items))]


def _scenario_greeting(rng: random.Random) -> list[dict]:
    user = _pick(rng, ["oi", "olá", "bom dia", "boa tarde", "boa noite", "e aí"])
    assistant = _pick(
        rng,
        [
            "Oi! Em que posso ajudar hoje?",
            "Olá! Como posso ajudar?",
            "Tudo bem! O que voce precisa?",
            "Oi! Posso ajudar com algo agora?",
        ],
    )
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _scenario_help(rng: random.Random) -> list[dict]:
    user = _pick(
        rng,
        [
            "o que voce pode fazer",
            "me mostra comandos",
            "quais funcoes voce tem",
        ],
    )
    assistant = _pick(
        rng,
        [
            "Posso buscar arquivos, abrir resultados, tocar música e responder perguntas.",
            "Exemplos: /buscar <termo>, /abrir <número>, tocar música, abrir YouTube.",
            "Posso conversar, abrir arquivos e ajudar com tarefas do app.",
        ],
    )
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _scenario_help_followup(rng: random.Random) -> list[dict]:
    return [
        {"role": "user", "content": "me mostra um exemplo"},
        {"role": "assistant", "content": "Exemplo: /buscar relatório, depois /abrir 1."},
    ]


def _scenario_search(rng: random.Random) -> list[dict]:
    term = _pick(rng, ["relatório", "música", "vídeo", "foto", "documento", "planilha"])
    assistant = _pick(
        rng,
        [
            f"Vou buscar por {term}. Se quiser, diga /abrir <número>.",
            f"Buscando {term}. Vou listar os resultados.",
        ],
    )
    return [{"role": "user", "content": f"/buscar {term}"}, {"role": "assistant", "content": assistant}]


def _scenario_open(rng: random.Random) -> list[dict]:
    idx = _pick(rng, ["1", "2", "3"])
    return [
        {"role": "user", "content": f"/abrir {idx}"},
        {"role": "assistant", "content": f"Abrindo o resultado {idx}."},
    ]


def _scenario_open_error(rng: random.Random) -> list[dict]:
    return [
        {"role": "user", "content": "/abrir 99"},
        {"role": "assistant", "content": "Número inválido. Tente um índice da lista."},
    ]


def _scenario_play_music(rng: random.Random) -> list[dict]:
    user = _pick(rng, ["tocar música", "tocar música local", "quero música"])
    assistant = _pick(
        rng,
        [
            "Quer tocar online (YouTube Music) ou local?",
            "Prefere música online ou arquivos locais?",
        ],
    )
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _scenario_play_all(rng: random.Random) -> list[dict]:
    return [
        {"role": "user", "content": "tocar todas"},
        {"role": "assistant", "content": "Tocando todas as músicas em sequência."},
    ]


def _scenario_control_audio(rng: random.Random) -> list[dict]:
    user = _pick(rng, ["pausar música", "parar música", "próxima música", "música anterior"])
    assistant = _pick(
        rng,
        [
            "Ok, ajustei o controle de áudio.",
            "Feito. Se quiser retomar, use Play.",
        ],
    )
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _scenario_youtube(rng: random.Random) -> list[dict]:
    query = _pick(rng, ["lofi hip hop", "tutorial python", "música relaxante"])
    return [
        {"role": "user", "content": f"tocar {query}"},
        {"role": "assistant", "content": f"Buscando e tocando '{query}' no YouTube."},
    ]


def _scenario_youtube_url(rng: random.Random) -> list[dict]:
    url = _pick(
        rng,
        [
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=5qap5aO4i9A",
            "https://www.youtube.com/watch?v=jfKfPfyJRdk",
        ],
    )
    return [
        {"role": "user", "content": f"/yt {url}"},
        {"role": "assistant", "content": "Vou processar esse video do YouTube."},
    ]


def _scenario_settings(rng: random.Random) -> list[dict]:
    user = _pick(rng, ["abrir configurações", "trocar modelo", "mudar modelo"])
    assistant = _pick(
        rng,
        [
            "Abrindo configurações.",
            "Qual modelo voce quer usar?",
        ],
    )
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _scenario_smalltalk(rng: random.Random) -> list[dict]:
    user = _pick(rng, ["como você está", "tudo bem", "você é legal"])
    assistant = _pick(
        rng,
        [
            "Estou bem! Posso ajudar em algo?",
            "Tudo certo por aqui. Em que posso ajudar?",
            "Obrigado! Estou aqui para ajudar.",
        ],
    )
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _scenario_task(rng: random.Random) -> list[dict]:
    user = _pick(
        rng,
        [
            "me ajuda a organizar meus arquivos",
            "como faço para abrir um arquivo",
            "como buscar por documentos",
        ],
    )
    assistant = _pick(
        rng,
        [
            "Use /buscar <termo> e depois /abrir <número> para abrir.",
            "Digite /buscar seguido do termo e eu mostro os resultados.",
            "Posso buscar por nome e abrir direto. Quer tentar agora?",
        ],
    )
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _scenario_time_date(rng: random.Random) -> list[dict]:
    user = _pick(rng, ["que horas são", "qual a data de hoje", "me fala a hora"])
    assistant = _pick(
        rng,
        [
            "Posso te mostrar a hora se você quiser.",
            "Quer que eu consulte a hora atual?",
        ],
    )
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _scenario_attach(rng: random.Random) -> list[dict]:
    return [
        {"role": "user", "content": "como anexo uma imagem"},
        {"role": "assistant", "content": "Clique no botão de anexo e escolha Imagem."},
    ]


def _scenario_error_generic(rng: random.Random) -> list[dict]:
    return [
        {"role": "user", "content": "deu erro ao abrir"},
        {"role": "assistant", "content": "Qual arquivo? Posso tentar abrir novamente."},
    ]


def _scenario_search_nothing(rng: random.Random) -> list[dict]:
    term = _pick(rng, ["arquivo_inexistente", "xxx_yyy", "nao sei"])
    return [
        {"role": "user", "content": f"/buscar {term}"},
        {"role": "assistant", "content": "Não encontrei resultados. Quer tentar outro termo?"},
    ]


def _scenario_followup_open(rng: random.Random) -> list[dict]:
    return [
        {"role": "user", "content": "abre o segundo"},
        {"role": "assistant", "content": "Para abrir, use /abrir 2."},
    ]


SCENARIOS = [
    _scenario_greeting,
    _scenario_help,
    _scenario_help_followup,
    _scenario_search,
    _scenario_search_nothing,
    _scenario_open,
    _scenario_open_error,
    _scenario_play_music,
    _scenario_play_all,
    _scenario_control_audio,
    _scenario_youtube,
    _scenario_youtube_url,
    _scenario_settings,
    _scenario_smalltalk,
    _scenario_task,
    _scenario_time_date,
    _scenario_attach,
    _scenario_error_generic,
    _scenario_followup_open,
]


def _build_dialog(rng: random.Random) -> list[dict]:
    dialog: list[dict] = []
    if rng.random() < 0.25:
        dialog.append({"role": "system", "content": _pick(rng, SYSTEM_PROMPTS)})
    dialog.extend(_pick(rng, SCENARIOS)(rng))
    if rng.random() < 0.2:
        dialog.extend(_scenario_help_followup(rng))
    if rng.random() < 0.2:
        dialog.extend(_scenario_followup_open(rng))
    if rng.random() < 0.25:
        dialog.extend(_scenario_open(rng))
    return dialog


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-jsonl", required=True)
    ap.add_argument("--out-txt", required=True)
    ap.add_argument("--lines", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    out_jsonl = Path(args.out_jsonl).expanduser().resolve()
    out_txt = Path(args.out_txt).expanduser().resolve()
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    with out_jsonl.open("w", encoding="utf-8") as f_jsonl, out_txt.open("w", encoding="utf-8") as f_txt:
        for _ in range(int(args.lines)):
            messages = _build_dialog(rng)
            f_jsonl.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")

            for msg in messages:
                role = msg.get("role", "").strip().lower()
                content = str(msg.get("content") or "").strip()
                if not content:
                    continue
                if role == "system":
                    f_txt.write(f"Sistema: {content}\n")
                elif role == "assistant":
                    f_txt.write(f"Assistente: {content}\n")
                else:
                    f_txt.write(f"Usuário: {content}\n")
            f_txt.write("----\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
