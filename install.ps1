# MiMo-Code — Windows Installer
# Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.
#
# Запуск: powershell -ExecutionPolicy Bypass -File install.ps1
#
# Логика:
#   1. Проверяет наличие старой версии Bun
#   2. Если найдена — предлагает удалить
#   3. Устанавливает Node.js порт
#   4. Прописывает mimo в PATH

$ErrorActionPreference = "Stop"

$MIMO_HOME = "$env:USERPROFILE\.mimocode"
$MIMO_BIN = "$MIMO_HOME\bin"
$OPENCODE_DIR = "$env:USERPROFILE\DEPLOY\MiMo-Code-main-patched"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  MiMo-Code — Installer" -ForegroundColor Cyan
Write-Host "  Borodachamba Studio, Nick Antonov 1998-2026" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- Шаг 1: Проверка старой версии Bun ---
Write-Host "[1/5] Проверка старой версии..." -ForegroundColor Yellow

$BUN_FOUND = $false
$mimoExe = "$MIMO_BIN\mimo.exe"
$mimoBak = "$MIMO_BIN\mimo.bun.bak"

if (Test-Path $mimoExe) {
    $BUN_FOUND = $true
    $size = (Get-Item $mimoExe).Length / 1MB
    Write-Host "  Найдена старая версия Bun ([math]::Round($size,0) MB)" -ForegroundColor Red
}
if (Test-Path $mimoBak) {
    $BUN_FOUND = $true
}

if ($BUN_FOUND) {
    Write-Host ""
    Write-Host "  Старая версия MiMo-Code на Bun будет заменена на Node.js порт." -ForegroundColor Yellow
    Write-Host "  Это безопасно — все данные останутся на месте." -ForegroundColor Yellow
    Write-Host ""
    $reply = Read-Host "  Удалить старую версию? (Y/n)"
    if ($reply -match "^[Nn]") {
        Write-Host "  Установка отменена" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Удаляю старую версию..."
    Remove-Item $mimoExe -Force -ErrorAction SilentlyContinue
    Remove-Item $mimoBak -Force -ErrorAction SilentlyContinue
    Write-Host "  Старая версия удалена" -ForegroundColor Green
} else {
    Write-Host "  Старая версия не найдена" -ForegroundColor Green
}

# --- Шаг 2: Проверка Node.js ---
Write-Host ""
Write-Host "[2/5] Проверка Node.js..." -ForegroundColor Yellow

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host "  Node.js не найден!" -ForegroundColor Red
    Write-Host "  Скачайте с https://nodejs.org/ (LTS версия)" -ForegroundColor Gray
    Write-Host "  Или установите nvm-windows: https://github.com/coreybutler/nvm-windows" -ForegroundColor Gray
    exit 1
}

$nodeVer = & node --version
Write-Host "  Node.js $nodeVer" -ForegroundColor Green

# --- Шаг 3: Проверка esbuild ---
Write-Host ""
Write-Host "[3/5] Проверка esbuild..." -ForegroundColor Yellow

$esbuildCmd = Get-Command esbuild -ErrorAction SilentlyContinue
if (-not $esbuildCmd) {
    Write-Host "  Устанавливаю esbuild..."
    & npm install -g esbuild
}
Write-Host "  esbuild" -ForegroundColor Green

# --- Шаг 4: Установка mimo ---
Write-Host ""
Write-Host "[4/5] Установка MiMo-Code..." -ForegroundColor Yellow

New-Item -ItemType Directory -Force -Path $MIMO_BIN | Out-Null

# mimo.cmd для Windows
$openCodePath = $OPENCODE_DIR -replace "\\", "\\"
$mimoCmd = @"
@echo off
set "NODE_BIN=%USERPROFILE%\.nvm\versions\nvm4v\22.23.1\node.exe"
if not exist "%NODE_BIN%" set "NODE_BIN=node"
"%NODE_BIN%" --no-experimental-strip-types "%OPENCODE_DIR%\packages\opencode\run-node.mjs" %*
"@

Set-Content -Path "$MIMO_BIN\mimo.cmd" -Value $mimoCmd -Encoding ASCII

# mimo.bat как fallback
Copy-Item "$MIMO_BIN\mimo.cmd" "$MIMO_BIN\mimo.bat" -Force

Write-Host "  mimo установлен" -ForegroundColor Green

# --- Шаг 5: esbuild platform package ---
Write-Host ""
Write-Host "[5/5] Настройка esbuild..." -ForegroundColor Yellow

$OPENCODE_NM = "$OPENCODE_DIR\packages\opencode\node_modules"
$esbuildGlobal = & npm root -g 2>$null
if ($esbuildGlobal -and (Test-Path "$esbuildGlobal\@esbuild")) {
    if (-not (Test-Path "$OPENCODE_NM\@esbuild")) {
        New-Item -ItemType SymbolicLink -Force -Path "$OPENCODE_NM\@esbuild" -Target "$esbuildGlobal\@esbuild" 2>$null
    }
    Write-Host "  esbuild platform package" -ForegroundColor Green
} else {
    Write-Host "  Предупреждение: esbuild platform package не найден" -ForegroundColor Yellow
}

# --- Готово ---
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Установка завершена!" -ForegroundColor Green
Write-Host ""
Write-Host "  Запуск:  mimo --help"
Write-Host "  Тест:    mimo run `"привет`""
Write-Host "  Модели:  mimo models"
Write-Host "============================================" -ForegroundColor Cyan
