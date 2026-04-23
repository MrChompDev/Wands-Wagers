# constants.py  ─  Wand & Wager

BASE_W, BASE_H   = 1280, 720
SCREEN_W, SCREEN_H = 1280, 720
FPS              = 60
TITLE            = "Wand & Wager"
TILE_SIZE        = 32

# ── Colours ───────────────────────────────────────────────────────────────────
BLACK      = (0,   0,   0)
WHITE      = (255, 255, 255)
DARK_BG    = (14,  12,  26)
PANEL_BG   = (22,  18,  40)
BORDER_COL = (60,  50,  90)
TEXT_MAIN  = (225, 215, 255)
TEXT_DIM   = (130, 120, 160)
HP_GREEN   = (70,  200, 90)
HP_YELLOW  = (220, 195, 50)
HP_RED     = (210, 55,  55)
GOLD       = (220, 170, 40)
SILVER     = (170, 170, 190)

ELEM_COL = {
    "fire":      (216, 90,  48),
    "ice":       (55,  138, 221),
    "lightning": (210, 185, 40),
    "earth":     (90,  160, 45),
    "wind":      (50,  195, 160),
    "shadow":    (127, 119, 221),
    "arcane":    (212, 83,  126),
}

ELEM_LABELS = {
    "fire":      "Pyromancer",
    "ice":       "Glacialist",
    "lightning": "Stormcaller",
    "earth":     "Terramancer",
    "wind":      "Zephyrist",
}

# ── Physics ───────────────────────────────────────────────────────────────────
GRAVITY       = 1150.0
GROUND_FRIC   = 0.70
AIR_FRIC      = 0.97
PLAYER_SPEED  = 245.0
PLAYER_JUMP   = -570.0
MAX_FALL      = 950.0
PLAYER_W      = 26
PLAYER_H      = 44

BASE_HP          = 200
SPAWN_INVINCIBLE = 1.8
ROUNDS_TO_WIN    = 3

SHRINK_AFTER  = 30.0
SHRINK_RATE   = 22.0
OOB_DAMAGE    = 20.0

# ── Wands ─────────────────────────────────────────────────────────────────────
WANDS = {
    "oak":      {"name": "Oak Wand",      "dmg": 1.00, "cast": 1.00, "size": 1.00, "pspd": 1.00},
    "willow":   {"name": "Willow Wand",   "dmg": 0.90, "cast": 1.20, "size": 1.00, "pspd": 1.00},
    "obsidian": {"name": "Obsidian Wand", "dmg": 1.25, "cast": 0.80, "size": 1.00, "pspd": 1.00},
    "crystal":  {"name": "Crystal Wand",  "dmg": 1.00, "cast": 1.00, "size": 1.30, "pspd": 0.85},
    "bone":     {"name": "Bone Wand",     "dmg": 0.80, "cast": 1.00, "size": 1.00, "pspd": 1.00, "split": True},
    "iron":     {"name": "Iron Wand",     "dmg": 1.00, "cast": 1.00, "size": 0.90, "pspd": 1.00, "pierce": True},
}

