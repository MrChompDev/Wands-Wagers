#  Wand & Wager

> *Build your wizard. Fight your rivals. Wager everything on a coin flip.*

A 2D online multiplayer wizard fighting game built in Python / Pygame for a game jam around the theme **All or Nothing**. Up to 8 players battle across elemental classes, combining spells to create powerful combos, then after every round gamble their hard-earned upgrades on a single coin flip.

---

##  Gameplay

### The Loop

1. **Choose your wizard** — pick an elemental class, a wand, and load into the arena
2. **Fight** — last wizard standing wins the round
3. **All or Nothing** — after every round, every player receives upgrade cards then faces the wager:
   - **HOLD** — keep your new upgrades safely
   - **WAGER** — bet *all* your upgrades (new + every previous one) on a coin flip. Guess right → every upgrade you own is **doubled**. Guess wrong → you lose **everything**.
4. First to win **3 rounds** wins the match

### Controls

| Input | Action |
|---|---|
| `W` / `↑` / `Space` | Jump |
| `A` / `←` | Move left |
| `D` / `→` | Move right |
| `1` | Cast spell slot 1 |
| `2` | Cast spell slot 2 |
| `3` | Cast spell slot 3 |
| `4` | Cast combo spell (if unlocked) |
| `Mouse` | Aim all spells |
| `Esc` | Pause / back |

---

## 🧙 Classes & Spells

### Playable Classes

| Class | Element | Playstyle |
|---|---|---|
| **Pyromancer** |  Fire | High damage, AoE bursts, burning DoT |
| **Glacialist** |  Ice | Control, slows, walls, traps |
| **Stormcaller** |  Lightning | Fast projectiles, chain arcs, stuns |
| **Terramancer** |  Earth | Tank, massive knockback, zone denial |
| **Zephyrist** |  Wind | Top mobility, deflection, pull zones |

Each class has **5 spells** — you bring 3 into each match.

### Spell Combinations

Equip two compatible spells and unlock a powerful **combo spell** in slot 4:

| Spells | Combo Result |
|---|---|
| Ice Spike + Frost Wall | **Spiking Ice Wall** — a barrier that auto-fires ice spikes |
| Fireball + Flame Wall | **Inferno Barrier** — a burning wall that launches fireballs |
| Fireball + Ice Spike | **Steam Burst** — scalding cloud that blinds on impact |
| Thunder Clap + Ice Spike | **Frozen Thunder** — stuns for 1.2 seconds instead of slowing |
| Wind Blast + Fireball | **Fire Tornado** — a moving vortex of flames across the arena |
| Stone Wall + Flame Wall | **Magma Wall** — a lava barrier with a burning floor zone |

---

##  Wands

Wands are passive stat modifiers chosen in the wizard builder:

| Wand | Effect |
|---|---|
| Oak Wand | Balanced — no changes |
| Willow Wand | +20% cast speed, −10% damage |
| Obsidian Wand | +25% damage, −20% cast speed |
| Crystal Wand | +30% spell size, −15% spell speed |
| Bone Wand | Projectiles split on hit, −20% damage per hit |
| Iron Wand | Spells pierce walls once, −10% size |

---

##  All or Nothing — The Wager

The post-round screen has two phases:

**Phase 1 — Deal**
Cards fly in. The round winner draws **2** upgrade cards; every loser draws **1**.

**Phase 2 — Decide**
Every player simultaneously chooses:
- `HOLD` → keep your new cards, apply them safely
- `WAGER` → pick **Heads** or **Tails**
  - Correct → every upgrade you own is applied **twice**
  - Wrong → you lose *all* upgrades — new ones and every one you've ever earned

CPU opponents use risk-weighted logic: the more upgrades they've accumulated, the less likely they are to wager.

### Upgrade Pool (14 cards)

Upgrades range from Wager Value (WV) 1 (safe) to 5 (risky). During the old blackjack variant, busting over WV 7 loses everything — this is preserved in the bust threshold constant if you want to revert.

---

##  Multiplayer

The game supports **2–8 players online** using a WebSocket authoritative server.

### Playing Online

1. One player deploys the server (see below) and shares the URL
2. Launch the game → pick **Online** from the mode select
3. Enter the server URL, pick your wizard, click **Ready**
4. Match starts when all connected players are ready

### Running the Server Locally (LAN)

```bash
pip install websockets
python Scripts/server.py
# or custom port:
python Scripts/server.py --port 8000
```

Other players on the same network connect to `ws://<your-local-ip>:7890`.

