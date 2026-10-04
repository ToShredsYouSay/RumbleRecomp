#!/usr/bin/env python3
"""Draws the launcher artwork into tools/launcher_art/ (all original drawings, no game artwork):
  capsule_<colour>.png / capsule_<colour>_open.png   version tabs (green, red, blue): a clear capsule with the
                                              wind-up key inside; it pops apart when the tab is selected
  controller.png                              flat stencil gamepad with each input labelled, with the
                                              button letters the game shows in its own prompts
  keyboard.png                                flat stencil keycaps the game uses, labelled
Run: python tools/make_launcher_art.py   (needs Pillow and the Segoe UI fonts that come with Windows)"""
import os
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'launcher_art')
FONTS = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
NUNITO = os.path.join(ROOT, 'tools', 'fonts')  # bundled Nunito (SIL Open Font License), as in the launcher
INK = (28, 30, 32, 255)
WHITE = (246, 246, 246, 255)
STEEL, STEEL_HI = (150, 158, 166, 255), (206, 212, 218, 255)
COLOURS = {  # tab colour -> (top half, shine)
    'green': ((26, 118, 56, 255), (74, 166, 104, 255)),
    'red': ((196, 38, 38, 255), (236, 104, 96, 255)),
    'blue': ((30, 86, 196, 255), (98, 148, 236, 255)),
}
def font(size, bold=False):
    return ImageFont.truetype(os.path.join(NUNITO, 'Nunito-Bold.ttf' if bold else 'Nunito-Regular.ttf'), size)


def symbol_font(size):
    """For the arrow keys: Nunito has no arrows."""
    return ImageFont.truetype(os.path.join(FONTS, 'segoeuib.ttf'), size)


# ---- version tabs and app icon: a clear gacha capsule with a colour-coded wind-up key inside ----

KEYS = {'green': ((26, 118, 56), (74, 166, 104)), 'red': ((196, 38, 38), (236, 104, 96)),
        'blue': ((30, 86, 196), (98, 148, 236)), 'steel': ((150, 158, 166), (206, 212, 218))}
W, H = 1400, 1700          # working canvas
CX, CY, R, OL = 700, 1160, 420, 34
GAP_OPEN = 75  # how far each half moves when the capsule pops open
RIM, SEAM = (206, 220, 240, 255), (206, 220, 240, 150)


def key_layer(colour, scale=0.72):
    """A wind-up key, upright, centred on its own layer: bow of two loops, collar, stem with teeth."""
    base, hi = KEYS[colour]
    base, hi = base + (255,), hi + (255,)
    im = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, top, ol = W // 2, 230, 26
    for sx in (-1, 1):
        x0 = cx + sx * 140
        d.ellipse([x0 - 135, top, x0 + 135, top + 215], fill=base, outline=INK, width=ol)
        d.ellipse([x0 - 58, top + 62, x0 + 58, top + 153], fill=(0, 0, 0, 0), outline=INK, width=ol)
        d.arc([x0 - 105, top + 26, x0 + 105, top + 189], 200, 290, fill=hi, width=20)
    d.rectangle([cx - 55, top + 100, cx + 55, top + 700], fill=base, outline=INK, width=ol)
    d.rectangle([cx - 28, top + 190, cx - 8, top + 680], fill=hi)
    d.ellipse([cx - 85, top + 60, cx + 85, top + 165], fill=base, outline=INK, width=ol)
    d.ellipse([cx - 52, top + 82, cx + 24, top + 120], fill=hi)
    for y in (top + 590, top + 640):  # teeth
        d.rectangle([cx + 55, y, cx + 115, y + 32], fill=base, outline=INK, width=16)
    im = im.crop(im.getbbox())
    return im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)


