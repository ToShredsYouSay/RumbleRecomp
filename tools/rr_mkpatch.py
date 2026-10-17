"""Write a patch of files changed in an upstream clone, on top of the patches already applied to it.
  python tools/rr_mkpatch.py REPO OUT.patch FILE... [--after PATCH...]
Compares each FILE in the working tree with the clone's HEAD plus the --after patches (a temporary index, so
nothing in the clone changes). Line endings are normalised, so a file edited on Windows does not show as
rewritten. New files are written as additions."""
import difflib, os, subprocess, sys, tempfile

args = sys.argv[1:]
repo, out = args[0], args[1]
rest = args[2:]
after = rest[rest.index('--after') + 1:] if '--after' in rest else []
files = rest[:rest.index('--after')] if '--after' in rest else rest
index = os.path.join(tempfile.mkdtemp(), 'index')
env = dict(os.environ, GIT_INDEX_FILE=index)
subprocess.run(['git', '-C', repo, 'read-tree', 'HEAD'], env=env, check=True)
for patch in after:
    subprocess.run(['git', '-C', repo, 'apply', '--cached', '--ignore-whitespace', os.path.abspath(patch)], env=env, check=True)
parts = []
for f in files:
    shown = subprocess.run(['git', '-C', repo, 'show', ':' + f], env=env, capture_output=True)
    base = shown.stdout.decode('utf-8').replace('\r\n', '\n').splitlines(keepends=True) if shown.returncode == 0 else []
    with open(os.path.join(repo, f), encoding='utf-8', newline='') as fh:
        cur = fh.read().replace('\r\n', '\n').splitlines(keepends=True)
    if base != cur:
        parts.append(''.join(difflib.unified_diff(base, cur, 'a/' + f if base else '/dev/null', 'b/' + f, n=3)))
with open(out, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(''.join(parts))
print(f'{out}: {sum(p.count(chr(10)) for p in parts)} lines, {len(parts)} files')
