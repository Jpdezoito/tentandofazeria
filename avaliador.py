"""
avaliador.py - Módulo para avaliar a coerência das respostas da RNA.
"""

import difflib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class Avaliador:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()

    def avaliar_coerencia(self, pergunta, resposta, palavras_chave=None):
        # Similaridade de texto
        seq = difflib.SequenceMatcher(None, pergunta, resposta)
        similaridade = seq.ratio()

        # Similaridade de coseno se houver palavras-chave
        score_coseno = 0
        if palavras_chave:
            try:
                tfidf = self.vectorizer.fit_transform([pergunta, resposta])
                score_coseno = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            except:
                score_coseno = 0

        # Diversidade lexical (proporção de palavras únicas)
        palavras_resposta = set(resposta.lower().split())
        diversidade = len(palavras_resposta) / max(1, len(resposta.split())) if resposta else 0

        # Score total: média das métricas
        score = (similaridade + score_coseno + diversidade) / 3

        # Critérios simples: score mínimo 0.3, resposta não vazia, diversidade > 0.1
        aceitavel = score >= 0.3 and len(resposta.strip()) > 0 and diversidade > 0.1

        return score, aceitavel

    def gerar_perguntas_teste(self, num=5):
        perguntas = [
            "Olá, como você está?",
            "Qual é o seu nome?",
            "O que é inteligência artificial?",
            "Conte uma piada.",
            "Qual é a capital do Brasil?"
        ]
        return perguntas[:num]