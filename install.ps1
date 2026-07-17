# MiMo-Code Auto Installer for Windows
# Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.
# Run: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Continue"
$MIMO_HOME = "$env:USERPROFILE\.mimocode"
$MIMO_BIN = "$MIMO_HOME\bin"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "============================================"
Write-Host "  MiMo-Code Auto Installer"
Write-Host "  Borodachamba Studio"
Write-Host "============================================"
Write-Host ""

# Step 1: Check old Bun version
Write-Host "[1/5] Checking for old Bun version..."

$BUN_FOUND = $false
foreach ($mimo in @("$MIMO_BIN\mimo.exe", "$MIMO_BIN\mimo")) {
    if (Test-Path $mimo) {
        $bytes = [System.IO.File]::ReadAllBytes($mimo)
        if ($bytes[0] -eq 0x7f -and $bytes[1] -eq 0x45) {
            $size = [math]::Round((Get-Item $mimo).Length / 1MB, 1)
            Write-Host "  Found old Bun MiMo-Code ($size MB)" -ForegroundColor Red
            $BUN_FOUND = $true
        }
    }
}

if ($BUN_FOUND) {
    Write-Host ""
    Write-Host "  Old Bun version will be replaced with Node.js port." -ForegroundColor Yellow
    Write-Host "  All data (sessions, configs) will be kept." -ForegroundColor Yellow
    Write-Host ""
    $reply = Read-Host "  Remove old version? (Y/n)"
    if ($reply -match "^[Nn]") {
        Write-Host "  Installation cancelled" -ForegroundColor Red
        exit 1
    }
    Remove-Item "$MIMO_BIN\mimo.exe" -Force -ErrorAction SilentlyContinue
    Remove-Item "$MIMO_BIN\mimo" -Force -ErrorAction SilentlyContinue
    Write-Host "  Old version removed" -ForegroundColor Green
} else {
    Write-Host "  No old version found" -ForegroundColor Green
}

# Step 2: Check Node.js
Write-Host ""
Write-Host "[2/5] Checking Node.js..."

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    $nodeVer = & node --version 2>&1
    Write-Host "  Node.js $nodeVer" -ForegroundColor Green
} else {
    Write-Host "  Node.js not found!" -ForegroundColor Red
    Write-Host "  Download from: https://nodejs.org/" -ForegroundColor White
    Write-Host "  Or install nvm-windows: https://github.com/coreybutler/nvm-windows" -ForegroundColor Gray
    exit 1
}

# Step 3: Install mimo
Write-Host ""
Write-Host "[3/5] Installing MiMo-Code..."

New-Item -ItemType Directory -Force -Path $MIMO_BIN | Out-Null

$foundNode = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $foundNode) { $foundNode = "node" }

$mimoCmd = @"
@echo off
rem MiMo-Code Node.js launcher
rem Borodachamba Studio, Nick Antonov 1998-2026.
set "NODE_EXE=$foundNode"
set "SCRIPT_DIR=%~dp0"
"%NODE_EXE%" --no-experimental-strip-types "%SCRIPT_DIR%..\..\packages\opencode\run-node.mjs" %*
"@

Set-Content -Path "$MIMO_BIN\mimo.cmd" -Value $mimoCmd -Encoding ASCII
Copy-Item "$MIMO_BIN\mimo.cmd" "$MIMO_BIN\mimo.bat" -Force

Write-Host "  mimo installed to $MIMO_BIN" -ForegroundColor Green

# Step 4: PATH
Write-Host ""
Write-Host "[4/5] Configuring PATH..."

$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$MIMO_BIN*") {
    [Environment]::SetEnvironmentVariable("Path", "$MIMO_BIN;$currentPath", "User")
    $env:Path = "$MIMO_BIN;$env:Path"
    Write-Host "  Added $MIMO_BIN to PATH" -ForegroundColor Green
} else {
    Write-Host "  PATH already configured" -ForegroundColor Green
}

# Step 5: esbuild
Write-Host ""
Write-Host "[5/5] Checking esbuild..."

$esbuildCmd = Get-Command esbuild -ErrorAction SilentlyContinue
if (-not $esbuildCmd) {
    Write-Host "  Installing esbuild..." -ForegroundColor Gray
    & npm install -g esbuild 2>$null
}
Write-Host "  esbuild OK" -ForegroundColor Green

# Done
Write-Host ""
Write-Host "============================================"
Write-Host "  Installation complete!"
Write-Host ""
Write-Host "  Close and reopen terminal."
Write-Host "  Then:"
Write-Host ""
Write-Host "  mimo --help"
Write-Host "  mimo run `"hello`""
Write-Host "  mimo models"
Write-Host "============================================"
Write-Host ""
