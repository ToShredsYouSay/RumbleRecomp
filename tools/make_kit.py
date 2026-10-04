#!/usr/bin/env python3
"""Assemble the compile kit (kit/) that lets a player's PC build the game modules from their own game files
(tools/rr_compile.py). It holds only project/open-source code and tools, never game data:

  kit/bin/dolrecomp.exe                    PowerPC -> C converter (DolRecomp, patched)
  kit/src/module-template/                 module_export.c, gen_module_tables.py
  kit/src/GXRuntime/{include,src/core}/    CPU support code compiled into each module
  kit/src/StaticRecomp/StaticRecompABI.h   module <-> runtime interface
  kit/src/module_hooks/                    rumble_hud.c + hooks.txt
  kit/pgo/{vanilla,weekend}.profdata       speed-tuning profiles (execution counts, no game code)
  kit/toolchain/                           clang/lld (llvm-mingw), only with --toolchain

Usage: python tools/make_kit.py [--toolchain] [--out kit]"""
import glob, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOLPHIN = os.path.join(ROOT, 'third_party', 'ModernGekko', 'vendor', 'dolphin')
# The speed-tuning profiles and the llvm-mingw folder: set RR_PGO_VANILLA, RR_PGO_WEEKEND, and RR_TOOLCHAIN to
# use your own (the defaults are the developer's). Release zips carry the profiles in kit/pgo.
PROFILES = {'vanilla': os.environ.get('RR_PGO_VANILLA', r'C:\mgpgo\prof3\merged.profdata'),
            'weekend': os.environ.get('RR_PGO_WEEKEND', r'C:\mgpgo\wk_prof\merged.profdata')}
TOOLCHAIN = os.environ.get('RR_TOOLCHAIN') or os.path.join(os.path.expanduser('~'), '.local', 'share', 'retcomm',
                                                            'toolchains', 'cmake-clang-v1',
                         'latest')


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def main(argv):
    out = os.path.join(ROOT, argv[argv.index('--out') + 1] if '--out' in argv else 'kit')
    copy(os.path.join(ROOT, 'build', 'mg', 'dolrecomp.exe'), os.path.join(out, 'bin', 'dolrecomp.exe'))
    for f in ('module_export.c', 'gen_module_tables.py'):
        copy(os.path.join(DOLPHIN, 'module-template', f), os.path.join(out, 'src', 'module-template', f))
    shutil.copytree(os.path.join(DOLPHIN, 'GXRuntime', 'include'), os.path.join(out, 'src', 'GXRuntime', 'include'),
                    dirs_exist_ok=True)
    for f in glob.glob(os.path.join(DOLPHIN, 'GXRuntime', 'src', 'core', '*.[ch]')):
        copy(f, os.path.join(out, 'src', 'GXRuntime', 'src', 'core', os.path.basename(f)))
    copy(os.path.join(DOLPHIN, 'Source', 'Core', 'Core', 'PowerPC', 'StaticRecomp', 'StaticRecompABI.h'),
         os.path.join(out, 'src', 'StaticRecomp', 'StaticRecompABI.h'))
    for f in ('rumble_hud.c', 'hooks.txt'):
        copy(os.path.join(ROOT, 'src', 'module_hooks', f), os.path.join(out, 'src', 'module_hooks', f))
    for name, path in PROFILES.items():
        copy(path, os.path.join(out, 'pgo', f'{name}.profdata'))
    if '--toolchain' in argv:
        copy_toolchain(os.path.join(out, 'toolchain'))
    print('kit ready:', out)


def copy_toolchain(dst):
    """Only what building a 64-bit Windows C DLL needs (clang + lld + mingw-w64 x86_64), ~25% of llvm-mingw:
    no other targets, C++ headers, debugger, clang-tidy/clangd, CMake, Python."""
    T = TOOLCHAIN
    shutil.rmtree(dst, ignore_errors=True)
    for f in ('clang.exe', 'clang-22.exe', 'ld.lld.exe', 'libLLVM-22.dll', 'libclang-cpp.dll', 'libc++.dll',
              'libunwind.dll', 'x86_64-w64-windows-gnu.cfg', 'x86_64-pc-windows-gnu.cfg', 'mingw32-common.cfg'):
        copy(os.path.join(T, 'bin', f), os.path.join(dst, 'bin', f))
    shutil.copytree(os.path.join(T, 'include'), os.path.join(dst, 'include'),
                    ignore=shutil.ignore_patterns('c++', 'GL', 'ddk', '*.idl'))
    shutil.copytree(os.path.join(T, 'lib', 'clang', '22', 'include'), os.path.join(dst, 'lib', 'clang', '22', 'include'))
    copy(os.path.join(T, 'lib', 'clang', '22', 'lib', 'windows', 'libclang_rt.builtins-x86_64.a'),
         os.path.join(dst, 'lib', 'clang', '22', 'lib', 'windows', 'libclang_rt.builtins-x86_64.a'))
    for d in ('include', 'lib'):  # game modules never use SDL, so its headers and libraries stay out
        shutil.copytree(os.path.join(T, 'x86_64-w64-mingw32', d), os.path.join(dst, 'x86_64-w64-mingw32', d),
                        ignore=shutil.ignore_patterns('SDL2', 'SDL3', 'libSDL*'))
    for f in ('LICENSE.TXT', 'README.md'):
        copy(os.path.join(T, f), os.path.join(dst, f))


if __name__ == '__main__':
    main(sys.argv[1:])
