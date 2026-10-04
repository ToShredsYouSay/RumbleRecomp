#!/usr/bin/env python3
"""Performance sampling for the running game window: FPS from the window title, and per-thread CPU%."""
import ctypes, re, subprocess, time, json
from ctypes import wintypes
user32 = ctypes.WinDLL('user32', use_last_error=True)

def window_title():
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n and user32.IsWindowVisible(hwnd):
            b = ctypes.create_unicode_buffer(n + 1); user32.GetWindowTextW(hwnd, b, n + 1)
            if b.value.startswith('ModernGekko - Poke'): found.append(b.value)
        return True
    user32.EnumWindows(cb, 0)
    return found[0] if found else ''

def fps():
    m = re.search(r'([\d.]+) FPS', window_title())
    return float(m.group(1)) if m else None

def pid():
    out = subprocess.run(['tasklist', '/fi', 'imagename eq moderngekko-run.exe', '/fo', 'csv', '/nh'], capture_output=True, text=True).stdout
    m = re.search(r'"moderngekko-run.exe","(\d+)"', out)
    return int(m.group(1)) if m else None

def thread_cpu(seconds=3.0):
    """Return list of (thread_id, cpu_percent_of_one_core) sorted desc, sampled over `seconds`."""
    p = pid()
    ps = ("$p=Get-Process -Id %d; function s{ $h=@{}; foreach($t in (Get-Process -Id %d).Threads){ $h[$t.Id]=$t.TotalProcessorTime.TotalMilliseconds }; $h };"
          "$a=s; Start-Sleep -Milliseconds %d; $b=s; $r=@(); foreach($k in $b.Keys){ if($a.ContainsKey($k)){ $r+=[pscustomobject]@{id=$k;ms=$b[$k]-$a[$k]} } };"
          "$r | Sort-Object ms -Descending | Select-Object -First 8 | ConvertTo-Json -Compress") % (p, p, int(seconds * 1000))
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True).stdout.strip()
    data = json.loads(out) if out else []
    if isinstance(data, dict): data = [data]
    return [(d['id'], round(d['ms'] / (seconds * 10), 1)) for d in data]

def sample(seconds=10, label=''):
    """Sample FPS once per second and thread CPU once; print a summary."""
    vals = []; t0 = time.time()
    import threading
    res = {}
    th = threading.Thread(target=lambda: res.setdefault('cpu', thread_cpu(min(seconds, 5))))
    th.start()
    while time.time() - t0 < seconds:
        f = fps()
        if f is not None: vals.append(f)
        time.sleep(1)
    th.join()
    print(f'[{label}] fps min/avg/max = {min(vals):.1f}/{sum(vals)/len(vals):.1f}/{max(vals):.1f}  samples={len(vals)}   '
          f'top threads (% of one core): {res.get("cpu")}')
    return vals, res.get('cpu')
