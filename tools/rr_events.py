#!/usr/bin/env python3
"""Compare short frame dips around gameplay events (enemies turning into drops, the Pokémon swap after a
knockout) between the recomp and Dolphin's own JIT on the same savestate.

Loads a savestate, then for N seconds attacks (J/K) while nudging toward the enemies with real keystrokes,
sampling the automation status every 0.1 s. Prints a dip summary and writes build/events_<label>.csv.
Usage: python tools/rr_events.py LABEL [--jit] [--state PATH] [--seconds N] [--module PATH]
Needs the game window in the foreground (keystrokes); don't type while it runs."""
import os, sys, time, threading, csv, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rr_drive as d, rr_keys as k

ROOT = d.ROOT


def main():
    a = sys.argv[1:]
    label = a[0]
    opt = lambda key, dflt=None: a[a.index(key) + 1] if key in a else dflt
    state = opt('--state', os.path.join(ROOT, 'build', 'states', 'forest_group.sav'))
    seconds = float(opt('--seconds', 25))
    os.environ.setdefault('RR_USERDIR', os.path.join(ROOT, 'build', 'userdir_auto'))
    try:
        os.remove(os.path.join(d.AUTO, 'status.txt'))
    except OSError:
        pass
    proc = d.start(headless=False, jit='--jit' in a, module=opt('--module'), extra=('--load-state', state))
    t0 = time.time()
    while time.time() - t0 < 120:
        s = d.status()
        try:
            if s.get('state') == 'running' and int(s.get('frame_count', 0)) > 1000 and float(s.get('fps', 0)) > 10:
                break
        except ValueError:
            pass
        time.sleep(0.3)
    time.sleep(1.5)
    assert k.focus(), 'could not focus the game window'

    samples, stop = [], threading.Event()

    def sampler():
        start = time.time()
        while not stop.is_set():
            s = d.status()
            try:
                samples.append((time.time() - start, float(s['speed']), float(s['fps']), int(s['frame_count'])))
            except (KeyError, ValueError):
                pass
            time.sleep(0.1)

    th = threading.Thread(target=sampler); th.start()
    end = time.time() + seconds
    step = 0
    while time.time() < end and k.is_foreground():
        k.tap('J' if step % 3 else 'K')
        if step % 8 == 0:
            k.hold('W', 0.25)
        step += 1
        time.sleep(0.15)
        if step % 40 == 0:
            d.shot(f'events_{label}_{step // 40}')
    stop.set(); th.join()
    d.stop()
    try:
        proc.wait(60)
    except Exception:
        proc.kill()

    with open(os.path.join(ROOT, 'build', f'events_{label}.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['t', 'speed', 'fps', 'frame']); w.writerows(samples)
    fps = [s[2] for s in samples]; sp = [s[1] for s in samples]
    dips = [s for s in samples if s[2] < 57]
    print(f'{label}: fps mean {statistics.mean(fps):.1f} min {min(fps):.1f} | speed mean {statistics.mean(sp):.3f} '
          f'min {min(sp):.3f} | samples below 57 fps: {len(dips)}/{len(samples)}')
    for t, s_, f_, fr in dips[:40]:
        print(f'   t={t:5.1f}s fps={f_:5.1f} speed={s_:.3f}')


if __name__ == '__main__':
    main()
