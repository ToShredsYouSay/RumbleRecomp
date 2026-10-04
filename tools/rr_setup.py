#!/usr/bin/env python3
"""RumbleRecomp first-run setup: check the player's own WAD, build the Weekend Edition WADs from the
player's own patch files, and unpack each version's game code for compiling. Nothing here contains or
downloads game data; every input comes from the player and every output is checked by fingerprint.

Library (used by the launcher) and CLI:
  python tools/rr_setup.py --wad <original.wad> [--weekend-bps <RW 1.5 ...bps>] [--patch1 <...PATCH1.xdelta>]
                           [--data <dir>]          (default: <repo>/data)
Result: <data>/wads/{vanilla,weekend15,weekend15_patch1}.wad, <data>/gameroot/<profile>/sys/{main.dol,boot.bin},
        <data>/setup.json (which versions are ready)."""
import hashlib, json, os, shutil, struct, subprocess, sys, zlib

ROOT = (os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, 'tools')
DTK = os.path.join(TOOLS, 'dtk.exe')
XDELTA = os.path.join(TOOLS, 'xdelta3', 'xdelta3-3.1.0-x86_64.exe')
NO_WINDOW = 0x08000000

# SHA-1 fingerprints of the only supported inputs/outputs (USA Rev 0 WiiWare, Weekend 1.5, PATCH1).
SHA1 = {
    'vanilla_wad': 'fa02ca7a05596498f5980ce0faf351533a1c1b91',
    'weekend_wad': 'dd8b0a581bcbc4d6bb6bf70d7518c134ab6a87a7',
    'patch1_wad': '849787c4939fe6f3afda1d94e0efda94ec6a0a4b',
    'vanilla_dol': 'fd9a2c00c97e420a42355e2c27f3dc0ebbd3d8f9',
    'weekend_dol': '9a75bafc05c9d57a637645e9be4058fba8fb71ab',
}
# profile -> (WAD file in <data>/wads, gameroot folder, DOL fingerprint or None = not compiled separately)
PROFILES = {
    'vanilla': ('vanilla.wad', 'vanilla', SHA1['vanilla_dol']),
    'weekend': ('weekend15.wad', 'weekend', SHA1['weekend_dol']),
    # PATCH1 only changes data, so it runs on the Weekend build; no separate game code to compile.
    'weekend_patch1': ('weekend15_patch1.wad', None, None),
}


class SetupError(Exception):
    """A problem the player can fix; the message is shown to them as-is."""


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def identify_wad(path):
    """Name of a known WAD ('vanilla_wad', 'weekend_wad', 'patch1_wad') or None."""
    digest = sha1(path)
    return next((k for k, v in SHA1.items() if k.endswith('_wad') and v == digest), None)


def check_vanilla_wad(path):
    """(ok, message) for the WAD the player picked."""
    if not path or not os.path.isfile(path):
        return False, 'File not found.'
    kind = identify_wad(path)
    if kind == 'vanilla_wad':
        return True, 'Original game (USA WiiWare) recognised.'
    if kind in ('weekend_wad', 'patch1_wad'):
        return False, ('This is an already-patched Weekend Edition WAD. Please choose your original, '
                       'unpatched WAD; the Weekend versions are built from it.')
    return False, ('Not recognised. RumbleRecomp needs the original USA WiiWare release (title WPSE01), '
                   'unmodified, as a .wad file.')


# ---- BPS patching (beat format, as used by Flips) ---------------------------------------------------
def _bps_number(p, i):
    data, shift = 0, 1
    while True:
        x = p[i]; i += 1
        data += (x & 0x7F) * shift
        if x & 0x80:
            return data, i
        shift <<= 7
        data += shift


def apply_bps(source, patch):
    if patch[:4] != b'BPS1':
        raise SetupError('That file is not a BPS patch.')
    src_crc, dst_crc, patch_crc = struct.unpack('<III', patch[-12:])
    if zlib.crc32(patch[:-4]) & 0xFFFFFFFF != patch_crc:
        raise SetupError('The Weekend patch file is damaged (checksum mismatch). Please download it again.')
    if zlib.crc32(source) & 0xFFFFFFFF != src_crc:
        raise SetupError('This Weekend patch does not fit the original game file. The Weekend 1.5 download '
                         'contains two .bps files; try the other one ("try this if the first patch '
                         "doesn't work\").")
    i = 4
    src_size, i = _bps_number(patch, i)
    dst_size, i = _bps_number(patch, i)
    meta, i = _bps_number(patch, i)
    i += meta
    out = bytearray(dst_size)
    o = src_rel = dst_rel = 0
    end = len(patch) - 12
    while i < end:
        data, i = _bps_number(patch, i)
        cmd, length = data & 3, (data >> 2) + 1
        if cmd == 0:    # SourceRead
            out[o:o + length] = source[o:o + length]
        elif cmd == 1:  # TargetRead
            out[o:o + length] = patch[i:i + length]; i += length
        else:
            d, i = _bps_number(patch, i)
            delta = -(d >> 1) if d & 1 else (d >> 1)
            if cmd == 2:  # SourceCopy
                src_rel += delta
                out[o:o + length] = source[src_rel:src_rel + length]; src_rel += length
            else:         # TargetCopy (may overlap the bytes it is writing)
                dst_rel += delta
                if dst_rel + length <= o:
                    out[o:o + length] = out[dst_rel:dst_rel + length]
                else:
                    for k in range(length):
                        out[o + k] = out[dst_rel + k]
                dst_rel += length
        o += length
    if o != dst_size or zlib.crc32(out) & 0xFFFFFFFF != dst_crc:
        raise SetupError('Applying the Weekend patch failed (result checksum mismatch).')
    return bytes(out)


