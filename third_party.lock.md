# Upstream versions (not tracked in this repo)

`third_party/` and `reference/` are upstream git clones. This repo tracks only our changes to them, as patches in
`patches/moderngekko/`, which apply to exactly these commits (see `tools/build_and_run.ps1` for the apply order).

| Path | Commit | Upstream |
|---|---|---|
| `third_party/ModernGekko` | `a2e4e2b026a68d4848f20ebf16f0e0ddeb573957` | https://github.com/ExpansionPak/ModernGekko |
| `third_party/ModernGekko/vendor/dolphin` (submodule) | `cf8ceb81b47d6172164cd0572f57aa7624719f33` | https://github.com/ExpansionPak/RecompCore.git |
| `third_party/ModernGekko/vendor/dolphin/DolRecomp` (submodule) | `71ce7f97419b1bb1ba9a9596c41507f6629e0fb0` | https://github.com/ExpansionPak/DolRecomp.git |
| `third_party/DolRecomp` (reference only; the build uses the vendored copy) | `06fbc30e9e065860cfe8cea2262d684d4c7e0169` | https://github.com/ExpansionPak/DolRecomp |
| `third_party/ModernGekko-Template` | `c2553a99584b2045dbe46a70e1570994dae8beef` | https://github.com/ExpansionPak/ModernGekko-Template |
| `reference/rumble-decomp` (decomp: symbols, headers) | `11c112f7548b26ab2cecfcf52e201b8d3b76120f` | [KooShnoo's Rumble decompilation](https://github.com/KooShnoo/pokemon-rumble) |

Patches by repository:
- ModernGekko: 0001, 0005, 0006, 0009, 0011, 0013, 0015, 0016, 0018, and 0019
- vendor/dolphin (RecompCore): 0002, 0004, 0007, 0010, 0012, 0014, and 0017
- vendor/dolphin/DolRecomp: 0003 and 0008
