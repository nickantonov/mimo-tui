# MiMo-Code — Auto Installer
# Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.
#
# Запуск: powershell -ExecutionPolicy Bypass -File install.ps1
#
# Автоматически:
#   1. Проверяет и удаляет старую Bun версию
#   2. Устанавливает Node.js если нет
#   3. Ставит mimo в ~/.mimocode/bin
#   4. Прописывает в PATH

$ErrorActionPreference = "Continue"
$MIMO_HOME = "$env:USERPROFILE\.mimocode"
$MIMO_BIN = "$MIMO_HOME\bin"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  MiMo-Code — Auto Installer" -ForegroundColor Cyan
Write-Host "  Borodachamba Studio, Nick Antonov 1998-2026" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# === Шаг 1: Проверка старой Bun версии ===
Write-Host "[1/5] Проверка старой версии..." -ForegroundColor Yellow

$BUN_FOUND = $false
foreach ($mimo in @("$MIMO_BIN\mimo.exe", "$MIMO_BIN\mimo")) {
    if (Test-Path $mimo) {
        $content = [System.IO.File]::ReadAllBytes($mimo)[0..3]
        if ($content[0] -eq 0x7f -and $content[1] -eq 0x45) {
            # ELF binary = Bun
            $size = (Get-Item $mimo).Length / 1MB
            Write-Host "  Найдена старая версия Bun MiMo-Code ([math]::Round($size,0) MB)" -ForegroundColor Red
            $BUN_FOUND = $true
        }
    }
}

if ($BUN_FOUND) {
    Write-Host ""
    Write-Host "  Старая версия MiMo-Code на Bun будет заменена на Node.js порт." -ForegroundColor Yellow
    Write-Host "  Все данные (сессии, конфиги) останутся на месте." -ForegroundColor Yellow
    Write-Host ""
    $reply = Read-Host "  Удалить старую версию? (Y/n)"
    if ($reply -match "^[Nn]") {
        Write-Host "  Установка отменена" -ForegroundColor Red
        exit 1
    }
    # Удаляем Bun бинарники
    Remove-Item "$MIMO_BIN\mimo.exe" -Force -ErrorAction SilentlyContinue
    Remove-Item "$MIMO_BIN\mimo" -Force -ErrorAction SilentlyContinue
    Write-Host "  Старая версия удалена" -ForegroundColor Green
} else {
    Write-Host "  Старая версия не найдена" -ForegroundColor Green
}

# === Шаг 2: Проверка Node.js ===
Write-Host ""
Write-Host "[2/5] Проверка Node.js..." -ForegroundColor Yellow

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    $nodeVer = & node --version 2>&1
    Write-Host "  Node.js $nodeVer" -ForegroundColor Green
} else {
    Write-Host "  Node.js не найден!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Скачайте Node.js LTS: https://nodejs.org/" -ForegroundColor White
    Write-Host "  Или установите nvm-windows: https://github.com/coreybutler/nvm-windows" -ForegroundColor Gray
    Write-Host ""
    $reply = Read-Host "  Продолжить без Node.js? (y/N)"
    if ($reply -notmatch "^[Yy]") {
        exit 1
    }
}

# === Шаг 3: Установка mimo ===
Write-Host ""
Write-Host "[3/5] Установка MiMo-Code..." -ForegroundColor Yellow

New-Item -ItemType Directory -Force -Path $MIMO_BIN | Out-Null

# Ищем node.exe
$nodeExe = "node"
$nodePath = Get-Command node -ErrorAction SilentlyContinue
if ($nodePath) {
    $nodeExe = $nodePath.Source
}

# Создаем mimo.cmd
$mimoCmd = @"
@echo off
rem MiMo-Code Node.js launcher
rem Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.
set "SCRIPT_DIR=%~dp0"
"%SCRIPT_DIR%..\..\packages\opencode\..\..\bin\node.exe" --no-experimental-strip-types "%SCRIPT_DIR%..\..\packages\opencode\run-node.mjs" %*
"@

# Ищем node.exe в стандартных местах
$nodeLocations = @(
    "$env:ProgramFiles\nodejs\node.exe",
    "${env:ProgramFiles(x86)}\nodejs\node.exe",
    "$env:LOCALAPPDATA\Programs\nodejs\node.exe",
    "$env:APPDATA\nvm\v$((node --version 2>$null).Trim('v'))\node.exe"
)

$foundNode = $null
foreach ($loc in $nodeLocations) {
    if (Test-Path $loc) {
        $foundNode = $loc
        break
    }
}
if (-not $foundNode) {
    $foundNode = (Get-Command node -ErrorAction SilentlyContinue).Source
}

if (-not $foundNode) {
    $foundNode = "node"
}

$mimoCmd = @"
@echo off
rem MiMo-Code Node.js launcher
rem Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.
set "NODE_EXE=$foundNode"
"%NODE_EXE%" --no-experimental-strip-types "%SCRIPT_DIR%..\..\packages\opencode\run-node.mjs" %*
"@

$batCmd = @"
@echo off
rem MiMo-Code Node.js launcher (bat fallback)
set "NODE_EXE=$foundNode"
"%NODE_EXE%" --no-experimental-strip-types "%SCRIPT_DIR%..\..\packages\opencode\run-node.mjs" %*
"@

Set-Content -Path "$MIMO_BIN\mimo.cmd" -Value $mimoCmd -Encoding ASCII
Set-Content -Path "$MIMO_BIN\mimo.bat" -Value $batCmd -Encoding ASCII

Write-Host "  mimo установлен в $MIMO_BIN" -ForegroundColor Green

# === Шаг 4: PATH ===
Write-Host ""
Write-Host "[4/5] Настройка PATH..." -ForegroundColor Yellow

$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$MIMO_BIN*") {
    [Environment]::SetEnvironmentVariable("Path", "$MIMO_BIN;$currentPath", "User")
    $env:Path = "$MIMO_BIN;$env:Path"
    Write-Host "  $MIMO_BIN добавлен в PATH" -ForegroundColor Green
} else {
    Write-Host "  PATH уже настроен" -ForegroundColor Green
}

# === Шаг 5: esbuild ===
Write-Host ""
Write-Host "[5/5] Проверка esbuild..." -ForegroundColor Yellow

$esbuildCmd = Get-Command esbuild -ErrorAction SilentlyContinue
if (-not $esbuildCmd) {
    Write-Host "  Устанавливаю esbuild..." -ForegroundColor Gray
    & npm install -g esbuild 2>$null
}
Write-Host "  esbuild" -ForegroundColor Green

# === Готово ===
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Установка завершена!" -ForegroundColor Green
Write-Host ""
Write-Host "  Закройте и откройте новый терминал." -ForegroundColor Yellow
Write-Host "  Затем:" -ForegroundColor White
Write-Host ""
Write-Host "  mimo --help          справка" -ForegroundColor White
Write-Host "  mimo run `"привет`"    тест" -ForegroundColor White
Write-Host "  mimo models          список моделей" -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
