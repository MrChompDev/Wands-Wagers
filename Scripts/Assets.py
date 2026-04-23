# assets.py  ─  Wand & Wager  ─  Central asset manager
# Loads every image/sound once, serves them by key.
# All paths resolve relative to the project root (one level above Scripts/).

import pygame
import os

# ── Path helpers ──────────────────────────────────────────────────────────────
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT        = os.path.dirname(_SCRIPTS_DIR)

def _path(*parts):
    return os.path.join(_ROOT, "Assets", *parts)


# ── Wizard → player_id mapping ────────────────────────────────────────────────
WIZARD_BY_ID = {
    0: "Red_Wizard",
    1: "Blue_Wizard",
    2: "Green_Wizard",
    3: "Yellow_Wizard",
    4: "Orange_Wizard",
    5: "Pink_Wizard",
    6: "Aqua_Wizard",
    7: "Aqua_Wizard",
}

# Element accent fallback if no wizard sprite
WIZARD_BY_ELEMENT = {
    "fire":      "Red_Wizard",
    "ice":       "Aqua_Wizard",
    "lightning": "Yellow_Wizard",
    "earth":     "Green_Wizard",
    "wind":      "Blue_Wizard",
    "shadow":    "Pink_Wizard",
    "arcane":    "Pink_Wizard",
}

# Tile id → filename (no extension)
TILE_SPRITES = {
    1: "Tile_01",
    2: "Hazard",
    3: "Ice",
    4: "Bounce",
}


# ─────────────────────────────────────────────────────────────────────────────
class Assets:
    """
    Singleton-style asset store.
    Call Assets.load() once after pygame.init().
    Then get images via Assets.wizard(player_id), Assets.tile(tile_id), etc.
    """
    _wizards:   dict = {}   # name  → original Surface
    _tiles:     dict = {}   # tile_id → original Surface
    _wands:     dict = {}   # wand_id → original Surface
    _sounds:    dict = {}   # key → Sound
    _music:     list = []   # list of file paths
    _missing_surf = None    # fallback 1x1 transparent

    _loaded = False

    # ── Load ──────────────────────────────────────────────────────────────────

    @classmethod
    def load(cls):
        if cls._loaded:
            return
        cls._loaded = True
        cls._missing_surf = pygame.Surface((1, 1), pygame.SRCALPHA)

        cls._load_wizards()
        cls._load_tiles()
        cls._load_wands()
        cls._load_sounds()

    @classmethod
    def _load_image(cls, path, alpha=True):
        """Load image with graceful fallback if file missing."""
        if not os.path.exists(path):
            # Return a small coloured square so missing assets are visible
            s = pygame.Surface((32, 32), pygame.SRCALPHA)
            s.fill((200, 0, 200, 180))
            return s
        try:
            img = pygame.image.load(path)
            return img.convert_alpha() if alpha else img.convert()
        except Exception:
            s = pygame.Surface((32, 32), pygame.SRCALPHA)
            s.fill((200, 0, 200, 180))
            return s

    @classmethod
    def _load_wizards(cls):
        for wiz_name in WIZARD_BY_ID.values():
            if wiz_name not in cls._wizards:
                p = _path("Characters", wiz_name + ".png")
                cls._wizards[wiz_name] = cls._load_image(p)

    @classmethod
    def _load_tiles(cls):
        for tid, fname in TILE_SPRITES.items():
            p = _path("Tiles", fname + ".png")
            cls._tiles[tid] = cls._load_image(p)

    @classmethod
    def _load_wands(cls):
        from constants import WANDS
        for wid in WANDS:
            p = _path("Wands", wid + ".png")
            cls._wands[wid] = cls._load_image(p)

    @classmethod
    def _load_sounds(cls):
        sfx_dir = _path("SFX")
        if not os.path.isdir(sfx_dir):
            return
        for fname in os.listdir(sfx_dir):
            if fname.endswith((".wav", ".ogg", ".mp3")):
                key = os.path.splitext(fname)[0].lower()
                try:
                    cls._sounds[key] = pygame.mixer.Sound(os.path.join(sfx_dir, fname))
                except Exception:
                    pass

        music_dir = _path("Music")
        if os.path.isdir(music_dir):
            cls._music = [
                os.path.join(music_dir, f)
                for f in sorted(os.listdir(music_dir))
                if f.endswith((".ogg", ".mp3", ".wav"))
            ]

    # ── Getters ───────────────────────────────────────────────────────────────

    @classmethod
    def wizard(cls, player_id: int, target_w: int, target_h: int) -> pygame.Surface:
        """Return wizard sprite scaled to target_w × target_h."""
        name = WIZARD_BY_ID.get(player_id % 8, "Red_Wizard")
        return cls._scaled(cls._wizards.get(name, cls._missing_surf), target_w, target_h)

    @classmethod
    def wizard_by_element(cls, element: str, target_w: int, target_h: int) -> pygame.Surface:
        name = WIZARD_BY_ELEMENT.get(element, "Red_Wizard")
        return cls._scaled(cls._wizards.get(name, cls._missing_surf), target_w, target_h)

    @classmethod
    def wizard_raw(cls, player_id: int) -> pygame.Surface:
        """Return original unscaled wizard surface."""
        name = WIZARD_BY_ID.get(player_id % 8, "Red_Wizard")
        return cls._wizards.get(name, cls._missing_surf)

    @classmethod
    def tile(cls, tile_id: int, size: int) -> pygame.Surface:
        """Return tile sprite scaled to size × size."""
        src = cls._tiles.get(tile_id, cls._missing_surf)
        return cls._scaled(src, size, size)

    @classmethod
    def wand(cls, wand_id: str, target_w: int, target_h: int) -> pygame.Surface:
        src = cls._wands.get(wand_id, cls._missing_surf)
        return cls._scaled(src, target_w, target_h)

    @classmethod
    def play_sfx(cls, key: str, volume: float = 0.7):
        snd = cls._sounds.get(key.lower())
        if snd:
            snd.set_volume(volume)
            snd.play()

    @classmethod
    def start_music(cls, volume: float = 0.4):
        if not cls._music:
            return
        try:
            pygame.mixer.music.load(cls._music[0])
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(-1)
        except Exception:
            pass

    # ── Internal scale cache ──────────────────────────────────────────────────
    _scale_cache: dict = {}

    @classmethod
    def _scaled(cls, surf: pygame.Surface, w: int, h: int) -> pygame.Surface:
        if w <= 0 or h <= 0:
            return surf
        key = (id(surf), w, h)
        if key not in cls._scale_cache:
            cls._scale_cache[key] = pygame.transform.smoothscale(surf, (w, h))
        return cls._scale_cache[key]

    @classmethod
    def flush_scale_cache(cls):
        """Call after a window resize to clear stale scaled surfaces."""
        cls._scale_cache.clear()