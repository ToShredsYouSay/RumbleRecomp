#!/usr/bin/env python3
"""Repeatable perf benchmark: boot -> Continue (Save A) -> Silent Forest stage -> sample FPS + per-thread CPU.
Usage: python tools/rr_bench.py LABEL [--stay N]"""
import sys, time
sys.path.insert(0, r'C:\RumbleRecomp\tools')
import rr_drive as d, rr_keys as k, rr_perf as perf

def run(label, stage_seconds=12, extra_args=(), module=None, jit=False):
    d.start(headless=False, extra=tuple(extra_args), module=module, jit=jit)
    t0 = time.time()
    while time.time() - t0 < 200:
        s = d.status()
        if s.get('state') == 'running' and int(s.get('frame_count', 0) or 0) > 2200: break
        time.sleep(1)
    assert k.focus(), 'could not focus game window'
    perf.sample(5, f'{label} | title')
    k.tap('J'); time.sleep(3); k.tap('J'); time.sleep(4)
    for _ in range(12): k.tap('J'); time.sleep(1.3)
    time.sleep(1.5)
    perf.sample(6, f'{label} | hub')
    k.hold_many(['W', 'A'], 1.5); time.sleep(0.8)
    k.hold_many(['S', 'D'], 0.9); time.sleep(0.6)
    k.hold('S', 0.8); time.sleep(1.5)
    k.hold('A', 0.55); time.sleep(0.5)
    k.tap('J'); time.sleep(14)
    d.shot(f'bench_{label}')
    return perf.sample(stage_seconds, f'{label} | STAGE')

if __name__ == '__main__':
    run(sys.argv[1], jit='--jit' in sys.argv, module=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--module=')), None))
    d.stop()
