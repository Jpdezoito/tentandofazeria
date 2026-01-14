#!/bin/bash
# Launcher para ianova - Hub de IAs Locais
# Este script inicia o aplicativo ianova no Linux/Mac

echo "========================================"
echo "  ianova - Hub de IAs Locais"
echo "========================================"
echo ""

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "ERRO: Python não encontrado!"
    echo "Por favor, instale Python 3.8 ou superior"
    exit 1
fi

echo "Python encontrado!"
echo ""

# Verificar se as dependências estão instaladas
echo "Verificando dependências..."
python3 -c "import requests, PIL, cv2, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "Instalando dependências..."
    python3 -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERRO: Falha ao instalar dependências"
        exit 1
    fi
fi

echo ""
echo "Iniciando ianova..."
echo ""

# Iniciar o aplicativo
python3 ianova.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERRO: Falha ao iniciar o aplicativo"
    exit 1
fi
