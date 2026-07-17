# MiMo-Code: Исключение Bun — Статус проекта

**Дата обновления:** 2026-07-16 23:40
**Цель:** Полностью исключить Bun runtime из MiMo-Code, заменив на Node.js
**Проект:** `/home/fox/DEPLOY/mimo/MiMo-Code-main/packages/opencode`
**Целевая машина:** Windows 10 x64, Xeon 5472, **без AVX**

---

## ❌ BUN BASELINE BINARY — МЁРТВЫЙ ПУТЬ

### Доказано экспериментально:
```
Bun v1.3.14 Windows x64 (baseline)
CPU lacks AVX support. Please consider upgrading to a newer CPU.
panic(thread 388): Illegal instruction at address 0x7FF633916E63
```

- `--baseline` убирает AVX2 только из **JavaScript кода**
- Сам **Bun runtime** использует AVX инструкции на уровне ассемблера
- **Никакая сборка Bun не будет работать на процессоре без AVX**

### Построенные бинарники (все мёртвы для Xeon 5472):
| Файл | Размер | Статус |
|------|--------|--------|
| `dist/mimocode-windows-x64-baseline/bin/mimo.exe` | 128 MB | CRASH — no AVX |
| `dist/mimocode-linux-x64-baseline/bin/mimo` | 127 MB | Работает на build machine |
| `dist/mimocode-linux-x64-baseline-musl/bin/mimo` | 124 MB | - |
| `dist/mimocode-linux-x64/bin/mimo` | 127 MB | - |

### Инсталлер (не работает на целевой машине):
- `mimocode-installer/` — install.bat, install.ps1, mimo.exe
- `mimocode-v0.1.6-windows-baseline.zip` — 46 MB

---

## ✅ NODE.JS ПОРТ — ЗАМОРОЖЕН (90% готово)

### Что сделано:
- **N-API addon** (`native/bun-ffi-shim/`) — работает, загружает libopentui.so
- **50+ файлов** — Bun API заменены на Node.js (readFileSync, fs, url, и т.д.)
- **@opentui/core + solid** — пропатчены (bun:ffi → N-API, .ts→.js stubs)
- **txt-hooks.mjs** — unified ESM loader (bun: shims, .txt, .ts→esbuild, @/ aliases)
- **rpc.ts** — typeof guard для onmessage (Worker API в Node.js main thread)
- **proxy.ts** — try-catch для WebSocket creation
- **drizzle-orm/node-sqlite** — замена drizzle-orm/bun-sqlite
- **node:sqlite DatabaseSync** — замена bun:sqlite Database

### Блокер: Effect runtime init hangs
- `app-runtime.ts` импортирует ~40+ модулей через Effect Layer pattern
- В Bun — работает (особая семантика ESM модулей)
- В Node.js — зависает (circular lazy init deadlock)
- Сервер логирует `service=server-proxy` но никогда не слушает порт 4096

### Root cause:
Effect runtime использует `Layer.effect` + `InstanceState.make` с lazy initialization chains. В Bun ESM module resolution разрешает circular deps иначе. В Node.js — deadlock.

---

## 🔬 ИССЛЕДОВАТЕЛЬСКАЯ ГИПОТЕЗА (не проверена)

### ESM-компиляция без bundling
- Скомпилировать .ts → .js через esbuild с `--splitting` (без `--bundle`)
- Запустить раздельные .js файлы напрямую в Node.js
- **Почему может работать:** В bundle circular deps создают deadlock из-за `__esm` lazy init. В раздельных ESM файлах Node.js загружает модули по одному, circular refs получают `undefined` (а не hang).

---

## 📋 ПЛАН ДЕЙСТВИЙ

### Приоритет 1: Node.js порт
1. Проверить ESM-split гипотезу
2. Если не поможет — dynamic imports для разрыва circular deps в app-runtime.ts
3. Если не поможет — рефакторинг Effect runtime

### Приоритет 2: C/ASM launcher (после Node.js порта)
- Tiny C программа для CPU detection (AVX/не-AVX)
- Запуск правильного Node.js бинарника
- НЕ для "обхода" AVX — Bun всё равно не работает без AVX

### Приоритет 3: Заморозка
- Ветка `node-port/research` с N-API addon и всеми результатами
