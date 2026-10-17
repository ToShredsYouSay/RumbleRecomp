"""Disassemble guest PowerPC code (paired singles included) from a game's main.dol.
  python tools/rr_dis.py ADDR LEN [weekend]      e.g. python tools/rr_dis.py 8013D8A0 94"""
import os, struct, sys
import capstone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
version = sys.argv[3] if len(sys.argv) > 3 else 'vanilla'
dol = open(os.path.join(ROOT, 'build', 'gameroot', version, 'sys', 'main.dol'), 'rb').read()
offs, addrs, sizes = (struct.unpack('>18I', dol[i:i + 72]) for i in (0, 72, 144))


def read(addr, n):
    for o, a, s in zip(offs, addrs, sizes):
        if a <= addr < a + s:
            return dol[o + addr - a:o + addr - a + n]


start, n = int(sys.argv[1], 16), int(sys.argv[2], 16)
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN | getattr(capstone, 'CS_MODE_PS', 0))
md.skipdata = True
for i in md.disasm(read(start, n), start):
    print(f'{i.address:08x} {i.mnemonic} {i.op_str}')
