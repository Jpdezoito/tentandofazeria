@echo off
echo ========================================
echo     IA Conversacional - Docker Setup
echo ========================================

if "%1"=="build" (
    echo Construindo imagem Docker...
    docker-compose build
    goto :eof
)

if "%1"=="up" (
    echo Iniciando serviços...
    docker-compose up -d
    echo.
    echo Aguardando Ollama iniciar...
    timeout /t 10 /nobreak > nul
    echo.
    echo Para acessar a IA, use: docker-compose exec ia-conversa bash
    echo Ou para logs: docker-compose logs -f ia-conversa
    goto :eof
)

if "%1"=="down" (
    echo Parando serviços...
    docker-compose down
    goto :eof
)

if "%1"=="logs" (
    echo Mostrando logs...
    docker-compose logs -f
    goto :eof
)

if "%1"=="shell" (
    echo Abrindo shell no container da IA...
    docker-compose exec ia-conversa bash
    goto :eof
)

if "%1"=="clean" (
    echo Limpando containers e volumes...
    docker-compose down -v
    docker system prune -f
    goto :eof
)

echo Uso: %0 {build|up|down|logs|shell|clean}
echo.
echo Comandos:
echo   build  - Construir imagem Docker
echo   up     - Iniciar todos os servicos
echo   down   - Parar todos os servicos
echo   logs   - Ver logs em tempo real
echo   shell  - Abrir shell no container da IA
echo   clean  - Limpar containers e volumes
echo.
echo Exemplo: %0 up