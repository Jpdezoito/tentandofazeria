# Exemplos de Uso - ianova

Este arquivo contém exemplos práticos de como usar o ianova.

## Comandos Básicos

### Chat Simples
```
Olá! Como você está?
Qual é a capital do Brasil?
Me explique o que é inteligência artificial
```

### Buscar Arquivos (/buscar)
```
/buscar documento.pdf
/buscar relatorio
/buscar foto.jpg
/buscar apresentacao
```

### Abrir Arquivos (/abrir)
```
/abrir C:\Users\SeuUsuario\Documents\arquivo.txt
/abrir "C:\Arquivos de Programas\pasta\documento.pdf"
/abrir ~/Documents/notas.txt
```

### Abrir Páginas Web (/web)
```
/web google.com
/web https://github.com
/web youtube.com
/web https://www.wikipedia.org
```

### Ajuda
```
/ajuda
```

## Usando Anexos (📎)

### Análise de Imagem

1. Clique no botão 📎
2. Selecione uma imagem (PNG, JPG, JPEG, BMP, GIF)
3. Exemplos de perguntas:
   - "Descreva esta imagem"
   - "Quais objetos você vê nesta foto?"
   - "Qual é a resolução desta imagem?"

### Análise de Vídeo

1. Clique no botão 📎
2. Selecione um vídeo (MP4, AVI, MOV)
3. Exemplos de perguntas:
   - "Quantos frames tem este vídeo?"
   - "Qual a duração deste vídeo?"
   - "Analise o conteúdo deste vídeo"

### Processamento de Áudio

1. Clique no botão 📎
2. Selecione um arquivo de áudio (WAV, MP3)
3. O sistema processará o áudio (reconhecimento de voz se Vosk estiver instalado)

## Fluxos de Trabalho Típicos

### Fluxo 1: Buscar e Abrir Arquivo
```
1. /buscar relatorio_vendas.xlsx
2. (Veja os resultados)
3. /abrir C:\Users\SeuUsuario\Documents\relatorio_vendas.xlsx
```

### Fluxo 2: Pesquisar na Web
```
1. Me explique sobre machine learning
2. (Leia a resposta da IA)
3. /web https://en.wikipedia.org/wiki/Machine_learning
```

### Fluxo 3: Análise de Imagens
```
1. Clique em 📎 e selecione uma foto
2. "Esta imagem mostra o quê?"
3. (Receba análise detalhada)
4. "Qual a resolução?"
```

### Fluxo 4: Análise de Vídeo
```
1. Clique em 📎 e selecione um vídeo
2. "Analise este vídeo"
3. (Receba informações sobre duração, frames, resolução)
4. "Quantos FPS tem este vídeo?"
```

## Dicas e Truques

### Melhorando as Respostas do Chat
- Seja específico nas suas perguntas
- Forneça contexto quando necessário
- Use linguagem clara e direta

### Organizando Arquivos
- Use /buscar para encontrar arquivos rapidamente
- Mantenha uma estrutura de pastas organizada
- Use nomes de arquivo descritivos

### Trabalhando com Imagens
- Formatos suportados: PNG, JPG, JPEG, BMP, GIF
- O sistema fornece informações sobre dimensões e formato
- Faça perguntas específicas sobre o conteúdo

### Trabalhando com Vídeos
- Formatos suportados: MP4, AVI, MOV
- O sistema analisa frames, FPS e duração
- Use para classificação e aprendizado de vídeo

## Configurações Avançadas

### Alterar Modelo Ollama
1. Clique em ⚙️ Configurações
2. Altere o campo "Modelo" (ex: llama2, mistral, codellama)
3. Clique em Salvar

### Alterar URL do Ollama
1. Clique em ⚙️ Configurações
2. Altere "URL do Ollama" se estiver em outra máquina
3. Exemplo: http://192.168.1.100:11434
4. Clique em Salvar

## Solução de Problemas Comuns

### Problema: Ollama não responde
**Solução:**
```bash
# Verifique se o Ollama está rodando
ollama serve

# Em outro terminal, verifique se o modelo está disponível
ollama list

# Se não tiver o modelo, baixe
ollama pull llama2
```

### Problema: Erro ao processar imagem
**Solução:**
```bash
# Instale ou reinstale Pillow
pip install --upgrade Pillow
```

### Problema: Erro ao processar vídeo
**Solução:**
```bash
# Instale ou reinstale OpenCV
pip install --upgrade opencv-python
```

### Problema: Busca não encontra arquivos
**Verificações:**
- O arquivo está em Documents, Downloads ou Desktop?
- O nome do arquivo contém o termo de busca?
- Você tem permissão para acessar a pasta?

## Casos de Uso Reais

### Caso 1: Pesquisador
```
1. /buscar artigo_neurociencia.pdf
2. /abrir [caminho do arquivo]
3. "Resuma os principais pontos sobre neuroplasticidade"
```

### Caso 2: Designer
```
1. 📎 Selecionar mockup.png
2. "Analise as cores e composição desta imagem"
3. "Sugira melhorias no design"
```

### Caso 3: Estudante
```
1. "Explique o teorema de Pitágoras"
2. /web https://pt.wikipedia.org/wiki/Teorema_de_Pitágoras
3. "Dê exemplos práticos de aplicação"
```

### Caso 4: Analista de Vídeo
```
1. 📎 Selecionar video_treinamento.mp4
2. "Qual a qualidade deste vídeo?"
3. "Quantos frames por segundo?"
```

## Recursos Futuros (Planejados)

- ✅ Chat com IA local (Ollama)
- ✅ Reconhecimento de imagem
- ✅ Análise de vídeo
- ✅ Busca em pastas
- ✅ Comandos especiais
- ⏳ Reconhecimento de voz com Vosk
- ⏳ Transcrição de áudio
- ⏳ Histórico de conversas
- ⏳ Export de conversas
- ⏳ Temas personalizáveis

## Suporte

Para problemas ou sugestões:
1. Abra uma issue no GitHub
2. Descreva o problema detalhadamente
3. Inclua logs de erro se disponíveis
4. Informe sua versão do Python e sistema operacional
