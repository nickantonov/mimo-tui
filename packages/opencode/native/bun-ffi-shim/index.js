/**
 * bun-ffi-shim — Node.js N-API replacement for bun:ffi
 * Uses libffi via C++ addon for cross-platform FFI.
 */

const binding = require("./build/Release/bun_ffi_shim.node");

// ============================================================
// dlopen(path, symbolsDef) → { symbols: { name: { ptr, name } } }
// ============================================================

function dlopen(libPath, symbolsDef) {
  return binding.dlopen(libPath, symbolsDef);
}

// ============================================================
// ptr(buffer) → Number (pointer address)
// ============================================================

function ptr(buffer) {
  if (buffer instanceof ArrayBuffer) {
    buffer = Buffer.from(buffer);
  }
  return binding.ptr(buffer);
}

// ============================================================
// toArrayBuffer(ptr, offset, length) → ArrayBuffer
// ============================================================

function toArrayBuffer(ptr, offset, length) {
  return binding.toArrayBuffer(ptr, offset, length);
}

// ============================================================
// JSCallback class
// ============================================================

class JSCallback {
  constructor(fn, options) {
    const result = binding.createCallback(fn, options.args, options.returns);
    this.ptr = result.ptr;
    this._externalData = result._data;
  }

  free() {
    if (this._externalData) {
      binding.freeCallback(this._externalData);
      this._externalData = null;
      this.ptr = null;
    }
  }
}

module.exports = {
  dlopen,
  ptr,
  toArrayBuffer,
  JSCallback,
};
