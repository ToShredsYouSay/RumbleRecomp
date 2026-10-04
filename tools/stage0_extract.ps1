# Stage 0: reproducible extraction of USA Rev 0 (WPSE01_01) inputs. Run from repo root.
# Requires tools\dtk.exe (decomp-toolkit v1.8.3) and original\*.wad supplied by the user.
$ErrorActionPreference = 'Stop'
$wad = Get-Item 'original\*.wad' | Select-Object -First 1
$wadSha1 = 'fa02ca7a05596498f5980ce0faf351533a1c1b91'
$dolSha1 = 'fd9a2c00c97e420a42355e2c27f3dc0ebbd3d8f9'
if ((Get-FileHash $wad -Algorithm SHA1).Hash.ToLower() -ne $wadSha1) { throw 'WAD SHA-1 mismatch' }
New-Item -ItemType Directory -Force extracted\WPSE01_01 | Out-Null
.\tools\dtk.exe vfs cp "$($wad.FullName):0000001.app:nlzss" extracted\WPSE01_01\main.dol
if ((Get-FileHash extracted\WPSE01_01\main.dol -Algorithm SHA1).Hash.ToLower() -ne $dolSha1) { throw 'main.dol SHA-1 mismatch' }
foreach ($i in 2,3,4,5) {
  New-Item -ItemType Directory -Force "extracted\content\$i" | Out-Null
  .\tools\dtk.exe vfs cp "$($wad.FullName):0000000$i.app:" "extracted\content\$i"
}
foreach ($i in 0,6) { .\tools\dtk.exe vfs cp "$($wad.FullName):0000000$i.app" "extracted\content\$i.app" }
'Stage 0 OK'
