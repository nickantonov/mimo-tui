# Архитектура Node.js порта

## Цель

Порт MiMo-Code с Bun на Node.js для работы на Xeon 5472 (нет AVX → Bun не запускается).

## Слои

```
┌─────────────────────────────────────────────────────┐
│  run-node.mjs                                        │
│  ├── GlobalThis.Bun shim (main thread)               │
│  ├── Free tier fetch interceptor                     │
│  ├── register(txt-hooks.mjs) — ESM loader            │
│  └── import("./src/index.ts")                        │
├─────────────────────────────────────────────────────┤
│  txt-hooks.mjs (ESM loader worker thread)            │
│  ├── resolve() — алиасы путей, bun:sqlite/ffi       │
│  ├── load() — esbuild TS transform, stripTypes      │
│  └── GlobalThis.Bun shim (worker context)            │
├─────────────────────────────────────────────────────┤
│  index.ts (CLI)                                      │
│  ├── yargs 18 — парсинг аргументов                  │
│  ├── handler dispatch                                │
│  └── process.exit() → handler via globalThis         │
├─────────────────────────────────────────────────────┤
│  run.ts (handler)                                    │
│  ├── Argument parsing                                │
│  ├── Bootstrap (Effect runtime)                      │
│  ├── Server (Hono in-process)                        │
│  ├── SDK client (opencode.ai compatible)             │
│  └── LLM session (streamText)                        │
├─────────────────────────────────────────────────────┤
│  provider.ts                                         │
│  ├── Model resolution                                │
│  ├── SDK initialization (@ai-sdk/openai-compatible)  │
│  ├── Fetch interceptor (opencode.ai → xiaomimimo)   │
│  └── SSE streaming (ReadableStream)                  │
└─────────────────────────────────────────────────────┘
```

## Ключевые файлы

| Файл | Назначение | Строки |
|------|-----------|--------|
| `run-node.mjs` | Entry point, Bun shim, fetch interceptor | ~80 |
| `txt-hooks.mjs` | ESM loader (resolve + load hooks) | ~420 |
| `index.ts` | CLI entry, yargs dispatch | ~275 |
| `run.ts` | `mimo run` command handler | ~720 |
| `provider/provider.ts` | LLM provider, SSE streaming | ~1870 |
| `server/server.ts` | In-process HTTP server (Hono) | ~350 |

## Потоки данных

### `mimo run "привет"`

```
1. run-node.mjs: GlobalThis.Bun shim → register(txt-hooks) → import(index.ts)
2. index.ts: yargs parses "run привет" → dispatches to RunCommand.handler
3. run.ts: handler parses args, builds message
4. run.ts: bootstrap() → Effect runtime init → Server.init → Provider.init
5. run.ts: SDK creates session → sends prompt
6. provider.ts: resolves model → creates @ai-sdk/openai-compatible
7. provider.ts: streamText() → fetch to opencode.ai (Cloudflare)
8. provider.ts: SSE stream → response chunks → session update
9. run.ts: loop() polls session.status until completion
10. run.ts: prints response to stdout
```

## Паттерны

### ESM Loader Hook Registration

```javascript
// run-node.mjs
register("./src/util/txt-hooks.mjs", import.meta.url)
await import("./src/index.ts")
```

`register()` загружает хуки в **worker thread**. `import()` запускает приложение в **main thread**.

### Bun Shim Isolation

```javascript
// run-node.mjs — main thread shim
globalThis.Bun = { file(), write(), stdin, ... }

// txt-hooks.mjs — worker thread shim  
if (typeof globalThis.Bun === "undefined") {
  globalThis.Bun = { ... }
}
```

Main thread shim необходим потому что `globalThis.Bun` из worker thread **не пропагируется** в main thread.

### Handler Promise Retention

```javascript
// index.ts
cli.parse()  // sync — dispatches handler
const hp = globalThis.__handlerPromise
if (hp) await hp

// run.ts
const _p = (async () => { /* handler body */ })()
globalThis.__handlerPromise = _p
```

Yargs 18 не сохраняет промис handler. Решение — хранить его на `globalThis`.
