// ESM wrapper for bun-ffi-shim CJS binding
import { createRequire } from "module"
import { fileURLToPath } from "url"
import path from "path"

const require = createRequire(import.meta.url)
const binding = require(path.join(path.dirname(fileURLToPath(import.meta.url)), "index.js"))

export const dlopen = binding.dlopen
export const ptr = binding.ptr
export const toArrayBuffer = binding.toArrayBuffer
export const JSCallback = binding.JSCallback

export default {
  dlopen: binding.dlopen,
  ptr: binding.ptr,
  toArrayBuffer: binding.toArrayBuffer,
  JSCallback: binding.JSCallback,
}
