# treino_rna_qualquer_imagem (RNA Open-World)

Projeto local (Windows 10/11) em Python para um sistema “RNA” que **aprende qualquer imagem** de forma incremental.

## Ideia

- Quando você adiciona uma imagem, o sistema extrai um **embedding** (vetor) com um backbone pré-treinado (ResNet/EfficientNet via Keras Applications quando disponível).
- Ele tenta classificar por similaridade com as classes já aprendidas.
- Se a confiança/similaridade for baixa, trata como **DESCONHECIDO** e você pode:
  - criar nova classe
  - adicionar a classe existente
  - enviar para **cluster provisório** (Classe_Nova_001, ...), para revisar depois

## Persistência (tudo dentro de `treinos/`)

A pasta do projeto é:

- `treino_rna_qualquer_imagem/`

E tudo que o sistema gera/aprende é salvo em:

- `treino_rna_qualquer_imagem/treinos/`
  - `dataset.db` (SQLite)
  - `embeddings_cache/` (vetores `.npy` por imagem)
  - `model/centroids.json` (estado do classificador)
  - `thresholds.json`
  - `logs/` (reservado)

## Instalação

Crie e ative uma venv (exemplo):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale dependências:

```powershell
pip install -r requirements.txt
```

### Importante (offline)

- Para embeddings bons, **TensorFlow** precisa estar instalado e os pesos do modelo precisam estar **no cache local do Keras**.
- Se os pesos não estiverem no cache, o projeto roda, mas usa pesos aleatórios (qualidade baixa).

## Rodar

```powershell
python main.py
```

## Uso

1) Clique em **Adicionar imagens** e selecione imagens.
  - Alternativa: clique em **Adicionar por URL/endereço** e cole um link `http(s)`, uma `data:image/...;base64,...` ou um caminho local (ex: `C:\\pasta\\foto.jpg`).
  - Imagens importadas por URL são salvas em `treinos/imported_images/`.
2) Veja o preview e os top-5 palpites.
3) Se aparecer **DESCONHECIDO**, use:
   - **Criar nova classe**
   - **Adicionar a classe existente**
   - **Enviar para cluster provisório**
4) Clique em **Treinar agora** para atualizar as classes aprendidas.

## Como funciona o “Desconhecido”

- O sistema usa um classificador por **centroides** (média dos embeddings por classe) e compara por **similaridade cosseno**.
- Se top-1 tiver:
  - `confiança < min_top1_confidence` ou
  - `similaridade < min_top1_similarity`

então vira DESCONHECIDO.

## Próximos upgrades (já previstos)

- Clustering com DBSCAN/HDBSCAN (quando `scikit-learn` estiver disponível)
- Métricas: acurácia em validação e matriz de confusão
- Fine-tuning leve do backbone (opcional)
