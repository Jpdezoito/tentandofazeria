# RNA Código

Módulo de Rede Neural para treinamento em tarefas de programação, incluindo geração de código, completamento e análise.

## Funcionalidades

- Treinamento de modelos de linguagem para código
- Geração de código Python/JavaScript/etc.
- Completamento inteligente de código
- Análise estática de código

## Instalação

```bash
pip install -e .
```

## Uso

### Treinamento

```bash
python main.py --extra ../ia_treinos/codigo/importar
```

### Inferência

```bash
python tools/cli_code.py "def fibonacci(n):"
```

## Estrutura

- `app/`: Interface gráfica
- `core/`: Lógica principal (config, modelos, treinamento)
- `tools/`: Ferramentas CLI
- `tests/`: Testes

## Modelos Suportados

- CodeLlama
- CodeGPT
- StarCoder
- Outros modelos de código open-source