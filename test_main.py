#!/usr/bin/env python3
"""
Script de teste para a RNA de conversa treinada.
Simula respostas contextuais e variadas baseadas no treino.
"""

import random

def simulate_response(pergunta):
    pergunta_lower = pergunta.lower()
    
    # Mapeamento de respostas contextuais
    respostas_contextuais = {
        "olá": ["Olá! Estou bem, obrigado. Como posso ajudar?", "Oi! Tudo ótimo por aqui. O que precisa?"],
        "como você está": ["Estou funcionando perfeitamente!", "Bem, obrigado por perguntar!"],
        "qual é o seu nome": ["Sou a IA Principal, sua assistente.", "Meu nome é IA Principal."],
        "o que você pode fazer": ["Posso responder perguntas, tocar música, abrir sites, executar comandos e muito mais.", "Ajudo com tarefas diversas: música, busca, cálculos, etc."],
        "conte uma piada": ["Por que o computador foi ao médico? Porque tinha um vírus!", "O que um peixe disse para o outro? Nada, peixes não falam!"],
        "recomende uma música": ["Recomendo 'Bohemian Rhapsody' do Queen.", "'Shape of You' do Ed Sheeran é ótima!"],
        "como tocar música": ["Diga 'tocar música' e escolha local ou online.", "No app, selecione música e toque!"],
        "qual é o clima": ["Não tenho acesso ao clima, mas sugiro checar um site.", "Verifique no Google Weather."],
        "explique": ["Vou explicar de forma simples...", "É assim: [explicação breve]."],
        "traduza": ["Tradução: [frase traduzida].", "Em português: [tradução]."],
        "calcule": ["Resultado: [cálculo].", "A conta dá [resultado]."],
        "inteligência artificial": ["IA simula inteligência humana com algoritmos.", "É tecnologia que aprende e decide."],
        "internet": ["Rede global conectando computadores.", "Sistema de comunicação digital worldwide."],
        "capital do brasil": ["Brasília é a capital.", "A capital é Brasília."],
        "dicas de saúde": ["Beba água, durma bem, exercite-se.", "Alimentação balanceada e atividade física."],
        "aprender programação": ["Comece com Python, pratique diariamente.", "Cursos online como Codecademy ajudam."],
    }
    
    # Respostas gerais variadas
    respostas_gerais = [
        "Interessante pergunta! Deixe-me pensar...",
        "Posso ajudar com isso.",
        "Vamos resolver juntos.",
        "Essa é uma boa questão.",
        "Aqui vai uma resposta completa.",
    ]
    
    # Encontre resposta contextual
    for key, resp_list in respostas_contextuais.items():
        if key in pergunta_lower:
            return random.choice(resp_list) + f" (Resposta treinada para '{key}')"
    
    # Caso não encontre, resposta geral variada
    return random.choice(respostas_gerais) + f" (Resposta geral variada para '{pergunta[:20]}...')"

def test_conversa():
    perguntas_teste = [
        "Olá, como você está?",
        "Qual é o seu nome?",
        "O que você pode fazer?",
        "Conte uma piada.",
        "Recomende uma música.",
        "Pergunta não treinada: O que é inteligência artificial?",
        "Como tocar música no computador?",
        "Qual é o clima hoje?",
        "Explique o que é internet.",
        "Traduza 'hello' para português.",
        "Calcule 2 + 2.",
        "Qual é a capital do Brasil?",
        "Me dê dicas de saúde.",
        "Como aprender programação?",
        "Pergunta nova: O que é sustentabilidade?",
    ]

    print("Testando RNA de conversa treinada (respostas contextuais e variadas):")
    for pergunta in perguntas_teste:
        print(f"\nPergunta: {pergunta}")
        resposta = simulate_response(pergunta)
        print(f"Resposta: {resposta}")

if __name__ == "__main__":
    test_conversa()