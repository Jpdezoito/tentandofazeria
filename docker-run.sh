#!/bin/bash

echo "========================================"
echo "    IA Conversacional - Docker Setup"
echo "========================================"

case "$1" in
    build)
        echo "Construindo imagem Docker..."
        docker-compose build
        ;;
    up)
        echo "Iniciando serviços..."
        docker-compose up -d
        echo ""
        echo "Aguardando Ollama iniciar..."
        sleep 10
        echo ""
        echo "Para acessar a IA, use: docker-compose exec ia-conversa bash"
        echo "Ou para logs: docker-compose logs -f ia-conversa"
        ;;
    down)
        echo "Parando serviços..."
        docker-compose down
        ;;
    logs)
        echo "Mostrando logs..."
        docker-compose logs -f
        ;;
    shell)
        echo "Abrindo shell no container da IA..."
        docker-compose exec ia-conversa bash
        ;;
    clean)
        echo "Limpando containers e volumes..."
        docker-compose down -v
        docker system prune -f
        ;;
    *)
        echo "Uso: $0 {build|up|down|logs|shell|clean}"
        echo ""
        echo "Comandos:"
        echo "  build  - Construir imagem Docker"
        echo "  up     - Iniciar todos os serviços"
        echo "  down   - Parar todos os serviços"
        echo "  logs   - Ver logs em tempo real"
        echo "  shell  - Abrir shell no container da IA"
        echo "  clean  - Limpar containers e volumes"
        echo ""
        echo "Exemplo: $0 up"
        ;;
esac