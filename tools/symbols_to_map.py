#!/usr/bin/env python3
"""Convert a decomp-toolkit symbols.txt into the 'ADDR SIZE NAME' map DolRecomp's --map reads.
Usage: symbols_to_map.py symbols.txt out.map   (functions only)"""
import re, sys
pat = re.compile(r'^(\S+) = \.\w+:0x([0-9A-Fa-f]+); // type:function size:0x([0-9A-Fa-f]+)')
n = 0
with open(sys.argv[1], encoding='utf-8') as f, open(sys.argv[2], 'w', encoding='utf-8') as o:
    for line in f:
        m = pat.match(line)
        if m:
            o.write(f'{m.group(2)} {m.group(3)} {m.group(1)}\n'); n += 1
print(f'{n} function symbols written')
