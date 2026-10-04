#!/usr/bin/env python3
"""Graphics-settings experiments (Stage 11/12): run a savestate under a given frontend resolution and Dolphin
GFX.ini overrides, measure speed/fps and take a screenshot. Uses build/userdir_gfx (a copy of the save data and
config) so the real build/userdir is never touched.

Usage: python tools/rr_gfx.py LABEL [--res 1920x1080] [--state PATH] [--wad PATH] [--module PATH]
                              [--seconds N] [--gfx Section.Key=Value ...]
Screenshot: build/auto/gfx_<LABEL>.png"""
import os, sys, time, statistics, configparser, ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixels for window sizing/capture
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rr_drive as d

ROOT = d.ROOT
USERDIR = os.path.join(ROOT, 'build', 'userdir_gfx')


def set_ini(path, section, key, value):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str  # keep Dolphin's key case
    if os.path.exists(path):
        cp.read(path, encoding='utf-8')
    if not cp.has_section(section):
        cp.add_section(section)
    cp.set(section, key, value)
    with open(path, 'w', encoding='utf-8') as f:
        cp.write(f, space_around_delimiters=True)


def find_window(pid):
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum(hwnd, _):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    user32.EnumWindows(enum, 0)
    return found[0] if found else None


def resize_client(pid, width, height):
    """Resize the game window so its client area is width x height (physical pixels)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    hwnd = find_window(pid)
    if not hwnd:
        return False
    rect = wintypes.RECT(0, 0, width, height)
    style = user32.GetWindowLongW(hwnd, -16); exstyle = user32.GetWindowLongW(hwnd, -20)
    user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, exstyle)
    user32.SetWindowPos(hwnd, 0, 0, 0, rect.right - rect.left, rect.bottom - rect.top, 0x0004 | 0x0010)
    return True


def window_capture(pid, path):
    """Capture the game window's client area as displayed (includes presenter-only drawing such as
    the native-aspect side panels, which the frame-dump screenshot does not show)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum(hwnd, _):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    user32.EnumWindows(enum, 0)
    if not found:
        return None
    hwnd = found[0]
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    rect = wintypes.RECT(); user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = wintypes.POINT(0, 0); user32.ClientToScreen(hwnd, ctypes.byref(pt))
    from PIL import ImageGrab
    img = ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + rect.right, pt.y + rect.bottom), all_screens=True)
    img.save(path)
    return path


def main():
    a = sys.argv[1:]
    label = a[0]
    opt = lambda k, dflt=None: a[a.index(k) + 1] if k in a else dflt
    # frontend resolution (config.ini [Video] resolution) -> Dolphin internal-resolution multiple
    set_ini(os.path.join(USERDIR, 'config.ini'), 'Video', 'resolution', opt('--res', '1920x1080'))
    gfx_ini = os.path.join(USERDIR, 'Config', 'GFX.ini')
    # reset experiment keys to Dolphin defaults, then apply this run's overrides
    for sec, key, val in [('Settings', 'AspectRatio', '0'), ('Settings', 'wideScreenHack', 'False'),
                          ('Settings', 'HiresTextures', 'False'), ('Settings', 'DumpTextures', 'False'), ('Settings', 'wideScreenHackHUDFix', 'True'), ('Settings', 'EnableMods', 'False'),
                          ('Settings', 'CustomAspectRatioWidth', '1'), ('Settings', 'CustomAspectRatioHeight', '1')]:
        set_ini(gfx_ini, sec, key, val)
    if '--gfx' in a:
        for item in a[a.index('--gfx') + 1:]:
            if item.startswith('--'):
                break
            sk, _, val = item.partition('=')
            sec, _, key = sk.partition('.')
            set_ini(gfx_ini, sec, key, val)
    state = opt('--state', os.path.join(ROOT, 'build', 'states', 'forest_group.sav'))
    try:
        os.remove(os.path.join(d.AUTO, 'status.txt'))
    except OSError:
        pass
    proc = d.start(headless=False, wad=opt('--wad'), module=opt('--module'), user_dir=USERDIR,
                   extra=('--load-state', state))
    t0 = time.time()
    while time.time() - t0 < 120:
        s = d.status()
        try:
            if s.get('state') == 'running' and int(s.get('frame_count', 0)) > 1000 and float(s.get('fps', 0)) > 10:
                break
        except ValueError:
            pass
        time.sleep(0.3)
    if opt('--window'):
        ww, wh = (int(v) for v in opt('--window').split('x'))
        resize_client(proc.pid, ww, wh)
    time.sleep(float(opt('--settle', 2)))
    shot = d.shot(f'gfx_{label}')
    window_capture(proc.pid, os.path.join(d.AUTO, f'win_{label}.png'))
    sp, fp = [], []
    for _ in range(int(float(opt('--seconds', 6)) * 2)):
        time.sleep(0.5)
        s = d.status()
        try:
            sp.append(float(s['speed'])); fp.append(float(s['fps']))
        except (KeyError, ValueError):
            pass
    d.stop()
    try:
        proc.wait(60)
    except Exception:
        proc.kill()
    size = ''
    try:
        from PIL import Image
        size = '%dx%d' % Image.open(shot).size
    except Exception:
        pass
    print(f'{label}: speed mean {statistics.mean(sp):.3f} min {min(sp):.3f} | fps mean {statistics.mean(fp):.1f} '
          f'| screenshot {size} -> {shot}')


if __name__ == '__main__':
    main()
