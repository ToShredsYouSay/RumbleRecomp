#!/usr/bin/env python3
"""RumbleRecomp launcher (beta): pick the game version, randomizer, and screen shape, then play.

Players join by pressing a button: the keyboard always controls Player 1; the first controller
you press a button on also controls Player 1, the next one becomes Player 2, and so on (up to 4).
Controllers can join mid-game. Settings are remembered in build/launcher.json.
Run: double-click tools/launcher.pyw (or: pythonw tools/launcher.pyw)."""
import configparser, glob, json, os, queue, re, shutil, subprocess, sys, threading, tkinter as tk, webbrowser
from tkinter import ttk, messagebox, filedialog, font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rr_compile
import zipfile
import rr_setup

# Built as RumbleRecomp.exe (tools/build_launcher_exe.ps1) the exe sits in the repo root.
ROOT = (os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.join(ROOT, 'build')


def ttf_family(path):
    """The font's family name as Windows sees it (name table, ID 1, Windows platform)."""
    import struct
    data = open(path, 'rb').read()
    for i in range(struct.unpack('>H', data[4:6])[0]):
        tag, _, offset, _ = struct.unpack('>4sIII', data[12 + 16 * i:28 + 16 * i])
        if tag == b'name':
            _, count, strings = struct.unpack('>HHH', data[offset:offset + 6])
            for j in range(count):
                plat, _, _, name_id, length, start = struct.unpack('>6H', data[offset + 6 + 12 * j:offset + 18 + 12 * j])
                if plat == 3 and name_id == 1:
                    pos = offset + strings + start
                    return data[pos:pos + length].decode('utf-16-be')
    return None


def load_ui_font():
    """Registers the bundled Nunito (tools/fonts, SIL Open Font License) for this process only, so nothing is
    installed; returns its family name, or Segoe UI if that fails."""
    try:
        import ctypes
        folder = os.path.join(ROOT, 'tools', 'fonts')
        family = None
        for weight in ('Regular', 'SemiBold', 'Bold', 'ExtraBold'):
            path = os.path.join(folder, f'Nunito-{weight}.ttf')
            if ctypes.windll.gdi32.AddFontResourceExW(path, 0x10, 0):  # FR_PRIVATE
                family = family or ttf_family(path)
        return family or 'Segoe UI'
    except (OSError, AttributeError, ValueError):
        return 'Segoe UI'


UI_FONT = load_ui_font()
VERSION = '0.7.1'
DATA = rr_setup.default_data_dir()
WEEKEND_URL = 'https://projectpokemon.org/home/files/file/4256-pokemon-rumble-weekend-edition/'
PATCH1_URL = 'https://projectpokemon.org/home/files/file/5855-unofficial-weekend-edition-v150patch1/'
# Release layout (tools/make_release.py): the game program is in runtime/, and everything of the player's
# (saves, settings, logs, built modules) lives in data/. Developer layout: build/bin, build/userdir.
GAME_EXE = 'RumbleRecomp-game.exe'  # the game program's name in releases (moderngekko-run.exe in the dev tree)
RELEASE = os.path.isfile(os.path.join(ROOT, 'runtime', GAME_EXE))
RUNTIME = os.path.join(ROOT, 'runtime') if RELEASE else os.path.join(BUILD, 'bin')
STATE = DATA if RELEASE else BUILD
USER = os.path.join(DATA, 'user') if RELEASE else os.path.join(BUILD, 'userdir')
SETTINGS = os.path.join(STATE, 'launcher.json')
GAMES = {  # 'dev_wad': the developer layout used before first-run setup existed (still honoured)
    'Vanilla': dict(profile='vanilla', build='vanilla',
                     dev_wad=next(iter(sorted(glob.glob(os.path.join(ROOT, 'original', '*.wad')))), ''),
                     root='vanilla', module='gWPSE01_recomp.dll', randomizer=0),
    'Weekend Edition 1.5': dict(profile='weekend', build='weekend',
                                dev_wad=os.path.join(ROOT, 'patches', 'out', 'weekend15.wad'),
                                root='weekend', module='gWPSE01_weekend_recomp.dll', randomizer=556),
    'Weekend Edition 1.5 + PATCH1': dict(profile='weekend_patch1', build='weekend',
                                         dev_wad=os.path.join(ROOT, 'patches', 'out', 'weekend15_patch1.wad'),
                                         root='weekend', module='gWPSE01_weekend_recomp.dll', randomizer=559),
}


def game_files(game):
    """(wad, gameroot, module or None) if the game files are set up, else None. Prefers the first-run
    setup and modules built on this PC (data/), then the developer layout (build/)."""
    g = GAMES[game]
    prof = rr_setup.load_state(DATA)['profiles'].get(g['profile'])
    if prof:
        wad, root = os.path.join(DATA, prof['wad']), os.path.join(DATA, 'gameroot', prof['gameroot'])
    else:
        wad, root = g['dev_wad'], os.path.join(BUILD, 'gameroot', g['root'])
    if not (os.path.exists(wad) and os.path.exists(root)):
        return None
    module = next((m for m in (rr_compile.module_path(g['build'], DATA), os.path.join(BUILD, 'bin', g['module']))
                   if os.path.isfile(m)), None)
    return wad, root, module


def game_paths(game):
    """(wad, gameroot, module) if the game is ready to play, else None."""
    files = game_files(game)
    return files if files and files[2] else None
SCREENS = {  # GFX.ini values: AspectRatio, custom W, custom H, widescreen hack. The first is the default.
    'Fit to window': ('3', '1', '1', 'True'),
    '16:9 (original)': ('0', '1', '1', 'False'),
    '21:9 ultrawide': ('4', '21', '9', 'True'),
    '32:9 super-ultrawide': ('4', '32', '9', 'True'),
}

KB = 'DInput/0/Keyboard Mouse:'
# Player 1 is a Wii Remote with a Classic Controller plugged in: keyboard (always) + whichever controller joins
# as Player 1. Outside the multiplayer screen the game only reads Player 1 from a Wii Remote (a GameCube pad on
# port 1 is ignored, even from a cold boot; see GCPAD1 for multiplayer), and the Classic's analogue stick gives full 360 degree movement where the Wii Remote's d-pad only
# has 8 directions. With the Classic attached the game ignores the Wii Remote's own buttons, so everything is
# bound on the Classic. Same physical buttons, same jobs as before: a attacks 1 and confirms, b attacks 2 and
# cancels, x (or y) opens the team list, + pauses, - toggles favourite.
WIIMOTE1 = {
    'Extension': 'Classic',
    'Classic/Buttons/A': f'`{KB}J` | `Button S`',  # Space is fast forward (game window), not bound here
    'Classic/Buttons/B': f'`{KB}K` | `Button W`',
    'Classic/Buttons/X': f'`{KB}L` | `Button E` | `Shoulder R`',
    'Classic/Buttons/+': f'`{KB}RETURN` | `Start`',
    'Classic/Buttons/-': f'`{KB}BACK` | `Back`',
    'Classic/Buttons/Home': '',  # unbound: the game's HOME Menu would try to leave for the Wii System Menu
    'Classic/D-Pad/Up': f'`{KB}W` | `{KB}UP` | `Pad N`',
    'Classic/D-Pad/Down': f'`{KB}S` | `{KB}DOWN` | `Pad S`',
    'Classic/D-Pad/Left': f'`{KB}A` | `{KB}LEFT` | `Pad W`',
    'Classic/D-Pad/Right': f'`{KB}D` | `{KB}RIGHT` | `Pad E`',
    'Classic/Left Stick/Up': '`Left Y+`',
    'Classic/Left Stick/Down': '`Left Y-`',
    'Classic/Left Stick/Left': '`Left X-`',
    'Classic/Left Stick/Right': '`Left X+`',
    'Buttons/Home': '',
    # The opening screens (How to Hold the Wii Remote, How to access GX rank) only skip on the Wii Remote's own
    # buttons, so confirm also presses 2. Same job as the Classic's a; pause and favourite stay Classic-only,
    # since pressing a toggle on both at once could count twice.
    'Buttons/2': f'`{KB}J` | `Button S`',
    'Rumble/Motor': '`Motor L` | `Motor R`',  # the game rumbles the Wii Remote, not the Classic
    'Options/Sideways Wiimote': 'True',
}
GCPAD = {  # Players 2-4 (GameCube pad ports 2-4, what the game's local multiplayer reads)
    'Buttons/A': '`Button S`', 'Buttons/B': '`Button W`', 'Buttons/X': '`Button E` | `Shoulder R`',
    'Buttons/Y': '`Button N`', 'Buttons/Z': '', 'Buttons/Start': '`Start`',
    'Main Stick/Up': '`Left Y+`', 'Main Stick/Down': '`Left Y-`', 'Main Stick/Left': '`Left X-`',
    'Main Stick/Right': '`Left X+`', 'D-Pad/Up': '`Pad N`', 'D-Pad/Down': '`Pad S`', 'D-Pad/Left': '`Pad W`',
    'D-Pad/Right': '`Pad E`', 'Triggers/L': '', 'Triggers/R': '',  # R1 is Switch (X), as in single player
    'Rumble/Motor': '`Motor L` | `Motor R`',
}
# Player 1 is also GameCube pad port 1: the multiplayer join screen only reads GameCube pads (it ignores the Wii
# Remote when four are plugged in), while single player only reads the Wii Remote. Same keys and buttons on both.
GCPAD1 = dict(GCPAD, **{
    'Buttons/A': f'`{KB}J` | `Button S`', 'Buttons/B': f'`{KB}K` | `Button W`',
    'Buttons/X': f'`{KB}L` | `Button E` | `Shoulder R`', 'Buttons/Start': f'`{KB}RETURN` | `Start`',
    'Main Stick/Up': f'`{KB}W` | `{KB}UP` | `Left Y+`', 'Main Stick/Down': f'`{KB}S` | `{KB}DOWN` | `Left Y-`',
    'Main Stick/Left': f'`{KB}A` | `{KB}LEFT` | `Left X-`', 'Main Stick/Right': f'`{KB}D` | `{KB}RIGHT` | `Left X+`',
})


def ini_update(path, section_values, drop_sections=()):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if os.path.exists(path):
        cp.read(path, encoding='utf-8')
    for sec in drop_sections:
        cp.remove_section(sec)
    for sec, values in section_values.items():
        if not cp.has_section(sec):
            cp.add_section(sec)
        for k, v in values.items():
            cp.set(sec, k, v)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        cp.write(f, space_around_delimiters=True)


def write_config(screen, hd=False):
    cfg = os.path.join(USER, 'Config')
    ini_update(os.path.join(cfg, 'WiimoteNew.ini'), {'Wiimote1': dict(WIIMOTE1, Device='')},
               drop_sections=('Wiimote1', 'Wiimote2', 'Wiimote3', 'Wiimote4'))
    ini_update(os.path.join(cfg, 'Wiimote.ini'), {'Wiimote1': {'Source': '1'}, 'Wiimote2': {'Source': '0'},
                                                  'Wiimote3': {'Source': '0'}, 'Wiimote4': {'Source': '0'}})
    ini_update(os.path.join(cfg, 'GCPadNew.ini'),
               {f'GCPad{i}': dict(GCPAD1 if i == 1 else GCPAD, Device='') for i in (1, 2, 3, 4)},
               drop_sections=('GCPad1', 'GCPad2', 'GCPad3', 'GCPad4'))
    ini_update(os.path.join(cfg, 'Dolphin.ini'), {'Core': {'SIDevice0': '6', 'SIDevice1': '6', 'SIDevice2': '6',
                                                           'SIDevice3': '6', 'CPUThread': 'True'}})
    ar, w, h, hack = SCREENS[screen]
    ini_update(os.path.join(cfg, 'GFX.ini'), {'Settings': {'AspectRatio': ar, 'CustomAspectRatioWidth': w,
                                                           'CustomAspectRatioHeight': h, 'wideScreenHack': hack,
                                                           'wideScreenHackHUDFix': 'True',
                                                           'HiresTextures': 'True' if hd else 'False'}})
    os.makedirs(os.path.join(USER, 'GameSettings'), exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'config', 'GameSettings', 'WPSE01.ini'),
                os.path.join(USER, 'GameSettings', 'WPSE01.ini'))


