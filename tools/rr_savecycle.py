#!/usr/bin/env python3
"""Stage 8 save test: quit -> relaunch -> Continue -> hub -> open the Release Point list -> screenshot,
then Go to Title (which saves) and quit. Runs on build/userdir_auto (a copy), never the real save.
Usage: python tools/rr_savecycle.py LABEL [--jit]"""
import os, sys, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rr_drive as d, rr_keys as k

USER = os.path.join(d.ROOT, 'build', 'userdir_auto')
SAVE = os.path.join(USER, 'Wii', 'title', '00010001', '57505345', 'data', 'savedata.bin')

def h(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]

def main():
    label = sys.argv[1]; jit = '--jit' in sys.argv
    before = (h(SAVE), os.path.getmtime(SAVE))
    p = d.start(headless=False, jit=jit, user_dir=USER)
    t0 = time.time()
    while time.time() - t0 < 200:
        s = d.status()
        if s.get('state') == 'running' and int(s.get('frame_count', 0) or 0) > 2400: break
        time.sleep(1)
    assert k.focus()
    k.tap('J'); time.sleep(3); d.shot(f'cyc_{label}_1menu')
    k.tap('J'); time.sleep(4)
    for _ in range(12): k.tap('J'); time.sleep(1.3)
    time.sleep(2); d.shot(f'cyc_{label}_2hub')
    after_hub = (h(SAVE), os.path.getmtime(SAVE))
    # hub start -> Release Point (blue machine)
    k.hold('S', 2.0); time.sleep(0.4); k.hold('S', 1.2); time.sleep(0.6)
    k.hold('A', 0.12); time.sleep(0.2); k.hold('W', 0.55); time.sleep(0.6)
    k.tap('J'); time.sleep(2); k.tap('J'); time.sleep(2)
    d.shot(f'cyc_{label}_3list')
    k.tap('K'); time.sleep(1.5)
    k.tap('RETURN'); time.sleep(1.2); k.tap('S'); time.sleep(0.4); k.tap('J'); time.sleep(5)
    d.stop(); rc = p.wait(60)
    end = (h(SAVE), os.path.getmtime(SAVE))
    print(f'{label}: exit {hex(rc & 0xFFFFFFFF)} | save before {before[0]} | written on hub arrival: '
          f'{after_hub[1] > before[1]} | written on Go to Title: {end[1] > after_hub[1]} | end {end[0]}')

if __name__ == '__main__':
    main()
