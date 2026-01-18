import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

model_name = 'microsoft/DialoGPT-small'
lora_path = 'models/conversa_lora'

model = AutoModelForCausalLM.from_pretrained(model_name)
model = PeftModel.from_pretrained(model, lora_path)
tokenizer = AutoTokenizer.from_pretrained(model_name)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model.save_pretrained('models/conversa_finetuned')
tokenizer.save_pretrained('models/conversa_finetuned')
print('Modelo salvo em models/conversa_finetuned')