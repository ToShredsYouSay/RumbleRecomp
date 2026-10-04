#!/usr/bin/env python3
"""Build a game module on the player's PC from their own game code (prepared by tools/rr_setup.py),
using the compile kit (tools/make_kit.py). Same recipe as the developer build: DolRecomp with the
instruction hooks, every C file compiled in parallel with the speed-tuning profile, ThinLTO link.

Library (used by the launcher) and CLI:
  python tools/rr_compile.py vanilla|weekend [--data <dir>] [--jobs N] [--clean]
Result: <data>/modules/<module>.dll. Intermediate files (<data>/build/<profile>) are kept so that rebuilds
after an update only recompile what changed (--clean removes them afterwards)."""
import concurrent.futures, glob, hashlib, json, os, runpy, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rr_setup

ROOT = rr_setup.ROOT
KIT = os.environ.get('RR_KIT') or os.path.join(ROOT, 'kit')
NO_WINDOW = 0x08000000
# profile -> (gameroot folder, module file name, profile data)
MODULES = {
    'vanilla': ('vanilla', 'gWPSE01_recomp.dll', 'vanilla.profdata'),
    'weekend': ('weekend', 'gWPSE01_weekend_recomp.dll', 'weekend.profdata'),
}
CORE_SOURCES = ['cpu.c', 'cpu_exception.c', 'cpu_interpreter.c', 'cpu_interpreter_table.c',
                'cpu_interpreter_float.c', 'cpu_interpreter_integer.c']


class CompileError(Exception):
    """Build failure; the message is shown to the player."""


def module_path(profile, data_dir=None):
    return os.path.join(data_dir or rr_setup.default_data_dir(), 'modules', MODULES[profile][1])


def find_clang():
    bundled = os.path.join(KIT, 'toolchain', 'bin', 'clang.exe')
    if os.path.isfile(bundled):
        return bundled
    found = shutil.which('clang')
    if not found:
        raise CompileError('The compiler is missing (kit/toolchain). Please re-install RumbleRecomp.')
    return found


def hooks():
    with open(os.path.join(KIT, 'src', 'module_hooks', 'hooks.txt'), encoding='utf-8') as f:
        return ','.join(l.strip() for l in f if l.strip() and not l.startswith('#'))


def run(cmd, env=None, log=None):
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, creationflags=NO_WINDOW)
    if log:
        log.write(' '.join(cmd) + '\n' + r.stdout + r.stderr + '\n')
    return r


