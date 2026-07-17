#!/bin/bash
# MiMo-Code — Installer
# Borodachamba Studio, Nick Antonov 1998-2026. All rights reserved.
#
# curl -fsSL https://raw.githubusercontent.com/nickantonov/mimocode-nodejs-port/master/install.sh | bash
#
# Логика:
#   1. Проверяет наличие старой версии Bun
#   2. Если найдена — предлагает удалить
#   3. Устанавливает Node.js порт
#   4. Прописывает mimo в PATH

set -e

MIMO_HOME="$HOME/.mimocode"
MIMO_BIN="$MIMO_HOME/bin"
OPENCODE_DIR="$HOME/DEPLOY/MiMo-Code-main-patched"
NODE_VERSION="22"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════╗"
echo "║  MiMo-Code — Installer                      ║"
echo "║  Borodachamba Studio, Nick Antonov 1998-2026 ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Шаг 1: Проверка старой версии Bun ───────────────────────
echo -e "${YELLOW}[1/5]${NC} Проверка старой версии..."

BUN_FOUND=false
if [ -f "$MIMO_BIN/mimo" ]; then
  if file "$MIMO_BIN/mimo" 2>/dev/null | grep -q "ELF"; then
    BUN_FOUND=true
    BUN_SIZE=$(du -h "$MIMO_BIN/mimo" | cut -f1)
    echo -e "  ${RED}Найдена старая версия Bun ($BUN_SIZE)${NC}"
  fi
elif [ -f "$MIMO_BIN/mimo.exe" ]; then
  BUN_FOUND=true
  echo -e "  ${RED}Найдена старая версия Bun (Windows)${NC}"
fi

if [ "$BUN_FOUND" = true ]; then
  echo ""
  echo -e "  ${YELLOW}Старая версия MiMo-Code на Bun будет заменена на Node.js порт.${NC}"
  echo -e "  ${YELLOW}Это безопасно — все данные останутся на месте.${NC}"
  echo ""
  read -p "  Удалить старую версию? [Y/n] " -n 1 -r
  echo ""
  if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo -e "  ${RED}Установка отменена${NC}"
    exit 1
  fi
  echo -e "  Удаляю старую версию..."
  rm -f "$MIMO_BIN/mimo" "$MIMO_BIN/mimo.exe"
  echo -e "  ${GREEN}Старая версия удалена ✓${NC}"
else
  echo -e "  ${GREEN}Старая версия не найдена ✓${NC}"
fi

# ─── Шаг 2: Проверка Node.js ──────────────────────────────────
echo ""
echo -e "${YELLOW}[2/5]${NC} Проверка Node.js..."

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

if command -v node &>/dev/null; then
  NODE_VER=$(node --version | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
  if [ "$NODE_MAJOR" -ge "$NODE_VERSION" ]; then
    echo -e "  Node.js $NODE_VER ✓"
  else
    echo -e "  ${YELLOW}Node.js $NODE_VER — нужен >= $NODE_VERSION${NC}"
    echo "  Обновляю..."
    nvm install "$NODE_VERSION"
    nvm use "$NODE_VERSION"
  fi
else
  echo -e "  ${YELLOW}Node.js не найден${NC}"
  echo "  Устанавливаю через nvm..."
  if [ ! -d "$HOME/.nvm" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  fi
  . "$NVM_DIR/nvm.sh"
  nvm install "$NODE_VERSION"
  nvm use "$NODE_VERSION"
fi
echo -e "  ${GREEN}Node.js $(node --version) ✓${NC}"

# ─── Шаг 3: Проверка esbuild ─────────────────────────────────
echo ""
echo -e "${YELLOW}[3/5]${NC} Проверка esbuild..."
if ! npx esbuild --version &>/dev/null 2>&1; then
  echo "  Устанавливаю esbuild..."
  npm install -g esbuild
fi
echo -e "  ${GREEN}esbuild ✓${NC}"

# ─── Шаг 4: Установка mimo ──────────────────────────────────
echo ""
echo -e "${YELLOW}[4/5]${NC} Установка MiMo-Code..."
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
  echo "Clone: git clone https://github.com/nickantonov/mimocode-nodejs-port.git" >&2
  exit 1
fi

exec "$NODE_BIN" --no-experimental-strip-types "$OPENCODE_DIR/run-node.mjs" "$@"
WRAPPER

chmod +x "$MIMO_BIN/mimo"
echo -e "  ${GREEN}mimo установлен ✓${NC}"

# ─── Шаг 5: esbuild platform package ────────────────────────
echo ""
echo -e "${YELLOW}[5/5]${NC} Настройка esbuild..."
OPENCODE_NM="$OPENCODE_DIR/packages/opencode/node_modules"
if [ ! -d "$OPENCODE_NM/@esbuild" ]; then
  npm install -g @esbuild/linux-x64 2>/dev/null || true
  GLOBAL_NM=$(npm root -g)
  if [ -d "$GLOBAL_NM/@esbuild" ]; then
    ln -sf "$GLOBAL_NM/@esbuild" "$OPENCODE_NM/@esbuild"
    echo -e "  ${GREEN}esbuild platform package ✓${NC}"
  else
    echo -e "  ${RED}Не удалось настроить esbuild platform package${NC}"
  fi
else
  echo -e "  ${GREEN}esbuild platform package ✓${NC}"
fi

# ─── Готово ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Установка завершена!${NC}"
echo ""
echo -e "  Запуск:  mimo --help"
echo -e "  Тест:    mimo run \"привет\""
echo -e "  Модели:  mimo models"
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
