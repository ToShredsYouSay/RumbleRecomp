#!/usr/bin/env python3
"""Drive a PGO training run of an instrumented module through the automation protocol.

Two ways to use it:
  1. Alongside `moderngekko-port pgo-run ... -- <runner options incl. --automation-dir build/auto>`:
       python tools/rr_pgo_train.py [--seconds N] [--scenes a.sav,b.sav]
     waits for the game pgo-run launched, cycles the savestates, then stops it normally.
  2. Standalone (what the installed modules were trained with), launching the game itself:
       python tools/rr_pgo_train.py --launch --module <instrumented.dll> --profile-dir C:/mgpgo/x
           [--wad <wad>] [--scenes ...] [--seconds N]
     writes <profile-dir>/raw/*.profraw; then `llvm-profdata merge -o merged.profdata raw/*.profraw`
     and build the module with -fprofile-use (tools/rr_compile.py shows how).
Savestate names are relative to build/states. Launched runs use the save-data copy build/userdir_auto."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rr_drive as d

STATES = os.path.join(d.ROOT, 'build', 'states')
VANILLA_SCENES = ['forest4_group.sav', 'lobby4.sav', 'forest_group.sav', 'cave_group.sav', 'forest4_start.sav',
                  'hub4.sav', 'cave_start.sav', 'forest_start.sav', 'hub.sav', 'forest4_group.sav',
                  'lobby4_picked.sav', 'cave_group.sav']
WEEKEND_SCENES = ['wk_forest4_group.sav', 'wk_lobby4.sav', 'wk_forest_group.sav', 'wk_forest4_start.sav',
                  'wk_hub4.sav', 'wk_forest_start.sav', 'wk_hub.sav', 'wk_forest4_group.sav', 'wk_forest_group.sav']


def wait_running(timeout=2400):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = d.status()
        try:
            if s.get('state') == 'running' and int(s.get('frame_count', 0) or 0) > 0:
                return True
        except ValueError:
            pass
        time.sleep(1)
    return False


def main():
    a = sys.argv[1:]
    opt = lambda k, dflt=None: a[a.index(k) + 1] if k in a else dflt
    per_scene = float(opt('--seconds', 25))
    scenes = opt('--scenes')
    scenes = scenes.split(',') if scenes else (WEEKEND_SCENES if 'weekend' in (opt('--wad') or '') else VANILLA_SCENES)
    proc = None
    if '--launch' in a:
        prof = opt('--profile-dir')
        assert prof and opt('--module'), '--launch needs --module and --profile-dir'
        os.makedirs(os.path.join(prof, 'raw'), exist_ok=True)
        os.environ['LLVM_PROFILE_FILE'] = os.path.join(prof, 'raw', 'WPSE01-%p.profraw')
        try:
            os.remove(os.path.join(d.AUTO, 'status.txt'))
        except OSError:
            pass
        proc = d.start(headless=False, wad=opt('--wad'), module=opt('--module'),
                       user_dir=os.path.join(d.ROOT, 'build', 'userdir_auto'),
                       extra=('--load-state', os.path.join(STATES, scenes[0])))
    assert wait_running(), 'training run never reached the running state'
    time.sleep(5)
    for scene in scenes:
        print('scene', scene, d.send(command='load_state', path=os.path.join(STATES, scene)), flush=True)
        time.sleep(per_scene)
        print('  speed', d.status().get('speed'), flush=True)
    d.stop()
    if proc:
        rc = proc.wait(120)
        print('exit code', hex(rc & 0xFFFFFFFF), flush=True)


if __name__ == '__main__':
    main()
