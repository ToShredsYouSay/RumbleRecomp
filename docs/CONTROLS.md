# Controls (RumbleRecomp default profile)

The launcher writes the controller config into the user dir every time it starts the game (`write_config` in
`tools/launcher.pyw`). Player 1 is the keyboard plus the first controller to press a button; players 2 to 4 are
further controllers, joining as GameCube pads on ports 2 to 4.

Every player has full analogue movement and every player shows the same GameCube icon on the multiplayer join
screen. How the game reads controllers (tested 2026-10-04):

| | Single player (title, hub, stages) | Multiplayer join screen and multiplayer stages |
|---|---|---|
| Wii Remote 1 (with Classic) | read | ignored when four GameCube pads are plugged in |
| GameCube pad port 1 | ignored | player 1 |
| GameCube pads ports 2 to 4 | (not used) | players 2 to 4 |
| Wii Remotes 2 to 4 | (not used) | ignored, even with a Classic Controller |

So player 1 is bound twice, to the same keys and controller: Wii Remote 1 with a Classic Controller
(`WIIMOTE1`) and GameCube pad port 1 (`GCPAD1`). Press-to-join gives the first controller to both (patch 0016).
The multiplayer screen is the table with two gold figures near the bottom of the hub; the pause menu also
offers Multiplayer while you're in the hub.

## Player 1 is a Classic Controller

Player 1 is an emulated Wii Remote with a **Classic Controller** plugged in (`Extension = Classic`). Why:

- The Wii Remote's d-pad only gives 8 directions. The Classic's left stick gives full analogue movement: the game
  turns player 1 to in-between angles (stick at 20 degrees settles at a facing of 105, 65 settles at 147), the
  same way it already did for players 2 to 4 on GameCube pads.
- The game only reads player 1 from a Wii Remote. A GameCube pad on port 1 does nothing, both from a save state
  and from a cold boot (the title menu ignores its A and Start).
- With the Classic attached the game ignores the Wii Remote's own buttons, so every player 1 binding lives on
  the Classic. The game switches its on-screen button prompts to Classic labels (a, b, minus) by itself.
- The game refuses a Nunchuk (it waits on its "Compatible with the Classic Controller and the Wii Remote" notice).
- The opening screens ("How to Hold the Wii Remote", and "How to access GX rank" in the Weekend Edition) only
  skip on the Wii Remote's own buttons (2 or A); Classic presses wait for their timer (about ten seconds). So
  confirm (J, Cross) also presses the Wii Remote's 2. Pause and favourite stay Classic-only, since pressing a
  toggle on both at once could count twice.

| Classic Controller | In game | Keyboard (P1) | Gamepad (SDL, PS4 names) |
|---|---|---|---|
| Left stick | Move (analogue) | (none) | Left stick |
| D-Pad | Move (8 directions), menu navigation | W A S D or arrow keys | D-pad |
| **a** | Attack 1, confirm | J | Cross |
| **b** | Attack 2, cancel | K | Square |
| **x** | Open the team list, switch character | L | Circle, R1 |
| **y** | Open the team list (same as x) | (none) | (none) |
| **+** | Pause, open menu, menu options | Enter | Options/Start |
| **-** | Favourite or unfavourite the selected character | Backspace | Share/Back |
| L, R, ZL, ZR | (no use found in a stage) | (none) | (none) |
| **HOME** | Wii HOME Menu: unbound, as there is no Wii system to return to | (none) | (none) |
| Rumble (Wii Remote) | | (none) | pad motors |

The physical buttons do the same jobs as the old sideways Wii Remote profile (2, 1, A, +, -). The launcher's
controller and keyboard pictures (`tools/make_launcher_art.py`) label each job with a round badge showing the
letter the game uses in its own prompts (A, B, X, minus, plus), which match in single player and multiplayer. Keyboard input only reaches the game while its window has focus
(BackgroundInput is off). Automation (`--automation-dir`) does not block real input: its override drops as soon as
a real control changes.

## GameCube pads (player 1 in multiplayer, players 2 to 4)

A attack 1, confirm, and join; B attack 2 and cancel; X team list (Circle or R1 on a gamepad); Y leaves the join screen; Start pause; main
stick analogue movement (player 1's stick angles 20 and 65 degrees settle at facings 100 and 151 in a
multiplayer fight). No favourite button was found on the GameCube pad. Player 1's keyboard on port 1: J or
J = A, K = B, L = X, Enter = Start, WASD or arrows = main stick. See `GCPAD` and `GCPAD1` in
`tools/launcher.pyw`.

## In-game menu (patches 0017 and 0018)

HOME (the Guide or PS button) on any connected controller, both sticks pressed in together, the touchpad click
on a PlayStation controller, or Esc on the keyboard, pauses the game and opens
RumbleRecomp's menu, drawn over the paused game in the colour of the version being played (the launcher passes
`RR_MENU_COLOUR`). Items: Resume, Save state, Load state, Fullscreen (On or Off), and Quit game.

- Save and load use 4 slots per version, stored in `<user dir>/StateSaves/RumbleRecomp/<version>/` (the
  launcher passes `RR_MENU_SLOTS`: vanilla, weekend, or weekend_patch1, as Weekend and PATCH1 share a game folder) as
  `slotN.sav` plus `slotN.thumb` (the picture: "RRTH", width and height as little-endian u32, then RGBA).
  The picture is the game frame from the moment the menu opened, shrunk to 480 pixels wide.
- Controls in the menu: d-pad or left stick (arrows or WASD) to move, A (Enter, J) to choose,
  B (Esc, Backspace, K) to go back. HOME or Esc closes it from the first page.
- Closing waits until the menu's buttons are let go, so the game never sees them (Enter is also its pause key).
- Quit game stops at once (a polite shutdown would wait for the paused game to answer).
- While paused, the menu redraws the last game frame about 60 times a second through Dolphin's video thread.

Other keys in the game window: hold Space to fast forward (Space is not bound to anything in the game), F11 or
Alt+Enter for fullscreen. Esc no longer quits the game; use Quit game in the menu or close the window.
Automation can drive the menu without focus: `menu_key key=escape|up|down|left|right|enter|back`.

## Tools

- `tools/rr_drive.py` drives a test instance through the automation folder (pad commands, screenshots, memory
  reads). Classic Controller fields are `classic_a`, `classic_b`, `classic_x`, `classic_y`, `classic_plus`,
  `classic_minus`, `classic_dpad_*`, `classic_l`, `classic_r`, `classic_zl`, `classic_zr`, and the sticks
  `classic_lx`, `classic_ly`, `classic_rx`, `classic_ry` (patch 0015).
- `tools/rr_keys.py` sends real key presses to the game window (only while it is the foreground window).
- `tools/make_controller_config.py` is the old pre-launcher generator (sideways Wii Remote, no Classic). The launcher
  replaced it.
