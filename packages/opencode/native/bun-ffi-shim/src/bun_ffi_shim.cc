// bun_ffi_shim.cc — N-API replacement for bun:ffi
// Uses Number instead of BigInt for pointers to avoid conversion issues
#include <napi.h>
#include <ffi.h>
#include <dlfcn.h>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

static ffi_type* resolve_type(const std::string& name) {
  if (name=="void") return &ffi_type_void;
  if (name=="bool") return &ffi_type_sint;
  if (name=="u8") return &ffi_type_uint8;
  if (name=="u16") return &ffi_type_uint16;
  if (name=="u32") return &ffi_type_uint32;
  if (name=="u64") return &ffi_type_uint64;
  if (name=="i8") return &ffi_type_sint8;
  if (name=="i16") return &ffi_type_sint16;
  if (name=="i32") return &ffi_type_sint32;
  if (name=="i64") return &ffi_type_sint64;
  if (name=="f32") return &ffi_type_float;
  if (name=="f64") return &ffi_type_double;
  return &ffi_type_pointer;
}

static std::map<int, void*> g_libs;
static int g_nextId = 1;

// Store function pointers as doubles (lossy but works for addresses on 64-bit)
static std::map<double, void*> g_ptrs;

static double ptrToDouble(void* p) {
  double d;
  memcpy(&d, &p, sizeof(p));
  return d;
}

static void* doubleToPtr(double d) {
  void* p;
  memcpy(&p, &d, sizeof(p));
  return p;
}

Napi::Value Dlopen(const Napi::CallbackInfo& info) {
  Napi::Env env = info.Env();
  if (info.Length() < 2) return env.Undefined();
  std::string path = info[0].As<Napi::String>().Utf8Value();
  Napi::Object symDef = info[1].As<Napi::Object>();
  void* h = dlopen(path.c_str(), RTLD_LAZY);
  if (!h) { fprintf(stderr, "dlopen: %s\n", dlerror()); return env.Undefined(); }
  int id = g_nextId++;
  g_libs[id] = h;
  Napi::Object syms = Napi::Object::New(env);
  Napi::Array names = symDef.GetPropertyNames();
  for (uint32_t i = 0; i < names.Length(); i++) {
    std::string n = names.Get(i).As<Napi::String>().Utf8Value();
    void* fp = dlsym(h, n.c_str());
    if (!fp) continue;
    double d = ptrToDouble(fp);
    g_ptrs[d] = fp;
    Napi::Function fn = Napi::Function::New(env, [](const Napi::CallbackInfo&) {});
    fn.Set("ptr", Napi::Number::New(env, d));
    fn.Set("name", Napi::String::New(env, n));
    syms.Set(n, fn);
  }
  Napi::Object r = Napi::Object::New(env);
  r.Set("id", Napi::Number::New(env, id));
  r.Set("symbols", syms);
  return r;
}

Napi::Value Ptr(const Napi::CallbackInfo& info) {
  Napi::Env env = info.Env();
  if (info.Length() < 1) return Napi::Number::New(env, 0);
  if (info[0].IsBuffer()) {
    void* p = info[0].As<Napi::Buffer<uint8_t>>().Data();
    return Napi::Number::New(env, ptrToDouble(p));
  }
  if (info[0].IsArrayBuffer()) {
    void* p = info[0].As<Napi::ArrayBuffer>().Data();
    return Napi::Number::New(env, ptrToDouble(p));
  }
  if (info[0].IsNumber()) return info[0];
  return Napi::Number::New(env, 0);
}

Napi::Value ToArrayBuffer(const Napi::CallbackInfo& info) {
  Napi::Env env = info.Env();
  if (info.Length() < 3) return Napi::ArrayBuffer::New(env, 0);
  double d = info[0].As<Napi::Number>().DoubleValue();
  void* addr = doubleToPtr(d);
  int64_t off = info[1].As<Napi::Number>().Int64Value();
  int64_t len = info[2].As<Napi::Number>().Int64Value();
  if (!addr || len <= 0) return Napi::ArrayBuffer::New(env, 0);
  Napi::ArrayBuffer ab = Napi::ArrayBuffer::New(env, len);
  memcpy(ab.Data(), (const uint8_t*)addr + off, len);
  return ab;
}

