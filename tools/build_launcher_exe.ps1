# Builds RumbleRecomp.exe (the launcher, tools\launcher.pyw) into the repo root. Run from the repo root.
# Needs: python -m pip install pyinstaller
# (PyInstaller logs progress to stderr, so don't use $ErrorActionPreference = 'Stop' here.)
python -m PyInstaller --clean --noconfirm --onefile --noconsole --paths tools --name RumbleRecomp --icon "$PWD\tools\launcher.ico" `
  --distpath . --workpath build\pyinstaller --specpath build\pyinstaller tools\launcher.pyw 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }
Get-Item RumbleRecomp.exe