def launch(game, randomizer, screen, hd=False, record=False):
    g = GAMES[game]
    paths = game_paths(game)
    running = subprocess.run(['tasklist', '/NH'], capture_output=True,
                             text=True, creationflags=0x08000000).stdout
    if GAME_EXE.lower() in running.lower() or 'moderngekko-run.exe' in running.lower():
        messagebox.showerror('RumbleRecomp', 'The game is already running. Close it first.')
        return False
    if not paths:
        messagebox.showerror('RumbleRecomp', f'{game} is not set up yet. Use "Game files..." first.')
        return False
    wad, gameroot, module = paths
    write_config(screen, hd)
    env = dict(os.environ, MODERNGEKKO_BOOT_FILE=wad, RR_PRESS_TO_JOIN='1', MODERNGEKKO_NO_MENU='1',
               RUMBLE_RANDOMIZER=str(g['randomizer'] if randomizer else 0),
               RR_MENU_COLOUR=TABS[game]['colour'],  # the in-game menu (HOME or Esc) matches the tab
               RR_MENU_SLOTS=g['profile'],  # its save slots, one folder per version
               RR_FONT_DIR=os.path.join(ROOT, 'tools', 'fonts'))  # the menu uses the launcher's Nunito
    if record:  # save every texture the game draws (Dump/Textures/WPSE01), for people making texture packs
        env['MODERNGEKKO_DUMP_TEXTURES'] = '1'
    auto = os.path.join(STATE, 'auto')
    for d in ('commands', 'processed', 'failed'):
        os.makedirs(os.path.join(auto, d), exist_ok=True)
    subprocess.Popen([os.path.join(RUNTIME, GAME_EXE if RELEASE else 'moderngekko-run.exe'),
                      '--game', gameroot,
                      '--module', module,
                      '--user-dir', USER, '--no-mods', '--graphics', 'Vulkan', '--automation-dir', auto,
                      '--title', f'RumbleRecomp Beta {VERSION}'],
                     env=env, cwd=ROOT, stdout=open(os.path.join(STATE, 'play.log'), 'w'),
                     stderr=subprocess.STDOUT, creationflags=0x08000000)
    return True


