# Work Log — MiMo-Code Node.js Port

## Repository State

| Item | Value |
|------|-------|
| **Main repo** | `/home/fox/DEPLOY/MiMo-Code-main` branch `main` (clean) |
| **Patched repo** | `/home/fox/DEPLOY/MiMo-Code-main-patched` branch `master` |
| **Runtime** | Node.js v22.23.1 via nvm |
| **Launch** | `node --no-experimental-strip-types packages/opencode/run-node.mjs` |
| **Status** | **WORKING** — `--help`, `models`, `stats`, `run` all functional |

## ROOT CAUSE FOUND AND FIXED

**Problem**: `globalThis.Bun` was set in ESM loader **worker thread** (txt-hooks.mjs), but handler code runs in **main thread**. Worker's `globalThis` doesn't propagate to main thread.

**Fix**: Added Bun shim directly in `run-node.mjs` (main thread entry point).

## Modified Files

### `packages/opencode/run-node.mjs`
- L18-43: opencode.ai free tier fetch interceptor
- L44-79: **MAIN THREAD Bun shim** (BunFile, Bun.write, Bun.stdin, Bun.version, etc.)
- L81: `register("./src/util/txt-hooks.mjs", import.meta.url)`
- L83: `await import("./src/index.ts")`

### `packages/opencode/src/util/txt-hooks.mjs` (~415 lines)
- ESM loader hooks (esbuild TS transform, @tui/@/ aliases, bun:sqlite/ffi shims)
- Worker thread Bun shim (for ESM loader context)

### `packages/opencode/src/index.ts`
- L231-236: `cli.parse()` + `globalThis.__handlerPromise` await

### `packages/opencode/src/cli/cmd/run.ts`
- Handler stores promise on `globalThis.__handlerPromise`
- L105: `continue` → `return` in ReadableStream.pull()

### `packages/opencode/src/provider/provider.ts`
- Removed duplicate imports (lines 23-24)

### `packages/opencode/src/cli/cmd/run.ts` debug markers
- [RUN-DEBUG] handler entered/message built/directory check/stdin/bootstrap/execute

## Rollback Points

| File | Backup |
|------|--------|
| `backups/db.ts.bak` | DB layer |
| `backups/proxy.ts.bak` | Proxy layer |
| `backups/rpc.ts.bak` | RPC layer |
| `backups/win32.ts.bak` | Win32 layer |
| Symlink | `node_modules/@esbuild` → global |

```bash
# Full rollback:
rm -rf /home/fox/DEPLOY/MiMo-Code-main-patched
cp -a /home/fox/DEPLOY/MiMo-Code-main /home/fox/DEPLOY/MiMo-Code-main-patched
ln -s /home/fox/.nvm/versions/node/v22.23.1/lib/node_modules/@esbuild node_modules/@esbuild
```

## Known Issues

1. **hy3-free model not responding** — same as Bun version. Model `opencode/hy3-free` doesn't return content. Need different model.
2. **Bun.stdin shim always returns ""** — real stdin unavailable in this context.
3. **esbuild timeout (5s)** — some files hang esbuild (e.g. provider.ts had `continue` in ReadableStream).
