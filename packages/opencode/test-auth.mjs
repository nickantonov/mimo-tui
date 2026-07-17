// Простой скрипт для проверки всех вариантов авторизации
// Запуск: node test-auth.mjs

import { readFileSync } from "fs"
import { homedir } from "os"
import { join } from "path"

const FINGERPRINT = readFileSync(join(homedir(), ".local/share/mimocode/mimo-free-client"), "utf-8").trim()
console.log("=== FINGERPRINT ===")
console.log(FINGERPRINT)
console.log()

// 1. Bootstrap → JWT
console.log("=== 1. BOOTSTRAP → JWT ===")
const bootstrapResp = await fetch("https://api.xiaomimimo.com/api/free-ai/bootstrap", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ client: FINGERPRINT }),
})
const bootstrapData = await bootstrapResp.json()
const JWT = bootstrapData.jwt
console.log("Status:", bootstrapResp.status)
console.log("JWT:", JWT ? JWT.slice(0, 50) + "..." : "NONE")
console.log()

// 2. GET models — opencode.ai с ?key=
console.log("=== 2. GET opencode.ai/zen/v1/models?key=FINGERPRINT ===")
const modelsResp = await fetch(`https://opencode.ai/zen/v1/models?key=${FINGERPRINT}`)
const modelsData = await modelsResp.json()
const freeModels = (modelsData.data || []).filter(m => m.id.includes("free") || m.id.includes("mimo"))
console.log("Status:", modelsResp.status)
console.log("Free/MiMo models:", freeModels.map(m => m.id).slice(0, 8))
console.log()

// 3. POST chat — opencode.ai с ?key=
console.log("=== 3. POST opencode.ai/zen/v1/chat/completions?key=FINGERPRINT ===")
const chatResp1 = await fetch("https://opencode.ai/zen/v1/chat/completions?key=" + FINGERPRINT, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "mimo-v2.5-free",
    messages: [{ role: "user", content: "say hi in one word" }],
    max_tokens: 10,
    stream: false,
  }),
})
const chatData1 = await chatResp1.json()
console.log("Status:", chatResp1.status)
if (chatData1.error) console.log("Error:", chatData1.error)
else console.log("Model:", chatData1.model, "Cost:", chatData1.cost, "Reply:", chatData1.choices?.[0]?.message?.content)
console.log()

// 4. POST chat — api.xiaomimimo.com с JWT Bearer
console.log("=== 4. POST api.xiaomimimo.com/api/free-ai/openai/chat с JWT ===")
const chatResp2 = await fetch("https://api.xiaomimimo.com/api/free-ai/openai/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${JWT}`,
    "X-Mimo-Source": "mimocode-cli-free",
  },
  body: JSON.stringify({
    model: "mimo-auto",
    messages: [{ role: "user", content: "say hi in one word" }],
    max_tokens: 10,
    stream: false,
  }),
})
const chatData2 = await chatResp2.json()
console.log("Status:", chatResp2.status)
if (chatData2.error) console.log("Error:", chatData2.error)
else console.log("Model:", chatData2.model, "Reply:", chatData2.choices?.[0]?.message?.content)
console.log()

// 5. POST chat — opencode.ai с Authorization Bearer JWT (неправильно, для сравнения)
console.log("=== 5. POST opencode.ai с Bearer JWT (wrong auth) ===")
const chatResp3 = await fetch("https://opencode.ai/zen/v1/chat/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${JWT}`,
  },
  body: JSON.stringify({
    model: "mimo-v2.5-free",
    messages: [{ role: "user", content: "say hi in one word" }],
    max_tokens: 10,
    stream: false,
  }),
})
const chatData3 = await chatResp3.json()
console.log("Status:", chatResp3.status)
if (chatData3.error) console.log("Error:", chatData3.error)
else console.log("Model:", chatData3.model, "Reply:", chatData3.choices?.[0]?.message?.content)
console.log()

// 6. GET models — api.xiaomimimo.com
console.log("=== 6. GET api.xiaomimimo.com/api/free-ai/openai/models с JWT ===")
const modelsResp2 = await fetch("https://api.xiaomimimo.com/api/free-ai/openai/models", {
  headers: { "Authorization": `Bearer ${JWT}`, "X-Mimo-Source": "mimocode-cli-free" },
})
console.log("Status:", modelsResp2.status)
const modelsText = await modelsResp2.text()
console.log("Body:", modelsText.slice(0, 200))