### Deploying the Server Free (Internet Play)

The server is designed to deploy to **[Render.com](https://render.com)** (free tier, no credit card required):

1. Push this repo to GitHub
2. Go to Render → New → **Web Service** → connect your repo
3. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python Scripts/server.py`
4. Click Deploy — you get a URL like `wand-wager.onrender.com`
5. Players connect to `wss://wand-wager.onrender.com`

> **Note:** Render's free tier sleeps after 15 minutes of inactivity. The first connection wakes it up in ~30 seconds.

The server runs headlessly using `pygame_stub.py` — no display required on the host machine.

---

##  Map Builder

A built-in level editor for creating custom arenas:

```bash
python Scripts/map_builder.py
```

| Control | Action |
|---|---|
| Left-click / drag | Paint tile |
| Right-click / drag | Erase |
| Middle-click / drag or Space+drag | Pan |
| Scroll wheel | Zoom |
| `1`–`4` | Select tile type (Platform / Hazard / Ice / Bounce) |
| `S` | Spawn tool (place up to 8 player spawns) |
| `F` | Flood fill |
| `G` | Toggle grid |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo |
| `Ctrl+S` | Save |
| `Delete` | Clear map |

Maps are saved as `.json` files in the `Maps/` folder and auto-loaded by the game at match start.

---

##  Project Structure

```
Wand & Wager/
├── Scripts/
│   ├── main.py            # Entry point + dynamic screen scaling
│   ├── game.py            # Game state machine (char select → combat → AoN → match over)
│   ├── player.py          # Player physics, spell casting, upgrades
│   ├── spells.py          # All spell effect types (projectile, wall, dash, AoE, etc.)
│   ├── ai.py              # CPU controller (Hunt / Engage / Evade / Dodge FSM)
│   ├── arena.py           # Map loading, platform collision, shrink zone
│   ├── constants.py       # All tunable values, spell/wand/upgrade data
│   ├── hud.py             # Top-bar HUD, health bars, cooldown pips
│   ├── vfx.py             # Particle system (impacts, explosions, trails)
│   ├── upgrade_screen.py  # All or Nothing coin-wager screen
│   ├── assets.py          # Asset loader (sprites, tiles, wands, SFX)
│   ├── network.py         # Shared WebSocket message protocol
│   ├── server.py          # Authoritative game server (asyncio + websockets)
│   ├── multiplayer.py     # Client networking + lobby screen
│   ├── pygame_stub.py     # Headless pygame replacement for the server
│   └── map_builder.py     # In-engine level editor
├── Assets/
│   ├── Characters/        # Wizard sprites (Red/Blue/Green/Yellow/Orange/Pink/Aqua)
│   ├── Tiles/             # Tile sprites (Tile_01, Hazard, Ice, Bounce)
│   ├── Wands/             # Wand sprites
│   ├── Cards/             # Upgrade card art
│   ├── VFX/               # Visual effects sprites
│   ├── Music/             # Background music (.ogg / .mp3)
│   └── SFX/               # Sound effects (.wav / .ogg)
├── Maps/                  # Arena JSON files
├── requirements.txt       # Server dependencies (websockets)
├── Procfile               # Render / Railway deploy command
├── railway.json           # Railway project config
└── runtime.txt            # Python version pin
```

---

##  Installation

### Requirements

- Python 3.11+
- pygame 2.x

```bash
pip install pygame
```

For multiplayer (server only):
```bash
pip install websockets
```

### Running the Game

```bash
python Scripts/main.py
```

The window is **fully resizable** — the game renders to a 1280×720 virtual surface and scales to any window size with letterboxing.

---

##  Tech Stack

| Layer | Technology |
|---|---|
| Game engine | Python / Pygame 2.x |
| Physics | Custom platformer physics with coyote time |
| Networking | `asyncio` + `websockets` (authoritative server model) |
| State sync | JSON delta packets at 20 ticks/sec |
| Server hosting | Render.com / Railway (headless, no pygame) |
| Map format | JSON (0 = air, 1 = platform, 2 = hazard, 3 = ice, 4 = bounce) |
| Assets | Procedurally generated placeholders (replace with your own) |

---

## Game Jam

Built for a game jam around the theme **All or Nothing**. The wager mechanic is the direct translation of the theme — every upgrade system in the game is designed around a single high-stakes gamble that can either compound your power or strip you back to nothing.

---

## License

MIT — do whatever you want with it. Creidt is nice :)
