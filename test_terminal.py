#!/usr/bin/env python3
"""
Teste interativo da RNA de conversa no terminal.
Digite perguntas e veja respostas variadas.
Digite 'sair' para encerrar.
"""

import random
import re
import json
import os

MEMORY_FILE = "learned_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory, f, ensure_ascii=False, indent=4)

learned_answers = load_memory()  # Carrega memória persistente

def simulate_response(pergunta):
    pergunta_lower = pergunta.lower()
    
    # Verificar se é uma pergunta de cálculo simples
    calc_match = re.search(r'quanto é (\d+) \+ (\d+)', pergunta_lower)
    if calc_match:
        num1 = int(calc_match.group(1))
        num2 = int(calc_match.group(2))
        return f"{num1} + {num2} = {num1 + num2}"
    
    # Verificar aprendizado anterior
    for key, answer in learned_answers.items():
        if key in pergunta_lower:
            return f"Da minha memória: {answer}"
    
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
    
    # Encontre resposta contextual
    for key, resp_list in respostas_contextuais.items():
        if key in pergunta_lower:
            return random.choice(resp_list)
    
    # Se não sabe, perguntar de volta para aprender
    return f"Não sei ainda, {pergunta}? Me diga a resposta para eu aprender!"

def learn_from_interaction(pergunta, resposta_usuario):
    learned_answers[pergunta.lower()] = resposta_usuario
    save_memory(learned_answers)
    return "Legal! Adicionei na minha memória de aprendizado."

def automatic_test():
    perguntas_teste = [
        "Olá, como você está?",
        "Qual é o seu nome?",
        "Quanto é 1 + 1?",  # Teste de cálculo
        "O que é machine learning?",  # Conhecido
        "Pergunta nova: Qual é a cor do céu?",  # Desconhecido, deve perguntar
    ]

    print("=== Teste Automático da RNA de Conversa com Aprendizado ===")
    for pergunta in perguntas_teste:
        print(f"Você: {pergunta}")
        resposta = simulate_response(pergunta)
        print(f"IA: {resposta}")
        if "Não sei ainda" in resposta:
            # Simular resposta do usuário
            resposta_usuario = "Azul"  # Exemplo
            learn_response = learn_from_interaction(pergunta, resposta_usuario)
            print(f"Você: {resposta_usuario}")
            print(f"IA: {learn_response}")
            # Testar novamente
            print(f"Testando novamente: {pergunta}")
            resposta_aprendida = simulate_response(pergunta)
            print(f"IA: {resposta_aprendida}")
        print()

if __name__ == "__main__":
    automatic_test()