#!/usr/bin/env python3
"""Summarize a STATICRECOMP_PC_PROFILE histogram by guest function (decomp symbols.txt).
Usage: python tools/rr_pcprof.py build/pcprof.txt [N]"""
import bisect, collections, os, re, sys
SYMS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reference', 'rumble-decomp',
                    'config', 'WPSE01_01', 'symbols.txt')
syms = []
for l in open(SYMS):
    m = re.match(r'^(\S+) = \.text:0x([0-9A-Fa-f]+); // type:function size:0x([0-9A-Fa-f]+)', l)
    if m: syms.append((int(m.group(2), 16), int(m.group(3), 16), m.group(1)))
syms.sort(); starts = [s[0] for s in syms]
hist = collections.Counter(); total = 0
for l in open(sys.argv[1]):
    if l.startswith('#'): continue
    pc, n = l.split(); pc = int(pc, 16); n = int(n); total += n
    i = bisect.bisect_right(starts, pc) - 1
    name = syms[i][2] if i >= 0 and pc < syms[i][0] + syms[i][1] else f'?{pc:08x}'
    hist[name] += n
N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
print(f'total samples {total}')
for name, n in hist.most_common(N):
    print(f'{100*n/total:5.1f}%  {name}')
