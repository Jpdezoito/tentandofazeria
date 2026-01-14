@echo off
REM Launcher para ianova - Hub de IAs Locais
REM Este script inicia o aplicativo ianova no Windows
REM Nota: Acentos removidos para compatibilidade com diferentes encodings do Windows

echo ========================================
echo  ianova - Hub de IAs Locais
echo ========================================
echo.

REM Verificar se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: Python nao encontrado!
    echo Por favor, instale Python 3.8 ou superior
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python encontrado!
echo.

REM Verificar se as dependências estão instaladas
echo Verificando dependencias...
python -c "import requests, PIL, cv2, numpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Instalando dependencias...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERRO: Falha ao instalar dependencias
        pause
        exit /b 1
    )
)

echo.
echo Iniciando ianova...
echo.

REM Iniciar o aplicativo
python ianova.py

if %errorlevel% neq 0 (
    echo.
    echo ERRO: Falha ao iniciar o aplicativo
    pause
    exit /b 1
)
