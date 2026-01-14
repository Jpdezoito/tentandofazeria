# RNA (Assistente local Windows)

Assistente local em **Python 3.12** para Windows 10/11 que entende comandos em português do tipo **"abrir X"** / **"executar X"**, faz busca por apps/arquivos/pastas seguindo uma ordem padronizada e abre o item encontrado.

## Recursos

- Parsing de comandos em PT-BR (somente intenções seguras: abrir/executar).
- Normalização (lower, remove acentos, remove stopwords).
- Indexação local persistida (SQLite) com reindexação incremental.
- NÃO faz indexação completa no startup.
- Busca fuzzy (RapidFuzz se disponível; fallback para difflib).
- Ranking por:
  - preferência aprendida (quando você escolhe um item)
  - alias exato
  - fuzzy score
  - uso recente/frequente
  - fonte (Desktop/Start Menu com peso maior)
- GUI Tkinter com:
  - campo de entrada
  - botões Executar / Indexar-Reindexar / Cancelar
  - logs ao vivo (diretórios visitados, status, erros)
  - lista de resultados (duplo clique para abrir)
- “Modo treinamento” incremental:
  - salva preferência por comando normalizado em `data/stats.json`
  - registra contagem e última abertura

## Estrutura

- `app/` GUI Tkinter
- `core/` parser, normalização, indexação, busca, abertura
- `data/` `aliases.json`, `stats.json`, `index.db`
- `treinos/` (onde tudo é salvo: aliases/stats/índice/cache/logs)
- `tests/` testes unitários (pytest)
- `main.py` inicialização

## Instalação

Requisito: Python 3.12.

Opcional (melhor fuzzy e melhor resolução de atalhos):
- RapidFuzz (`rapidfuzz`)
- pywin32 (`pywin32`) para resolver `.lnk` via COM

Para rodar testes:
- pytest (`pytest`)

Se você tiver internet e quiser instalar (opcional):

```bash
pip install -r requirements.txt
```

> O app funciona sem RapidFuzz/pywin32 (usa fallbacks locais).

## Como rodar

Na pasta do projeto:

```bash
python main.py
```

No startup ele **não** indexa. Ao usar **Executar**, ele tenta:

- Camada 1: busca rápida (aliases/preferências + Desktop/pastas padrão + Start Menu + caminhos candidatos curtos)
- Camada 2: busca limitada (profundidade/timeout/limites, cancelável)
- Camada 3: se existir índice pronto, tenta usar; se não, pede autorização para indexar

## Como reindexar

Na GUI clique em **Indexar/Reindexar**.

> A indexação completa NUNCA roda automaticamente no startup.

- A indexação visita as pastas na ordem:
  1) Desktop do usuário
  2) Documentos / Downloads / Imagens / Vídeos
  3) Menu Iniciar (atalhos)
  4) Program Files / Program Files (x86)
  5) AppData (Roaming/Local)
  6) Drives locais (C:, D:, ...) com limites por tempo/quantidade

## Aliases (apelidos)

Edite `treino_rna_buscarpastas/treinos/aliases.json` (ou `treinos/aliases.json` dentro do projeto):

```json
{
  "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "meu jogo": "D:\\Games\\Valorant\\RiotClientServices.exe"
}
```

## Exemplos de comando

- `abrir chrome`
- `abrir o word`
- `executar discord`
- `abrir pasta downloads`
- `abrir arquivo planilha.xlsx`

## Observações de segurança

- O parser bloqueia comandos destrutivos (deletar/excluir/formatar/etc.).
- A execução é limitada a extensões configuradas em `core/config.py`.

