@echo off
setlocal

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv-3\Scripts\python.exe"

if exist "%VENV_PY%" (
  "%VENV_PY%" "%ROOT%ia_principal\main.py"
) else (
  python "%ROOT%ia_principal\main.py"
)

endlocal
