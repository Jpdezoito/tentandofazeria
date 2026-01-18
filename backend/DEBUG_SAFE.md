# Debug seguro (não queima o PC)

Este workspace tem módulos que podem consumir muito CPU/Disk (indexação de drive, leitura de vídeo/frames, embeddings com TensorFlow).
Para debugar sem travar a máquina, use o modo seguro via env var:

- `IANOVA_SAFE_DEBUG=1`

## O que muda com `IANOVA_SAFE_DEBUG=1`

- `treino_rna_buscarpastas`: desliga scan de drives (`enable_drive_scan=False`) e reduz limites/timeout.
- `rna_de_video`: força `backbone=fallback_hist` e reduz frames/timeout de download.
- `treino_rna_qualquer_imagem`: força `backbone=simple_histogram` e reduz `image_size`.
- `rna_de_conversa`: reduz turnos/topk e diminui timeout do Ollama.

## Rodar no VS Code (recomendado)

Use as configs em `.vscode/launch.json` com sufixo **SAFE DEBUG**.

## Dicas de debug (passo-a-passo)

1) Comece pelo entrypoint (main) do módulo.
2) Coloque breakpoint no `main()` e rode a config SAFE DEBUG.
3) Se o app abrir, avance para:
   - GUI: handlers `on_*` (cliques) em vez de deixar executar tudo no startup.
   - CLI: rode com args mínimos.
4) Se ainda ficar pesado:
   - Não clique em botões de treino/indexação completa.
   - No BuscarPastas, evite reindexar drives.
   - No Vídeo, use vídeos curtos e/ou trechos (`--start/--end`).

## Rodar via terminal (opcional)

PowerShell:

```powershell
$env:IANOVA_SAFE_DEBUG = "1"
python main_ia.py
```
