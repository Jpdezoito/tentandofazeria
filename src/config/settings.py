# Configuration file for the IA Conversacional project

# Model settings
MODEL_CONFIG = {
    "base_model": "gpt2",
    "max_length": 512,
    "temperature": 0.7,
    "top_p": 0.9,
    "do_sample": True
}

# Training settings
TRAINING_CONFIG = {
    "batch_size": 4,
    "learning_rate": 5e-5,
    "num_epochs": 3,
    "save_steps": 500,
    "eval_steps": 500,
    "logging_steps": 100
}

# Data paths
DATA_PATHS = {
    "raw_data": "data/raw",
    "training_data": "data/training",
    "models": "data/models",
    "logs": "logs"
}

# Ollama settings
OLLAMA_CONFIG = {
    "host": "http://localhost:11434",
    "model": "llama2",
    "timeout": 30
}

# UI settings
UI_CONFIG = {
    "theme": "dark",
    "window_size": (1200, 800),
    "font_size": 12
}