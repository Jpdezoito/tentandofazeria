# ianova

Sistema de IA Conversacional com RNA - Versão Simplificada

## 📁 Estrutura do Projeto

```
ianova/
├── src/
│   ├── core/              # Componentes core
│   │   ├── rna.py        # Lógica da RNA
│   │   ├── avaliador.py  # Avaliação de respostas
│   │   └── ui_components.py # Componentes UI
│   ├── ui/
│   │   └── ia_principal/ # Interface gráfica principal
│   └── config/
│       └── settings.py   # Configurações
├── data/
│   ├── raw/              # Dados de entrada
│   └── models/           # Modelos treinados
├── main.py               # Ponto de entrada
├── requirements.txt      # Dependências
├── Dockerfile            # Container Docker
└── README.md
```

## 🚀 Execução com Docker (Recomendado)

### Pré-requisitos
- Docker e Docker Compose instalados

### Início Rápido
```bash
# Construir e iniciar
docker-compose up --build

# Ou usar script helper (Windows)
docker-run.bat up
```

## 📦 Instalação Manual

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar
python main.py
```

## 🎯 Características

- **RNA Conversacional**: Sistema de IA baseado em GPT-2 com fine-tuning
- **Interface Gráfica**: GUI moderna com CustomTkinter
- **Avaliação Automática**: Sistema de avaliação de coerência
- **Suporte Docker**: Execução containerizada
- **RAG**: Retrieval-Augmented Generation (opcional)

## 📄 Licença

Este projeto é open source e está disponível sob a licença MIT.
