#!/usr/bin/env python3
"""Assemble a release of RumbleRecomp: everything a player needs to set up and build the game from their own
game files, and nothing of the game itself. The result is checked before it is zipped.

  dist/RumbleRecomp-Beta<version>/
    RumbleRecomp.exe          launcher (tools/launcher.pyw, PyInstaller)
    runtime/                  RumbleRecomp-game.exe (moderngekko-run) + libc++/libunwind + Dolphin Sys data
    kit/                      compile kit incl. trimmed clang/lld toolchain (tools/make_kit.py)
    tools/                    dtk.exe (WAD unpacking), xdelta3 (PATCH1), launcher.ico
    config/GameSettings/      WPSE01.ini
    source/                   our patches to the GPL components + where their source is (GPL requirement)
    LICENSES/                 licence texts of the bundled components
    README.txt                player guide
  dist/RumbleRecomp-Beta<version>.zip

Usage: python tools/make_release.py [--no-zip] [--skip-kit]"""
import glob, hashlib, os, re, shutil, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import make_kit, rr_setup

TP = os.path.join(ROOT, 'third_party', 'ModernGekko')
DOLPHIN = os.path.join(TP, 'vendor', 'dolphin')
GAME_EXTS = {'.wad', '.dol', '.app', '.iso', '.wbfs', '.rvz', '.gcm', '.ciso', '.sav', '.bin', '.tik', '.tmd'}
ALLOWED_BIN = {'codehandler.bin'}  # Dolphin Sys file (Gecko code handler, part of Dolphin)
OUR_SOURCES = ['LICENSE', 'third_party.lock.md', 'tools/launcher.pyw', 'tools/rr_setup.py', 'tools/rr_compile.py',
               'tools/make_kit.py', 'tools/make_release.py', 'tools/build_launcher_exe.ps1',
               'tools/make_launcher_icon.py', 'tools/make_launcher_art.py', 'src/module_hooks/rumble_hud.c', 'src/module_hooks/hooks.txt']


def version():
    src = open(os.path.join(ROOT, 'tools', 'launcher.pyw'), encoding='utf-8').read()
    return re.search(r"^VERSION = '([^']+)'", src, re.M).group(1)


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


README = """Good news, everyone!

RumbleRecomp Beta {ver}
=====================

A native PC version of the 2009 WiiWare game, built on your own PC from your own copy of the game.
RumbleRecomp contains no game files: you need the original USA WiiWare release (title WPSE01) as a .wad file.

First run
---------
1. Unzip this folder anywhere (not inside Program Files) and run RumbleRecomp.exe.
   Windows may warn that the program is from an unknown publisher: More info -> Run anyway.
2. In "Game files", choose your original .wad. Optional: for Weekend Edition 1.5, download its patch
   files yourself from the Weekend Edition release page (and PATCH1 from its own page) and choose them too.
   Press "Set up".
3. Press Play. Each version is built for your PC the first time (about 20-40 minutes, once).
   Later updates only rebuild what changed.

Controls
--------
Keyboard is Player 1: WASD/arrows move, J attack, K second attack, Enter pause.
Controllers: press any button to join. The first controller is Player 1, the next Player 2, and so on.
Multiplayer: walk to the table with two gold figures at the bottom of the hub, or choose Multiplayer
from the pause menu while you're in the hub.
Every player moves in any direction with the left stick (the d-pad gives the classic 8 directions).
HOME on a controller (or both sticks pressed in), or Esc, opens the menu: save and load states (4 slots per version, with
pictures), fullscreen, and quit. Hold Space to fast forward. F11 also switches fullscreen.
Keep the game window focused while playing.

Texture packs
-------------
Under "Textures", add texture packs made for this game (a folder or a .zip of Dolphin custom textures for
game ID WPSE01), then tick "Custom textures" next to PLAY. Making your own: tick "Record textures while
playing" there, and every texture the game shows is saved for you to edit.

Your files
----------
Everything of yours (game files, saves, settings, and the built game) is kept in the "data" folder next to
RumbleRecomp.exe. Back it up to keep your saves. Deleting "data\\build" frees disk space (the next build
of that version then takes the full time again).

Requirements
------------
Windows 10/11 64-bit, a graphics card with Vulkan support, about 4 GB of free disk space.

Licences and source code
------------------------
RumbleRecomp is free software under the GNU General Public License, version 3 or later (LICENSE.txt).
Its source is in source\\rumblerecomp. Its runtime is built from Dolphin, RecompCore, ModernGekko, and
DolRecomp (GPL); their licences are in LICENSES, and where to get their exact source code is in
source\\SOURCE.txt (our changes to them are in source\\patches).
"""

