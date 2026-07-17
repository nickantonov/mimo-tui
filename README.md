# MiMo-Code — Node.js Port

<p align="center">
  <img src="assets/logo/mimocode.svg" alt="MiMo-Code Logo" width="120" height="120"/>
</p>

**Браузер для LLM.** Как Chrome ходит на веб-серверы, так MiMo-Code ходит на LLM-серверы Xiaomi.

**Автор:** Nick Antonov, Borodachamba Studio (1998-2026). All rights reserved.

## Архитектура

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐
│  Пользователь │───▶│ MiMo-Code TUI │───▶│ Xiaomi LLM Backend  │
│  (терминал)   │◀───│ (браузер)     │◀───│ (Alibaba Cloud)     │
└─────────────┘    └──────────────┘    └─────────────────────┘
                         │
                    Node.js 22.23.1
                    (ESM loader)
```

MiMo-Code — терминальный TUI-клиент (fork OpenCode), который подключается к серверам Xiaomi для инференса LLM. Модели (`mimo-v2.5-free`, `hy3-free` и др.) живут на стороне сервера. Клиент — это локальный TUI.

**Проблема**: исходный клиент работает на Bun, который требует AVX. На Xeon 5472 (нет AVX) Bun не запускается. Порт на Node.js решает эту проблему.

## Быстрый старт

### Зависимости

- **Node.js** >= 22.23.1 (через nvm)
- **esbuild** (для трансформации TypeScript)
- **@esbuild/linux-x64** (платформенный бинарник esbuild)

### Установка

```bash
# 1. Установить nvm и Node.js 22
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 22

# 2. Установить esbuild глобально
npm install -g esbuild

# 3. Слинковать платформенный пакет
ln -s $(npm root -g)/@esbuild packages/opencode/node_modules/@esbuild

# 4. Запуск
cd packages/opencode
node --no-experimental-strip-types run-node.mjs --help
```

### Запуск

```bash
# TUI (интерактивный режим)
node --no-experimental-strip-types run-node.mjs

# CLI (одноразовый запрос)
node --no-experimental-strip-types run-node.mjs run "привет"
node --no-experimental-strip-types run-node.mjs run "привет" -m "opencode/mimo-v2.5-free"

# Список моделей
node --no-experimental-strip-types run-node.mjs models

