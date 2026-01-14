# ianova

Arquitetura organizada para IA local com CLI unica, RAG e modulos separados.

## Estrutura sugerida

- `ia_core/` utilitarios comuns (config, eval, registry)
- `configs/` configs centralizadas
- `models/` registry de modelos (`models/index.json`)
- `eval/` perguntas e resultados de avaliacao
- `data/` dados brutos/limpos (opcional)
- `train/` wrappers de treino/ingestao
- `inference/` wrappers de inferencia
- Modulos existentes: `rna_de_conversa`, `rna_de_video`, `treino_rna_qualquer_imagem`, `treino_rna_buscarpastas`

## CLI unica

```powershell
python ia_cli.py chat --text "oi"
python ia_cli.py ingest --path C:\caminho\para\pasta
python ia_cli.py eval
```

### RAG com indice vetorial

O comando `ingest` agora atualiza um indice vetorial (TF-IDF) automaticamente:

```powershell
python ia_cli.py ingest --path C:\caminho\para\pasta
```

Requerencias: instale `scikit-learn` (veja rna_de_conversa/requirements.txt).

### Chroma (banco vetorial dedicado)

Para usar Chroma + embeddings, defina variavel de ambiente:

```
IANOVA_VECTOR_BACKEND=chroma
```

Opcionalmente, defina o modelo de embeddings:

```
IANOVA_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Para desativar a atualizacao do indice:

```powershell
python ia_cli.py ingest --path C:\caminho\para\pasta --no-index
```

Outros comandos:

```powershell
python ia_cli.py assistant --text "buscar: projeto"
python ia_cli.py search --query "texto"
python ia_cli.py image --path C:\img.jpg
python ia_cli.py index-image --path C:\img.jpg
python ia_cli.py video --path C:\video.mp4 --mode appearance
python ia_cli.py index-video --path C:\video.mp4 --mode appearance
python ia_cli.py train-images
python ia_cli.py import-conversa
python ia_cli.py register-model --name modeloX --task conversa --data-version v1 --path models/modeloX --metrics "{}"
python ia_cli.py register-dataset --name conversa_v1 --path data/conversa.jsonl --meta "{}"
python ia_cli.py finetune-lora --model nome/modelo --data data/conversa.jsonl --output models/lora_out
```

## Safety

Se quiser restringir caminhos que o assistente pode ler, edite `configs/app.json`:

```json
{
  "safety": {
    "allowed_roots": ["C:/Users/SeuUsuario/Documents"]
  }
}
```

### Permissoes por acao

No mesmo arquivo, voce pode controlar quais acoes estao liberadas e o modo de seguranca:

```json
{
  "permissions": {
    "mode": "safe",
    "actions": {
      "buscar": true,
      "imagem": true,
      "video": true,
      "audio": true,
      "chat": true
    }
  }
}
```

- `mode: safe` aplica restricoes de caminho + acoes.
- `mode: full` ignora restricoes (uso com cuidado).

## Memoria longa

No chat, use:

- `/lembrar chave=valor`
- `/pref tema=dark`
