"""
main.py - Controle total do sistema de treino e autoavaliação da RNA de conversa.
Executar com: python main.py
"""

import os
import json
import requests
import time
import torch
from src.core.rna import RNAConversa
from src.core.avaliador import Avaliador
import pypdf as PyPDF2

def load_local_data(diretorio='data/raw'):
    dados = []
    arquivos_carregados = []
    total_arquivos = 0
    total_caracteres = 0
    if not os.path.exists(diretorio):
        os.makedirs(diretorio)
        print(f"Diretório {diretorio} criado. Adicione arquivos TXT, PDF, JSON.")
        return dados, arquivos_carregados, total_arquivos, total_caracteres

    for arquivo in os.listdir(diretorio):
        caminho = os.path.join(diretorio, arquivo)
        if arquivo.endswith('.txt'):
            with open(caminho, 'r', encoding='utf-8') as f:
                texto = f.read()
                dados.append(texto)
                arquivos_carregados.append(arquivo)
                total_caracteres += len(texto)
                total_arquivos += 1
        elif arquivo.endswith('.pdf'):
            with open(caminho, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                texto = ''
                for page in reader.pages:
                    texto += page.extract_text()
                dados.append(texto)
                arquivos_carregados.append(arquivo)
                total_caracteres += len(texto)
                total_arquivos += 1
        elif arquivo.endswith('.json'):
            with open(caminho, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        texto = str(item)
                        dados.append(texto)
                        arquivos_carregados.append(arquivo)
                        total_caracteres += len(texto)
                        total_arquivos += 1
                else:
                    texto = str(data)
                    dados.append(texto)
                    arquivos_carregados.append(arquivo)
                    total_caracteres += len(texto)
                    total_arquivos += 1

    print(f"Caminho absoluto do dataset: {os.path.abspath(diretorio)}")
    print(f"Arquivos carregados: {arquivos_carregados}")
    print(f"Dados locais carregados: {total_arquivos} arquivos, {total_caracteres} caracteres.")
    return dados, arquivos_carregados, total_arquivos, total_caracteres

def load_online_data(url='https://api.example.com/dados'):
    dados = []
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                dados = [str(item) for item in data]
            else:
                dados = [str(data)]
            print(f"Dados online carregados: {len(dados)} itens.")
        else:
            print("Falha ao carregar dados online.")
    except Exception as e:
        print(f"Erro ao carregar dados online: {e}")
    return dados

def train_cycle(rna, dados, epochs=1):
    print(f"Iniciando treino com {epochs} epochs...")
    start_time = time.time()
    from torch.utils.data import DataLoader
    from rna import ConversaDataset
    dataset = ConversaDataset(dados, rna.tokenizer)
    dataloader = DataLoader(dataset, batch_size=2, shuffle=True)
    num_batches = len(dataloader)
    print(f"Número de batches por epoch: {num_batches}")
    rna.treinar(dados, epochs=epochs)
    end_time = time.time()
    print(f"Tempo gasto no treino: {end_time - start_time:.2f} segundos")

def run_self_test(rna, avaliador, perguntas_teste):
    print("Executando testes automáticos...")
    scores = []
    for pergunta in perguntas_teste:
        resposta = rna.gerar_resposta(pergunta)
        score, aceitavel = avaliador.avaliar_coerencia(pergunta, resposta)
        scores.append(score)
        print(f"P: {pergunta}")
        print(f"R: {resposta}")
        print(f"Score: {score:.2f} (Aceitável: {aceitavel})")
        print("-" * 50)
    score_medio = sum(scores) / len(scores) if scores else 0
    print(f"Score médio do ciclo: {score_medio:.2f}")
    return score_medio

def verificar_e_imprimir_modelo(path='modelo_rna'):
    arquivos = ['config.json', 'pytorch_model.bin', 'tokenizer_config.json', 'vocab.json', 'merges.txt']
    print("Verificando arquivos salvos:")
    for arquivo in arquivos:
        caminho = os.path.join(path, arquivo)
        if os.path.exists(caminho):
            tamanho = os.path.getsize(caminho)
            print(f"  {arquivo}: {tamanho} bytes")
        else:
            print(f"  {arquivo}: não encontrado")

def recarregar_e_testar(path='modelo_rna'):
    print("Recarregando modelo do disco...")
    rna_reloaded = RNAConversa(model_name=path)
    print("Modelo recarregado do disco com sucesso")
    perguntas_teste = ["Olá", "Qual é o seu nome?", "O que é IA?"]
    for pergunta in perguntas_teste:
        resposta = rna_reloaded.gerar_resposta(pergunta)
        print(f"P: {pergunta} -> R: {resposta}")

def main():
    print("Iniciando sistema de treino e autoavaliação da RNA de conversa...")

    # Carregar dados locais
    dados_locais, arquivos, num_arquivos, total_chars = load_local_data()
    if num_arquivos == 0:
        print("ERRO: Nenhum arquivo encontrado em 'dados/'. Adicione arquivos TXT, PDF ou JSON e execute novamente.")
        return

    # Estimar tokens
    rna_temp = RNAConversa()
    total_tokens = sum(len(rna_temp.tokenizer.encode(texto)) for texto in dados_locais)
    print(f"Número total de exemplos: {len(dados_locais)}")
    print(f"Número total de tokens estimados: {total_tokens}")
    print(f"Device em uso: {'GPU' if torch.cuda.is_available() else 'CPU'}")
    if torch.cuda.is_available():
        print(f"Nome da GPU: {torch.cuda.get_device_name(0)}")

    # Carregar dados online (opcional)
    dados_online = load_online_data()
    dados = dados_locais + dados_online

    # Inicializar RNA e Avaliador
    rna = RNAConversa()
    avaliador = Avaliador()
    perguntas_teste = avaliador.gerar_perguntas_teste()

    threshold = 0.5
    max_iteracoes = 10
    iteracao = 0

    while iteracao < max_iteracoes:
        print(f"\n=== Iteração {iteracao + 1}/{max_iteracoes} ===")

        # Treinar
        train_cycle(rna, dados, epochs=1)

        # Testar
        score_medio = run_self_test(rna, avaliador, perguntas_teste)

        # Verificar threshold
        if score_medio >= threshold:
            print(f"Score >= {threshold}. Salvando modelo...")
            rna.salvar_modelo()
            verificar_e_imprimir_modelo()
            recarregar_e_testar()
            break
        else:
            print(f"Score < {threshold}. Ajustando pesos e continuando...")
            rna.ajustar_pesos(novo_lr=1e-6)

        iteracao += 1

    if iteracao == max_iteracoes:
        print("Máximo de iterações atingido. Salvando modelo atual...")
        rna.salvar_modelo()
        verificar_e_imprimir_modelo()
        recarregar_e_testar()

    print("Sistema concluído.")

if __name__ == "__main__":
    main()