def open_setup(parent, on_done):
    """'Game files' window: the player's original WAD (required) and, optionally, their own copies of
    the Weekend Edition 1.5 patch (.bps) and PATCH1 (.xdelta). Builds everything into data/."""
    win = tk.Toplevel(parent, bg=PANEL)
    win.title('Game files')
    win.resizable(False, False)
    win.transient(parent)
    frm = ttk.Frame(win, padding=16)
    frm.grid()
    ttk.Label(frm, justify='left', wraplength=520, text=(
        'RumbleRecomp needs your own copy of the original game: the USA WiiWare release as a .wad file. '
        'Weekend Edition is optional: download its patch files yourself from the Weekend Edition release '
        "page (and PATCH1 from its own page). They're applied to your original game file here; nothing is "
        'downloaded or shared by RumbleRecomp.')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 12))
    rows = [('Original game (.wad)', [('WAD files', '*.wad')]),
            ('Weekend Edition 1.5 patch (.bps, optional)', [('BPS patches', '*.bps')]),
            ('PATCH1 (.xdelta, optional)', [('xdelta patches', '*.xdelta')])]
    paths, notes = [], []
    for i, (label, types) in enumerate(rows):
        r = 1 + i * 2
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky='w', padx=(0, 10))
        var = tk.StringVar()
        ttk.Entry(frm, textvariable=var, width=52).grid(row=r, column=1, sticky='w')
        note = ttk.Label(frm, foreground=MUTED, wraplength=520, justify='left')
        note.grid(row=r + 1, column=0, columnspan=3, sticky='w', pady=(2, 8))

        def browse(var=var, types=types, i=i):
            path = filedialog.askopenfilename(parent=win, filetypes=types + [('All files', '*.*')])
            if path:
                var.set(os.path.normpath(path))
                if i == 0:
                    ok, msg = rr_setup.check_vanilla_wad(var.get())
                    notes[0].configure(text=('✔ ' if ok else '✘ ') + msg,
                                       foreground='#7ee2a0' if ok else '#ff8a80')
        ttk.Button(frm, text='Browse...', command=browse).grid(row=r, column=2, padx=(8, 0))
        paths.append(var)
        notes.append(note)
    status = ttk.Label(frm, text='', wraplength=520, justify='left')
    status.grid(row=8, column=0, columnspan=3, sticky='w', pady=(4, 0))
    go = ttk.Button(frm, text='Set up')
    go.grid(row=9, column=0, columnspan=3, pady=(12, 0), ipadx=24)

    def run():
        wad, bps, x = (p.get().strip() or None for p in paths)
        if not wad:
            status.configure(text='Choose your original game file first.', foreground='#ff8a80')
            return
        go.state(['disabled'])
        # The worker only posts messages; the window reads them on its own thread (Tk is not thread-safe).
        msgs = queue.Queue()

        def work():
            try:
                rr_setup.setup(wad, bps, x, DATA, progress=lambda m: msgs.put(('progress', m)))
                msgs.put(('done', None))
            except rr_setup.SetupError as e:
                msgs.put(('error', str(e)))
            except Exception as e:  # unexpected: show it rather than fail silently
                msgs.put(('error', f'{type(e).__name__}: {e}'))

        def poll():
            while not msgs.empty():
                kind, text = msgs.get()
                if kind == 'progress':
                    status.configure(text=text, foreground=FG)
                elif kind == 'error':
                    status.configure(text='✘ ' + text, foreground='#ff8a80')
                    go.state(['!disabled'])
                    return
                else:
                    on_done()
                    win.destroy()
                    return
            win.after(100, poll)
        threading.Thread(target=work, daemon=True).start()
        poll()
    go.configure(command=run)
    win.grab_set()