def apply_xdelta(source_path, patch_path, out_path):
    r = subprocess.run([XDELTA, '-d', '-f', '-s', source_path, patch_path, out_path],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode != 0:
        raise SetupError('Applying the PATCH1 file failed. Make sure it is the "v1.5.0 PATCH1" .xdelta file.\n'
                         + (r.stderr or '').strip()[:300])


# ---- unpacking ----------------------------------------------------------------------------------------
def unpack_game_code(wad, gameroot, dol_sha1, title='Poke Rumble'):
    """Write <gameroot>/sys/main.dol (the WAD's boot content, decompressed) and a minimal sys/boot.bin
    (game ID + Wii magic + title), which is all the compiler and runner use to identify the game."""
    sys_dir = os.path.join(gameroot, 'sys')
    os.makedirs(sys_dir, exist_ok=True)
    os.makedirs(os.path.join(gameroot, 'files'), exist_ok=True)
    dol = os.path.join(sys_dir, 'main.dol')
    r = subprocess.run([DTK, 'vfs', 'cp', f'{wad}:0000001.app:nlzss', dol],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode != 0 or not os.path.isfile(dol):
        raise SetupError('Could not unpack the game code from the WAD.\n' + (r.stderr or '').strip()[:300])
    if sha1(dol) != dol_sha1:
        raise SetupError('The unpacked game code does not match the expected version.')
    boot = bytearray(0x440)
    boot[0:6] = b'WPSE01'
    struct.pack_into('>I', boot, 0x18, 0x5D1C9EA3)  # Wii disc magic
    boot[0x20:0x20 + len(title)] = title.encode('ascii')
    with open(os.path.join(sys_dir, 'boot.bin'), 'wb') as f:
        f.write(boot)


# ---- the whole setup ------------------------------------------------------------------------------------
def default_data_dir():
    return os.environ.get('RR_DATA') or os.path.join(ROOT, 'data')


def load_state(data_dir=None):
    try:
        with open(os.path.join(data_dir or default_data_dir(), 'setup.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'profiles': {}}


def setup(vanilla_wad, weekend_bps=None, patch1_xdelta=None, data_dir=None, progress=print):
    """Run every step that the given inputs allow. Returns the saved state. Raises SetupError."""
    data_dir = data_dir or default_data_dir()
    wads = os.path.join(data_dir, 'wads')
    os.makedirs(wads, exist_ok=True)
    state = load_state(data_dir)

    progress('Checking your game file...')
    ok, msg = check_vanilla_wad(vanilla_wad)
    if not ok:
        raise SetupError(msg)
    van = os.path.join(wads, 'vanilla.wad')
    if not (os.path.isfile(van) and sha1(van) == SHA1['vanilla_wad']):
        shutil.copyfile(vanilla_wad, van)

    built = {'vanilla': van}
    if weekend_bps:
        progress('Building Weekend Edition 1.5 from your patch file...')
        with open(van, 'rb') as f:
            source = f.read()
        with open(weekend_bps, 'rb') as f:
            out = apply_bps(source, f.read())
        if hashlib.sha1(out).hexdigest() != SHA1['weekend_wad']:
            raise SetupError('That Weekend patch produced an unrecognised version. The Weekend 1.5 download '
                             'contains two .bps files; try the other one ("try this if the first patch '
                             "doesn't work\").")
        wk = os.path.join(wads, 'weekend15.wad')
        with open(wk, 'wb') as f:
            f.write(out)
        built['weekend'] = wk
        if patch1_xdelta:
            progress('Adding PATCH1...')
            p1 = os.path.join(wads, 'weekend15_patch1.wad')
            apply_xdelta(wk, patch1_xdelta, p1)
            if sha1(p1) != SHA1['patch1_wad']:
                os.remove(p1)
                raise SetupError('PATCH1 produced an unrecognised version. Make sure it is the '
                                 '"Unofficial Weekend Edition v1.5.0PATCH1" .xdelta file.')
            built['weekend_patch1'] = p1
    elif patch1_xdelta:
        raise SetupError('PATCH1 goes on top of Weekend Edition 1.5, so please also choose the Weekend .bps file.')

    for profile, wad in built.items():
        _, root_name, dol_sha1 = PROFILES[profile]
        if root_name:
            progress(f'Unpacking game code ({profile})...')
            unpack_game_code(wad, os.path.join(data_dir, 'gameroot', root_name), dol_sha1)
        state['profiles'][profile] = {'wad': os.path.relpath(wad, data_dir),
                                      'gameroot': PROFILES[profile][1] or 'weekend'}
    with open(os.path.join(data_dir, 'setup.json'), 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
    progress('Game files ready: ' + ', '.join(state['profiles']))
    return state


def main(argv):
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    if not opt('--wad'):
        print(__doc__)
        return 2
    try:
        setup(opt('--wad'), opt('--weekend-bps'), opt('--patch1'), opt('--data'))
    except SetupError as e:
        print('SETUP FAILED:', e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
