# ianova - Hub de IAs Locais 🤖

**ianova** é um hub de inteligência artificial local desenvolvido em Python com interface Tkinter para Windows. O aplicativo integra múltiplas funcionalidades de IA incluindo chat com modelos locais (Ollama), reconhecimento de imagem, classificação de vídeo e busca em pastas.

## 🌟 Características

- **💬 Chat com IA Local**: Integração com Ollama para conversação com modelos de linguagem
- **🖼️ Reconhecimento de Imagem**: Análise de imagens com informações detalhadas
- **🎥 Classificação de Vídeo**: Processamento e análise de vídeos
- **🎤 Reconhecimento de Voz**: Suporte opcional para Vosk
- **📁 Busca em Pastas**: Busca rápida de arquivos no sistema
- **📎 Anexos**: Envie imagens, vídeos e áudio diretamente pela interface
- **⚡ Comandos Especiais**: 
  - `/buscar <termo>` - Busca arquivos no sistema
  - `/abrir <arquivo>` - Abre um arquivo
  - `/web <url>` - Abre URLs no navegador
  - `/ajuda` - Mostra ajuda

## 📋 Requisitos

- Python 3.8 ou superior
- Windows (recomendado) ou Linux/Mac
- [Ollama](https://ollama.ai/) instalado e rodando (para funcionalidade de chat)

## 🚀 Instalação

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/Jpdezoito/tentandofazeria.git
   cd tentandofazeria
   ```

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Instale e configure o Ollama:**
   - Baixe o Ollama em [https://ollama.ai/](https://ollama.ai/)
   - Instale e inicie o serviço:
     ```bash
     ollama serve
     ```
   - Baixe um modelo (ex: llama2):
     ```bash
     ollama pull llama2
     ```

## 💻 Uso

Execute o aplicativo com:

```bash
python ianova.py
```

### Interface Principal

- **Campo de entrada**: Digite suas mensagens ou comandos
- **Botão 📎**: Anexe imagens, vídeos ou áudio
- **Botão Enviar**: Envia a mensagem para processamento
- **⚙️ Configurações**: Configure URL do Ollama e modelo a usar

### Exemplos de Uso

#### Chat Simples
```
Olá, como você pode me ajudar?
```

#### Buscar Arquivos
```
/buscar relatório.pdf
/buscar foto
```

#### Abrir Arquivo
```
/abrir C:\Users\SeuUsuario\Documents\documento.txt
```

#### Abrir Página Web
```
/web google.com
/web https://github.com
```

#### Análise de Imagem
1. Clique no botão 📎
2. Selecione uma imagem
3. Digite uma pergunta sobre a imagem (opcional)
4. Clique em Enviar

#### Análise de Vídeo
1. Clique no botão 📎
2. Selecione um vídeo
3. Digite uma pergunta sobre o vídeo (opcional)
4. Clique em Enviar

## ⚙️ Configuração

As configurações são salvas automaticamente em `~/.ianova_config.json` e incluem:

- **URL do Ollama**: Padrão `http://localhost:11434`
- **Modelo**: Padrão `llama2`

Você pode alterar essas configurações clicando no botão ⚙️ Configurações na interface.

## 🔧 Dependências

### Obrigatórias
- `requests` - Para comunicação com Ollama
- `Pillow` - Para processamento de imagens
- `opencv-python` - Para processamento de vídeo
- `numpy` - Para operações numéricas

### Opcionais
- `vosk` - Para reconhecimento de voz (não obrigatório)

## 🐛 Solução de Problemas

### Ollama não conecta
- Certifique-se de que o Ollama está rodando: `ollama serve`
- Verifique se o modelo está instalado: `ollama list`
- Verifique a URL nas configurações

### Erro ao processar imagem/vídeo
- Verifique se as bibliotecas estão instaladas: `pip install Pillow opencv-python`
- Certifique-se de que o arquivo está em um formato suportado

### Busca não encontra arquivos
- A busca é limitada a Documents, Downloads e Desktop
- Verifique as permissões de acesso às pastas

## 📝 Estrutura do Projeto

```
tentandofazeria/
├── ianova.py           # Aplicação principal
├── requirements.txt    # Dependências Python
└── README.md          # Este arquivo
```

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

## 📄 Licença

Este projeto é open source e está disponível sob a licença MIT.

## 👨‍💻 Autor

Desenvolvido por Jpdezoito

## 🙏 Agradecimentos

- [Ollama](https://ollama.ai/) - Por fornecer modelos de IA locais
- [OpenCV](https://opencv.org/) - Para processamento de vídeo
- [Pillow](https://python-pillow.org/) - Para processamento de imagens