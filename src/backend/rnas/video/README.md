# rna_de_video (RNA que aprende com vídeo)

Projeto local (Windows 10/11) em Python para uma “RNA” que **aprende com vídeo** de forma incremental.

Na prática, ele aprende assim:

1) Você adiciona vídeos (MP4/MKV/AVI/...) pela GUI.
2) O sistema amostra alguns frames do vídeo.
3) Você escolhe um **modo de treino** (no topo da GUI):
  - **Aparência (frames)**: embedding por frame + média
  - **Movimento (diferença)**: histograma da diferença entre frames
  - **Aparência + Movimento**: concatena os dois
  - **Cena (chave + aparência)**: tenta pegar keyframes por mudança de cena e faz média
  - **Áudio (ffmpeg)**: extrai áudio do vídeo e cria um embedding simples (energia + centróide espectral)
   
   Você também pode treinar por **trecho** usando os campos **Início(s)** e **Fim(s)** (em segundos).
4) O app salva um embedding do vídeo **por modo**.
4) Você rotula (cria classe / adiciona numa classe existente).
5) Clica em **Treinar agora**: o classificador por **centróides** atualiza as classes aprendidas.

## Persistência (tudo dentro de `rna_de_video/treinos/`)

- `dataset.db` (SQLite com vídeos e rótulos + embeddings por modo)
- `embeddings_cache/` (vetores `.npy` por vídeo e por modo)
- `model/centroids_<modo>.json` (um classificador por modo)
- `thresholds.json` (limiares para decidir “DESCONHECIDO”)

## Rodar

```powershell
python rna_de_video\main.py
```

## Dependências

Recomendado: **Python 3.10–3.12** (no Python 3.14 pode não existir wheel do `opencv-python`).

Instale o básico:

```powershell
pip install -r rna_de_video\requirements.txt
```

Obs.: no **Python 3.14**, o projeto usa `imageio+ffmpeg` para ler vídeos (porque o `opencv-python` pode ter conflitos de dependências). Em Pythons mais antigos, o OpenCV pode ser usado normalmente.

### Observação sobre “qualidade do aprendizado”

- Sem TensorFlow, o projeto roda com um fallback simples (histograma de cores). Funciona, mas a qualidade é menor.
- No Windows nativo, o `pip install tensorflow` costuma falhar (não há wheels oficiais no PyPI). Nesse caso, siga sem TensorFlow (fallback) ou use WSL2/Linux para habilitar TensorFlow.
- Com TensorFlow + pesos do ResNet50 no cache local do Keras (em plataformas suportadas), o embedding melhora bastante.
- O modo **Áudio** precisa do `ffmpeg` instalado e disponível no `PATH`.

## Dicas de uso

- Comece com 5–20 vídeos por classe.
- Para treinar por trecho, preencha **Início(s)** e **Fim(s)** e use **Salvar trecho do vídeo atual** para criar vários exemplos do mesmo vídeo.
- Os rótulos agora são por **exemplo** (modo + trecho). Assim, trechos diferentes do mesmo vídeo podem virar classes diferentes.
- Para vídeos online, use **Adicionar por URL** (o arquivo baixa para `treinos/imported_videos/`).
  - Link direto (`.mp4`, `.mkv`...): baixa com downloader simples.
  - YouTube / links não-diretos: precisa de `yt-dlp` (`pip install yt-dlp`).
- Se aparecer **DESCONHECIDO**, você pode:
  - criar uma classe nova
  - colocar em uma classe existente
  - mandar para cluster provisório e revisar depois

## Limitações (por design, por enquanto)

- Isso não faz “treino de rede profunda do zero” (fine-tuning pesado). É incremental e leve: embeddings + centróides.
- Para aprender ações complexas, às vezes você precisa de mais classes e mais variedade de vídeos.
