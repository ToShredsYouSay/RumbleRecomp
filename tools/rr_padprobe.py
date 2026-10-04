#!/usr/bin/env python3
"""Read XInput controllers directly (no Dolphin) and print every change, to tell whether a controller
reports input to Windows at all. Usage: python tools/rr_padprobe.py [seconds]"""
import ctypes, sys, time
from ctypes import wintypes


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [('wButtons', wintypes.WORD), ('bLeftTrigger', ctypes.c_ubyte), ('bRightTrigger', ctypes.c_ubyte),
                ('sThumbLX', ctypes.c_short), ('sThumbLY', ctypes.c_short),
                ('sThumbRX', ctypes.c_short), ('sThumbRY', ctypes.c_short)]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [('dwPacketNumber', wintypes.DWORD), ('Gamepad', XINPUT_GAMEPAD)]


BUTTONS = {0x0001: 'DPadUp', 0x0002: 'DPadDown', 0x0004: 'DPadLeft', 0x0008: 'DPadRight', 0x0010: 'Start',
           0x0020: 'Back', 0x0040: 'LThumb', 0x0080: 'RThumb', 0x0100: 'LB', 0x0200: 'RB', 0x1000: 'A',
           0x2000: 'B', 0x4000: 'X', 0x8000: 'Y'}


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 20
    xi = None
    for name in ('xinput1_4', 'xinput1_3', 'xinput9_1_0'):
        try:
            xi = ctypes.WinDLL(name); break
        except OSError:
            pass
    connected = []
    for i in range(4):
        st = XINPUT_STATE()
        if xi.XInputGetState(i, ctypes.byref(st)) == 0:
            connected.append(i)
    print('XInput slots connected:', connected, flush=True)
    last = {}
    end = time.time() + seconds
    while time.time() < end:
        for i in connected:
            st = XINPUT_STATE()
            if xi.XInputGetState(i, ctypes.byref(st)) != 0:
                continue
            g = st.Gamepad
            pressed = [n for b, n in BUTTONS.items() if g.wButtons & b]
            stick = (round(g.sThumbLX / 32767, 1), round(g.sThumbLY / 32767, 1))
            state = (tuple(pressed), stick, g.bLeftTrigger > 30, g.bRightTrigger > 30)
            if last.get(i) != state:
                last[i] = state
                print(f'slot {i}: buttons={pressed or "-"} left_stick={stick} LT={state[2]} RT={state[3]}', flush=True)
        time.sleep(0.02)


if __name__ == '__main__':
    main()