SOURCE = """Source code for the GPL components in this release
==================================================

runtime\\RumbleRecomp-game.exe (ModernGekko's moderngekko-run) and kit\\bin\\dolrecomp.exe are built from these upstream commits plus the
patches in source\\patches (apply order: see the list below). The modules built on your PC also contain
code from RecompCore's GXRuntime (kit\\src, included as source).

{lock}

Apply order (git apply, from the repository named):
  ModernGekko:              0001 0005 0006 0009 0011 0013 0015 0016 0018 0019
  vendor/dolphin:           0002 0004 0007 0010 0012 0014 0017
  vendor/dolphin/DolRecomp: 0003 0008
"""

THIRD_PARTY = """Bundled third-party components
==============================
- Dolphin (GPL-2.0-or-later; in aggregate GPL-3.0 here) - runtime\\, LICENSES\\Dolphin*
- RecompCore / ModernGekko (GPL-3.0) - runtime\\, kit\\src\\GXRuntime, LICENSES\\ModernGekko-GPL-3.0.txt
- DolRecomp (GPL-3.0) - kit\\bin\\dolrecomp.exe, LICENSES\\DolRecomp-GPL-3.0.txt
- llvm-mingw: LLVM/clang/lld (Apache-2.0 WITH LLVM-exception), mingw-w64 (ZPL and others) - kit\\toolchain,
  licence in kit\\toolchain\\LICENSE.TXT
- decomp-toolkit (dtk) 1.8.3 - tools\\dtk.exe - https://github.com/encounter/decomp-toolkit
- xdelta3 3.1.0 (Apache-2.0) - tools\\xdelta3 - https://github.com/jmacd/xdelta
- Python and PyInstaller (PSF licence; PyInstaller bootloader GPL with exception) - RumbleRecomp.exe
- Nunito font (SIL Open Font License 1.1) - tools\\fonts, LICENSES\\Nunito-OFL.txt - https://github.com/googlefonts/nunito
"""


def assemble(out, skip_kit=False):
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    # launcher
    r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        os.path.join(ROOT, 'tools', 'build_launcher_exe.ps1')], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('launcher build failed:\n' + r.stdout + r.stderr)
    copy(os.path.join(ROOT, 'RumbleRecomp.exe'), os.path.join(out, 'RumbleRecomp.exe'))
    # runtime
    rt = os.path.join(out, 'runtime')
    copy(os.path.join(ROOT, 'build', 'bin', 'moderngekko-run.exe'), os.path.join(rt, 'RumbleRecomp-game.exe'))
    for dll in ('libc++.dll', 'libunwind.dll'):
        copy(os.path.join(make_kit.TOOLCHAIN, 'bin', dll), os.path.join(rt, dll))
    # Dolphin's Sys data, minus what RumbleRecomp never uses: settings for every other game (ours comes from
    # config/GameSettings) and the title database (the launcher sets the window title)
    shutil.copytree(os.path.join(ROOT, 'build', 'mg', 'Sys'), os.path.join(rt, 'Sys'),
                    ignore=shutil.ignore_patterns('GameSettings', 'wiitdb-*.txt', 'triforcetdb-*.txt'))
    # compile kit (+ toolchain)
    if not skip_kit:
        make_kit.main(['--toolchain'])
    shutil.copytree(os.path.join(ROOT, 'kit'), os.path.join(out, 'kit'))
    # setup tools
    copy(os.path.join(ROOT, 'tools', 'dtk.exe'), os.path.join(out, 'tools', 'dtk.exe'))
    copy(rr_setup.XDELTA, os.path.join(out, 'tools', 'xdelta3', os.path.basename(rr_setup.XDELTA)))
    copy(os.path.join(ROOT, 'tools', 'launcher.ico'), os.path.join(out, 'tools', 'launcher.ico'))
    shutil.copytree(os.path.join(ROOT, 'tools', 'launcher_art'), os.path.join(out, 'tools', 'launcher_art'))
    shutil.copytree(os.path.join(ROOT, 'tools', 'fonts'), os.path.join(out, 'tools', 'fonts'))  # Nunito (OFL)
    copy(os.path.join(ROOT, 'config', 'GameSettings', 'WPSE01.ini'),
         os.path.join(out, 'config', 'GameSettings', 'WPSE01.ini'))
    # source + licences
    for p in glob.glob(os.path.join(ROOT, 'patches', 'moderngekko', '*.patch')):
        copy(p, os.path.join(out, 'source', 'patches', os.path.basename(p)))
    lock = open(os.path.join(ROOT, 'third_party.lock.md'), encoding='utf-8').read()
    lock = '\n'.join(l for l in lock.splitlines() if 'reference/' not in l and 'ModernGekko-Template' not in l)
    with open(os.path.join(out, 'source', 'SOURCE.txt'), 'w', encoding='utf-8') as f:
        f.write(SOURCE.format(lock=lock))
    lic = os.path.join(out, 'LICENSES')
    copy(os.path.join(TP, 'LICENSE'), os.path.join(lic, 'ModernGekko-GPL-3.0.txt'))
    copy(os.path.join(DOLPHIN, 'COPYING'), os.path.join(lic, 'Dolphin-COPYING.txt'))
    shutil.copytree(os.path.join(DOLPHIN, 'LICENSES'), os.path.join(lic, 'Dolphin-LICENSES'))
    copy(os.path.join(DOLPHIN, 'DolRecomp', 'LICENSE'), os.path.join(lic, 'DolRecomp-GPL-3.0.txt'))
    copy(os.path.join(ROOT, 'tools', 'fonts', 'OFL.txt'), os.path.join(lic, 'Nunito-OFL.txt'))
    copy(os.path.join(ROOT, 'LICENSE'), os.path.join(out, 'LICENSE.txt'))
    # our own source (GPL: the launcher exe and the setup/build tools ship with their source)
    for f in OUR_SOURCES:
        copy(os.path.join(ROOT, f), os.path.join(out, 'source', 'rumblerecomp', f))
    with open(os.path.join(lic, 'THIRD_PARTY.txt'), 'w', encoding='utf-8') as f:
        f.write(THIRD_PARTY)
    with open(os.path.join(out, 'README.txt'), 'w', encoding='utf-8') as f:
        f.write(README.format(ver=version()))


