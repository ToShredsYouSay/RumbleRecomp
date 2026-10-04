#!/usr/bin/env python3
"""RumbleRecomp automation driver: launch the game headless-with-Vulkan, send pad commands, take screenshots.
Library + tiny CLI:  python tools/rr_drive.py start | send k=v ... | shot name | stop | status"""
import glob, itertools, os, subprocess, sys, time

ROOT = r'C:\RumbleRecomp'
# Automation folders: the user's own play session (tools/build_and_run.ps1) uses build/auto; every test
# instance started from here uses build/auto_tools, so a test can never send commands (screenshot, stop,
# load_state...) to the user's game. Talk to the live game explicitly with use_live_game().
LIVE_AUTO = os.path.join(ROOT, 'build', 'auto')
AUTO = os.environ.get('RR_AUTO') or os.path.join(ROOT, 'build', 'auto_tools')


def use_live_game():
    """Point send/status/shot at the user's running game (build/auto) instead of test instances."""
    global AUTO
    AUTO = LIVE_AUTO
_ctr = itertools.count(int(time.time()) % 100000 * 100)

def start(wad=None, graphics='Vulkan', extra=(), headless=True, module=None, jit=False, user_dir=None):
    wad = wad or sorted(glob.glob(os.path.join(ROOT, 'original', '*.wad')))[0]
    # RR_USERDIR lets automation run against a copy of the user's save data (build/userdir_auto)
    # Test instances never touch the user's real save (build/userdir) unless explicitly asked to.
    user_dir = user_dir or os.environ.get('RR_USERDIR') or os.path.join(ROOT, 'build', 'userdir_auto')
    if os.path.normcase(os.path.abspath(AUTO)) == os.path.normcase(os.path.abspath(LIVE_AUTO)):
        raise RuntimeError('refusing to start a test instance on the live-game automation folder')
    for d in ('commands', 'processed', 'failed'):
        os.makedirs(os.path.join(AUTO, d), exist_ok=True)
        for f in os.listdir(os.path.join(AUTO, d)):
            os.remove(os.path.join(AUTO, d, f))
    env = dict(os.environ, MODERNGEKKO_BOOT_FILE=wad)
    if jit: env['MODERNGEKKO_STATICRECOMP'] = '0'   # Dolphin's own JIT64 instead of the recompiled module
    log = open(os.path.join(ROOT, 'build', 'drive.log'), 'w')
    runner = os.environ.get('RR_RUNNER') or os.path.join(ROOT, 'build', 'bin', 'moderngekko-run.exe')
    return subprocess.Popen([runner,
        '--game', os.path.join(ROOT, 'build', 'gameroot', 'vanilla'),
        *(['--allow-interpreter'] if jit else ['--module', module or os.path.join(ROOT, 'build', 'bin', 'gWPSE01_recomp.dll')]),
        '--user-dir', user_dir, *(['--headless'] if headless else []), '--graphics', graphics,
        '--no-mods', '--automation-dir', AUTO, *extra], env=env, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)

def status():
    d = {}
    try:
        for line in open(os.path.join(AUTO, 'status.txt')):
            k, _, v = line.strip().partition('=')
            d[k] = v
    except OSError:
        pass
    return d

def wait_frames(n, timeout=120):
    """Wait until n more emulated frames have elapsed."""
    t0 = time.time(); start = int(status().get('frame_count', 0) or 0)
    while time.time() - t0 < timeout:
        if int(status().get('frame_count', 0) or 0) >= start + n:
            return True
        time.sleep(0.1)
    return False

def send(**kw):
    name = f'{next(_ctr):08d}.cmd'
    tmp = os.path.join(AUTO, name + '.tmp')  # outside commands/ so the game never reads a partial file
    body = ''.join(f'{k}={v}\n' for k, v in kw.items())
    with open(tmp, 'w') as f:
        f.write(body)
    final = os.path.join(AUTO, 'commands', name)
    os.replace(tmp, final)
    for _ in range(300):
        if os.path.exists(os.path.join(AUTO, 'processed', name)):
            return True
        if os.path.exists(os.path.join(AUTO, 'failed', name)):
            print('FAILED command', kw); return False
        time.sleep(0.05)
    print('timeout waiting for', name); return False

def press(button, frames=6, **extra):
    ok = send(command='pad_frames', port=0, frames=frames, **{button: 1}, **extra)
    wait_frames(frames + 2)
    return ok

def shot(name):
    p = os.path.join(AUTO, name + '.png')
    if os.path.exists(p):
        os.remove(p)
    send(command='screenshot', path=p)
    last = -1
    for _ in range(100):  # wait until the PNG exists and its size is stable
        time.sleep(0.1)
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        if size > 0 and size == last:
            break
        last = size
    return p

def stop():
    send(command='stop')

if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'start': start()
    elif c == 'send': send(**dict(a.split('=', 1) for a in sys.argv[2:]))
    elif c == 'shot': print(shot(sys.argv[2]))
    elif c == 'stop': stop()
    elif c == 'status': print(status())
