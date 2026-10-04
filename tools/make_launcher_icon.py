"""Draws tools/launcher.ico: a clear gacha capsule with the green wind-up key inside (an original drawing, no
game artwork; the same drawing as the launcher's version tabs, tools/make_launcher_art.py).
Run: python tools/make_launcher_icon.py [preview.png]   then rebuild the exe (tools/build_launcher_exe.ps1)."""
import os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from make_launcher_art import app_icon

sq = app_icon()
big = sq.resize((256, 256), Image.LANCZOS)
big.save(os.path.join(ROOT, 'tools', 'launcher.ico'),
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
if len(sys.argv) > 1:  # preview strip: 256, 64, 32, and 16 px on a dark background
    prev = Image.new('RGBA', (400, 256), (16, 26, 51, 255))
    prev.alpha_composite(big, (0, 0))
    for x, n in ((264, 64), (336, 32), (376, 16)):
        prev.alpha_composite(sq.resize((n, n), Image.LANCZOS), (x, 0))
    prev.save(sys.argv[1])
