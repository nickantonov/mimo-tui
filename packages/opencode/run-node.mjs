#!/usr/bin/env node
// MiMo-Code Node.js entry point
// Registers custom ESM loader (txt-hooks.mjs) that handles:
//   - TypeScript transpilation via esbuild
//   - @/ @tui/ path aliases
//   - bun:sqlite → node:sqlite shim
//   - bun:ffi → N-API addon
//   - .txt / .wasm / .scm imports
//   - GlobalThis.Bun polyfill (Bun.file, Bun.write, etc.)
//   - opencode.ai free tier fetch interception (?key= instead of Authorization header)
//
// Usage: node --no-experimental-strip-types run-node.mjs
import { register } from "node:module"
import { readFileSync, existsSync } from "fs"
import { join } from "path"
import { homedir } from "os"

// Intercept fetch for opencode.ai free tier BEFORE any SDK loads
// opencode.ai expects ?key= query parameter, not Authorization header
const freeClientPaths = [
  join(homedir(), ".local/share/mimocode/mimo-free-client"),
  join(process.cwd(), "mimo-free-client"),
]
let freeKey
for (const p of freeClientPaths) {
  try {
    if (existsSync(p)) { freeKey = readFileSync(p, "utf-8").trim(); break }
  } catch {}
}
if (freeKey) {
  const origFetch = globalThis.fetch
  globalThis.fetch = async function(input, init) {
    const urlStr = typeof input === "string" ? input : input instanceof URL ? input.href : String(input)
    if (urlStr.includes("opencode.ai") || urlStr.includes("zen")) {
      const u = new URL(urlStr)
      u.searchParams.set("key", freeKey)
      const headers = new Headers(init?.headers)
      headers.delete("authorization")
      return origFetch(u.href, { ...init, headers })
    }
    return origFetch(input, init)
  }
}

// Bun shim for main thread — worker thread shim doesn't propagate to main thread
if (typeof globalThis.Bun === "undefined") {
  const { readFileSync, writeFileSync, statSync } = await import("fs")

  class BunFile {
    #path
    constructor(filePath) { this.#path = filePath }
    text() { return readFileSync(this.#path, "utf8") }
    json() { return JSON.parse(readFileSync(this.#path, "utf8")) }
    arrayBuffer() { return readFileSync(this.#path).buffer }
    exists() { try { statSync(this.#path); return true } catch { return false } }
  }

  let stringWidthPkg
  try { stringWidthPkg = (await import("string-width")).default } catch { stringWidthPkg = (s) => [...s].length }

  globalThis.Bun = {
    file(filePath) { return new BunFile(filePath) },
    write(filePath, data) { writeFileSync(filePath, data); return Promise.resolve() },
    stringWidth(str) { return stringWidthPkg(str) },
    stripANSI(str) { return str.replace(/\x1B\[[0-9;]*[mK]/g, "") },
    sleep(ms) { return new Promise(r => setTimeout(r, ms)) },
    stdin: { text() { return Promise.resolve("") } },
    get version() { return process.version.replace("v", "") },
    Transpiler: class { transformSync(code) { return { code } } },
    build() { throw new Error("Bun.build not available on Node.js") },
  }
}

register("./src/util/txt-hooks.mjs", import.meta.url)

await import("./src/index.ts")
