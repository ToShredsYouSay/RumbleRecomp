# RumbleRecomp

Good news, everyone!

RumbleRecomp turns your own copy of the 2009 WiiWare game *Poke Rumble* into a native Windows program. The
game's code is translated into C and compiled on your own PC, then runs on a trimmed-down Dolphin runtime, so it
plays at full speed with modern extras such as widescreen, save states, and texture packs.

**No game files are included or downloaded.** You need your own copy of the original USA WiiWare release
(title WPSE01) as a `.wad` file. The game is built from it on your PC the first time you play.

## Features

- **Native code.** The game's PowerPC code is statically recompiled to C, then compiled with clang. Busy
  four-player fights run at full speed.
- **Any screen shape:** fit to window, 16:9 (the original), 21:9, or 32:9, with the HUD kept in proportion.
- **In-game menu** on HOME or Esc: save and load states (4 slots per version, each with a picture and the time),
  fullscreen, and quit.
- **Controllers:** press any button to join, up to four players, with full analogue movement for everyone. The
  keyboard is always player 1.
- **Weekend Edition 1.5 and PATCH1,** the fan-made expansions, built from your own copies of their patches. An
  optional randomizer shuffles wild encounters.
- **Texture packs:** install a folder or a `.zip` of custom textures, with a switch to turn them off. You can also
  record every texture the game shows, to make your own.

## Getting started

1. Download the latest zip from [Releases](../../releases) and unzip it anywhere (not inside Program Files).
2. Run `RumbleRecomp.exe`. Windows may warn about an unknown publisher: choose More info, then Run anyway.
3. Under **Game files**, choose your `.wad`. For the Weekend Edition, download its patch yourself from the page
   linked in the launcher and choose it there too.
4. Press **Play**. The first time, each version is built for your PC, which takes about 20 to 40 minutes. Later
   updates only rebuild what changed.

**You need:** Windows 10 or 11 (64-bit), a graphics card with Vulkan, and about 4 GB of free space.

## Controls

| Action | Keyboard | Controller |
|---|---|---|
| Move | WASD or arrow keys | Left stick or d-pad |
| Attack 1 / Confirm | J | Bottom face button |
| Attack 2 / Cancel | K | Left face button |
| Switch | L | Right face button or right shoulder |
| Pause | Enter | Start |
| Favourite (single player) | Backspace | Back |
| Menu (save, load, and fullscreen) | Esc | HOME, or press both sticks in |
| Fast forward (hold) | Space | |
| Fullscreen | F11 | |

For multiplayer, walk to the table with two gold figures at the bottom of the hub, or choose Multiplayer
from the pause menu while you're in the hub.

If Steam is running, HOME may open Steam's Big Picture instead. Press both sticks in to open the menu, or turn off
"Guide button focuses Steam" in Steam's controller settings.

## Troubleshooting

- **Windows says it protected your PC.** RumbleRecomp isn't code-signed. Choose More info, then Run anyway.
- **Your antivirus flags `RumbleRecomp.exe`.** Launchers packed with Python's PyInstaller are sometimes flagged
  by mistake. The full source is here, so you can check it or build it yourself.
- **HOME opens Steam's Big Picture.** Press both sticks in to open the menu instead, or turn off "Guide button
  focuses Steam" in Steam's controller settings.
- **The keyboard does nothing.** Click the game window first. Keyboard input only reaches the game while its window
  has focus.
- **The first Play takes a long time.** Each version is built for your PC once, which takes about 20 to 40
  minutes. Later updates only rebuild what changed.
- **Where are my saves?** Everything of yours (game files, saves, settings, and the built game) lives in the
  `data` folder next to `RumbleRecomp.exe`. Back it up to keep your saves.

## Known issues

- This is a beta. Full playthroughs of every version are still in progress, so please report anything odd.
- Most testing so far has been on NVIDIA graphics cards. Reports from AMD and Intel graphics are very welcome.

Found a problem? [Open an issue](../../issues/new/choose) and attach `data\play.log`, which records your last
session.

## Building from source

See [docs/BUILDING.md](docs/BUILDING.md).

## How this was made

RumbleRecomp was built with a lot of help from an AI coding assistant, Claude by Anthropic. I started the project
and directed it. I set its ground rules (players use their own copy, no game files are shared, and it builds with
clang), made the design decisions, and tested every change by playing the game, including on real controllers and
with fresh installs on two PCs. Claude wrote most of the code, patches, and scripts from that direction, and many
of the fixes started with problems I found while playing.

I'm saying this upfront because it matters to a lot of people in this community. Every change to Dolphin,
ModernGekko, and DolRecomp is documented as a patch, the build guide lets anyone rebuild it from source, and bug
reports are very welcome.

## Credits

RumbleRecomp stands on the work of others:

- [Dolphin](https://dolphin-emu.org), the GameCube and Wii emulator (GPL-2.0-or-later).
- [ModernGekko, RecompCore, and DolRecomp](https://github.com/ExpansionPak) by ExpansionPak, the static
  recompilation framework (GPL-3.0).
- [The Rumble decompilation](https://github.com/KooShnoo/pokemon-rumble) by KooShnoo, used for symbols and
  headers.
- [decomp-toolkit](https://github.com/encounter/decomp-toolkit) by encounter, and
  [xdelta](https://github.com/jmacd/xdelta) by Joshua MacDonald.
- [Weekend Edition](https://projectpokemon.org/home/files/file/4256-pokemon-rumble-weekend-edition/) by
  [WindyPrairie](https://projectpokemon.org/home/profile/101169-windyprairie/), and
  [PATCH1](https://projectpokemon.org/home/files/file/5855-unofficial-weekend-edition-v150patch1/) by
  [eman_not_ava](https://projectpokemon.org/home/profile/88062-eman_not_ava/).
- Lincoln, for the original wild encounter randomizer code.
- [Nunito](https://github.com/googlefonts/nunito) by the Nunito Project Authors (SIL Open Font License 1.1).

## Legal

RumbleRecomp is a fan project. It is not affiliated with or endorsed by Nintendo, Game Freak, Creatures,
Ambrella, or the game's other rights holders. All trademarks belong to their respective owners. RumbleRecomp
contains no game code or assets: you must supply your own copy of the game.

Copyright 2026 ToShredsYouSay. RumbleRecomp is free software under the GNU General Public License, version 3 or
later. See [LICENSE](LICENSE).
