import json
import random

# Lista de perguntas e respostas em PT-BR para treinar a RNA de conversa
perguntas_base = [
    "Olá, como você está?",
    "Qual é o seu nome?",
    "O que você pode fazer?",
    "Me ajude com uma tarefa.",
    "Conte uma piada.",
    "Qual é o clima hoje?",
    "Explique algo complexo.",
    "Recomende uma música.",
    "Como tocar música no computador?",
    "Busque informações sobre um tópico.",
    "Abra um site.",
    "Responda a uma pergunta geral.",
    "Dê conselhos.",
    "Traduza uma frase.",
    "Calcule algo.",
    "Jogue um jogo.",
    "Lembre-me de algo.",
    "Envie uma mensagem.",
    "Edite um arquivo.",
    "Execute um comando.",
    "O que é IA?",
    "Como funciona a internet?",
    "Qual é a capital do Brasil?",
    "Me diga uma receita simples.",
    "Explique a teoria da relatividade.",
    "Qual é o maior planeta?",
    "Como aprender programação?",
    "Recomende um filme.",
    "O que é sustentabilidade?",
    "Me ajude a resolver um problema matemático.",
    "Conte uma história curta.",
    "Qual é a diferença entre CPU e GPU?",
    "Como fazer backup de dados?",
    "O que é blockchain?",
    "Recomende livros para ler.",
    "Explique o aquecimento global.",
    "Como criar uma senha segura?",
    "O que é machine learning?",
    "Me dê dicas de saúde.",
    "Como organizar o tempo?",
    "Explique a fotosíntese.",
    "Qual é o maior oceano?",
    "Como fazer compostagem?",
    "O que é economia circular?",
    "Recomende exercícios físicos.",
    "Explique a evolução.",
    "Como investir em ações?",
    "O que é realidade virtual?",
    "Me ajude com um plano de estudos.",
    "Como reduzir o estresse?",
]

respostas_base = [
    "Olá! Estou bem, obrigado por perguntar. Como posso ajudar?",
    "Meu nome é IA Principal, seu assistente inteligente.",
    "Posso ajudar com tarefas, responder perguntas, tocar música, buscar informações e muito mais.",
    "Claro, me diga o que precisa.",
    "Por que o computador foi ao médico? Porque tinha um vírus!",
    "Desculpe, não tenho acesso ao clima em tempo real, mas posso sugerir verificar um site de meteorologia.",
    "Vou explicar de forma simples: [explicação].",
    "Recomendo 'Bohemian Rhapsody' do Queen.",
    "Para tocar música, diga 'tocar música' e escolha local ou online.",
    "Buscando... Encontrei informações sobre [tópico].",
    "Abrindo [site].",
    "A resposta é [resposta].",
    "Meu conselho: [conselho].",
    "A tradução é: [tradução].",
    "O resultado é [cálculo].",
    "Vamos jogar! Pense em um número entre 1 e 10.",
    "Lembrarei disso para você.",
    "Mensagem enviada.",
    "Arquivo editado com sucesso.",
    "Comando executado.",
    "IA é Inteligência Artificial, sistemas que simulam inteligência humana.",
    "A internet é uma rede global de computadores conectados.",
    "A capital do Brasil é Brasília.",
    "Uma receita simples: macarrão com queijo.",
    "A teoria da relatividade de Einstein explica espaço, tempo e gravidade.",
    "O maior planeta é Júpiter.",
    "Aprenda programação com Python, pratique diariamente.",
    "Recomendo 'Inception' de Christopher Nolan.",
    "Sustentabilidade é usar recursos sem esgotá-los.",
    "Para resolver x + 5 = 10, x = 5.",
    "Era uma vez um dragão que amava pizza...",
    "CPU processa instruções, GPU processa gráficos.",
    "Faça backup regularmente em nuvem ou HD externo.",
    "Blockchain é uma cadeia de blocos para transações seguras.",
    "Recomendo '1984' de George Orwell.",
    "Aquecimento global é o aumento da temperatura da Terra devido a gases.",
    "Use letras, números e símbolos, pelo menos 12 caracteres.",
    "Machine learning é IA que aprende com dados.",
    "Dicas: beba água, durma bem, exercite-se.",
    "Organize com listas de tarefas e prioridades.",
    "Fotosíntese é como plantas fazem comida com luz.",
    "O maior oceano é o Pacífico.",
    "Compostagem transforma lixo orgânico em adubo.",
    "Economia circular reutiliza recursos em loop.",
    "Exercícios: corrida, musculação, yoga.",
    "Evolução é mudança de espécies ao longo do tempo.",
    "Invista com pesquisa e diversificação.",
    "Realidade virtual é simulação imersiva.",
    "Plano: defina metas, divida em tópicos, revise.",
    "Reduza estresse com meditação e hobbies.",
]

# Gerar 10000 linhas de treino (para simulação, gerar 100 e multiplicar variações)
dados_treino = []
for i in range(10000):
    pergunta = random.choice(perguntas_base) + f" (variação {i})"
    resposta = random.choice(respostas_base) + f" Resposta única {i}."
    conversa = {
        "messages": [
            {"role": "user", "content": pergunta},
            {"role": "assistant", "content": resposta}
        ]
    }
    dados_treino.append(conversa)

# Salvar em JSONL
with open("conversa_treino.jsonl", "w", encoding="utf-8") as f:
    for item in dados_treino:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print("Arquivo conversa_treino.jsonl criado com 10000 conversas em PT-BR.")