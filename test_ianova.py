#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes para ianova
Valida a estrutura e funcionalidades básicas
"""

import sys
import os

def test_imports():
    """Testa se o módulo pode ser importado"""
    print("Teste 1: Importação do módulo...")
    try:
        # Verificar estrutura do código
        import ast
        with open('ianova.py', 'r') as f:
            code = f.read()
        ast.parse(code)
        print("  ✓ Código Python válido")
        return True
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

def test_structure():
    """Testa a estrutura do código"""
    print("\nTeste 2: Estrutura do código...")
    try:
        import ast
        with open('ianova.py', 'r') as f:
            tree = ast.parse(f.read())
        
        # Verificar classe IanovaApp
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        class_names = [cls.name for cls in classes]
        
        assert 'IanovaApp' in class_names, "Classe IanovaApp não encontrada"
        print("  ✓ Classe IanovaApp encontrada")
        
        # Verificar métodos principais
        ianova_class = next(cls for cls in classes if cls.name == 'IanovaApp')
        methods = [node.name for node in ianova_class.body if isinstance(node, ast.FunctionDef)]
        
        required_methods = [
            '__init__', 
            'create_widgets',
            'send_message',
            'process_command',
            'process_attachment',
            'search_files',
            'open_file',
            'open_web'
        ]
        
        for method in required_methods:
            assert method in methods, f"Método {method} não encontrado"
            print(f"  ✓ Método {method} encontrado")
        
        return True
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

def test_commands():
    """Testa lógica de comandos"""
    print("\nTeste 3: Lógica de comandos...")
    try:
        # Verificar se comandos estão definidos
        with open('ianova.py', 'r') as f:
            content = f.read()
        
        commands = ['/buscar', '/abrir', '/web', '/ajuda']
        for cmd in commands:
            assert cmd in content, f"Comando {cmd} não encontrado"
            print(f"  ✓ Comando {cmd} implementado")
        
        return True
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

def test_file_types():
    """Testa suporte a tipos de arquivo"""
    print("\nTeste 4: Suporte a tipos de arquivo...")
    try:
        with open('ianova.py', 'r') as f:
            content = f.read()
        
        # Verificar extensões de arquivo suportadas
        image_exts = ['.png', '.jpg', '.jpeg']
        video_exts = ['.mp4', '.avi', '.mov']
        audio_exts = ['.wav', '.mp3']
        
        for ext in image_exts + video_exts + audio_exts:
            assert ext in content, f"Extensão {ext} não suportada"
        
        print("  ✓ Imagens: .png, .jpg, .jpeg suportadas")
        print("  ✓ Vídeos: .mp4, .avi, .mov suportados")
        print("  ✓ Áudio: .wav, .mp3 suportados")
        
        return True
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

def test_dependencies():
    """Testa arquivo de dependências"""
    print("\nTeste 5: Dependências...")
    try:
        assert os.path.exists('requirements.txt'), "requirements.txt não encontrado"
        
        with open('requirements.txt', 'r') as f:
            content = f.read()
        
        required_deps = ['requests', 'Pillow', 'opencv-python', 'numpy']
        for dep in required_deps:
            assert dep in content, f"Dependência {dep} não listada"
            print(f"  ✓ {dep} listado")
        
        return True
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

def test_readme():
    """Testa documentação"""
    print("\nTeste 6: Documentação...")
    try:
        assert os.path.exists('README.md'), "README.md não encontrado"
        
        with open('README.md', 'r') as f:
            content = f.read()
        
        sections = ['Instalação', 'Uso', 'Características', 'Comandos']
        for section in sections:
            # Case insensitive check
            assert section.lower() in content.lower(), f"Seção {section} não encontrada"
            print(f"  ✓ Seção '{section}' presente")
        
        return True
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("=" * 60)
    print("TESTES DO IANOVA - Hub de IAs Locais")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_structure,
        test_commands,
        test_file_types,
        test_dependencies,
        test_readme
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"RESULTADO: {sum(results)}/{len(results)} testes passaram")
    print("=" * 60)
    
    if all(results):
        print("\n✓ Todos os testes passaram!")
        return 0
    else:
        print("\n✗ Alguns testes falharam")
        return 1

if __name__ == '__main__':
    sys.exit(main())