def shell(top, cy=CY):
    """One clear half of the capsule as a layer: lightly tinted plastic with a light rim (it reads as clear on a
    dark background), a thin seam, and highlights."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box = [CX - R, cy - R, CX + R, cy + R]
    start, end = (180, 360) if top else (0, 180)
    d.pieslice(box, start, end, fill=(214, 232, 255, 40))
    hl = Image.new('RGBA', im.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    if top:
        hd.arc([CX - R + 55, cy - R + 55, CX + R - 55, cy + R - 55], 198, 250, fill=(255, 255, 255, 230), width=42)
        hd.ellipse([CX + 170, cy - R + 120, CX + 245, cy - R + 195], fill=(255, 255, 255, 220))
    else:
        hd.arc([CX - R + 40, cy - R + 40, CX + R - 40, cy + R - 40], 25, 155, fill=(255, 255, 255, 70), width=28)
    im.alpha_composite(hl.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(im)
    d.arc(box, start, end, fill=RIM, width=OL)
    d.line([CX - R + 4, cy, CX + R - 4, cy], fill=SEAM, width=10)
    return im


def capsule_full(colour, open_=False):
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    # The key sits in the same place either way; when open, the two halves move apart evenly (top up, bottom
    # down), leaving a gap across the middle.
    key = key_layer(colour, 0.78).rotate(-36, resample=Image.BICUBIC, expand=True)
    k = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    k.alpha_composite(key, (CX - key.width // 2, CY - key.height // 2))
    mask = Image.new('L', canvas.size, 0)
    ImageDraw.Draw(mask).ellipse([CX - R + 24, CY - R + 24, CX + R - 24, CY + R - 24], fill=255)
    k.putalpha(Image.composite(k.getchannel('A'), Image.new('L', canvas.size, 0), mask))
    canvas.alpha_composite(k)
    gap = GAP_OPEN if open_ else 0
    canvas.alpha_composite(shell(False), (0, gap))
    canvas.alpha_composite(shell(True), (0, -gap))
    return canvas


def tab_capsules(colour, height=120):
    """(closed, open) tab images in one shared frame, so the capsule stays centred when the tab is selected."""
    closed, opened = capsule_full(colour, False), capsule_full(colour, True)
    a, b = closed.getbbox(), opened.getbbox()
    box = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
    out = []
    for im in (closed, opened):
        im = im.crop(box)
        out.append(im.resize((height * im.width // im.height, height), Image.LANCZOS))
    return out


def app_icon():
    """Closed capsule with the green key, square, for tools/launcher.ico."""
    im = capsule_full('green', False)
    im = im.crop(im.getbbox())
    side = max(im.size) + 40
    sq = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    sq.alpha_composite(im, ((side - im.width) // 2, (side - im.height) // 2))
    return sq



TEXT = (244, 246, 250)
MUTED = (185, 192, 204)
STENCIL = (207, 213, 223, 255)   # flat silhouette colour, neutral so it sits on any tab tint
LINE = (138, 147, 166, 255)      # callout lines: visible on the silhouette and on the dark background


def label(d, xy, text, anchor, f, fill=TEXT):
    d.text(xy, text, font=f, fill=fill, anchor=anchor)


def badge(im, d, cx, cy, r, text, f):
    """A round button badge with the letter the game itself shows in its on-screen prompts."""
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=LINE, width=max(2, r // 7))
    if text in '+−':  # the symbols are much smaller than the letters at the same font size
        f = f.font_variant(size=int(f.size * 1.5))
    # centre the drawn pixels themselves: the font's own boxes include side bearings and line space
    glyph = Image.new('L', (4 * r, 4 * r), 0)
    ImageDraw.Draw(glyph).text((2 * r, 2 * r), text, font=f, fill=255, anchor='mm')
    glyph = glyph.crop(glyph.getbbox())
    ink = Image.new('RGBA', glyph.size, TEXT + (255,))
    im.paste(ink, (round(cx - glyph.width / 2), round(cy - glyph.height / 2)), glyph)


def controller(path):
    """Flat stencil gamepad in a DualShock-like shape: a slim top body, long grips angled down and out,
    d-pad and face buttons up top, both sticks low in the middle. Controls are cut out as holes."""
    W, H, sc = 1160, 580, 2  # design units; drawn at 2x, saved at the launcher's display size
    OX = 40                  # left margin in design units
    s = lambda *v: [int((x + (OX if i % 2 == 0 else 0)) * sc) for i, x in enumerate(v)]
    mask = Image.new('L', (W * sc, H * sc), 0)
    m = ImageDraw.Draw(mask)

    def grip(cx, cy, w, h, angle):
        layer = Image.new('L', mask.size, 0)
        ImageDraw.Draw(layer).ellipse(s(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), fill=255)
        layer = layer.rotate(angle, resample=Image.BICUBIC, center=((cx + OX) * sc, cy * sc))
        return ImageChops.lighter(mask, layer)

    m.rounded_rectangle(s(330, 170, 750, 320), radius=64 * sc, fill=255)        # top body
    mask = grip(372, 335, 120, 250, -24)                                          # left grip, angled out
    mask = grip(708, 335, 120, 250, 24)                                           # right grip
    m = ImageDraw.Draw(mask)
    m.ellipse(s(410, 255, 520, 365), fill=255)                                    # stick bulges
    m.ellipse(s(560, 255, 670, 365), fill=255)
    m.rounded_rectangle(s(346, 138, 446, 176), radius=14 * sc, fill=255)          # shoulders
    m.rounded_rectangle(s(634, 138, 734, 176), radius=14 * sc, fill=255)
    m.rectangle(s(346, 168, 446, 174), fill=0)                                    # gap under the shoulders
    m.rectangle(s(634, 168, 734, 174), fill=0)

    def ring(cx, cy, r, w):
        m.ellipse(s(cx - r, cy - r, cx + r, cy + r), fill=0)
        m.ellipse(s(cx - r + w, cy - r + w, cx + r - w, cy + r - w), fill=255)
    ring(465, 310, 36, 9)                                                         # left stick
    ring(615, 310, 36, 9)                                                         # right stick
    cx, cy = 400, 238                                                             # d-pad
    m.rounded_rectangle(s(cx - 11, cy - 34, cx + 11, cy + 34), radius=4 * sc, fill=0)
    m.rounded_rectangle(s(cx - 34, cy - 11, cx + 34, cy + 11), radius=4 * sc, fill=0)
    for x, y in ((680, 206), (650, 238), (710, 238), (680, 270)):                 # face buttons
        m.ellipse(s(x - 15, y - 15, x + 15, y + 15), fill=0)
    m.rounded_rectangle(s(492, 206, 518, 220), radius=7 * sc, fill=0)             # back / share
    m.rounded_rectangle(s(562, 206, 588, 220), radius=7 * sc, fill=0)             # start / options
    # HOME, in the middle of the controller: a round hole with a little house left standing inside it
    m.ellipse(s(519, 241, 561, 283), fill=0)
    m.polygon(s(540, 248, 528, 260, 552, 260), fill=255)                           # roof
    m.rectangle(s(532, 259, 548, 274), fill=255)                                   # walls
    m.rectangle(s(538, 266, 542, 274), fill=0)                                     # door

    im = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    im.paste(Image.new('RGBA', mask.size, STENCIL), (0, 0), mask)
    d = ImageDraw.Draw(im)
    f, fb = font(24 * sc), font(28 * sc, bold=True)

    def dot(px, py):
        d.ellipse(s(px - 5, py - 5, px + 5, py + 5), fill=LINE)

    fbadge, R, GAP = font(21 * sc, bold=True), 17, 10

    # Each label is the input's job; jobs of equal weight share a line ("Attack 1 / Confirm"). A second, smaller
    # line is only for an extra instruction, in brackets.
    def callout(px, py, tx, ty, title, side, letter=None, sub=None):
        d.line(s(px, py, tx + (12 if side == 'l' else -12), ty), fill=LINE, width=2 * sc)
        dot(px, py)
        a = 'rm' if side == 'l' else 'lm'
        cy = ty - 16 if sub else ty
        x = tx
        if letter and side == 'r':
            badge(im, d, *s(tx + R, cy), R * sc, letter, fbadge)
            x = tx + 2 * R + GAP
        label(d, s(x, cy), title, a, fb)
        if sub:
            label(d, s(tx, ty + 20), sub, a, f, MUTED)
        if letter and side == 'l':
            w = fb.getlength(title) / sc
            badge(im, d, *s(tx - w - GAP - R, cy), R * sc, letter, fbadge)

    def above(px, py, tx, ty, title, letter, sub=None):
        d.line(s(px, py, tx, ty + (10 if sub else -22)), fill=LINE, width=2 * sc)
        dot(px, py)
        w = fb.getlength(title) / sc + GAP + 2 * R    # badge and title centred together over the line
        x0 = tx - w / 2
        badge(im, d, *s(x0 + R, ty - 41), R * sc, letter, fbadge)
        label(d, s(x0 + 2 * R + GAP, ty - 30), title, 'ls', fb)
        if sub:
            label(d, s(tx, ty + 4), sub, 'mb', f, MUTED)

    callout(400, 238, 250, 230, 'Move', 'l')
    callout(465, 310, 250, 340, 'Move', 'l')
    callout(690, 150, 820, 90, 'Switch', 'r', 'X')
    callout(710, 238, 820, 190, 'Switch', 'r', 'X')
    callout(650, 238, 820, 290, 'Attack 2 / Cancel', 'r', 'B')
    callout(680, 270, 820, 390, 'Attack 1 / Confirm', 'r', 'A')
    above(505, 213, 420, 70, 'Favourite', '−', '(single player)')
    above(575, 213, 640, 70, 'Pause', '+')
    # HOME opens RumbleRecomp's own menu (save and load states, fullscreen), below the controller
    d.line(s(540, 283, 540, 500), fill=LINE, width=2 * sc)
    label(d, s(540, 522), 'Menu', 'mm', fb)
    label(d, s(540, 556), '(or press both sticks in)', 'mm', f, MUTED)
    im.resize((620, 620 * H // W), Image.LANCZOS).save(path)


def keyboard(path):
    """Flat stencil keycaps: one neutral colour, the legend cut into the cap. Three rows of three, each key with
    its job beside it (and the game's button badge where it has one); the columns and the gaps between rows are
    spread evenly over the picture."""
    W, H, sc = 1080, 598, 2  # same displayed height as the controller picture
    s = lambda *v: [int(x * sc) for x in v]
    fk, fl, fs = font(30 * sc, bold=True), font(27 * sc, bold=True), font(23 * sc)
    fb, R, GAP, PAD = font(19 * sc, bold=True), 15, 8, 14
    im = Image.new('RGBA', (W * sc, H * sc), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def key(x, y, text, w=64):
        cap = Image.new('L', (w * sc, 60 * sc), 0)
        c = ImageDraw.Draw(cap)
        c.rounded_rectangle((0, 0, w * sc - 1, 60 * sc - 1), radius=10 * sc, fill=255)
        f = symbol_font(30 * sc) if text in '↑←↓→' else fk if len(text) < 3 else fs
        c.text((w * sc / 2, 30 * sc), text, font=f, fill=0, anchor='mm')  # legend cut out
        im.paste(Image.new('RGBA', cap.size, STENCIL), (int(x * sc), int(y * sc)), cap)

    def caption_width(title, letter=None, sub=None):
        w = fl.getlength(title) / sc + (2 * R + GAP if letter else 0)
        return max(w, fs.getlength(sub) / sc if sub else 0)

    def caption(x, cy, title, letter=None, sub=None):
        ty = cy - 14 if sub else cy
        x0 = x
        if letter:
            badge(im, d, *s(x + R, ty), R * sc, letter, fb)
            x += 2 * R + GAP
        label(d, s(x, ty), title, 'lm', fl)
        if sub:
            label(d, s(x0, cy + 18), sub, 'lm', fs, MUTED)

    # Rows 2 and 3: (key, key width, job, badge, bracketed note). The top row is WASD "or" the arrow keys (one
    # Move item over the first two columns), then Esc and F11 stacked in the last column.
    side = [('Esc', 'Menu'), ('F11', 'Fullscreen')]
    rows = [
        [('J', 64, 'Attack 1 / Confirm', 'A', None), ('K', 64, 'Attack 2 / Cancel', 'B', None),
         ('L', 64, 'Switch', 'X', None)],
        [('Enter', 110, 'Pause', '+', None), ('Backspace', 150, 'Favourite', '−', '(single player)'),
         ('Space', 160, 'Fast forward', None, '(hold)')],
    ]
    widths = [[kw + PAD + caption_width(t, l, n) for _, kw, t, l, n in row] for row in rows]
    cols = [max(r[i] for r in widths) for i in range(3)]
    cols[2] = max(cols[2], 90 + PAD + max(caption_width(c) for _, c in side))
    gap_x = (W - sum(cols)) / 2
    xs = [0, cols[0] + gap_x, cols[0] + cols[1] + 2 * gap_x]
    heights = [126, 60, 60]
    gap_y = (H - sum(heights)) / 4
    y = gap_y

    def cluster(x, keys):  # one key above the middle of three
        key(x + 66, y, keys[0], w=60)
        for i, k in enumerate(keys[1:]):
            key(x + i * 66, y + 66, k, w=60)

    OR = 64  # room for the word "or" between the two clusters
    cluster(0, 'WASD')
    label(d, s(192 + OR / 2, y + 96), 'or', 'mm', fs, MUTED)
    cluster(192 + OR, '↑←↓→')
    caption(2 * 192 + OR + PAD, y + 96, 'Move')
    assert 2 * 192 + OR + PAD + caption_width('Move') < xs[2], 'Move group runs into the last column'
    for i, (kk, tt) in enumerate(side):
        key(xs[2], y + i * 66, kk, w=90)
        caption(xs[2] + 90 + PAD, y + i * 66 + 30, tt)
    y += heights[0] + gap_y
    for row, h in zip(rows, heights[1:]):
        for x, (k, kw, title, letter, sub) in zip(xs, row):
            key(x, y + (h - 60) / 2, k, w=kw)
            caption(x + kw + PAD, y + h / 2, title, letter, sub)
        y += h + gap_y
    im.resize((560, 560 * H // W), Image.LANCZOS).save(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, (top, shine) in COLOURS.items():
        closed, opened = tab_capsules(name)
        closed.save(os.path.join(OUT, f'capsule_{name}.png'))
        opened.save(os.path.join(OUT, f'capsule_{name}_open.png'))
    controller(os.path.join(OUT, 'controller.png'))
    keyboard(os.path.join(OUT, 'keyboard.png'))
    print('art written to', OUT)


if __name__ == '__main__':
    main()
