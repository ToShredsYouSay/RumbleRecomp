"""Run a test copy of the game on a saved scene, send menu keys and memory writes, and capture the game window
(PrintWindow, so the window needs no focus). Never touches the real game: it uses build/userdir_shot.

  python tools/rr_shot.py NAME --state hub.sav [--game vanilla|weekend] [--size 1280x720] [--fresh]
         [--steps "wait:2 shot:a menu:escape menu:down write:0x80910A60:00400003 shot:b"]

Steps run in order: wait:SECONDS, shot:NAME (saved to build/shots/NAME.png), menu:KEY (escape, up, down, left,
right, enter, back), write:ADDRESS:HEXBYTES. --fresh starts from a clean copy of build/userdir_auto.
Environment: RR_ACHIEVEMENTS is passed through (default the folder tools/achievements); RR_BIN names a folder
holding a test build of the runner and modules instead of build/bin."""
import argparse, ctypes, os, shutil, subprocess, sys, time
from ctypes import wintypes as wt
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import rr_drive as d

ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--state', required=True)
ap.add_argument('--game', default='vanilla')
ap.add_argument('--size', default='1280x720')
ap.add_argument('--fresh', action='store_true')
ap.add_argument('--steps', default='')
a = ap.parse_args()

user = os.path.join(ROOT, 'build', 'userdir_shot')
if a.fresh or not os.path.isdir(user):
    shutil.rmtree(user, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, 'build', 'userdir_auto'), user,
                    ignore=shutil.ignore_patterns('Dump', 'Load', 'StateSaves', 'Logs'))
for sub in ('commands', 'processed', 'failed'):
    os.makedirs(os.path.join(d.AUTO, sub), exist_ok=True)
    for f in os.listdir(os.path.join(d.AUTO, sub)):
        os.remove(os.path.join(d.AUTO, sub, f))
try:
    os.remove(os.path.join(d.AUTO, 'status.txt'))
except OSError:
    pass

weekend = a.game == 'weekend'
BIN = os.environ.get('RR_BIN') or os.path.join(ROOT, 'build', 'bin')  # RR_BIN: a folder with a test build of the runner
wad = os.path.join(ROOT, 'patches', 'out', 'weekend15_patch1.wad') if weekend else sorted(
    f for f in (os.path.join(ROOT, 'original', n) for n in os.listdir(os.path.join(ROOT, 'original'))) if f.endswith('.wad'))[0]
env = dict(os.environ, MODERNGEKKO_BOOT_FILE=wad, RUMBLE_RANDOMIZER='0', MODERNGEKKO_NO_MENU='1',
           RR_MENU_COLOUR='red' if weekend else 'green', RR_MENU_SLOTS='weekend' if weekend else 'vanilla',
           RR_FONT_DIR=os.path.join(ROOT, 'tools', 'fonts'))
env.setdefault('RR_ACHIEVEMENTS', os.path.join(ROOT, 'tools', 'achievements'))
state = a.state if os.path.isabs(a.state) else os.path.join(ROOT, 'build', 'states', a.state)
log = open(os.path.join(ROOT, 'build', 'shot.log'), 'w')
p = subprocess.Popen([os.path.join(BIN, 'moderngekko-run.exe'), '--game',
                      os.path.join(ROOT, 'build', 'gameroot', 'weekend' if weekend else 'vanilla'), '--module',
                      os.path.join(BIN, 'gWPSE01_weekend_recomp.dll' if weekend else 'gWPSE01_recomp.dll'),
                      '--user-dir', user, '--no-mods', '--graphics', 'Vulkan', '--automation-dir', d.AUTO, '--title',
                      'RumbleRecomp', '--load-state', state], env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while time.time() - t0 < 120:
    s = d.status()
    if s.get('state') == 'running' and int(s.get('frame_count', 0) or 0) > 300:
        break
    time.sleep(0.3)

u32, gdi = ctypes.windll.user32, ctypes.windll.gdi32
u32.SetProcessDPIAware()
found = []


@ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
def enum_cb(h, _):
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value == p.pid and u32.IsWindowVisible(h) and u32.GetWindowTextLengthW(h):
        found.append(h)
    return True


u32.EnumWindows(enum_cb, 0)
hwnd = found[0]
W, H = (int(v) for v in a.size.split('x'))
rc = wt.RECT(0, 0, W, H)
u32.AdjustWindowRectEx(ctypes.byref(rc), u32.GetWindowLongW(hwnd, -16), False, u32.GetWindowLongW(hwnd, -20))
u32.SetWindowPos(hwnd, None, 0, 0, rc.right - rc.left, rc.bottom - rc.top, 0x0004 | 0x0010)
time.sleep(2)


class BMI(ctypes.Structure):
    _fields_ = [('a', wt.DWORD), ('w', wt.LONG), ('h', wt.LONG), ('p', wt.WORD), ('b', wt.WORD), ('c', wt.DWORD),
                ('x1', wt.DWORD), ('x2', wt.LONG), ('x3', wt.LONG), ('x4', wt.DWORD), ('x5', wt.DWORD)]


def capture(path):
    r = wt.RECT()
    u32.GetClientRect(hwnd, ctypes.byref(r))
    cw, ch = r.right, r.bottom
    hdc = u32.GetDC(hwnd)
    mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, cw, ch)
    gdi.SelectObject(mdc, bmp)
    u32.PrintWindow(hwnd, mdc, 3)
    buf = ctypes.create_string_buffer(cw * ch * 4)
    gdi.GetDIBits(mdc, bmp, 0, ch, buf, ctypes.byref(BMI(ctypes.sizeof(BMI), cw, -ch, 1, 32, 0, 0, 0, 0, 0, 0)), 0)
    Image.frombuffer('RGB', (cw, ch), buf, 'raw', 'BGRX', 0, 1).save(path)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)


os.makedirs(os.path.join(ROOT, 'build', 'shots'), exist_ok=True)
for step in a.steps.split():
    kind, _, arg = step.partition(':')
    if kind == 'wait':
        time.sleep(float(arg))
    elif kind == 'shot':
        capture(os.path.join(ROOT, 'build', 'shots', arg + '.png'))
        print('shot', arg, flush=True)
    elif kind == 'menu':
        d.send(command='menu_key', key=arg)
        time.sleep(0.4)
    elif kind == 'write':
        addr, _, hexbytes = arg.partition(':')
        d.send(command='write_memory', address=addr, data=hexbytes)
capture(os.path.join(ROOT, 'build', 'shots', a.name + '.png'))
d.stop()
try:
    p.wait(30)
except Exception:
    p.kill()
print('log:', os.path.join(ROOT, 'build', 'shot.log'))
