#!/usr/bin/env python3
"""Repeatable busy-scene benchmark: boot straight into a savestate (no navigation, no input) and
average Dolphin's real-time `speed` over a fixed window.

Default scene build/states/forest_group.sav: Silent Forest, player + 5 wild ones closing in.
Usage: python tools/rr_scene.py LABEL [--state PATH] [--module PATH] [--wad PATH] [--jit] [--seconds N] [--rounds N]
Env vars in the calling environment (e.g. STATICRECOMP_*) pass through to the game.
"""
import os, sys, time, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rr_drive as d

ROOT = r'C:\RumbleRecomp'
DEFAULT_STATE = os.path.join(ROOT, 'build', 'states', 'forest_group.sav')
# Benchmarks run against a copy of the save data, never the user's real build/userdir.
if os.path.isdir(os.path.join(ROOT, 'build', 'userdir_auto')):
    os.environ.setdefault('RR_USERDIR', os.path.join(ROOT, 'build', 'userdir_auto'))


def run_once(state=DEFAULT_STATE, module=None, jit=False, seconds=12.0, settle=2.0, extra=(), wad=None):
    try:
        os.remove(os.path.join(d.AUTO, 'status.txt'))  # never read the previous run's status
    except OSError:
        pass
    proc = d.start(headless=False, module=module, jit=jit, wad=wad, extra=('--load-state', state, *extra))
    t0 = time.time()
    # The core boots first and applies the savestate a moment later (frame_count jumps to the
    # saved value, thousands of frames). Only start the clock once the loaded state is running
    # and rendering, otherwise the load pause is averaged in as zero speed.
    while time.time() - t0 < 120:
        s = d.status()
        try:
            if (s.get('state') == 'running' and int(s.get('frame_count', 0)) > 1000
                    and float(s.get('fps', 0)) > 10):
                break
        except ValueError:
            pass
        time.sleep(0.5)
    time.sleep(settle)
    speeds, fpss = [], []
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(0.5)
        s = d.status()
        try:
            speeds.append(float(s['speed'])); fpss.append(float(s['fps']))
        except (KeyError, ValueError):
            pass
    d.stop()
    try:
        proc.wait(30)
    except Exception:
        proc.kill()
    return speeds, fpss


def busy_builders():
    """Compiler/build processes that would steal CPU and invalidate a speed reading."""
    import subprocess
    out = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True).stdout.lower()
    return sorted({n for n in ('clang.exe', 'clang-cl.exe', 'ld.lld.exe', 'lld.exe', 'ninja.exe',
                               'dolrecomp.exe', 'moderngekko-port.exe', 'cmake.exe') if f'"{n}"' in out})


def main():
    a = sys.argv[1:]
    busy = busy_builders()
    if busy and '--allow-busy' not in a:
        sys.exit(f'refusing to benchmark while build processes are running: {busy} (pass --allow-busy to override)')
    label = a[0] if a and not a[0].startswith('--') else 'scene'
    opt = lambda k, dflt=None: a[a.index(k) + 1] if k in a else dflt
    rounds = int(opt('--rounds', 1))
    allsp = []
    for r in range(rounds):
        sp, fp = run_once(state=opt('--state', DEFAULT_STATE), module=opt('--module'), jit='--jit' in a,
                          seconds=float(opt('--seconds', 12)), wad=opt('--wad'))
        allsp += sp
        print(f'{label} round {r+1}: speed mean {statistics.mean(sp):.3f} min {min(sp):.3f} '
              f'| fps mean {statistics.mean(fp):.1f} min {min(fp):.1f} (n={len(sp)})', flush=True)
    if rounds > 1:
        print(f'{label} ALL: speed mean {statistics.mean(allsp):.3f} min {min(allsp):.3f}')


if __name__ == '__main__':
    main()