# Статистика
node --no-experimental-strip-types run-node.mjs stats
```

## Как это работает

### ESM Loader (txt-hooks.mjs)

Node.js не понимает TypeScript, Bun-специфичные импорты и алиасы путей. Решение — кастомный ESM loader:

1. **`resolve()` хук** — перехватывает импорты:
   - `@tui/` → `./src/cli/cmd/tui/`
   - `@/` → `./src/`
   - `bun:sqlite` → `node:sqlite` shim
   - `bun:ffi` → N-API addon
   - `.ts` расширения → резолвится в `.ts` файлы

2. **`load()` хук** — трансформирует файлы:
   - `.ts` / `.tsx` → esbuild трансформация (target: node22)
   - Если esbuild падает → stripTypes fallback (regex-based)
   - 5s таймаут на esbuild (зависшие файлы)
   - `.txt` → `export default content`
   - `.wasm` → `export default filePath`

### Bun Shim (run-node.mjs)

`globalThis.Bun` устанавливается **в main thread** (не в ESM worker):

| API | Реализация |
|-----|-----------|
| `Bun.file()` | `readFileSync` + lazy объект |
| `Bun.write()` | `writeFileSync` |
| `Bun.stdin.text()` | `Promise.resolve("")` (stdin недоступен) |
| `Bun.sleep()` | `setTimeout` |
| `Bun.stringWidth()` | npm `string-width` |
| `Bun.version` | `process.version` |

### Fetch Interceptor (run-node.mjs)

Перехватывает HTTP-запросы к `opencode.ai` и добавляет `?key=<fingerprint>` для авторизации бесплатного тира.

### Provider (provider.ts)

- Использует `@ai-sdk/openai-compatible` SDK
- Подключается к `opencode.ai` (Cloudflare) для списка моделей
- Подключается к Alibaba Cloud (47.236.x) для инференса
- SSE streaming через ReadableStream

## Модели

| Модель | Тип | Статус |
|--------|-----|--------|
| `opencode/mimo-v2.5-free` | Бесплатный | ✅ Работает |
| `opencode/deepseek-v4-flash-free` | Бесплатный | ? |
| `opencode/hy3-free` | Бесплатный | ❌ Null content |
| `opencode/nemotron-3-ultra-free` | Бесплатный | ? |
| `opencode/north-mini-code-free` | Бесплатный | ? |
| `xiaomi/mimo-v2.5` | Платный | ? |
| `xiaomi/mimo-v2.5-pro` | Платный | ? |

## Авторизация

Бесплатный тир использует `device fingerprint`:
- Файл: `~/.local/share/mimocode/mimo-free-client`
- Содержимое: SHA-256 хеш `(hostname|linux|x64|cpu-model|username)`
- Auth flow: bootstrap → JWT → Bearer token
- Endpoint: `api.xiaomimimo.com/api/free-ai/bootstrap`

## Известные проблемы

1. **yargs 18 + Node.js ESM**: `parse()` синхронный, не сохраняет промис handler. Решение: `globalThis.__handlerPromise`
2. **esbuild зависает** на некоторых файлах (например, `continue` в ReadableStream). Решение: 5s таймаут + stripTypes fallback
3. **Bun stdin** — в контексте ESM loader worker stdin используется для MessagePort IPC. Чтение stdin ломает протокол. Решение: всегда возвращать `""`.
4. **`@esbuild/linux-x64`** — платформенный пакет не в node_modules. Решение: symlink из global npm.

## Структура проекта

```
packages/opencode/
├── run-node.mjs              # Entry point (main thread Bun shim)
├── src/
│   ├── util/txt-hooks.mjs    # ESM loader (resolve + load hooks)
│   ├── cli/cmd/run.ts        # `mimo run` command handler
│   ├── provider/provider.ts  # LLM provider (AI SDK)
│   ├── server/server.ts      # In-process Hono HTTP server
│   └── index.ts              # CLI entry (yargs)
├── node_modules/
│   └── @esbuild → symlink    # Platform binary
└── migration/                # SQLite migrations
```

## Отладка

### Логи на stderr

ESM loader пишет в stderr:
```
[txt-hooks resolve] ./src/index.ts from .../run-node.mjs
[txt-hooks load:ts] esbuild ok, output 7716 bytes
```

Handler пишет в stderr:
```
[RUN-DEBUG] handler entered, pid=12345
[RUN-DEBUG] message built: привет
[RUN-DEBUG] bootstrap callback entered
```

### Crash diagnostics

Если процесс падает без вывода — проверяй stderr:
```bash
node --no-experimental-strip-types run-node.mjs run "тест" 2>/tmp/crash.log
cat /tmp/crash.log | grep "RUN-DEBUG\|ERROR\|FATAL"
```

### Network tracing

```bash
# Какие IP ходит Bun:
strace -f -e trace=connect ~/.mimocode/bin/mimo run "тест" 2>&1 | grep sin_addr

# Какие IP ходит Node.js:
strace -f -e trace=connect node --no-experimental-strip-types run-node.mjs run "тест" 2>&1 | grep sin_addr
```

## Rollback

```bash
# Полный откат к upstream:
rm -rf MiMo-Code-main-patched
cp -a MiMo-Code-main MiMo-Code-main-patched
ln -s $(npm root -g)/@esbuild MiMo-Code-main-patched/packages/opencode/node_modules/@esbuild
```

## Сеть

```
opencode.ai (Cloudflare: 104.26.x, 172.67.x)
    └── Список моделей, auth

api.xiaomimimo.com (Azure: 20.47.x, 20.157.x)
    └── Bootstrap JWT, free tier auth

Alibaba Cloud (47.236.x, 47.237.x, 8.222.x)
    └── LLM inference backend (mimo-v2.5-free и др.)
```

## Лицензия

См. [LICENSE](LICENSE)
