# MiMo-Code Node.js Port — Windows Installer
# Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.

$ErrorActionPreference = "Stop"
$MIMO_BIN = "$env:USERPROFILE\.mimocode\bin"
$OPENCODE_DIR = "$env:USERPROFILE\DEPLOY\MiMo-Code-main-patched\packages\opencode"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MiMo-Code Node.js Port — Installer   " -ForegroundColor Cyan
Write-Host "  Borodachamba Studio, Nick Antonov     " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Проверяем Node.js
Write-Host "[1/4] Проверка Node.js..." -ForegroundColor Yellow
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "  Node.js не найден. Установите с https://nodejs.org/" -ForegroundColor Red
    Write-Host "  Или: nvm install 22" -ForegroundColor Gray
    exit 1
}
Write-Host "  Node.js $($node.Version) ✓" -ForegroundColor Green

# 2. Удаляем старую Bun версию
Write-Host "[2/4] Удаление старой версии Bun..." -ForegroundColor Yellow
$bunMimo = "$MIMO_BIN\mimo.exe"
if (Test-Path $bunMimo) {
    Write-Host "  Найден Bun бинарник. Удаляю..." -ForegroundColor Red
    Remove-Item $bunMimo -Force
}
$bunBak = "$MIMO_BIN\mimo.bun.bak"
if (Test-Path $bunBak) {
    Remove-Item $bunBak -Force
}
Write-Host "  Старая версия удалена ✓" -ForegroundColor Green

# 3. Устанавливаем наш mimo
Write-Host "[3/4] Установка MiMo-Code Node.js порта..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $MIMO_BIN | Out-Null

$mimoBat = @"
@echo off
cd /d "%~dp0\..\.."
set PATH=%~dp0;%PATH%
node --no-experimental-strip-types packages\opencode\run-node.mjs %*
"@

Set-Content -Path "$MIMO_BIN\mimo.cmd" -Value $mimoBat
Write-Host "  mimo установлен ✓" -ForegroundColor Green

# 4. Проверяем esbuild
Write-Host "[4/4] Проверка esbuild..." -ForegroundColor Yellow
$esbuild = Get-Command esbuild -ErrorAction SilentlyContinue
if (-not $esbuild) {
    Write-Host "  Устанавливаю esbuild..." -ForegroundColor Gray
    npm install -g esbuild
}
Write-Host "  esbuild ✓" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Установка завершена!" -ForegroundColor Green
Write-Host ""
Write-Host "  Запуск: mimo --help" -ForegroundColor White
Write-Host "  Тест:   mimo run `"привет`"" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
