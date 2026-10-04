#!/usr/bin/env python3
"""Stage 9 stability soak: run the game for N minutes cycling busy savestates with constant automated
input (automation pad commands, no keystrokes, so the PC stays usable), and watch for freezes, speed
drops, memory growth and log errors. Uses build/userdir_auto (a copy of the save data).
Usage: python tools/rr_soak.py LABEL [--minutes N] [--wad PATH --module PATH] [--scenes a.sav,b.sav]"""
import os, sys, time, random, subprocess, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rr_drive as d

ROOT = d.ROOT
STATES = os.path.join(ROOT, 'build', 'states')
VANILLA = ['forest4_group', 'lobby4', 'forest_group', 'cave_group', 'hub4', 'cave_start', 'forest4_start', 'hub']
WEEKEND = ['wk_forest4_group', 'wk_lobby4', 'wk_forest_group', 'wk_forest4_start', 'wk_hub4', 'wk_hub']
MOVES = [{'wii_dpad_up': 1}, {'wii_dpad_down': 1}, {'wii_dpad_left': 1}, {'wii_dpad_right': 1},
         {'main_x': 1}, {'main_x': -1}, {'main_y': 1}, {'main_y': -1}]


def working_set_mb(pid):
    out = subprocess.run(['tasklist', '/fi', f'PID eq {pid}', '/fo', 'csv', '/nh'],
                         capture_output=True, text=True).stdout
    try:
        return int(out.strip().split('","')[4].replace(' K', '').replace(',', '').strip('"')) // 1024
    except (IndexError, ValueError):
        return -1


def main():
    a = sys.argv[1:]
    label = a[0]
    opt = lambda k, dflt=None: a[a.index(k) + 1] if k in a else dflt
    minutes = float(opt('--minutes', 30))
    wad = opt('--wad')
    scenes = opt('--scenes')
    scenes = scenes.split(',') if scenes else (WEEKEND if wad else VANILLA)
    user = os.path.join(ROOT, 'build', 'userdir_auto')
    try:
        os.remove(os.path.join(d.AUTO, 'status.txt'))
    except OSError:
        pass
    proc = d.start(headless=False, wad=wad, module=opt('--module'), user_dir=user,
                   extra=('--load-state', os.path.join(STATES, scenes[0] + '.sav')))
    t0 = time.time()
    while time.time() - t0 < 120 and d.status().get('state') != 'running':
        time.sleep(1)
    time.sleep(5)
    rnd = random.Random(1234)
    log, stalls, scene_i, last_frame = [], 0, 0, None
    end = time.time() + minutes * 60
    next_scene = time.time() + 60
    next_sample = time.time()
    while time.time() < end:
        if proc.poll() is not None:
            print(f'{label}: GAME EXITED early with code {hex(proc.returncode & 0xFFFFFFFF)}'); break
        if time.time() >= next_scene:
            scene_i = (scene_i + 1) % len(scenes)
            d.send(command='load_state', path=os.path.join(STATES, scenes[scene_i] + '.sav'))
            next_scene = time.time() + 60
        # player 1 (Wii Remote) and GameCube ports 1-3: random movement + attacks
        mv = rnd.choice(MOVES)
        d.send(command='pad_frames', port=0, frames=rnd.randint(6, 30), wii_a=1 if rnd.random() < 0.5 else 0,
               wii_b=1 if rnd.random() < 0.3 else 0, **{k: v for k, v in mv.items() if k.startswith('wii')})
        for port in (1, 2, 3):
            d.send(command='pad', port=port, a=rnd.randint(0, 1), b=rnd.randint(0, 1),
                   main_x=rnd.choice((-1, 0, 1)), main_y=rnd.choice((-1, 0, 1)))
        if time.time() >= next_sample:
            s = d.status()
            try:
                fc = int(s.get('frame_count', 0))
                sample = (round(time.time() - t0), float(s['speed']), float(s['fps']), fc, working_set_mb(proc.pid))
            except (KeyError, ValueError):
                sample = None
            if sample:
                if last_frame is not None and fc == last_frame:
                    stalls += 1
                last_frame = fc
                log.append(sample)
            next_sample = time.time() + 10
    d.stop()
    try:
        rc = proc.wait(90)
    except Exception:
        proc.kill(); rc = -1
    with open(os.path.join(ROOT, 'build', f'soak_{label}.csv'), 'w') as f:
        f.write('t,speed,fps,frame,mem_mb\n'); f.writelines(','.join(map(str, x)) + '\n' for x in log)
    drive_log = open(os.path.join(ROOT, 'build', 'drive.log'), encoding='utf-8', errors='replace').read()
    shutdown = [l for l in drive_log.splitlines() if 'shutdown:' in l or 'non-entry' in l]
    errors = [l for l in drive_log.splitlines() if any(w in l.lower() for w in ('error', 'panic', 'assert', 'exception', 'fatal'))]
    sp = [x[1] for x in log]; mem = [x[4] for x in log if x[4] > 0]
    print(f'{label}: {len(log)} samples over {minutes:g} min | exit {hex(rc & 0xFFFFFFFF)} | stalls {stalls}')
    print(f'  speed mean {statistics.mean(sp):.3f} min {min(sp):.3f} | samples below 0.9: {sum(1 for v in sp if v < 0.9)}')
    if mem:
        print(f'  memory MB: start {mem[0]} max {max(mem)} end {mem[-1]}')
    for l in shutdown: print('  ' + l)
    print(f'  log lines mentioning error/panic/assert/exception/fatal: {len(errors)}')
    for l in errors[:15]: print('   ! ' + l[:200])


if __name__ == '__main__':
    main()
