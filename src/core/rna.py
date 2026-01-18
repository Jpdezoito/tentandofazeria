"""
rna.py - Módulo para a RNA de conversa.
Implementa um modelo simples de linguagem baseado em transformers usando PyTorch com múltiplos otimizadores e métodos avançados.
"""

import torch
import torch.nn as nn
from transformers import GPT2LMHeadModel, GPT2Tokenizer
from torch.utils.data import Dataset, DataLoader
import json
import os

class ConversaDataset(Dataset):
    def __init__(self, data, tokenizer, max_length=512):
        self.tokenizer = tokenizer
        self.data = data
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        text = self.data[idx]
        encoding = self.tokenizer(text, truncation=True, padding='max_length', max_length=self.max_length, return_tensors='pt')
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': encoding['input_ids'].flatten()
        }

class RNAConversa:
    def __init__(self, model_name='gpt2'):
        self.tokenizer = GPT2Tokenizer.from_pretrained(model_name)
        self.model = GPT2LMHeadModel.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        # Multiple optimizers like TensorFlow
        self.optimizers = {
            'adam': torch.optim.Adam(self.model.parameters(), lr=5e-5),
            'adamw': torch.optim.AdamW(self.model.parameters(), lr=5e-5, weight_decay=0.01),
            'sgd': torch.optim.SGD(self.model.parameters(), lr=5e-5),
            'rmsprop': torch.optim.RMSprop(self.model.parameters(), lr=5e-5),
            'adagrad': torch.optim.Adagrad(self.model.parameters(), lr=5e-5),
            'adadelta': torch.optim.Adadelta(self.model.parameters(), lr=5e-5)
        }
        self.current_optimizer = 'adamw'
        self.scheduler = torch.optim.lr_scheduler.StepLR(self.optimizers[self.current_optimizer], step_size=1, gamma=0.9)

    def treinar(self, data, epochs=1, batch_size=2):
        dataset = ConversaDataset(data, self.tokenizer)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        self.model.train()
        for epoch in range(epochs):
            for batch in dataloader:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                labels = batch['labels'].to(self.device)
                self.optimizers[self.current_optimizer].zero_grad()
                outputs = self.model(input_ids, attention_mask=attention_mask, labels=labels)
                loss = outputs.loss
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)  # Gradient clipping
                self.optimizers[self.current_optimizer].step()
            self.scheduler.step()  # Update learning rate
            print(f"Epoch {epoch+1}/{epochs} - Loss: {loss.item():.4f} - LR: {self.scheduler.get_last_lr()[0]:.6f}")

    def gerar_resposta(self, pergunta, max_length=50):
        self.model.eval()
        input_ids = self.tokenizer.encode(pergunta, return_tensors='pt').to(self.device)
        with torch.no_grad():
            output = self.model.generate(input_ids, max_length=max_length, num_return_sequences=1, no_repeat_ngram_size=2)
        resposta = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return resposta

    def salvar_modelo(self, path='modelo_rna'):
        os.makedirs(path, exist_ok=True)
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
        print(f"Modelo salvo em {path}")

    def ajustar_pesos(self, novo_lr=1e-5, optimizer='adamw'):
        self.current_optimizer = optimizer
        self.optimizers[self.current_optimizer] = self.optimizers[optimizer].__class__(self.model.parameters(), lr=novo_lr)
        self.scheduler = torch.optim.lr_scheduler.StepLR(self.optimizers[self.current_optimizer], step_size=1, gamma=0.9)
        print(f"Optimizer ajustado para {optimizer} com LR {novo_lr}")