$ErrorActionPreference = "Stop"

param(
  [string]$Model,
  [string]$DataPath = "backend/rnas/conversa/treinos/treino_conversa_10000.jsonl",
  [string]$DataDir = "backend/rnas/conversa/treinos",
  [string]$OutputPath = "backend/rnas/conversa/treinos/saida_lora",
  [int]$Epochs = 2,
  [int]$Batch = 1,
  [double]$LearningRate = 2e-4,
  [switch]$QLoRA,
  [switch]$ListDatasets
)

if ($ListDatasets) {
  if (Test-Path $DataDir) {
    Get-ChildItem -Path $DataDir -Filter *.jsonl -File | Sort-Object LastWriteTime -Descending | Select-Object FullName, LastWriteTime
  } else {
    Write-Host "Nao achei a pasta: $DataDir" -ForegroundColor Red
  }
  exit 0
}

if (-not $Model) {
  Write-Host "Uso: .\\tools\\train\\run_conversa_train.ps1 -Model SEU_MODELO_BASE [-QLoRA] [-DataDir <pasta>] [-DataPath <arquivo.jsonl>] [-ListDatasets]" -ForegroundColor Yellow
  exit 1
}

$DataFull = Resolve-Path -Path $DataPath
if (-not (Test-Path $DataFull)) {
  if (Test-Path $DataDir) {
    $latest = Get-ChildItem -Path $DataDir -Filter *.jsonl -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
      $DataPath = $latest.FullName
      $DataFull = Resolve-Path -Path $DataPath
      Write-Host "Usando dataset mais recente: $DataPath" -ForegroundColor Yellow
    } else {
      Write-Host "Nao achei JSONL em: $DataDir" -ForegroundColor Red
      exit 1
    }
  } else {
    Write-Host "Nao achei o dataset: $DataPath" -ForegroundColor Red
    exit 1
  }
}

$OutDir = $OutputPath
if (-not (Test-Path $OutDir)) {
  New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
}

$args = @(
  "backend/train/finetune_lora.py",
  "--model", $Model,
  "--data", $DataPath,
  "--output", $OutputPath,
  "--epochs", $Epochs,
  "--batch", $Batch,
  "--lr", $LearningRate
)
if ($QLoRA) {
  $args += "--qlora"
}

Write-Host "Rodando treino LoRA..." -ForegroundColor Cyan
python @args
