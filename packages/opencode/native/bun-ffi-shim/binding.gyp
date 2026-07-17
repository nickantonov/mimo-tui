{
  "targets": [
    {
      "target_name": "bun_ffi_shim",
      "sources": ["src/bun_ffi_shim.cc"],
      "include_dirs": [
        "<!@(node -p \"require('node-addon-api').include\")"
      ],
      "libraries": ["-lffi", "-ldl"],
      "defines": ["NAPI_DISABLE_CPP_EXCEPTIONS"],
      "cflags!": ["-fno-exceptions"],
      "cflags_cc!": ["-fno-exceptions"],
      "cflags": ["-fexceptions"],
      "cflags_cc": ["-fexceptions"]
    }
  ]
}
