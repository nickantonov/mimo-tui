import { existsSync, readFileSync, writeFileSync, statSync } from "fs"
import { fileURLToPath, pathToFileURL } from "url"
import path from "path"
import { createRequire } from "module"
import { execSync } from "child_process"
import { randomBytes } from "crypto"

const require = createRequire(import.meta.url)
const SHIM_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..")

// ============================================================
// GlobalThis.Bun shim — Node.js implementations of Bun APIs
// ============================================================
if (typeof globalThis.Bun === "undefined") {
  let stringWidthPkg
  try {
    stringWidthPkg = require("string-width")
  } catch (e) {
    stringWidthPkg = (s) => [...s].length
  }

  class BunFile {
    #path
    #sync
    constructor(filePath) {
      this.#path = filePath
      this.#sync = true
    }
    text() {
      return readFileSync(this.#path, "utf8")
    }
    json() {
      return JSON.parse(readFileSync(this.#path, "utf8"))
    }
    arrayBuffer() {
      return readFileSync(this.#path).buffer
    }
    exists() {
      try {
        statSync(this.#path)
        return true
      } catch (e) {
        return false
      }
    }
  }

  globalThis.Bun = {
    file(filePath) {
      return new BunFile(filePath)
    },
    write(filePath, data) {
      if (data instanceof ArrayBuffer) {
        data = Buffer.from(data)
      } else if (data instanceof Blob) {
        // Blob → sync read not possible, but rare usage
        writeFileSync(filePath, data)
        return Promise.resolve()
      }
      writeFileSync(filePath, data)
      return Promise.resolve()
    },
    stringWidth(str) {
      return stringWidthPkg(str)
    },
    stripANSI(str) {
      return str.replace(/\x1B\[[0-9;]*[mK]/g, "")
    },
    sleep(ms) {
      return new Promise(resolve => setTimeout(resolve, ms))
    },
    get stdin() {
      return {
        text() {
          // Node.js uses stdin fd for ESM loader worker MessagePort communication.
          // Reading stdin here corrupts the protocol and causes deadlock.
          // Always return "" — real stdin is unavailable in this context.
          process.stderr.write("[BUN-SHIM] stdin.text() called, returning empty\n")
          return Promise.resolve("")
        }
      }
    },
    get version() {
      return process.version.replace("v", "")
    },
    Transpiler: class {
      #opts
      constructor(opts) {
        this.#opts = opts
      }
      transformSync(code) {
        if (esbuild) {
          const result = esbuild.transformSync(code, {
            loader: this.#opts?.loader || "ts",
            format: "esm",
            target: "node22",
          })
          return result.code
        }
        // Fallback: strip types
        return code
          .replace(/import\s+type\s+\{[^}]+\}\s+from\s+[^;]+;?\s*/gm, "")
          .replace(/import\s+type\s+\w+\s+from\s+[^;]+;?\s*/gm, "")
          .replace(/export\s+type\s+\{[^}]+\}\s+from\s+[^;]+;?\s*/gm, "")
          .replace(/import\s+\{[^}]+\}\s+from\s+[^"'][^;]+;?\s*/gm, "")
          .replace(/:\s*(string|number|boolean|any|unknown|void|never|object|symbol|bigint)\b(?=[=),;\n])/g, "")
      }
    },
    $(strings, ...values) {
      const cmd = strings.reduce((acc, str, i) => acc + str + (values[i] ?? ""), "")
      const result = execSync(cmd, { encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] })
      return {
        stdout: result,
        exitCode: 0,
        text() { return result },
        json() { return JSON.parse(result) },
      }
    },
    build(opts) {
      // Bun.build → esbuild.buildSync
      if (esbuild) {
        const result = esbuild.buildSync({
          entryPoints: opts.entrypoints,
          outdir: opts.outdir,
          target: "node22",
          format: "esm",
          splitting: false,
          bundle: true,
          write: false,
        })
        return {
          outputs: result.outputFiles.map(f => ({
            path: f.path,
            text: f.text,
          })),
          success: true,
        }
      }
      return { outputs: [], success: false }
    }
  }
}

// ============================================================
// opencode.ai free tier: intercept fetch to send ?key= instead of Authorization header
// The free client key lives at ~/.local/share/mimocode/mimo-free-client
// opencode.ai rejects requests with BOTH Authorization header AND ?key= param
// ============================================================
{
  const freeClientPaths = [
    path.join(path.dirname(fileURLToPath(import.meta.url)), "../../../../../.local/share/mimocode/mimo-free-client"),
    path.join(process.env.HOME || "", ".local/share/mimocode/mimo-free-client"),
  ]
  let freeKey
  for (const p of freeClientPaths) {
    try {
      freeKey = readFileSync(p, "utf-8").trim()
      if (freeKey) break
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
}

let esbuild
try {
  esbuild = require("esbuild")
} catch (e) {
  // esbuild not in node_modules — try global install locations
  try {
    const nvmGlobal = path.resolve(path.dirname(process.execPath), "..", "lib", "node_modules")
    esbuild = require(path.join(nvmGlobal, "esbuild"))
  } catch (e2) {
    try {
      esbuild = require("/home/fox/.npm-global/lib/node_modules/esbuild")
    } catch (e3) {}
  }
}

const BUN_SQLITE_SHIM = `
import { DatabaseSync } from "node:sqlite";
export const Database = DatabaseSync;
export { DatabaseSync };
`

export async function resolve(specifier, context, nextResolve) {
  hookLog("resolve", `${specifier} from ${context.parentURL || "none"}`)
  // @tui/ alias → ./src/cli/cmd/tui/
  if (specifier.startsWith("@tui/")) {
    const tuiPath = path.join(SHIM_DIR, specifier.replace("@tui/", "src/cli/cmd/tui/"))
    if (existsSync(tuiPath + ".ts")) {
      return { url: pathToFileURL(tuiPath + ".ts").href, shortCircuit: true }
    }
    if (existsSync(tuiPath + ".tsx")) {
      return { url: pathToFileURL(tuiPath + ".tsx").href, shortCircuit: true }
    }
    if (existsSync(path.join(tuiPath, "index.ts"))) {
      return { url: pathToFileURL(path.join(tuiPath, "index.ts")).href, shortCircuit: true }
    }
    if (existsSync(path.join(tuiPath, "index.tsx"))) {
      return { url: pathToFileURL(path.join(tuiPath, "index.tsx")).href, shortCircuit: true }
    }
  }

  // @/ alias → ./src/
  if (specifier.startsWith("@/")) {
    const srcPath = path.join(SHIM_DIR, specifier.replace("@/", "src/"))
    // Exact file match (not directory)
    if (existsSync(srcPath) && !srcPath.endsWith("/")) {
      const stat = require("fs").statSync(srcPath, { throwIfNoEntry: false })
      if (stat && stat.isFile()) {
        return { url: pathToFileURL(srcPath).href, shortCircuit: true }
      }
    }
    if (existsSync(srcPath + ".ts")) {
      return { url: pathToFileURL(srcPath + ".ts").href, shortCircuit: true }
    }
    if (existsSync(srcPath + ".tsx")) {
      return { url: pathToFileURL(srcPath + ".tsx").href, shortCircuit: true }
    }
    if (existsSync(path.join(srcPath, "index.ts"))) {
      return { url: pathToFileURL(path.join(srcPath, "index.ts")).href, shortCircuit: true }
    }
    if (existsSync(path.join(srcPath, "index.tsx"))) {
      return { url: pathToFileURL(path.join(srcPath, "index.tsx")).href, shortCircuit: true }
    }
    // Bun-style: directory + name.ts
    if (existsSync(srcPath)) {
      const stat = require("fs").statSync(srcPath, { throwIfNoEntry: false })
      if (stat && stat.isDirectory()) {
        const baseName = path.basename(srcPath)
        if (existsSync(path.join(srcPath, baseName + ".ts"))) {
          return { url: pathToFileURL(path.join(srcPath, baseName + ".ts")).href, shortCircuit: true }
        }
      }
    }
  }

  if (specifier === "bun:sqlite") {
    return { url: "data:text/javascript," + encodeURIComponent(BUN_SQLITE_SHIM), shortCircuit: true }
  }

  if (specifier === "bun:ffi") {
    const shimPath = path.join(SHIM_DIR, "native/bun-ffi-shim/index.mjs")
    if (existsSync(shimPath)) {
      return { url: pathToFileURL(shimPath).href, shortCircuit: true }
    }
  }

  if (specifier === "bun") {
    const bunShim = `
      export { fileURLToPath, pathToFileURL } from "node:url"
      export { readFileSync, writeFileSync, existsSync, mkdirSync, statSync, readdirSync, unlinkSync, copyFileSync } from "node:fs"
      export { join, resolve, dirname, basename, relative, extname } from "node:path"
      export function plugin() { return { name: 'noop', setup() {} } }
      export default { plugin() { return { name: 'noop', setup() {} } } }
    `
    return { url: "data:text/javascript," + encodeURIComponent(bunShim), shortCircuit: true }
  }

  // Handle relative imports without extension — try .ts
  if (specifier.startsWith(".") && context.parentURL) {
    const parentDir = path.dirname(fileURLToPath(context.parentURL))
    const resolved = path.resolve(parentDir, specifier)
    
    // .js → .ts redirect: if specifier ends in .js but only .ts exists, redirect
    if (specifier.endsWith(".js")) {
      const tsVersion = resolved.replace(/\.js$/, ".ts")
      if (existsSync(tsVersion) && !existsSync(resolved)) {
        return { url: pathToFileURL(tsVersion).href, shortCircuit: true }
      }
    }

    // Try .ts first for extensionless specifiers
    if (existsSync(resolved + ".ts")) {
      return { url: pathToFileURL(resolved + ".ts").href, shortCircuit: true }
    }
    if (existsSync(resolved + ".tsx")) {
      return { url: pathToFileURL(resolved + ".tsx").href, shortCircuit: true }
    }
    if (existsSync(path.join(resolved, "index.ts"))) {
      return { url: pathToFileURL(path.join(resolved, "index.ts")).href, shortCircuit: true }
    }
    if (existsSync(path.join(resolved, "index.tsx"))) {
      return { url: pathToFileURL(path.join(resolved, "index.tsx")).href, shortCircuit: true }
    }

    // Try the default resolution
    try {
      const result = await nextResolve(specifier, context)
      return result
    } catch (e) {}
    
    if (existsSync(path.join(resolved, "index.js"))) {
      return { url: pathToFileURL(path.join(resolved, "index.js")).href, shortCircuit: true }
    }
  }

  // npm packages: try .js and /index.js fallback
  if (!specifier.startsWith(".") && !specifier.startsWith("/") && !specifier.startsWith("node:") && !specifier.startsWith("file:") && !specifier.startsWith("data:") && !specifier.startsWith("bun:")) {
    try { return { url: pathToFileURL(require.resolve(specifier + ".js")).href, shortCircuit: true } } catch (e) {}
    try { return { url: pathToFileURL(require.resolve(specifier + "/index.js")).href, shortCircuit: true } } catch (e) {}
  }

  // Generic fallback: try nextResolve, and if it resolves to .js that doesn't exist, try .ts
  try {
    const result = await nextResolve(specifier, context)
    const url = new URL(result.url)
    if (url.pathname.endsWith(".js") && !existsSync(fileURLToPath(url))) {
      const tsPath = url.pathname.replace(/\.js$/, ".ts")
      if (existsSync(tsPath)) {
        return { url: pathToFileURL(tsPath).href, shortCircuit: true }
      }
    }
    return result
  } catch (e) {
    hookLog("resolve:nextResolve failed", specifier, e)
    // If nextResolve fails, try .ts extension
    if (context.parentURL) {
      const parentDir = path.dirname(fileURLToPath(context.parentURL))
      const base = specifier.startsWith(".") ? path.resolve(parentDir, specifier) : specifier
      if (existsSync(base + ".ts")) {
        return { url: pathToFileURL(base + ".ts").href, shortCircuit: true }
      }
    }
    throw e
  }
}

function stripTypes(content) {
  // import type { ... } from "..." (full line)
  content = content.replace(/^import\s+type\s+\{[^}]+\}\s+from\s+[^;]+;?\s*$/gm, "")
  // import type Foo from "..." (full line)
  content = content.replace(/^import\s+type\s+\w+\s+from\s+[^;]+;?\s*$/gm, "")
  // export type { ... } from "..." (full line)
  content = content.replace(/^export\s+type\s+\{[^}]+\}\s+from\s+[^;]+;?\s*$/gm, "")
  // inline type: { type Foo } → { Foo }, { type Foo as Bar } → { Foo as Bar }
  content = content.replace(/,\s*type\s+/g, ", ")
  content = content.replace(/{\s*type\s+/g, "{ ")
  return content
}

function hookLog(tag, msg, err) {
  const line = `[txt-hooks ${tag}] ${msg}` + (err ? `: ${err.message || err}` : "") + "\n"
  try { process.stderr.write(line) } catch {}
}

export async function load(url, context, nextLoad) {
  try {
  hookLog("load", `${url} format=${context.format || "?"}`)

  // .ts / .tsx — intercept FIRST, before any other checks
  if (typeof url === "string" && (url.endsWith(".ts") || url.endsWith(".tsx"))) {
    const filePath = fileURLToPath(url)
    const ext = url.endsWith(".tsx") ? "tsx" : "ts"
    hookLog("load:ts", `MATCH: ${filePath} ext=${ext} esbuild=${!!esbuild}`)
    const content = readFileSync(filePath, "utf8")
    hookLog("load:ts", `read ${content.length} bytes`)
    if (esbuild) {
      hookLog("load:ts", `calling esbuild.transform for ${filePath}...`)
      try {
        const transformPromise = esbuild.transform(content, {
          loader: ext,
          format: "esm",
          target: "node22",
        })
        const timeoutPromise = new Promise((_, reject) =>
          setTimeout(() => reject(new Error("esbuild timeout (5s)")), 5000)
        )
        const result = await Promise.race([transformPromise, timeoutPromise])
        hookLog("load:ts", `esbuild ok, output ${result.code.length} bytes`)
        return { format: "module", source: result.code, shortCircuit: true }
      } catch (ebErr) {
        hookLog("load:ts", `esbuild FAILED on ${filePath}: ${ebErr.message.split("\n")[0]}`)
      }
    }
    hookLog("load:ts", `using stripTypes for ${filePath}`)
    const stripped = stripTypes(content)
    return { format: "module", source: stripped, shortCircuit: true }
  }

  if (url.endsWith(".txt")) {
    try {
      const filePath = fileURLToPath(url)
      const content = readFileSync(filePath, "utf8")
      return { format: "module", source: `export default ${JSON.stringify(content)};`, shortCircuit: true }
    } catch (e) { hookLog("load:txt", url, e) }
  }

  if (url.endsWith(".scm")) {
    return { format: "module", source: "export default '';", shortCircuit: true }
  }

  if (url.endsWith(".wasm")) {
    try {
      const filePath = fileURLToPath(url)
      return { format: "module", source: `export default ${JSON.stringify(filePath)};`, shortCircuit: true }
    } catch (e) { hookLog("load:wasm", url, e) }
  }

  return nextLoad(url, context)
  } catch (e) { hookLog("load:FATAL", url, e); throw e }
}
