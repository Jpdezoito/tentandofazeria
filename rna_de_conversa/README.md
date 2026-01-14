# rna_de_conversa (RNA de Conversa)

Projeto local (Windows 10/11, Python 3.14) para uma **RNA de conversa** com:

- **Modo conversa** com memória curta (contexto da sessão)
- **Treino incremental local** (a partir de textos/diálogos)
- Persistência **somente dentro** de `rna_de_conversa/treinos/`
- GUI em **Tkinter** com logs ao vivo
- Integração opcional com **Ollama** (modelos locais), com fallback offline

## Persistência

Tudo fica em:

- `rna_de_conversa/treinos/`
  - `conversa.db` (SQLite: exemplos/perguntas-respostas)
  - `settings.json`
  - `importar/` (coloque aqui `.txt`/`.jsonl` para importar em lote)

## Rodar

```powershell
python rna_de_conversa\main.py
```

Ou pelo hub:

```powershell
python main_ia.py
```

## RAG (conhecimento por arquivos)

Para transformar arquivos em conhecimento consultavel:

```powershell
python rna_de_conversa\tools\cli_ingest.py --path C:\caminho\para\pasta_ou_arquivo
```

Formatos aceitos: `.txt`, `.md`, `.json`, `.jsonl`, `.yaml`, `.yml`, `.py`, `.log`, `.csv`, `.html`, `.htm`, `.zip`.
PDF e suportado se `PyPDF2` estiver instalado.

## Memoria longa e perfil

Comandos no chat:

- `/lembrar chave=valor`
- `/pref chave=valor`

## Ollama (opcional)

O app:
- detecta se o Ollama está instalado e rodando
- lista modelos disponíveis
- deixa você escolher um modelo e gerar resposta
- se não houver Ollama, usa fallback local (retrieval + templates)

Dica: se você instalar o Ollama e tiver um modelo baixado (ex.: `llama3`, `mistral`), clique em **Atualizar modelos** na GUI.

## Multimodal (Áudio e Visão)

A GUI tem abas **Áudio** e **Visão**.

- **Visão**: capturar **tela** (Pillow) e **webcam** (opencv-python) e enviar imagem para o Ollama.
- **Áudio**: gravar microfone (sounddevice + numpy), transcrever offline (vosk) e falar resposta (pyttsx3).

Essas dependências são opcionais: se não estiverem instaladas, o app mostra um erro explicando o que instalar.

### Instalar dependências opcionais (se quiser usar)

```powershell
pip install pillow opencv-python sounddevice numpy vosk pyttsx3
```

### Vosk (transcrição offline)

- Baixe um modelo Vosk (pt-BR, por exemplo) e coloque a pasta do modelo em:
  - `rna_de_conversa/treinos/vosk_model/`

Obs.: o app procura o modelo exatamente nesse caminho.

### Ollama com imagem

Para descrever tela/webcam, use um modelo multimodal no Ollama (ex.: `llava`). Modelos só-texto não vão “ver” a imagem.

## Importar treinos extras

- Coloque arquivos em `rna_de_conversa/treinos/importar/` e use o botão **Importar pasta**.

Formatos aceitos:

### TXT

Pares em blocos de 2 linhas (separados por linha em branco é ok):

```
usuario: oi
assistente: olá! como posso ajudar?

usuario: quem é você?
assistente: sou uma IA local.
```

### JSONL

Cada linha um JSON:

```json
{"user": "oi", "assistant": "olá"}
```