# ── Spells ────────────────────────────────────────────────────────────────────
# type: projectile | wall | combo_wall | dash | shield | trap | aoe | buff | melee_aoe | pull
SPELLS = {

    # ════════════════ FIRE ════════════════════════════════════════════════════
    "fireball": {
        "element":"fire", "name":"Fireball", "type":"projectile",
        "cooldown":0.85,  "damage":36,  "speed":430,   "radius":10,
        "color":(255,110,30), "glow":(255,60,0),
        "lifetime":2.8,   "knockback":210,
        "aoe_radius":52,  "aoe_damage":18,  "slow":0, "slow_dur":0,
        "sfx":"fireball",
    },
    "flame_wall": {
        "element":"fire", "name":"Flame Wall", "type":"wall",
        "cooldown":4.5,   "dps":18,     "width":16,    "height":112,
        "duration":4.0,   "wall_hp":9999,
        "color":(220,70,0), "glow":(255,140,0), "place_offset":55,
        "sfx":"wall_place",
    },
    "blaze_dash": {
        "element":"fire", "name":"Blaze Dash", "type":"dash",
        "cooldown":3.2,   "force":600,  "trail_dps":14,
        "trail_dur":2.0,  "trail_w":14, "color":(255,130,0),
        "sfx":"dash",
    },
    "ember_rain": {
        "element":"fire", "name":"Ember Rain", "type":"aoe",
        "cooldown":5.0,   "damage":22,  "radius":80,   "delay":0.7,
        "count":6, "color":(255,80,20), "sfx":"aoe_cast",
    },
    "ignite": {
        "element":"fire", "name":"Ignite", "type":"projectile",
        "cooldown":1.2,   "damage":8,   "speed":480,   "radius":7,
        "color":(255,200,0), "glow":(255,100,0),
        "lifetime":2.0,   "knockback":0,
        "aoe_radius":0,   "aoe_damage":0, "slow":0, "slow_dur":0,
        "debuff":"ignite", "debuff_dur":4.0, "sfx":"ignite",
    },

    # ════════════════ ICE ═════════════════════════════════════════════════════
    "ice_spike": {
        "element":"ice",  "name":"Ice Spike", "type":"projectile",
        "cooldown":0.60,  "damage":27,  "speed":590,   "radius":7,
        "color":(100,195,255), "glow":(60,160,240),
        "lifetime":2.4,   "knockback":75,
        "aoe_radius":0,   "aoe_damage":0, "slow":0.50, "slow_dur":2.0,
        "sfx":"ice_spike",
    },
    "frost_wall": {
        "element":"ice",  "name":"Frost Wall", "type":"wall",
        "cooldown":5.0,   "dps":0,      "width":16,    "height":115,
        "duration":6.0,   "wall_hp":80,
        "color":(130,200,255), "glow":(180,225,255), "place_offset":55,
        "sfx":"wall_place",
    },
    "blizzard": {
        "element":"ice",  "name":"Blizzard", "type":"aoe",
        "cooldown":5.5,   "damage":8,   "radius":90,   "delay":0.0,
        "count":8, "slow":0.45, "slow_dur":1.5,
        "color":(160,220,255), "sfx":"blizzard",
    },
    "glacial_shell": {
        "element":"ice",  "name":"Glacial Shell", "type":"shield",
        "cooldown":6.0,   "absorb":1,   "duration":2.0,
        "color":(180,230,255), "sfx":"shield",
    },
    "permafrost": {
        "element":"ice",  "name":"Permafrost", "type":"trap",
        "cooldown":4.0,   "damage":15,  "root_dur":1.6,
        "radius":18, "color":(80,160,220), "sfx":"trap_place",
    },

    # ════════════════ LIGHTNING ═══════════════════════════════════════════════
    "bolt": {
        "element":"lightning", "name":"Bolt", "type":"projectile",
        "cooldown":0.40,  "damage":22,  "speed":780,   "radius":5,
        "color":(240,230,80), "glow":(255,220,0),
        "lifetime":1.5,   "knockback":40,
        "aoe_radius":0,   "aoe_damage":0, "slow":0, "slow_dur":0,
        "sfx":"bolt",
    },
    "chain_lightning": {
        "element":"lightning", "name":"Chain Lightning", "type":"chain",
        "cooldown":1.4,   "damage":30,  "speed":500,   "radius":9,
        "color":(200,220,255), "glow":(160,200,255),
        "lifetime":1.2,   "knockback":80, "chain_count":2, "chain_range":140,
        "aoe_radius":0,   "aoe_damage":0, "slow":0, "slow_dur":0,
        "sfx":"chain_lightning",
    },
    "thunder_clap": {
        "element":"lightning", "name":"Thunder Clap", "type":"melee_aoe",
        "cooldown":2.8,   "damage":44,  "radius":90,
        "color":(230,230,120), "glow":(255,255,180),
        "stun_dur":0.7,   "knockback":320, "sfx":"thunder_clap",
    },
    "static_field": {
        "element":"lightning", "name":"Static Field", "type":"aoe",
        "cooldown":5.0,   "damage":6,   "radius":100,  "delay":0.0,
        "count":12, "slow":0.30, "slow_dur":0.6,
        "color":(200,215,255), "sfx":"aoe_cast",
    },
    "overcharge": {
        "element":"lightning", "name":"Overcharge", "type":"buff",
        "cooldown":9.0,   "duration":5.0,
        "dmg_bonus":0.25, "cast_bonus":0.20,
        "color":(255,245,100), "sfx":"overcharge",
    },

    # ════════════════ EARTH ═══════════════════════════════════════════════════
    "boulder_toss": {
        "element":"earth", "name":"Boulder Toss", "type":"projectile",
        "cooldown":1.4,   "damage":58,  "speed":260,   "radius":18,
        "color":(120,90,55), "glow":(160,130,80),
        "lifetime":3.0,   "knockback":460,
        "aoe_radius":48,  "aoe_damage":28, "slow":0, "slow_dur":0,
        "sfx":"boulder",
    },
    "stone_wall": {
        "element":"earth", "name":"Stone Wall", "type":"wall",
        "cooldown":5.5,   "dps":0,      "width":18,    "height":120,
        "duration":8.0,   "wall_hp":150,
        "color":(110,95,70), "glow":(150,130,100), "place_offset":55,
        "sfx":"wall_place",
    },
    "tremor": {
        "element":"earth", "name":"Tremor", "type":"melee_aoe",
        "cooldown":3.5,   "damage":30,  "radius":110,
        "color":(150,120,70), "glow":(190,160,100),
        "stun_dur":0.0,   "knockback":250, "sfx":"tremor",
    },
    "stalagmite": {
        "element":"earth", "name":"Stalagmite", "type":"trap",
        "cooldown":2.5,   "damage":35,  "root_dur":0.0,
        "radius":22, "color":(140,115,75), "sfx":"trap_place",
    },
    "iron_hide": {
        "element":"earth", "name":"Iron Hide", "type":"buff",
        "cooldown":7.0,   "duration":4.0,
        "dmg_reduction":0.40, "speed_penalty":0.15,
        "color":(160,150,130), "sfx":"shield",
    },

    # ════════════════ WIND ════════════════════════════════════════════════════
    "wind_blast": {
        "element":"wind",  "name":"Wind Blast", "type":"projectile",
        "cooldown":0.70,  "damage":16,  "speed":480,   "radius":14,
        "color":(100,220,190), "glow":(60,195,165),
        "lifetime":2.0,   "knockback":480,
        "aoe_radius":0,   "aoe_damage":0, "slow":0, "slow_dur":0,
        "sfx":"wind_blast",
    },
    "cyclone": {
        "element":"wind",  "name":"Cyclone", "type":"aoe",
        "cooldown":5.0,   "damage":10,  "radius":75,   "delay":0.0,
        "count":15, "slow":0, "slow_dur":0,
        "color":(80,210,175), "deflect":True, "sfx":"cyclone",
    },
    "gust_dash": {
        "element":"wind",  "name":"Gust Dash", "type":"dash",
        "cooldown":2.2,   "force":680,  "trail_dps":0,
        "trail_dur":0.5,  "trail_w":8,  "color":(100,220,190),
        "sfx":"dash",
    },
    "air_shield": {
        "element":"wind",  "name":"Air Shield", "type":"shield",
        "cooldown":4.5,   "absorb":2,   "duration":1.8,
        "color":(160,240,220), "sfx":"shield",
    },
    "vortex": {
        "element":"wind",  "name":"Vortex", "type":"pull",
        "cooldown":5.5,   "damage":8,   "radius":130,  "pull_force":280,
        "duration":2.5,
        "color":(60,195,165), "sfx":"cyclone",
    },

    # ════════════════ COMBOS ═════════════════════════════════════════════════
    "spiking_ice_wall": {
        "element":"ice",   "name":"Spiking Ice Wall", "type":"combo_wall",
        "cooldown":8.0,    "dps":0,      "width":16,    "height":115,
        "duration":6.0,    "wall_hp":100,
        "color":(100,195,255), "glow":(60,160,240), "place_offset":55,
        "fire_rate":1.2,   "spike_dmg":20, "spike_spd":500,
        "sfx":"wall_place",
    },
    "inferno_barrier": {
        "element":"fire",  "name":"Inferno Barrier", "type":"combo_wall",
        "cooldown":9.0,    "dps":22,     "width":16,    "height":112,
        "duration":5.0,    "wall_hp":9999,
        "color":(220,70,0), "glow":(255,140,0), "place_offset":55,
        "fire_rate":1.5,   "spike_dmg":28, "spike_spd":420,
        "sfx":"wall_place",
    },
    "steam_burst": {
        "element":"fire",  "name":"Steam Burst", "type":"projectile",
        "cooldown":1.6,    "damage":20,  "speed":380,   "radius":18,
        "color":(200,200,220), "glow":(160,180,200),
        "lifetime":1.8,    "knockback":100,
        "aoe_radius":65,   "aoe_damage":12, "slow":0, "slow_dur":0,
        "blind_dur":1.2,   "sfx":"fireball",
    },
    "frozen_thunder": {
        "element":"lightning", "name":"Frozen Thunder", "type":"projectile",
        "cooldown":1.8,    "damage":35,  "speed":620,   "radius":9,
        "color":(150,210,255), "glow":(100,180,255),
        "lifetime":2.0,    "knockback":60,
        "aoe_radius":0,    "aoe_damage":0, "slow":0.0, "slow_dur":0.0,
        "stun_dur":1.2,    "sfx":"chain_lightning",
    },
    "fire_tornado": {
        "element":"fire",  "name":"Fire Tornado", "type":"aoe",
        "cooldown":9.0,    "damage":18,  "radius":65,   "delay":0.0,
        "count":20, "slow":0, "slow_dur":0,
        "color":(255,100,20), "moving":True, "move_spd":120, "sfx":"aoe_cast",
    },
    "magma_wall": {
        "element":"fire",  "name":"Magma Wall", "type":"combo_wall",
        "cooldown":8.5,    "dps":28,     "width":16,    "height":120,
        "duration":5.5,    "wall_hp":9999,
        "color":(180,60,10), "glow":(240,100,0), "place_offset":55,
        "fire_rate":0,     "spike_dmg":0, "spike_spd":0,
        "floor_dps":16,    "sfx":"wall_place",
    },
}