def open_build(parent, profiles, on_done):
    """Build the given modules (rr_compile) with a progress bar. One-off per version, ~20-40 min."""
    win = tk.Toplevel(parent, bg=PANEL)
    win.title('Building')
    win.resizable(False, False)
    win.transient(parent)
    frm = ttk.Frame(win, padding=16)
    frm.grid()
    ttk.Label(frm, justify='left', wraplength=460, text=(
        'Building the game for your PC from your own game files. This happens once per version and takes '
        'about 20-40 minutes; your PC will be busy meanwhile. You can leave this window open and come back.')
              ).grid(row=0, column=0, sticky='w', pady=(0, 12))
    title = ttk.Label(frm, font=(UI_FONT, 10, 'bold'))
    title.grid(row=1, column=0, sticky='w')
    bar = ttk.Progressbar(frm, length=460, maximum=1000)
    bar.grid(row=2, column=0, pady=(6, 4))
    status = ttk.Label(frm, wraplength=460, justify='left')
    status.grid(row=3, column=0, sticky='w')
    msgs = queue.Queue()
    names = {'vanilla': 'Vanilla', 'weekend': 'Weekend Edition (covers PATCH1 too)'}

    def work():
        for n, p in enumerate(profiles):
            msgs.put(('title', f'{names[p]}  ({n + 1} of {len(profiles)})'))
            try:
                rr_compile.build(p, DATA, progress=lambda f, t: msgs.put(('progress', (f, t))))
            except (rr_compile.CompileError, rr_setup.SetupError) as e:
                msgs.put(('error', str(e)))
                return
            except Exception as e:
                msgs.put(('error', f'{type(e).__name__}: {e}'))
                return
        msgs.put(('done', None))

    def poll():
        while not msgs.empty():
            kind, val = msgs.get()
            if kind == 'title':
                title.configure(text=val)
            elif kind == 'progress':
                bar['value'] = int(val[0] * 1000)
                status.configure(text=val[1], foreground=FG)
            elif kind == 'error':
                status.configure(text='✘ ' + val, foreground='#ff8a80')
                win.protocol('WM_DELETE_WINDOW', win.destroy)
                on_done()
                return
            else:
                on_done()
                win.destroy()
                return
        win.after(200, poll)

    # Closing mid-build would leave the compiler running in the background; ask first.
    win.protocol('WM_DELETE_WINDOW', lambda: messagebox.showinfo(
        'Building', 'Please wait for the build to finish.', parent=win))
    threading.Thread(target=work, daemon=True).start()
    poll()
    win.grab_set()


def run_cli(argv):
    """Command-line use (also for automated release tests), same steps as the buttons:
      RumbleRecomp.exe --setup <original.wad> [<weekend .bps> [<PATCH1 .xdelta>]]
      RumbleRecomp.exe --build vanilla|weekend
    The exe has no console, so output goes to data/cli.log; the exit code is 0 on success."""
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, 'cli.log'), 'a', encoding='utf-8') as log:
        say = lambda *a: (log.write(' '.join(str(x) for x in a) + '\n'), log.flush())
        try:
            if argv[0] == '--setup':
                files = (argv[1:] + [None, None, None])[:3]
                rr_setup.setup(files[0], files[1], files[2], DATA, progress=say)
            elif argv[0] == '--build':
                rr_compile.build(argv[1], DATA, progress=lambda f, t: say(f'{f:5.1%} {t}'))
            else:
                say('unknown option', argv[0])
                return 2
        except (rr_setup.SetupError, rr_compile.CompileError) as e:
            say('FAILED:', e)
            return 1
    return 0


ART = os.path.join(ROOT, 'tools', 'launcher_art')
# Version tabs, colour-coded green / red / blue (balls drawn by tools/make_launcher_art.py). The selected tab
# tints most of the window: bg = window body, panel = the version panel, hex/light = accents and Play button.
TABS = {
    'Vanilla': dict(colour='green', bg='#10251a', panel='#173623', hex='#1f8a45', light='#2fa85a',
                    blurb='The original game, as released on WiiWare.', links=[]),
    'Weekend Edition 1.5': dict(colour='red', bg='#2a1012', panel='#3e181b', hex='#c42626', light='#e0483f',
                                blurb='A fan mod by [WindyPrairie](https://projectpokemon.org/home/profile/101169-windyprairie/), made for '
                                      'the Rumble Weekend shiny hunting event. It adds the second and third generations '
                                      'and their shinies in a new GX terminal, removes the fog from every stage, and '
                                      'fills the collection to all 493. The original game stays intact and saves carry '
                                      'over. Download the patch yourself and add it under "Game files".',
                                links=[('Get Weekend Edition 1.5', WEEKEND_URL)]),
    'Weekend Edition 1.5 + PATCH1': dict(colour='blue', bg='#0f1a33', panel='#172a50', hex='#1e56c4',
                                         light='#3f78e6',
                                         blurb='Weekend Edition 1.5 plus an unofficial fix-up by '
                                               '[eman_not_ava](https://projectpokemon.org/home/profile/88062-eman_not_ava/). Bosses no longer '
                                               'die instantly when the randomizer turns them into something never meant '
                                               'to be a boss, the new wild ones use proper moves instead of Struggle, '
                                               'eggs can appear without crashing, names use normal capitals, and '
                                               'Arceus, Castform, and Rotom forms get their proper types. Needs both '
                                               'downloads, added under "Game files".',
                                         links=[('Get Weekend Edition 1.5', WEEKEND_URL), ('Get PATCH1', PATCH1_URL)]),
}
# neutral chrome: title bar and the Game files / Building windows
BG, PANEL, EDGE = '#1b1c20', '#24262c', '#5a5f6b'
FG, MUTED = '#f2f3f5', '#aab0bc'


