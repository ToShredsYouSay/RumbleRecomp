# RumbleRecomp: reproducible Stage 2/3 pipeline (llvm-mingw clang). Run from repo root after tools\stage0_extract.ps1.
#   .\tools\build_and_run.ps1 -Step configure|build|module|run
param([ValidateSet('configure','build','module','run')][string]$Step = 'run',
      [string]$Wad = '',
      [string]$Graphics = 'Vulkan')
$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
switch ($Step) {
  'configure' {
    # ModernGekko needs: git submodule update --init --recursive --depth 1   (inside third_party\ModernGekko)
    # and apply the local patches (paths relative to the repo root):
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0001-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin apply ..\..\..\..\patches\moderngekko\0002-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin\DolRecomp apply ..\..\..\..\..\patches\moderngekko\0003-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin apply ..\..\..\..\patches\moderngekko\0004-*.patch
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0005-*.patch
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0006-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin apply ..\..\..\..\patches\moderngekko\0007-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin\DolRecomp apply ..\..\..\..\..\patches\moderngekko\0008-*.patch
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0009-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin apply ..\..\..\..\patches\moderngekko\0010-*.patch
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0011-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin apply ..\..\..\..\patches\moderngekko\0012-*.patch
    # 0012: native-aspect scenes switch shape in step with the camera (no squeezed first frame).
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0013-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin apply ..\..\..\..\patches\moderngekko\0014-*.patch
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0015-*.patch
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0016-*.patch
    #   git -C third_party\ModernGekko\vendor\dolphin apply ..\..\..\..\patches\moderngekko\0017-*.patch
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0018-*.patch
    #   git -C third_party\ModernGekko apply ..\..\patches\moderngekko\0019-*.patch
    # 0015: Classic Controller fields for automation. 0016: player 1 is also GameCube pad port 1.
    # 0017/0018: the in-game menu (HOME or Esc: save and load states, fullscreen, and quit).
    # 0019: the game program's icon is rebuilt when tools\launcher.ico changes.
    # 0013/0014: game window icon (configure with -DMODERNGEKKO_RUN_ICON=<repo>\tools\launcher.ico),
    # MODERNGEKKO_NO_MENU=1 hides the menu bar, no sunken client edge (thin frame around the picture).
    # 0011: RR_PRESS_TO_JOIN=1 (press a controller button to become the next player) and
    # RR_LOG_INPUT=1 (list input devices to <automation-dir>\inputs.txt). Used by tools\launcher.pyw.
    # 0010: ultrawide scene fixes + side panels for native-aspect scenes.
    # 0009: --import-wii-save / --export-wii-save (Wii SD data.bin).
    # 0007/0008: widescreen HUD (un-stretch 2D, anchor corner widgets via a native hook compiled
    # from src\module_hooks\rumble_hud.c; module build needs DOLRECOMP_HOOKS and
    # RECOMPCORE_MODULE_EXTRA_SOURCES; tools\rr_compile.py shows how).
    # 0006 adds MODERNGEKKO_DUMP_TEXTURES=1 (texture dumping for texture packs).
    # 0004/0005 fix the 0xC000041D exit crash (window destroyed after Config::Shutdown).
    # 0002/0003 are the multi-Poke performance work; the shipped
    # module is then built with PGO: see tools\rr_pgo_train.py for the pgo-run command and training.
    cmake -S third_party\ModernGekko -B build\mg -G Ninja -DCMAKE_BUILD_TYPE=Release "-DMODERNGEKKO_RUN_ICON=$root\tools\launcher.ico" "-DCMAKE_TOOLCHAIN_FILE=$root\tools\toolchain-llvm-mingw.cmake"
  }
  'build'  { ninja -C build\mg moderngekko-run moderngekko-port moderngekko-module-info }
  'module' {
    # Synthetic disc-style root: only sys\main.dol + sys\boot.bin are used to identify the game and build the module.
    New-Item -ItemType Directory -Force build\gameroot\vanilla\sys, build\gameroot\vanilla\files | Out-Null
    Copy-Item extracted\WPSE01_01\main.dol build\gameroot\vanilla\sys\main.dol -Force
    python -c "import struct;b=bytearray(0x440);b[0:6]=b'WPSE01';struct.pack_into('>I',b,0x18,0x5D1C9EA3);b[0x20:0x2B]=b'Poke Rumble';open('build/gameroot/vanilla/sys/boot.bin','wb').write(b)"
    .\build\mg\moderngekko-port.exe build build\gameroot\vanilla --backend c --toolchain clang --opt-level 1 --output build\module\gWPSE01_recomp.dll
    New-Item -ItemType Directory -Force build\bin | Out-Null
    Get-ChildItem build\module -Recurse -Filter gWPSE01_recomp.dll -File | Select-Object -First 1 | Copy-Item -Destination build\bin\gWPSE01_recomp.dll -Force
    Copy-Item build\mg\moderngekko-run.exe build\bin\ -Force
  }
  'run' {
    # Rumble is WiiWare: boot the WAD (Dolphin ES/NAND) while the native module replaces the CPU core.
    if (-not $Wad) { $Wad = (Get-Item 'original\*.wad' | Select-Object -First 1).FullName }
    $env:MODERNGEKKO_BOOT_FILE = $Wad
    New-Item -ItemType Directory -Force build\userdir\Logs, build\userdir\Config | Out-Null
    python tools\make_controller_config.py --user-dir $root\build\userdir   # keyboard + any gamepads seen in the last run; NEVER a Nunchuk (see config\WiimoteNew.ini)
    New-Item -ItemType Directory -Force build\userdir\GameSettings | Out-Null
    Copy-Item config\GameSettings\WPSE01.ini build\userdir\GameSettings\WPSE01.ini -Force   # fixes the ~half-speed stage framerate; see file for why
    New-Item -ItemType Directory -Force build\userdir\Cache\Shaders | Out-Null
    $dolphinIni = "build\userdir\Config\Dolphin.ini"
    if (Test-Path $dolphinIni) {
      $c = Get-Content $dolphinIni -Raw
      if ($c -notmatch '(?m)^CPUThread\s*=') { $c = $c -replace '(?m)^\[Core\]', "[Core]`nCPUThread = True" }
      Set-Content $dolphinIni $c -NoNewline
    } else {
      New-Item -ItemType Directory -Force build\userdir\Config | Out-Null
      Set-Content $dolphinIni "[Core]`nCPUThread = True`n"   # dual-core: GPU work off the emulation thread
    }

    .\build\bin\moderngekko-run.exe --game build\gameroot\vanilla --module build\bin\gWPSE01_recomp.dll `
      --user-dir "$root\build\userdir" --no-mods --graphics $Graphics --automation-dir "$root\build\auto"
  }
}
