#!/usr/bin/env python3
"""Poor-man's sampling profiler for the hot emulation thread of moderngekko-run.exe (Windows, 64-bit).

Suspends the busiest thread ~1 kHz, records RIP, maps it to (module, nearest symbol via llvm-nm).
Usage (game already running in a stage):  python tools/rr_prof.py [seconds] [--thread ID]
"""
import ctypes, subprocess, sys, time, bisect, collections, os, re, shutil
from ctypes import wintypes

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)
# LLVM tools from the llvm-mingw toolchain on PATH (override with RR_LLVM_BIN=<dir>).
_LLVM_BIN = os.environ.get('RR_LLVM_BIN')
NM = os.path.join(_LLVM_BIN, 'llvm-nm.exe') if _LLVM_BIN else (shutil.which('llvm-nm') or 'llvm-nm')
OBJDUMP = os.path.join(_LLVM_BIN, 'llvm-objdump.exe') if _LLVM_BIN else (shutil.which('llvm-objdump') or 'llvm-objdump')


def image_base(path):
    """PE preferred ImageBase: nm reports symbol addresses as ImageBase+RVA, so this
    must be subtracted to get RVAs comparable against (runtime_addr - runtime_load_base)."""
    out = subprocess.run([OBJDUMP, '-p', path], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if 'ImageBase' in line:
            return int(line.split()[-1], 16)
    return 0

k32.OpenThread.restype = wintypes.HANDLE
k32.OpenProcess.restype = wintypes.HANDLE
k32.SuspendThread.restype = wintypes.DWORD
k32.ResumeThread.restype = wintypes.DWORD
k32.GetThreadContext.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
psapi.GetModuleInformation.argtypes = [wintypes.HANDLE, wintypes.HMODULE, ctypes.c_void_p, wintypes.DWORD]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]


class MI(ctypes.Structure):
    _fields_ = [('base', ctypes.c_void_p), ('size', wintypes.DWORD), ('entry', ctypes.c_void_p)]


def modules(pid):
    h = k32.OpenProcess(0x0400 | 0x0010, False, pid)  # QUERY_INFORMATION | VM_READ
    arr = (wintypes.HMODULE * 2048)(); need = wintypes.DWORD()
    psapi.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(need), 3)
    out = []
    for i in range(need.value // ctypes.sizeof(wintypes.HMODULE)):
        buf = ctypes.create_unicode_buffer(1024)
        psapi.GetModuleFileNameExW(h, arr[i], buf, 1024)
        mi = MI(); psapi.GetModuleInformation(h, arr[i], ctypes.addressof(mi), ctypes.sizeof(mi))
        out.append((mi.base, mi.size, buf.value))
    k32.CloseHandle(h)
    return out


def load_symbols(path):
    """Return (sorted addrs, names) of text symbols, as RVAs (relative to the image base) --
    nm prints ImageBase+RVA, so that base must be subtracted to compare against
    (runtime_addr - runtime_load_base)."""
    base = image_base(path)
    out = subprocess.run([NM, '--numeric-sort', '--defined-only', path], capture_output=True, text=True).stdout
    pairs = []
    for line in out.splitlines():
        p = line.split(None, 2)
        if len(p) == 3 and p[1] in 'tTwW':
            pairs.append((int(p[0], 16) - base, p[2]))
    pairs.sort()
    return [a for a, _ in pairs], [n for _, n in pairs]


def sample(pid, tid, seconds):
    ht = k32.OpenThread(0x0002 | 0x0008 | 0x0040, False, tid)
    raw = ctypes.create_string_buffer(1232 + 64)
    addr = (ctypes.addressof(raw) + 15) & ~15
    ctx_flags = ctypes.c_uint32.from_address(addr + 0x30)
    rips = []
    end = time.time() + seconds
    while time.time() < end:
        ctypes.memset(addr, 0, 1232)
        ctx_flags.value = 0x100001  # CONTEXT_CONTROL (contains Rip)
        if k32.SuspendThread(ht) == 0xFFFFFFFF:
            break
        ok = k32.GetThreadContext(ht, ctypes.c_void_p(addr))
        rip = ctypes.c_uint64.from_address(addr + 0xF8).value if ok else 0
        k32.ResumeThread(ht)
        if ok: rips.append(rip)
        time.sleep(0.0005)
    k32.CloseHandle(ht)
    return rips


def main():
    import rr_perf as perf
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 8.0
    pid = perf.pid()
    tid = int(sys.argv[sys.argv.index('--thread') + 1]) if '--thread' in sys.argv else perf.thread_cpu(2.0)[0][0]
    mods = modules(pid)
    rips = sample(pid, tid, seconds)
    print(f'pid={pid} tid={tid} samples={len(rips)}')
    per_mod = collections.Counter(); per_sym = collections.Counter()
    symcache = {}
    for rip in rips:
        for base, size, name in mods:
            if base <= rip < base + size:
                short = os.path.basename(name)
                per_mod[short] += 1
                if short not in symcache:
                    symcache[short] = load_symbols(name) if short.lower().endswith(('.exe', '.dll')) and os.path.exists(name) else ([], [])
                addrs, names = symcache[short]
                rva = rip - base
                i = bisect.bisect_right(addrs, rva) - 1
                sym = names[i] if i >= 0 else f'?+0x{rva:x}'
                per_sym[(short, sym)] += 1
                break
        else:
            per_mod['<unmapped/JIT>'] += 1
    n = len(rips)
    print('\nBy module:')
    for m, c in per_mod.most_common(): print(f'  {100*c/n:5.1f}%  {m}')
    print('\nTop symbols:')
    for (m, s), c in per_sym.most_common(30): print(f'  {100*c/n:5.1f}%  [{m}] {s[:150]}')


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(__file__))
    main()
