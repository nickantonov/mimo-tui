#!/bin/bash
# MiMo-Code Node.js Port — Installer
# Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.
#
# Удаляет старую версию Bun и ставит Node.js порт.

set -e

MIMO_BIN="$HOME/.mimocode/bin"
OPENCODE_DIR="$HOME/DEPLOY/MiMo-Code-main-patched/packages/opencode"
NODE_VERSION="22"

echo "╔══════════════════════════════════════════════╗"
echo "║  MiMo-Code Node.js Port — Installer         ║"
echo "║  Borodachamba Studio, Nick Antonov 1998-2026 ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. Проверяем Node.js
echo "[1/4] Проверка Node.js..."
if ! command -v node &>/dev/null; then
  echo "  Node.js не найден. Устанавливаю через nvm..."
  if [ ! -d "$HOME/.nvm" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  else
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  fi
  nvm install "$NODE_VERSION"
  nvm use "$NODE_VERSION"
fi
echo "  Node.js $(node --version) ✓"

# 2. Проверяем esbuild
echo "[2/4] Проверка esbuild..."
if ! npm list -g esbuild &>/dev/null; then
  echo "  Устанавливаю esbuild..."
  npm install -g esbuild
fi
echo "  esbuild ✓"

# 3. Удаляем старую Bun версию
echo "[3/4] Удаление старой версии Bun..."
if [ -f "$MIMO_BIN/mimo.bun.bak" ]; then
  echo "  Найдена резервная копия Bun. Удаляю..."
  rm -f "$MIMO_BIN/mimo.bun.bak"
fi
if file "$MIMO_BIN/mimo" 2>/dev/null | grep -q "ELF"; then
  echo "  Найден Bun бинарник. Удаляю..."
  rm -f "$MIMO_BIN/mimo"
fi
echo "  Старая версия удалена ✓"

# 4. Устанавливаем наш mimo
echo "[4/4] Установка MiMo-Code Node.js порта..."
mkdir -p "$MIMO_BIN"

cat > "$MIMO_BIN/mimo" << 'WRAPPER'
#!/bin/bash
# MiMo-Code Node.js launcher
# Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NODE_BIN="$HOME/.nvm/versions/node/v22.23.1/bin/node"
OPENCODE_DIR="$HOME/DEPLOY/MiMo-Code-main-patched/packages/opencode"

if [ ! -x "$NODE_BIN" ]; then
  NODE_BIN="$(command -v node 2>/dev/null)"
fi

if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
  echo "Error: Node.js not found. Install: nvm install 22" >&2
  exit 1
fi

if [ ! -f "$OPENCODE_DIR/run-node.mjs" ]; then
  echo "Error: MiMo-Code not found at $OPENCODE_DIR" >&2
  exit 1
fi

exec "$NODE_BIN" --no-experimental-strip-types "$OPENCODE_DIR/run-node.mjs" "$@"
WRAPPER

chmod +x "$MIMO_BIN/mimo"
echo "  mimo установлен ✓"

# 5. Слинковать esbuild
echo "[5/5] Настройка esbuild..."
if [ ! -d "$OPENCODE_DIR/node_modules/@esbuild" ]; then
  npm install -g @esbuild/linux-x64 2>/dev/null || true
  ln -sf "$(npm root -g)/@esbuild" "$OPENCODE_DIR/node_modules/@esbuild"
  echo "  esbuild platform package ✓"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Установка завершена!"
echo ""
echo "  Запуск: mimo --help"
echo "  Тест:   mimo run \"привет\""
echo "═══════════════════════════════════════════════"
