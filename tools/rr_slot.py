"""Boot each savestate in a test copy and dump the game's current save slot (0x1360 bytes) to OUTDIR/<state>.slot.
  python tools/rr_slot.py OUTDIR STATE...      (STATE: a name in build/states, or a full path)
Set WEEKEND=1 for Weekend + PATCH1 states. Then decode the progress table with tools/rr_table.py."""
import os, subprocess, sys, struct, time
sys.path.insert(0, r'C:\RumbleRecomp\tools')
import rr_drive as d

R = r'C:\RumbleRecomp'
out = sys.argv[1]
os.makedirs(out, exist_ok=True)


def rd(addr, size, name):
    p = os.path.join(out, name)
    d.send(command='read_memory', address=hex(addr), size=size, path=p)
    return open(p, 'rb').read()


for state in sys.argv[2:]:
    for sub in ('commands', 'processed', 'failed'):
        os.makedirs(os.path.join(d.AUTO, sub), exist_ok=True)
        for f in os.listdir(os.path.join(d.AUTO, sub)):
            os.remove(os.path.join(d.AUTO, sub, f))
    try:
        os.remove(os.path.join(d.AUTO, 'status.txt'))
    except OSError:
        pass
    path = state if os.path.isabs(state) else os.path.join(R, 'build', 'states', state)
    if os.environ.get('WEEKEND'):
        env = dict(os.environ, MODERNGEKKO_BOOT_FILE=os.path.join(R, 'patches', 'out', 'weekend15_patch1.wad'))
        p = subprocess.Popen([os.path.join(R, 'build', 'bin', 'moderngekko-run.exe'), '--game',
                              os.path.join(R, 'build', 'gameroot', 'weekend'), '--module',
                              os.path.join(R, 'build', 'bin', 'gWPSE01_weekend_recomp.dll'), '--user-dir',
                              os.path.join(R, 'build', 'userdir_auto'), '--headless', '--graphics', 'Vulkan',
                              '--no-mods', '--automation-dir', d.AUTO, '--load-state', path],
                             env=env, cwd=R, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    else:
        p = d.start(headless=True, extra=('--load-state', path))
    t0 = time.time()
    while time.time() - t0 < 120:
        s = d.status()
        if s.get('state') == 'running' and int(s.get('frame_count', 0) or 0) > 1000:
            break
        time.sleep(0.3)
    time.sleep(2)
    mgr = struct.unpack('>I', rd(0x804B90D0, 4, 'tmp'))[0]
    m = rd(mgr, 0x100, os.path.basename(state) + '.mgr')
    base, cur = struct.unpack('>I', m[0x44:0x48])[0], m[4]
    rd(base + cur * 0x1360, 0x1360, os.path.basename(state) + '.slot')
    print(state, 'mgr', hex(mgr), 'slots', hex(base), 'cur', cur, flush=True)
    d.stop()
    try:
        p.wait(30)
    except Exception:
        p.kill()