# ── Spell combos ──────────────────────────────────────────────────────────────
COMBOS = {
    frozenset(["ice_spike",       "frost_wall"]):      "spiking_ice_wall",
    frozenset(["fireball",        "flame_wall"]):      "inferno_barrier",
    frozenset(["fireball",        "ice_spike"]):       "steam_burst",
    frozenset(["thunder_clap",    "ice_spike"]):       "frozen_thunder",
    frozenset(["wind_blast",      "fireball"]):        "fire_tornado",
    frozenset(["stone_wall",      "flame_wall"]):      "magma_wall",
}

# ── Default 3-spell loadouts ──────────────────────────────────────────────────
ELEMENT_SPELLS = {
    "fire":      ["fireball",      "flame_wall",    "blaze_dash"],
    "ice":       ["ice_spike",     "frost_wall",    "glacial_shell"],
    "lightning": ["bolt",          "chain_lightning","thunder_clap"],
    "earth":     ["boulder_toss",  "stone_wall",    "tremor"],
    "wind":      ["wind_blast",    "gust_dash",     "air_shield"],
}

# ── Upgrade pool ──────────────────────────────────────────────────────────────
UPGRADES = [
    {"id":"spell_power_1", "name":"Spell Power I",   "wv":1,"desc":"+10% spell damage",     "stat":"dmg_mult",        "amount":0.10},
    {"id":"spell_power_2", "name":"Spell Power II",  "wv":2,"desc":"+18% spell damage",     "stat":"dmg_mult",        "amount":0.18},
    {"id":"spell_power_3", "name":"Spell Power III", "wv":3,"desc":"+28% spell damage",     "stat":"dmg_mult",        "amount":0.28},
    {"id":"swift_cast",    "name":"Swift Cast",      "wv":2,"desc":"+15% cast speed",       "stat":"cast_mult",       "amount":0.15},
    {"id":"swift_cast_2",  "name":"Swift Cast II",   "wv":3,"desc":"+25% cast speed",       "stat":"cast_mult",       "amount":0.25},
    {"id":"spell_size",    "name":"Spell Size",      "wv":1,"desc":"+22% spell size",       "stat":"size_mult",       "amount":0.22},
    {"id":"extra_hp",      "name":"Extra HP",        "wv":2,"desc":"+35 max HP",            "stat":"max_hp",          "amount":35},
    {"id":"extra_hp_2",    "name":"Extra HP II",     "wv":3,"desc":"+55 max HP",            "stat":"max_hp",          "amount":55},
    {"id":"wall_breaker",  "name":"Wall Breaker",    "wv":3,"desc":"Spells pierce barriers","stat":"pierce_walls",    "amount":1},
    {"id":"multicast",     "name":"Multicast",       "wv":4,"desc":"20% chance cast twice", "stat":"multicast_chance","amount":0.20},
    {"id":"spell_bounce",  "name":"Spell Bounce",    "wv":3,"desc":"Projectiles bounce",    "stat":"bounce",          "amount":1},
    {"id":"chill_pulse",   "name":"Chill Pulse",     "wv":3,"desc":"All spells slow on hit","stat":"chill_all",       "amount":1},
    {"id":"life_steal",    "name":"Life Steal",      "wv":5,"desc":"8% damage as healing",  "stat":"life_steal",      "amount":0.08},
    {"id":"proj_speed",    "name":"Swift Spells",    "wv":2,"desc":"+20% projectile speed", "stat":"pspd_mult",       "amount":0.20},
]

BUST_THRESHOLD = 7

# ── Game states ───────────────────────────────────────────────────────────────
ST_CHAR_SELECT    = "char_select"
ST_COMBAT         = "combat"
ST_ROUND_OVER     = "round_over"
ST_ALL_OR_NOTHING = "all_or_nothing"
ST_MATCH_OVER     = "match_over"

# ── HUD ──────────────────────────────────────────────────────────────────────
HUD_H = 72   # pixels the HUD bar takes at the top of the screen