#!/usr/bin/env python3
"""Send real keyboard input (SendInput, hardware scancodes) to the RumbleRecomp game window.

Safety: keys are sent ONLY while the game window is the foreground window; otherwise nothing is sent.
Usage as a library:  import rr_keys as k; k.focus(); k.tap('J'); k.hold('S', 0.5)
"""
import ctypes, time
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
TITLE_PREFIX = 'ModernGekko - Poke'  # matches older set-ups too

# name -> (scancode, extended)
SC = {'J': (0x24, 0), 'K': (0x25, 0), 'L': (0x26, 0), 'I': (0x17, 0), 'W': (0x11, 0), 'A': (0x1E, 0),
      'S': (0x1F, 0), 'D': (0x20, 0), 'SPACE': (0x39, 0), 'RETURN': (0x1C, 0), 'BACK': (0x0E, 0), 'TAB': (0x0F, 0),
      'UP': (0x48, 1), 'DOWN': (0x50, 1), 'LEFT': (0x4B, 1), 'RIGHT': (0x4D, 1)}

KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x1, 0x2, 0x8

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
class _U(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('u', _U)]


def find_window():
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.startswith(TITLE_PREFIX):
                found.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def is_foreground():
    hwnd = find_window()
    return bool(hwnd) and user32.GetForegroundWindow() == hwnd


def focus():
    """Bring the game window to the foreground. Returns True only if it is really foreground afterwards."""
    hwnd = find_window()
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.keybd_event(0x12, 0, 0, 0)           # ALT down/up: lets SetForegroundWindow succeed
    user32.keybd_event(0x12, 0, KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    return user32.GetForegroundWindow() == hwnd


def _send(name, up):
    sc, ext = SC[name.upper()]
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if ext else 0) | (KEYEVENTF_KEYUP if up else 0)
    inp = INPUT(type=1, u=_U(ki=KEYBDINPUT(0, sc, flags, 0, 0)))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def hold(name, seconds=0.15):
    """Press and release a key; refuses (returns False) if the game window is not in the foreground."""
    if not is_foreground():
        return False
    _send(name, False)
    time.sleep(seconds)
    _send(name, True)   # always release, even if focus changed meanwhile
    return True


def tap(name):
    return hold(name, 0.15)


def hold_many(names, seconds=1.0):
    """Hold several keys at once (e.g. ['W','A'] = up-left). Same foreground safety as hold()."""
    if not is_foreground():
        return False
    for n in names: _send(n, False)
    time.sleep(seconds)
    for n in names: _send(n, True)
    return True
