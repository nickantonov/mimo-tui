#!/bin/bash
# MiMo-Code Node.js launcher
# Usage: ./node.sh [args...]
#
# Requirements:
#   - Node.js 22+  (nvm install 22)
#   - esbuild      (npm i -g esbuild)
#
# What this does:
#   Registers a custom ESM loader (txt-hooks.mjs) that provides:
#   - TypeScript → JavaScript transpilation via esbuild
#   - @/ @tui/ path alias resolution
#   - bun:sqlite → node:sqlite shim
#   - bun:ffi → N-API addon (libffi)
#   - .txt / .wasm / .scm import support
#   - GlobalThis.Bun polyfill (Bun.file, Bun.write, Bun.stringWidth, etc.)
#
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec node --no-experimental-strip-types "$SCRIPT_DIR/run-node.mjs" "$@"
