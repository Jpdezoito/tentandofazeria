# Checklist objetivo (IANOVA)

## Core / Arquitetura
- [x] Orquestrador unificado para chat/busca/imagem/video/audio
- [x] Separacao clara entre treino e inferencia
- [x] Config centralizada (configs/app.json)

## RAG / Conhecimento
- [x] Ingestao de TXT/MD/JSON/HTML/PDF/ZIP
- [x] Chunking configuravel
- [x] Indice vetorial (TF-IDF) persistente
- [x] Recuperacao por similaridade + fallback lexical
- [x] Banco vetorial dedicado (Chroma)

## Memoria
- [x] Memoria curta (sessao)
- [x] Memoria longa (SQLite)
- [x] Perfil/preferencias

## Ferramentas
- [x] BuscarPastas (search)
- [x] Classificar imagem
- [x] Classificar video
- [x] Indexar imagem/video como conhecimento

## Avaliacao / QA
- [x] CLI de avaliacao
- [x] Metricas basicas (tempo, fonte, tamanho, incerteza)
- [x] Metricas de suporte via conhecimento (overlap)

## Seguranca
- [x] Restricao por pasta (allowed_roots)
- [x] Permissao por acao (buscar/imagem/video/audio/chat)
- [x] Modo safe/full

## MLOps
- [x] Registro simples de modelos (models/index.json)
- [x] Registro de datasets com hash/contagem

## Fine-tuning
- [x] Pipeline LoRA/QLoRA (treino supervisionado)

## Vision/Video
- [x] Extracao/classificacao basica
- [x] OCR e captioning mais avancados
