# Building RumbleRecomp from source

Most players should use a release zip. This guide is for building the runtime, the launcher, and a release
yourself. Everything here runs on Windows with clang; MSVC is not used.

## What you need

- Windows 10 or 11 (64-bit).
- [llvm-mingw](https://github.com/mstorsjo/llvm-mingw) (clang 22, x86_64), with its `bin` folder on `PATH`.
- [CMake](https://cmake.org) 3.20 or newer, and [Ninja](https://ninja-build.org).
- [Git](https://git-scm.com).
- [Python](https://www.python.org) 3.12 or newer, with `pip install pillow pyinstaller`.
- Your own copy of the game (USA WiiWare, WPSE01) as a `.wad`, to test with.

## 1. Get the upstream sources

RumbleRecomp keeps only its own changes, as patches. Clone the upstream repositories at the exact commits listed
in [third_party.lock.md](../third_party.lock.md):

```
git clone https://github.com/ExpansionPak/ModernGekko third_party/ModernGekko
git -C third_party/ModernGekko checkout a2e4e2b026a68d4848f20ebf16f0e0ddeb573957
git -C third_party/ModernGekko submodule update --init --recursive
```

Check that `vendor/dolphin` and `vendor/dolphin/DolRecomp` are at the commits in the lock file.

## 2. Apply the patches

Apply `patches/moderngekko/*.patch` in number order, each in the repository it belongs to:

| Repository | Patches |
|---|---|
| `third_party/ModernGekko` | 0001, 0005, 0006, 0009, 0011, 0013, 0015, 0016, 0018, 0019 |
| `third_party/ModernGekko/vendor/dolphin` | 0002, 0004, 0007, 0010, 0012, 0014, 0017 |
| `third_party/ModernGekko/vendor/dolphin/DolRecomp` | 0003, 0008 |

For example, from the repository root:

```
git -C third_party/ModernGekko apply ../../patches/moderngekko/0001-stderr-alert-handler-and-boot-file.patch
git -C third_party/ModernGekko/vendor/dolphin apply ../../../../patches/moderngekko/0002-dolphin-staticrecomp-dispatch-perf.patch
```

## 3. Build the runtime

```
powershell -File tools/build_and_run.ps1 -Step configure
powershell -File tools/build_and_run.ps1 -Step build
```

This builds `build/mg/moderngekko-run.exe` (the game program, shipped as `RumbleRecomp-game.exe`), plus the
porting tools. Copy `moderngekko-run.exe` into `build/bin`.

## 4. Build the launcher

```
powershell -File tools/build_launcher_exe.ps1
```

This makes `RumbleRecomp.exe` in the repository root. You can also run the launcher straight from source with
`python tools/launcher.pyw`. Its **Game files** button sets up your WAD, and **Play** builds the game the first
time, the same way a release does.

## 5. Make a release

```
python tools/make_kit.py --toolchain
python tools/make_release.py
```

`make_kit.py` gathers the compile kit that builds the game on a player's PC. It needs the two speed-tuning
profiles (`vanilla.profdata` and `weekend.profdata`, execution counts with no game code in them). Copy them from
the `kit/pgo` folder of any release zip, or train your own with `tools/rr_pgo_train.py`, and point the kit at
them with the `RR_PGO_VANILLA` and `RR_PGO_WEEKEND` environment variables. `RR_TOOLCHAIN` sets the llvm-mingw
folder to copy into the kit.

`make_release.py` writes `dist/RumbleRecomp-Beta<version>.zip` and refuses to package anything that looks like
game data.

## More detail

[CONTROLS.md](CONTROLS.md) explains how controllers map onto the game, the in-game menu, and the automation
commands used for testing.