def build(profile, data_dir=None, jobs=None, keep=True, progress=lambda frac, text: print(f'{frac:5.1%} {text}')):
    """Build one module. progress(fraction 0..1, text). Raises CompileError."""
    data_dir = data_dir or rr_setup.default_data_dir()
    root_name, dll_name, prof_name = MODULES[profile]
    dol = os.path.join(data_dir, 'gameroot', root_name, 'sys', 'main.dol')
    if not os.path.isfile(dol):
        raise CompileError(f'{profile}: game files are not set up yet (use "Game files..." first).')
    clang = find_clang()
    prof = os.path.join(KIT, 'pgo', prof_name)
    work = os.path.join(data_dir, 'build', profile)
    gen, obj = os.path.join(work, 'gen'), os.path.join(work, 'obj')
    os.makedirs(obj, exist_ok=True)
    jobs = jobs or os.cpu_count() or 4
    log = open(os.path.join(work, 'build.log'), 'w', encoding='utf-8')
    t0 = time.time()

    # 1. PowerPC -> C, into a fresh folder; then copy over only files whose content changed, so unchanged
    #    files keep their compiled objects (an update that touches one hook rebuilds one chunk).
    progress(0.0, 'Converting the game code...')
    fresh = os.path.join(work, 'gen_new')
    shutil.rmtree(fresh, ignore_errors=True)
    env = dict(os.environ, DOLRECOMP_HOOKS=hooks())
    r = run([os.path.join(KIT, 'bin', 'dolrecomp.exe'), f'-j{jobs}', '--backend=c', '--cpu', 'broadway', dol,
             'WPSE01', fresh], env=env, log=log)
    if r.returncode != 0 or not os.path.isfile(os.path.join(fresh, 'generated', 'generated.h')):
        raise CompileError('Converting the game code failed. See ' + log.name)
    shutil.copy2(dol, os.path.join(fresh, 'generated', 'main.dol'))
    sync_tree(fresh, gen)
    shutil.rmtree(fresh, ignore_errors=True)
    generated = os.path.join(gen, 'generated')

    # 2. function tables
    progress(0.05, 'Preparing...')
    argv = sys.argv
    try:
        sys.argv = ['gen_module_tables.py', os.path.join(generated, 'generated.h'),
                    os.path.join(generated, 'generated_smc.txt'), os.path.join(generated, 'main.dol'),
                    os.path.join(obj, 'module_tables.inc')]
        runpy.run_path(os.path.join(KIT, 'src', 'module-template', 'gen_module_tables.py'), run_name='__main__')
    except SystemExit as e:
        if e.code not in (0, None):
            raise CompileError('Preparing the function tables failed.')
    finally:
        sys.argv = argv

    # 3. compile, in parallel, every file whose content, headers or settings changed since the last build
    src = os.path.join(KIT, 'src')
    sources = [os.path.join(src, 'module-template', 'module_export.c')]
    sources += [os.path.join(src, 'GXRuntime', 'src', 'core', s) for s in CORE_SOURCES]
    sources += [os.path.join(src, 'module_hooks', 'rumble_hud.c')]
    chunks = os.path.join(generated, 'chunks')
    sources += sorted(os.path.join(chunks, f) for f in os.listdir(chunks) if f.endswith('.c'))
    flags = ['-DDOLRECOMP_CPU_HEADER="core/cpu.h"', '-DMODULE_GAME_ID="WPSE01"', '-DgWPSE01_recomp_EXPORTS',
             '-I' + generated, '-I' + os.path.join(src, 'GXRuntime', 'include'),
             '-I' + os.path.join(src, 'StaticRecomp'), '-I' + obj,
             '-fprofile-use=' + prof, '-Wno-profile-instr-unprofiled', '-Wno-profile-instr-out-of-date',
             '-O3', '-DNDEBUG', '-std=gnu11', '-flto=thin', '-fvisibility=hidden', '-O2', '-ffp-contract=off',
             '-fno-fast-math']
    objects = [os.path.join(obj, os.path.basename(s) + '.o') for s in sources]
    # Anything every file depends on: settings, compiler, profile and all headers (any change -> rebuild all).
    common = hashlib.sha1()
    common.update(json.dumps(flags).encode())
    common.update(run([clang, '--version']).stdout.encode())
    for dep in [prof, os.path.join(obj, 'module_tables.inc')] + sorted(
            glob.glob(os.path.join(generated, '*.h')) + glob.glob(os.path.join(src, '**', '*.h'), recursive=True)):
        common.update(file_sha1(dep).encode())
    common = common.hexdigest()
    manifest_path = os.path.join(work, 'manifest.json')
    try:
        with open(manifest_path, encoding='utf-8') as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        manifest = {}
    keys = {o: common + file_sha1(s) for s, o in zip(sources, objects)}
    todo = [i for i, o in enumerate(objects)
            if not os.path.isfile(o) or manifest.get(os.path.basename(o)) != keys[o]]
    log.write(f'{len(todo)} of {len(sources)} files to compile\n')

    def compile_one(i):
        return i, run([clang] + flags + ['-c', sources[i], '-o', objects[i]])

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for i, r in pool.map(compile_one, todo):
            done += 1
            if r.returncode != 0:
                log.write(f'FAILED {sources[i]}\n{r.stdout}{r.stderr}\n')
                log.close()
                save_manifest(manifest_path, manifest)
                raise CompileError(f'Compiling failed ({os.path.basename(sources[i])}). See {log.name}')
            manifest[os.path.basename(objects[i])] = keys[objects[i]]
            if done % 16 == 0:
                save_manifest(manifest_path, manifest)  # an interrupted build resumes where it stopped
            progress(0.06 + 0.74 * done / len(todo), f'Compiling... {done}/{len(todo)}')
    for stale in set(os.listdir(obj)) - {os.path.basename(o) for o in objects} - {'module_tables.inc'}:
        os.remove(os.path.join(obj, stale))
        manifest.pop(stale, None)
    save_manifest(manifest_path, manifest)

    # 4. link (ThinLTO: the final whole-game optimisation; its cache skips unchanged parts on rebuilds)
    progress(0.80, 'Linking (final optimisation, this takes a few minutes)...')
    out = module_path(profile, data_dir)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rsp = os.path.join(work, 'link.rsp')
    with open(rsp, 'w', encoding='utf-8') as f:
        f.write('\n'.join('"' + o.replace('\\', '/') + '"' for o in objects))
    tmp_out = out + '.tmp'
    r = run([clang, '-fprofile-use=' + prof, '-Wno-profile-instr-unprofiled', '-Wno-profile-instr-out-of-date',
             '-O3', '-DNDEBUG', '-flto=thin', '-shared', '-o', tmp_out,
             '-Wl,--thinlto-cache-dir=' + os.path.join(work, 'lto_cache').replace('\\', '/'),
             '-Wl,--major-image-version,0,--minor-image-version,0', '@' + rsp], log=log)
    if r.returncode != 0 or not os.path.isfile(tmp_out):
        log.close()
        raise CompileError('Linking failed. See ' + log.name)
    os.replace(tmp_out, out)
    log.write(f'built {out} in {time.time() - t0:.0f} s\n')
    log.close()
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    progress(1.0, f'Done in {max(1, round((time.time() - t0) / 60))} min.')
    return out


def file_sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save_manifest(path, manifest):
    with open(path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(manifest, f)
    os.replace(path + '.tmp', path)


def sync_tree(src, dst):
    """Make dst identical to src, rewriting only files whose content differs."""
    for d, _, files in os.walk(src):
        rel = os.path.relpath(d, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in files:
            a, b = os.path.join(d, f), os.path.join(dst, rel, f)
            if not (os.path.isfile(b) and os.path.getsize(a) == os.path.getsize(b) and file_sha1(a) == file_sha1(b)):
                shutil.copy2(a, b)
    for d, _, files in os.walk(dst):
        rel = os.path.relpath(d, dst)
        for f in files:
            if not os.path.exists(os.path.join(src, rel, f)):
                os.remove(os.path.join(d, f))


def clean(profile, data_dir=None):
    """Free the disk space used by a module's intermediate files (the next build is a full one)."""
    shutil.rmtree(os.path.join(data_dir or rr_setup.default_data_dir(), 'build', profile), ignore_errors=True)


def main(argv):
    if not argv or argv[0] not in MODULES:
        print(__doc__)
        return 2
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    try:
        print(build(argv[0], opt('--data'), int(opt('--jobs')) if opt('--jobs') else None, '--clean' not in argv))
    except CompileError as e:
        print('BUILD FAILED:', e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
