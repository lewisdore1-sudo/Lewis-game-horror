# The Shifting Mansion

An original first-person psychological horror game for Windows, written in Python with the Panda3D engine.

**18+.** Psychological horror, jump scares, flashing lights, disturbing themes. There's no gore; the fear comes from absence, distance and uncertainty.

> *The house changes when you aren't looking.*

## The core design

The design carries over from the browser dashboard and Lewis's notes. The dashboard's panels became the game's systems:

| Dashboard / notes | In the game |
|---|---|
| **Room Shifting**: Quiet → Wrong → Night variants | Each of the three East Wing doors opens onto one of four rooms (Study, Bedroom, Gallery, Parlour). Each room can be **Quiet** (untouched), **Wrong** (mirrored, chairs upside down, pictures inverted, clocks stopped at 3:00) or **Night** (red dying light, furniture knocked over, stains, writing on the walls). |
| "PLAYER LEAVES → SHIFT → RETURN" | A room changes only after you've left it **and** aren't looking at its doorway. The Study can come back as the Gallery, and the door you remember is a different room now. |
| The Walker: *NO FACE // NO IDENTITY*, *MOVE WHEN UNSEEN* | An original tall, faceless silhouette. It freezes the instant it's in your view and moves only when you look away. If you stare too long, it vanishes and reappears behind you. |
| Botanical Garden: *The illusion of safety* | Open sky, moonlight and a glasshouse. The Walker won't follow you outside at first. As the house takes keys from you, the garden withers, the fog thickens and the safety ends. |
| Grand Hall shifts behind you | Every key you take changes the Hall. The portraits turn around, the chairs face the garden, and the lights die. |
| Mundane tasks | Read the note → take the three keys → water the orchid → leave through the front door. |
| Fluorescent inside, moonlight outside | The corridor has buzzing, flickering tube lights. The garden has cold moonlight with real shadows. |

Graphics features: per-pixel lighting, normal-mapped surfaces, real-time flashlight and moon shadows, bloom on every light source, exponential fog, a film-grain and vignette overlay, and a flickering flashlight that falters when the Walker is close. Every texture and sound is **generated from code on first launch**, so there's no third-party art or audio in the project.

![Map](docs/map.png)

## Install and play (Windows)

1. Install **Python 3.12 or 3.13** from python.org and tick *"Add python.exe to PATH"* in the installer.
2. Open PowerShell in this folder: shift + right-click inside the folder → *Open PowerShell window here*.

Check Python is found:

```
python --version
```

Install the engine and libraries:

```
python -m pip install -r requirements.txt
```

Start the game:

```
python main.py
```

After the first launch you can double-click **play.bat** instead.

The first launch spends about 10 seconds building textures and sounds into `assets/generated/`. Delete that folder, or run `python main.py --regen`, to rebuild them.

## Controls

| Key | Action |
|---|---|
| W A S D / arrows | Move |
| Mouse | Look |
| Shift | Run (stamina) |
| E / left click | Interact |
| F | Flashlight on/off |
| Esc | Pause (Q quits from the pause screen) |
| F11 | Toggle fullscreen |

You have three chances. If you're caught three times, the house keeps you.

## Settings

The game creates `settings.json` on first run. Edit it and restart the game.

| Setting | Default | Notes |
|---|---|---|
| `width`, `height`, `fullscreen` | 1600×900, false | |
| `mouse_sensitivity`, `invert_y` | 0.12, false | |
| `fov` | 78 | |
| `volume` | 0.8 | |
| `bloom` | true | Turn off on weak GPUs |
| `shadows` | true | Turn off to gain the most FPS |
| `film_grain`, `scanlines` | true, false | Scanlines give the VHS look from Lewis's notes |
| `msaa` | 4 | Only used when bloom is off |

## Troubleshooting

- **`No matching distribution found for panda3d`**: your Python is too new for the published Panda3D wheels. Install Python 3.12 or 3.13 alongside it and use `py -3.12 -m pip ...` and `py -3.12 main.py`.
- **"Fast mesh upload unavailable, using slow path"** in the console is harmless. Room changes just take a few extra milliseconds.
- **Low FPS**: set `"shadows": false`, then `"bloom": false`.
- If anything else goes wrong, copy the whole console output. That's the fastest way to get it fixed.

## Project layout

```text
main.py              launcher: settings, first-run asset build, window setup
play.bat             double-click launcher
game/
  layout.py          the map: areas, walls, doors, obstacles        (pure Python)
  rooms_data.py      room identities, variants, furniture, notes     (pure Python)
  shifting.py        the room-shifting state machine                 (pure Python)
  walker_ai.py       the Walker: move-when-unseen stalking AI        (pure Python)
  nav.py             navigation graph for the Walker                 (pure Python)
  physics.py         collision and line-of-sight                     (pure Python)
  objectives.py      the task chain and progress                     (pure Python)
  assets_gen.py      procedural textures, normal maps and sounds     (numpy + Pillow)
  geom.py            procedural mesh builder
  props.py           furniture models
  world.py           builds the mansion, garden, lights (Panda3D)
  walker.py          the Walker's body and animation (Panda3D)
  player.py          first-person movement and flashlight (Panda3D)
  fx.py / hud.py     post-processing and on-screen text (Panda3D)
  audio.py           ambience, one-shots, 3D breathing (Panda3D)
  app.py             game states and the main loop
tests/
  test_logic.py      20 tests: collisions, reachability, shifting, Walker, meshes
  smoke_stub.py      plays the whole game headlessly against a stubbed engine
```

Run the tests:

```
python -m unittest discover -s tests
```

## Where to take it next

- **Your hand-drawn entities**: drop transparent PNGs into `Source_Assets/Entities/`. They can go into the game as flat cut-out figures, the paper-doll style Lewis described, next to or instead of the Walker.
- **The West Wing**: it's chained shut for a reason. It's the natural place for chapter two.
- **More rooms**: add an identity to `rooms_data.py` (a base layout plus a style). The shifting system picks it up automatically.
