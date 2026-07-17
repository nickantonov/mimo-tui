import type { Hooks, PluginInput } from "@mimo-ai/plugin"
import { Log } from "../util"
import { Global } from "../global"
import crypto from "crypto"
import os from "os"
import fs from "fs"
import path from "path"

const log = Log.create({ service: "plugin.mimo-free" })

const MIMO_FREE_BASE_URL = (process.env.MIMO_FREE_BASE_URL || "https://api.xiaomimimo.com/").replace(/\/+$/, "")
const BOOTSTRAP_URL = `${MIMO_FREE_BASE_URL}/api/free-ai/bootstrap`
const CHAT_BASE_URL = `${MIMO_FREE_BASE_URL}/api/free-ai/openai`

// Cached fingerprint
let _fingerprint: string | undefined

function getFingerprint(): string {
  if (_fingerprint) return _fingerprint

  const filePath = path.join(Global.Path.data, "mimo-free-client")
  try {
    const existing = fs.readFileSync(filePath, "utf-8").trim()
    if (existing) {
      _fingerprint = existing
      return _fingerprint
    }
  } catch {}

  // Generate fingerprint from system info
  const cpuModel = os.cpus()[0]?.model ?? "unknown-cpu"
  const username = (() => {
    try { return os.userInfo().username } catch { return "unknown-user" }
  })()
  const identity = [os.hostname(), "linux", os.arch(), cpuModel, username].join("|")
  const hash = crypto.createHash("sha256").update(identity).digest("hex")

  try {
    fs.writeFileSync(filePath, hash, { mode: 0o600 })
  } catch (e) {
    log.warn("could not persist fingerprint", { error: e })
  }

  _fingerprint = hash
  return _fingerprint
}

// JWT token cache
let _jwt: string | undefined
let _jwtExp: number = 0
let _bootstrapPending: Promise<{ jwt: string; exp: number }> | undefined

function parseJwtExp(jwt: string): number {
  const parts = jwt.split(".")
  if (parts.length < 2) return Date.now() + 3_000_000 // 50 min fallback
  try {
    const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8"))
    if (typeof payload.exp === "number") return payload.exp * 1000
  } catch {}
  return Date.now() + 3_000_000
}

async function bootstrap(): Promise<{ jwt: string; exp: number }> {
  const resp = await fetch(BOOTSTRAP_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client: getFingerprint() }),
  })
  if (!resp.ok) {
    const body = await resp.text().catch(() => "")
    throw new Error(`mimo-free bootstrap failed: ${resp.status} ${body.slice(0, 200)}`)
  }
  const data = await resp.json() as { jwt?: string }
  if (!data.jwt) throw new Error("mimo-free bootstrap response missing jwt")
  return { jwt: data.jwt, exp: parseJwtExp(data.jwt) }
}

// Refresh margin: 5 minutes before expiry
const REFRESH_MARGIN = 300_000

async function getJwt(): Promise<string> {
  if (_jwt && _jwtExp - Date.now() > REFRESH_MARGIN) return _jwt
  if (_bootstrapPending) return (await _bootstrapPending).jwt
  _jwt = undefined
  _bootstrapPending = bootstrap()
  try {
    const result = await _bootstrapPending
    _jwt = result.jwt
    _jwtExp = result.exp
    return _jwt
  } finally {
    _bootstrapPending = undefined
  }
}

function withAuth(headers: HeadersInit | undefined, jwt: string): Headers {
  const h = new Headers(headers)
  h.set("Authorization", `Bearer ${jwt}`)
  h.set("X-Mimo-Source", "mimocode-cli-free")
  return h
}

async function chatFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  // Replace /chat/completions with /chat in URL (opencode SDK uses /chat/completions)
  let url = (typeof input === "string" || input instanceof URL ? String(input) : (input as any).url ?? String(input))
    .replace(/\/chat\/completions(\?|$)/, "/chat$1")

  let jwt = await getJwt()
  let resp = await fetch(url, { ...init, headers: withAuth(init?.headers, jwt) })

  // On 401/403, refresh token and retry
  if (resp.status === 401 || resp.status === 403) {
    _jwt = undefined
    jwt = await getJwt()
    resp = await fetch(url, { ...init, headers: withAuth(init?.headers, jwt) })
  }

  return resp
}

export async function MimoFreeAuthPlugin(_input: PluginInput): Promise<Hooks> {
  return {
    config: async (input) => {
      input.provider ??= {}
      input.provider.mimo ??= {
        name: "MiMo Auto (free)",
        npm: "@ai-sdk/openai-compatible",
        api: CHAT_BASE_URL,
        options: {
          apiKey: "anonymous", // Placeholder — auth handled by custom fetch
          fetch: chatFetch,
        },
        models: {
          "mimo-auto": {
            name: "MiMo Auto",
            attachment: true,
            reasoning: true,
            tool_call: true,
            temperature: true,
            modalities: {
              input: ["text", "image"],
              output: ["text"],
            },
            limit: {
              context: 1_000_000,
              output: 128_000,
            },
            cost: {
              input: 0,
              output: 0,
            },
          },
        },
      }
    },
  }
}