Napi::Value CallNative(const Napi::CallbackInfo& info) {
  Napi::Env env = info.Env();
  if (info.Length() < 4) return env.Undefined();
  double d = info[0].As<Napi::Number>().DoubleValue();
  void* fn = doubleToPtr(d);
  if (!fn) return env.Undefined();
  Napi::Array aTypes = info[1].As<Napi::Array>();
  Napi::Array aVals = info[2].As<Napi::Array>();
  std::string retType = info[3].As<Napi::String>().Utf8Value();
  ffi_cif cif;
  std::vector<ffi_type*> atypes;
  std::vector<int64_t> ivec;
  std::vector<double> dvec;
  std::vector<void*> ptrs;
  for (uint32_t i = 0; i < aTypes.Length(); i++) {
    atypes.push_back(resolve_type(aTypes.Get(i).As<Napi::String>().Utf8Value()));
    ivec.push_back(0);
    dvec.push_back(0.0);
    ptrs.push_back(nullptr);
  }
  if (ffi_prep_cif(&cif, FFI_DEFAULT_ABI, atypes.size(), resolve_type(retType), atypes.data()) != FFI_OK)
    return env.Undefined();
  for (uint32_t i = 0; i < aTypes.Length(); i++) {
    std::string t = aTypes.Get(i).As<Napi::String>().Utf8Value();
    Napi::Value v = aVals.Get(i);
    if (t == "ptr" || t == "pointer" || t == "usize") {
      ivec[i] = v.IsNumber() ? (int64_t)(intptr_t)doubleToPtr(v.As<Napi::Number>().DoubleValue()) : 0;
      if (v.IsBuffer()) ivec[i] = (int64_t)(intptr_t)v.As<Napi::Buffer<uint8_t>>().Data();
      ptrs[i] = &ivec[i];
    } else if (t == "f32" || t == "f64" || t == "float" || t == "double") {
      dvec[i] = v.As<Napi::Number>().DoubleValue();
      ptrs[i] = &dvec[i];
    } else {
      ivec[i] = v.IsNumber() ? (int64_t)v.As<Napi::Number>().Int64Value() : 0;
      ptrs[i] = &ivec[i];
    }
  }
  union { int64_t i; double f; } res;
  ffi_call(&cif, FFI_FN(fn), &res, ptrs.data());
  if (retType == "void") return env.Undefined();
  if (retType == "f32" || retType == "f64" || retType == "float" || retType == "double")
    return Napi::Number::New(env, res.f);
  if (retType == "bool") return Napi::Boolean::New(env, res.i != 0);
  if (retType == "ptr" || retType == "pointer" || retType == "usize")
    return Napi::Number::New(env, ptrToDouble((void*)(intptr_t)res.i));
  return Napi::Number::New(env, (double)res.i);
}

struct CBData { Napi::FunctionReference fn; ffi_cif* cif; void* closure; void* code; };
static void closure_handler(ffi_cif* cif, void* ret, void** args, void* ud) {
  CBData* d = (CBData*)ud;
  Napi::Env env = d->fn.Env();
  std::vector<napi_value> jsArgs;
  for (unsigned i = 0; i < cif->nargs; i++) {
    ffi_type* t = cif->arg_types[i];
    if (t == &ffi_type_pointer)
      jsArgs.push_back(Napi::Number::New(env, ptrToDouble(*(void**)args[i])));
    else if (t == &ffi_type_double)
      jsArgs.push_back(Napi::Number::New(env, *(double*)args[i]));
    else
      jsArgs.push_back(Napi::Number::New(env, (double)(*(int64_t*)args[i])));
  }
  Napi::Value r = d->fn.Call(jsArgs);
  ffi_type* rt = cif->rtype;
  if (rt != &ffi_type_void) {
    if (rt == &ffi_type_pointer)
      *(void**)ret = r.IsNumber() ? doubleToPtr(r.As<Napi::Number>().DoubleValue()) : nullptr;
    else if (rt == &ffi_type_double)
      *(double*)ret = r.As<Napi::Number>().DoubleValue();
    else
      *(int64_t*)ret = r.As<Napi::Number>().Int64Value();
  }
}

Napi::Value CreateCallback(const Napi::CallbackInfo& info) {
  Napi::Env env = info.Env();
  if (info.Length() < 3) return env.Undefined();
  CBData* d = new CBData();
  d->fn = Napi::Persistent(info[0].As<Napi::Function>());
  Napi::Array aTypes = info[1].As<Napi::Array>();
  std::string retType = info[2].As<Napi::String>().Utf8Value();
  d->cif = new ffi_cif();
  std::vector<ffi_type*> atypes;
  for (uint32_t i = 0; i < aTypes.Length(); i++)
    atypes.push_back(resolve_type(aTypes.Get(i).As<Napi::String>().Utf8Value()));
  ffi_prep_cif(d->cif, FFI_DEFAULT_ABI, atypes.size(), resolve_type(retType), atypes.data());
  d->closure = ffi_closure_alloc(sizeof(ffi_closure), &d->code);
  ffi_prep_closure_loc((ffi_closure*)d->closure, d->cif, closure_handler, d, d->code);
  Napi::Object r = Napi::Object::New(env);
  r.Set("ptr", Napi::Number::New(env, ptrToDouble(d->code)));
  r.Set("_data", Napi::External<CBData>::New(env, d));
  return r;
}

Napi::Value FreeCallback(const Napi::CallbackInfo& info) {
  if (info.Length() >= 1 && info[0].IsExternal()) {
    CBData* d = info[0].As<Napi::External<CBData>>().Data();
    if (d) { ffi_closure_free(d->closure); delete d->cif; delete d; }
  }
  return info.Env().Undefined();
}

Napi::Object Init(Napi::Env env, Napi::Object exports) {
  exports.Set("dlopen", Napi::Function::New(env, Dlopen));
  exports.Set("ptr", Napi::Function::New(env, Ptr));
  exports.Set("toArrayBuffer", Napi::Function::New(env, ToArrayBuffer));
  exports.Set("callNative", Napi::Function::New(env, CallNative));
  exports.Set("createCallback", Napi::Function::New(env, CreateCallback));
  exports.Set("freeCallback", Napi::Function::New(env, FreeCallback));
  return exports;
}

NODE_API_MODULE(bun_ffi_shim, Init)