def flat_button(parent, text, command, bg='#33363e', hover='#454953', fg=FG, font=(UI_FONT, 10, 'bold'),
                padx=14, pady=6, width=0):
    """A label that behaves like a button (fits the dark theme better than ttk buttons). width is in characters
    (0 fits the text)."""
    b = tk.Label(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor='hand2', width=width)
    b.bind('<Button-1>', lambda e: command())
    b.bind('<Enter>', lambda e: b.configure(bg=hover))
    b.bind('<Leave>', lambda e: b.configure(bg=bg))
    return b


class Check(tk.Frame):
    """A checkbox drawn by the launcher: an outlined box when off, filled with the accent colour and a white
    tick when on. (Windows draws Tk's own checkbox tick itself, which gets lost on the dark theme.)"""
    SIZE = 18

    def __init__(self, parent, text, variable, bg, accent, font=(UI_FONT, 11)):
        super().__init__(parent, bg=bg, cursor='hand2')
        self.var, self.accent, self.enabled = variable, accent, True
        self.box = tk.Canvas(self, width=self.SIZE, height=self.SIZE, bg=bg, highlightthickness=0)
        self.box.pack(side='left', padx=(0, 8))
        self.label = tk.Label(self, text=text, bg=bg, fg=FG, font=font)
        self.label.pack(side='left')
        for w in (self, self.box, self.label):
            w.bind('<Button-1>', self.toggle)
        variable.trace_add('write', lambda *_: self.draw())
        self.draw()

    def toggle(self, _event=None):
        if self.enabled:
            self.var.set(not self.var.get())

    def draw(self):
        c, s = self.box, self.SIZE
        c.delete('all')
        on = bool(self.var.get()) and self.enabled
        edge = self.accent if on else (MUTED if self.enabled else '#5c6170')
        c.create_rectangle(1, 1, s - 2, s - 2, outline=edge, width=2, fill=self.accent if on else '')
        if on:
            c.create_line(4, s // 2, s // 2 - 1, s - 5, s - 4, 4, fill='white', width=2.5, capstyle='round',
                          joinstyle='round')

    def set_theme(self, bg, accent):
        self.accent = accent
        for w in (self, self.box, self.label):
            w.configure(bg=bg)
        self.draw()

    def configure(self, cnf=None, **kw):
        if 'state' in kw:
            self.enabled = kw.pop('state') != 'disabled'
            self.label.configure(fg=FG if self.enabled else '#7c8190')
            self.configure(cursor='hand2' if self.enabled else '')
            self.draw()
        if 'text' in kw:
            self.label.configure(text=kw.pop('text'))
        if kw or cnf:
            super().configure(cnf, **kw)

    config = configure


LINK_WIDTH = 2 + max(len(label) for tab in TABS.values() for label, _ in tab['links'])  # download buttons


def set_blurb(text, blurb):
    """Shows a tab description; "[name](url)" parts become underlined links in the same colour."""
    text.configure(state='normal')
    text.delete('1.0', 'end')
    pos = 0
    for n, m in enumerate(re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', blurb)):
        text.insert('end', blurb[pos:m.start()])
        tag = f'link{n}'
        text.insert('end', m.group(1), tag)
        text.tag_configure(tag, underline=True)
        text.tag_bind(tag, '<Button-1>', lambda e, u=m.group(2): webbrowser.open(u))
        text.tag_bind(tag, '<Enter>', lambda e: text.configure(cursor='hand2'))
        text.tag_bind(tag, '<Leave>', lambda e: text.configure(cursor='arrow'))
        pos = m.end()
    text.insert('end', blurb[pos:])
    text.configure(state='disabled')


TEXTURE_FILES = ('.png', '.dds')


def texture_dir():
    """Where Dolphin looks for custom textures for this game (subfolders included)."""
    return os.path.join(USER, 'Load', 'Textures', 'WPSE01')


def installed_packs():
    """[(pack name, number of texture files)]: one entry per subfolder, plus loose files if any."""
    root = texture_dir()
    if not os.path.isdir(root):
        return []
    count = lambda d: sum(f.lower().endswith(TEXTURE_FILES) for _, _, fs in os.walk(d) for f in fs)
    packs = [(n, count(os.path.join(root, n))) for n in sorted(os.listdir(root))
             if os.path.isdir(os.path.join(root, n))]
    loose = sum(f.lower().endswith(TEXTURE_FILES) for f in os.listdir(root))
    return packs + ([('(loose files)', loose)] if loose else [])


def has_textures():
    return any(n for _, n in installed_packs())


def add_pack(src):
    """Copy a texture pack (a folder or a .zip) into its own subfolder. Returns (name, files copied)."""
    src = src.rstrip('/\\')
    name = os.path.splitext(os.path.basename(src))[0] or 'pack'
    if name.upper() == 'WPSE01':  # a pack folder named after the game ID: use its parent folder's name
        name = os.path.basename(os.path.dirname(src)) or name
    dest = os.path.join(texture_dir(), name)
    if os.path.exists(dest):
        raise ValueError(f'A pack called "{name}" is already installed. Remove it first to replace it.')
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            members = [(m, m.filename) for m in z.infolist()
                       if not m.is_dir() and m.filename.lower().endswith(TEXTURE_FILES)]
            files = [(lambda m=m: z.read(m), rel) for m, rel in members]
            copied = _copy_pack(files, dest)
    elif os.path.isdir(src):
        files = []
        for d, _, fs in os.walk(src):
            for f in fs:
                if f.lower().endswith(TEXTURE_FILES):
                    full = os.path.join(d, f)
                    files.append((lambda full=full: open(full, 'rb').read(), os.path.relpath(full, src)))
        copied = _copy_pack(files, dest)
    else:
        raise ValueError('Choose a folder or a .zip file.')
    if not copied:
        shutil.rmtree(dest, ignore_errors=True)
        raise ValueError('No textures (.png or .dds files) found in that pack.')
    return name, copied


def _copy_pack(files, dest):
    """Write the pack's files, dropping a leading WPSE01 folder (a common way packs are zipped)."""
    n = 0
    for read, rel in files:
        parts = [p for p in rel.replace('\\', '/').split('/') if p]
        if len(parts) > 1 and parts[0].upper() == 'WPSE01':
            parts = parts[1:]
        if any(p == '..' for p in parts):
            continue  # never write outside the pack folder
        out = os.path.join(dest, *parts)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'wb') as f:
            f.write(read())
        n += 1
    return n