def is_dolphin_sys_file(path, out):
    """Dolphin's own Sys data (free DSP ROM/font replacements, default WC24 files) ships with every Dolphin
    build; allowed only if byte-identical to the file in Dolphin's source tree."""
    rel = os.path.relpath(path, os.path.join(out, 'runtime', 'Sys'))
    if rel.startswith('..'):
        return False
    src = os.path.join(DOLPHIN, 'Data', 'Sys', rel)
    return os.path.isfile(src) and rr_setup.sha1(src) == rr_setup.sha1(path)


def private_strings():
    """Strings that must never ship: the building PC's user-profile path (taken from this PC, not written
    here) plus anything listed in RR_PRIVATE_STRINGS (separated by ';')."""
    user = os.path.basename(os.path.expanduser('~'))
    found = [f'Users\\{user}'.encode(), f'Users/{user}'.encode()]
    found += [s.encode() for s in os.environ.get('RR_PRIVATE_STRINGS', '').split(';') if s]
    return found


def check(out):
    """Fail if anything of the game, the player's data, or the developer's identity is in the release."""
    known = set(rr_setup.SHA1.values())
    problems = []
    for d, dirs, files in os.walk(out):
        rel = os.path.relpath(d, out)
        if rel.split(os.sep)[0] in ('data', 'build') and rel != '.':
            problems.append(f'unexpected folder: {rel}')
        for f in files:
            p = os.path.join(d, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in GAME_EXTS and f not in ALLOWED_BIN and not is_dolphin_sys_file(p, out):
                problems.append(f'game-like file: {os.path.relpath(p, out)}')
            if os.path.getsize(p) > 1 << 20 and rr_setup.sha1(p) in known:
                problems.append(f'game file by fingerprint: {os.path.relpath(p, out)}')
            with open(p, 'rb') as fh:
                blob = fh.read()
            for needle in private_strings():
                if needle in blob:
                    problems.append(f'developer path/identity in {os.path.relpath(p, out)}')
    return problems


def main(argv):
    ver = version()
    out = os.path.join(ROOT, 'dist', f'RumbleRecomp-Beta{ver}')
    assemble(out, skip_kit='--skip-kit' in argv)
    problems = check(out)
    if problems:
        print('RELEASE CHECK FAILED:')
        for p in problems:
            print('  ' + p)
        return 1
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    print(f'release folder OK: {out} ({size / 2**20:.0f} MB)')
    if '--no-zip' not in argv:
        z = out + '.zip'
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for d, _, fs in os.walk(out):
                for f in fs:
                    p = os.path.join(d, f)
                    zf.write(p, os.path.relpath(p, os.path.dirname(out)))
        print(f'zip: {z} ({os.path.getsize(z) / 2**20:.0f} MB)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
