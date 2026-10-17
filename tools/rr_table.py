"""Print the progress table in a dumped save slot (tools/rr_slot.py): every non-empty entry as
A B C D: clear count and flag bits (bit 0 seen, bit 1 cleared, bit 2 set on some entries).
  python tools/rr_table.py FILE.slot"""
import struct, sys

slot = open(sys.argv[1], 'rb').read()
for a in range(3):
    for b in range(5):
        for c in range(8):
            row = []
            for d in range(10):
                o = 0x18 + a * 0x640 + b * 0x140 + c * 0x28 + d * 4
                w = struct.unpack('>I', slot[o:o + 4])[0]
                if w:
                    row.append(f'{d}:x{w >> 22}/{w & 7}')
            if row:
                print(f'A{a} B{b} C{c}  ' + ' '.join(row))