def open_textures(parent, record, on_done):
    """Texture packs: install packs made by others (folder or .zip), remove them, record textures for making one."""
    win = tk.Toplevel(parent, bg=PANEL)
    win.title('Texture packs')
    win.resizable(False, False)
    win.transient(parent)
    frm = ttk.Frame(win, padding=16)
    frm.grid()
    ttk.Label(frm, justify='left', wraplength=520, text=(
        'Install texture packs made for this game: a folder or a .zip of Dolphin custom textures for game '
        'ID WPSE01. Turn them on with "Custom textures" next to PLAY. Packs work for Vanilla and Weekend.')
              ).grid(row=0, column=0, columnspan=4, sticky='w')
    packs = tk.Listbox(frm, height=6, width=60, bg=BG, fg=FG, selectbackground='#454953', selectforeground=FG,
                       highlightthickness=1, highlightbackground=EDGE, borderwidth=0, font=(UI_FONT, 10))
    packs.grid(row=1, column=0, columnspan=4, sticky='we', pady=(12, 6))
    note = ttk.Label(frm, foreground=MUTED, wraplength=520, justify='left')
    note.grid(row=2, column=0, columnspan=4, sticky='w')

    def refresh():
        packs.delete(0, 'end')
        items = installed_packs()
        for name, n in items:
            packs.insert('end', f'{name}    ({n} textures)')
        if not items:
            packs.insert('end', 'No texture packs installed.')
        on_done()

    def add(kind):
        if kind == 'zip':
            src = filedialog.askopenfilename(parent=win, filetypes=[('Zip files', '*.zip'), ('All files', '*.*')])
        else:
            src = filedialog.askdirectory(parent=win)
        if not src:
            return
        try:
            name, n = add_pack(os.path.normpath(src))
            note.configure(text=f'✔ Installed "{name}" ({n} textures).', foreground='#7ee2a0')
        except Exception as e:
            note.configure(text='✘ ' + str(e), foreground='#ff8a80')
        refresh()

    def remove():
        sel = packs.curselection()
        items = installed_packs()
        if not sel or sel[0] >= len(items):
            return
        name = items[sel[0]][0]
        if not messagebox.askyesno('Texture packs', f'Remove "{name}"?', parent=win):
            return
        root = texture_dir()
        if name == '(loose files)':
            for f in os.listdir(root):
                if f.lower().endswith(TEXTURE_FILES):
                    os.remove(os.path.join(root, f))
        else:
            shutil.rmtree(os.path.join(root, name), ignore_errors=True)
        note.configure(text=f'Removed "{name}".', foreground=MUTED)
        refresh()

    def open_dir(path):
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    ttk.Button(frm, text='Add folder…', command=lambda: add('dir')).grid(row=3, column=0, sticky='w', pady=(8, 0))
    ttk.Button(frm, text='Add .zip…', command=lambda: add('zip')).grid(row=3, column=1, sticky='w', padx=(8, 0),
                                                                      pady=(8, 0))
    ttk.Button(frm, text='Remove', command=remove).grid(row=3, column=2, sticky='w', padx=(8, 0), pady=(8, 0))
    ttk.Button(frm, text='Open textures folder', command=lambda: open_dir(texture_dir())).grid(
        row=3, column=3, sticky='e', pady=(8, 0))
    ttk.Label(frm, text='MAKING A PACK', foreground=MUTED, font=(UI_FONT, 9, 'bold')).grid(
        row=4, column=0, columnspan=4, sticky='w', pady=(16, 0))
    Check(frm, 'Record textures while playing (saves every texture the game shows)', record, PANEL, '#3f78e6',
          font=(UI_FONT, 10)).grid(row=5, column=0, columnspan=4, sticky='w', pady=(4, 0))
    ttk.Button(frm, text='Open recorded textures',
               command=lambda: open_dir(os.path.join(USER, 'Dump', 'Textures', 'WPSE01'))).grid(
        row=6, column=0, columnspan=2, sticky='w', pady=(6, 0))
    refresh()
    win.grab_set()


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith('--'):
        sys.exit(run_cli(sys.argv[1:]))
    try:
        saved = json.load(open(SETTINGS))
    except Exception:
        saved = {}
    root = tk.Tk()
    for named in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont', 'TkCaptionFont', 'TkTooltipFont'):
        tkfont.nametofont(named).configure(family=UI_FONT)
    root.title(f'RumbleRecomp Beta {VERSION}')
    root.resizable(False, False)
    root.configure(bg=BG)
    icon = os.path.join(ROOT, 'tools', 'launcher.ico')
    if os.path.isfile(icon):
        root.iconbitmap(default=icon)  # also used by the Game files window
    style = ttk.Style(root)
    style.theme_use('clam')
    # neutral defaults (Game files and Building windows)
    style.configure('.', background=PANEL, foreground=FG, fieldbackground=BG, bordercolor=EDGE,
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=BG, font=(UI_FONT, 10))
    style.configure('TButton', background='#33363e', foreground=FG, padding=(12, 5), borderwidth=0)
    style.map('TButton', background=[('active', '#454953'), ('disabled', '#2a2c32')],
              foreground=[('disabled', '#6b707c')])
    style.configure('TEntry', fieldbackground=BG, foreground=FG, insertcolor=FG)
    style.configure('Horizontal.TProgressbar', background='#3f78e6', troughcolor=BG, bordercolor=EDGE)
    root.option_add('*TCombobox*Listbox.foreground', FG)
    img = {n: tk.PhotoImage(file=os.path.join(ART, f'{n}.png')) for n in
           [f'capsule_{c}{k}' for c in ('green', 'red', 'blue') for k in ('', '_open')] + ['controller', 'keyboard']}

    game = tk.StringVar(value=saved.get('game') if saved.get('game') in GAMES else list(GAMES)[0])
    rand = tk.BooleanVar(value=saved.get('randomizer', False))
    hd = tk.BooleanVar(value=saved.get('hd', False))
    record = tk.BooleanVar(value=saved.get('record', False))
    screen = tk.StringVar(value=saved.get('screen') if saved.get('screen') in SCREENS else list(SCREENS)[0])
    tinted = {'bg': [], 'panel': []}  # widgets recoloured when the tab changes

    def tint(widget, role):
        tinted[role].append(widget)
        return widget

    # neutral title bar
    head = tk.Frame(root, bg=BG)
    head.pack(fill='x')
    tk.Label(head, text='RumbleRecomp', bg=BG, fg=FG, font=(UI_FONT, 22, 'bold')).pack(side='left',
                                                                                           padx=(24, 0), pady=12)
    tk.Label(head, text=f'Beta {VERSION}', bg=BG, fg=MUTED, font=(UI_FONT, 12)).pack(side='left', padx=(10, 0),
                                                                                     pady=(20, 12))
    flat_button(head, 'Game files…', lambda: open_setup(root, refresh_games)).pack(side='right', padx=(8, 24))
    flat_button(head, 'Textures…', lambda: open_textures(root, record, refresh_games)).pack(side='right')

    # everything below the title bar takes the selected version's colour
    body = tint(tk.Frame(root), 'bg')
    body.pack(fill='both', expand=True)
    tabs = tint(tk.Frame(body), 'bg')
    tabs.pack(padx=24, pady=(14, 0))
    tab_parts = {}
    for i, name in enumerate(GAMES):
        cell = tint(tk.Frame(tabs, cursor='hand2'), 'bg')
        cell.grid(row=0, column=i, padx=18)
        ball = tint(tk.Label(cell), 'bg')
        ball.pack()
        title = tint(tk.Label(cell, text=name, font=(UI_FONT, 13, 'bold')), 'bg')
        title.pack(pady=(2, 0))
        status = tint(tk.Label(cell, text='', fg=MUTED, font=(UI_FONT, 9)), 'bg')
        status.pack()
        bar = tk.Frame(cell, height=4, width=170)
        bar.pack(pady=(4, 0))
        for w in (cell, ball, title, status):
            w.bind('<Button-1>', lambda e, n=name: select(n))
        tab_parts[name] = (ball, title, status, bar)

    panel = tint(tk.Frame(body, highlightthickness=2), 'panel')
    panel.pack(fill='x', padx=24, pady=(8, 0))
    info = tint(tk.Frame(panel), 'panel')
    info.pack(fill='x', padx=18, pady=(14, 6))
    v_title = tint(tk.Label(info, fg=FG, font=(UI_FONT, 14, 'bold')), 'panel')
    v_title.grid(row=0, column=0, sticky='w')
    # A read-only Text rather than a Label, so names can be links ("[name](url)" in a blurb): underlined, same
    # colour. Three lines tall on every tab, so the window keeps its size.
    blurb_font = tkfont.Font(family=UI_FONT, size=10)
    v_blurb = tint(tk.Text(info, fg=MUTED, font=blurb_font, wrap='word', height=3, bd=0, highlightthickness=0,
                           width=820 // blurb_font.measure('0'), cursor='arrow', takefocus=0), 'panel')
    v_blurb.grid(row=1, column=0, sticky='w', pady=(2, 0))
    links = tint(tk.Frame(info), 'panel')
    links.grid(row=0, column=1, rowspan=2, sticky='ne', padx=(20, 0))
    info.columnconfigure(0, weight=1)
    ctl = tint(tk.Frame(panel), 'panel')
    ctl.pack(fill='x', padx=18, pady=(0, 14))
    tint(tk.Label(ctl, text='CONTROLS', fg=MUTED, font=(UI_FONT, 9, 'bold')), 'panel').grid(
        row=0, column=0, columnspan=2, sticky='w')
    tint(tk.Label(ctl, image=img['controller']), 'panel').grid(row=1, column=0, padx=(0, 10))
    kb = tint(tk.Frame(ctl), 'panel')
    kb.grid(row=1, column=1, sticky='n')
    tint(tk.Label(kb, image=img['keyboard']), 'panel').pack()

    # bottom row: screen size, big Play button, randomizer (the side columns have equal widths, so Play
    # stays centred whether or not the randomizer is shown)
    bottom = tint(tk.Frame(body), 'bg')
    bottom.pack(fill='x', padx=24, pady=(16, 20))
    for col in (0, 2):
        bottom.columnconfigure(col, weight=1, uniform='side')
    left = tint(tk.Frame(bottom), 'bg')
    left.grid(row=0, column=0, sticky='e', padx=(0, 24))
    tint(tk.Label(left, text='Screen', fg=MUTED, font=(UI_FONT, 11)), 'bg').pack(side='left', padx=(0, 8))
    ttk.Combobox(left, textvariable=screen, values=list(SCREENS), state='readonly', width=20,
                 font=(UI_FONT, 11), style='Tint.TCombobox').pack(side='left', ipady=4)
    play_btn = tint(tk.Canvas(bottom, width=360, height=64, highlightthickness=0, cursor='hand2'), 'bg')
    play_btn.grid(row=0, column=1)
    right = tint(tk.Frame(bottom), 'bg')
    right.grid(row=0, column=2, sticky='w', padx=(24, 0))
    rand_cb = tint(Check(right, 'Randomize wild encounters', rand, BG, '#3f78e6'), 'bg')
    rand_cb.pack(anchor='w', pady=(0, 6))
    hd_cb = tint(Check(right, 'Custom textures', hd, BG, '#3f78e6'), 'bg')
    hd_cb.pack(anchor='w')
    play_state = {'hover': False}

    def draw_play():
        t = TABS[game.get()]
        files = game_files(game.get())
        text = 'PLAY' if files and files[2] else 'BUILD & PLAY' if files else 'SET UP GAME FILES'
        c = t['light'] if play_state['hover'] else t['hex']
        play_btn.delete('all')
        r, w, h = 30, 360, 64
        play_btn.create_oval(0, 0, 2 * r, h, fill=c, outline=c)
        play_btn.create_oval(w - 2 * r, 0, w, h, fill=c, outline=c)
        play_btn.create_rectangle(r, 0, w - r, h, fill=c, outline=c)
        play_btn.create_text(w // 2, h // 2, text=text, fill='white', font=(UI_FONT, 20, 'bold'))
    play_btn.bind('<Enter>', lambda e: (play_state.update(hover=True), draw_play()))
    play_btn.bind('<Leave>', lambda e: (play_state.update(hover=False), draw_play()))
    play_btn.bind('<Button-1>', lambda e: play_safely())

    def select(name):
        game.set(name)
        update()

    def update():
        sel = game.get()
        t = TABS[sel]
        for role in ('bg', 'panel'):
            for w in tinted[role]:
                if isinstance(w, Check):
                    w.set_theme(t[role], t['hex'])
                else:
                    w.configure(bg=t[role])
        style.configure('Tint.TCombobox', fieldbackground=t['bg'], background=t['panel'], foreground=FG,
                        arrowcolor=FG, bordercolor=t['hex'], lightcolor=t['panel'], darkcolor=t['panel'])
        style.map('Tint.TCombobox', fieldbackground=[('readonly', t['bg'])], foreground=[('readonly', FG)],
                  selectbackground=[('readonly', t['bg'])], selectforeground=[('readonly', FG)])
        root.option_add('*TCombobox*Listbox.background', t['panel'])
        for name, (ball, title, status, bar) in tab_parts.items():
            on = name == sel
            ball.configure(image=img[f"capsule_{TABS[name]['colour']}{'_open' if on else ''}"])
            title.configure(fg=FG if on else MUTED)
            bar.configure(bg=TABS[name]['hex'] if on else t['bg'])
            files = game_files(name)
            status.configure(text='Ready' if files and files[2] else 'Needs building' if files else 'Not set up')
        panel.configure(highlightbackground=t['hex'], highlightcolor=t['hex'])
        v_title.configure(text=sel)
        set_blurb(v_blurb, t['blurb'])
        for w in links.winfo_children():
            w.destroy()
        for label, url in t['links']:
            flat_button(links, label + '  ↗', lambda u=url: webbrowser.open(u), bg=t['hex'], hover=t['light'],
                        width=LINK_WIDTH).pack(side='top', pady=(0, 6))
        if GAMES[sel]['randomizer'] > 0:  # Weekend versions only; hidden for Vanilla
            rand_cb.pack(anchor='w', pady=(0, 6), before=hd_cb)
        else:
            rand_cb.pack_forget()
        has_pack = has_textures()
        hd_cb.configure(state='normal' if has_pack else 'disabled',
                        text='Custom textures' if has_pack else 'Custom textures (add packs under Textures…)')
        draw_play()

    def refresh_games():
        """Re-read which versions are set up and built; returns those that are at least set up."""
        update()
        return [n for n in GAMES if game_files(n)]

    def play_safely():
        # A launcher with no console must never fail silently.
        try:
            play()
        except Exception as e:
            messagebox.showerror('RumbleRecomp', 'Could not start the game:\n' + f'{type(e).__name__}: {e}')

    def play():
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, 'w') as f:
            json.dump({'game': game.get(), 'randomizer': rand.get(), 'screen': screen.get(), 'hd': hd.get(),
                       'record': record.get()}, f)
        if not game_files(game.get()):
            open_setup(root, refresh_games)
            return
        if not game_paths(game.get()):
            # set up but not built yet: offer to build every version that needs it
            todo = sorted({GAMES[n]['build'] for n in GAMES if game_files(n) and not game_files(n)[2]},
                          key=['vanilla', 'weekend'].index)
            if messagebox.askyesno('RumbleRecomp', (
                    f'{game.get()} needs to be built for your PC first. This happens once and takes about '
                    f'20-40 minutes per version ({len(todo)} to build). Build now?')):
                open_build(root, todo, refresh_games)
            return
        if launch(game.get(), rand.get() and GAMES[game.get()]['randomizer'] > 0, screen.get(),
                  hd=hd.get() and has_textures(), record=record.get()):
            root.destroy()

    if not refresh_games():  # first run: nothing set up yet
        root.after(200, lambda: open_setup(root, refresh_games))
    root.mainloop()


if __name__ == '__main__':
    main()
