#!/usr/bin/env python3
"""Dump an NW4R .brlyt pane tree: type, name, translation, size, base position (origin)."""
import struct, sys
ORIG = ['TL','TC','TR','CL','C','CR','BL','BC','BR']
def dump(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'RLYT', path
    nsec = struct.unpack('>H', b[0xE:0x10])[0]; o = struct.unpack('>H', b[0xC:0xE])[0]
    depth = 0; out = []
    for _ in range(nsec):
        magic = b[o:o+4].decode('ascii', 'replace'); size = struct.unpack('>I', b[o+4:o+8])[0]
        if magic == 'lyt1':
            w, h = struct.unpack('>ff', b[o+0xC:o+0x14]); out.append(f'layout {w:g}x{h:g} centered={b[o+8]}')
        elif magic in ('pan1', 'pic1', 'txt1', 'wnd1', 'bnd1'):
            flags, origin, alpha = b[o+8], b[o+9], b[o+10]
            name = b[o+0xC:o+0x1C].split(b'\0')[0].decode('ascii', 'replace')
            tx, ty, tz = struct.unpack('>fff', b[o+0x24:o+0x30])
            sx, sy = struct.unpack('>ff', b[o+0x3C:o+0x44]); w, h = struct.unpack('>ff', b[o+0x44:o+0x4C])
            out.append(f'{"  "*depth}{magic[:3]} {name:<16} pos=({tx:7.1f},{ty:7.1f}) size={w:g}x{h:g} scale={sx:g},{sy:g} origin={ORIG[origin] if origin<9 else origin} vis={flags&1}')
        elif magic == 'pas1': depth += 1
        elif magic == 'pae1': depth -= 1
        o += size
    return '\n'.join(out)
if __name__ == '__main__':
    for p in sys.argv[1:]:
        print('==', p); print(dump(p))
