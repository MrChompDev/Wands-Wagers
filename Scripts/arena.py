# arena.py  ─  Wand & Wager

import pygame
import json
import os
import random
from constants import *

MAPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Maps")

TILE_COLOURS = {
    1: ((75,  65, 115), (110, 95, 165)),   # platform
    2: ((160, 45,  30), (210, 80,  55)),   # hazard
    3: ((70, 150, 210), (110,195, 250)),   # ice
    4: ((55, 160,  80), (90, 210, 115)),   # bounce
}


class Platform:
    def __init__(self, rect, tile_id=1):
        self.rect    = rect
        self.tile_id = tile_id
        self.dps     = 12 if tile_id == 2 else 0    # hazard tiles deal dps
        self.bounce  = tile_id == 4

    @property
    def is_solid(self):
        return True


class Arena:
    def __init__(self, map_data):
        self.name       = map_data.get("name", "unnamed")
        self.cols       = map_data["cols"]
        self.rows       = map_data["rows"]
        self.tile_size  = map_data.get("tile_size", TILE_SIZE)
        self.grid       = map_data["grid"]
        self.spawn_pts  = map_data.get("spawn_points", [])
        self.map_data   = map_data

        self.width      = self.cols * self.tile_size
        self.height     = self.rows * self.tile_size

        # Build merged platforms
        self.platforms  = self._build_platforms()

        # Safe-zone rect (shrinks over time)
        self.full_rect  = pygame.Rect(0, 0, self.width, self.height)
        self.safe_rect  = pygame.Rect(0, 0, self.width, self.height)
        self._shrink_t  = 0.0
        self._shrinking = False

        # Background star field
        self._stars = [
            (random.randint(0, self.width), random.randint(0, self.height),
             random.uniform(0.4, 1.2))
            for _ in range(120)
        ]
        self._star_t = 0.0

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_platforms(self):
        """Merge horizontally-adjacent same-tile rows into single Platform rects."""
        platforms = []
        ts = self.tile_size
        for r in range(self.rows):
            c = 0
            while c < self.cols:
                tid = self.grid[r][c]
                if tid == 0:
                    c += 1
                    continue
                # Extend right as far as same tile type
                start_c = c
                while c < self.cols and self.grid[r][c] == tid:
                    c += 1
                rect = pygame.Rect(start_c * ts, r * ts, (c - start_c) * ts, ts)
                platforms.append(Platform(rect, tid))
        return platforms

    # ── Spawn points ──────────────────────────────────────────────────────────

    def get_spawn(self, idx):
        ts = self.tile_size
        if self.spawn_pts:
            sp = self.spawn_pts[idx % len(self.spawn_pts)]
            return (sp[0] * ts + ts // 2, sp[1] * ts)
        # Fallback: spread evenly along ground
        margin = self.width // 8
        x = margin + (self.width - margin * 2) * (idx / 7)
        return (int(x), self.height - self.tile_size)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt, round_time):
        self._star_t += dt * 0.3

        if round_time >= SHRINK_AFTER and not self._shrinking:
            self._shrinking = True

        if self._shrinking:
            shrink = SHRINK_RATE * dt
            self.safe_rect = self.safe_rect.inflate(-shrink * 2, -shrink * 2)
            # Clamp minimum size
            min_size = self.tile_size * 4
            if self.safe_rect.width < min_size:
                self.safe_rect.width  = min_size
                self.safe_rect.centerx = self.full_rect.centerx
            if self.safe_rect.height < min_size:
                self.safe_rect.height = min_size
                self.safe_rect.centery = self.full_rect.centery

    def is_in_safe_zone(self, x, y):
        return self.safe_rect.collidepoint(x, y)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf, cam):
        ox, oy = cam

        # Background
        surf.fill(DARK_BG)

        # Stars
        for sx, sy, br in self._stars:
            ssx = int(sx - ox * 0.08)
            ssy = int(sy - oy * 0.08)
            al  = int(80 + 60 * abs(math.sin(self._star_t + br)))
            r   = 1 if br < 0.8 else 2
            sw, sh = surf.get_size()
            pygame.draw.circle(surf, (al, al, al + 20), (ssx % sw, ssy % sh), r)

        # OOB danger zone (pulsing red border)
        if self._shrinking:
            pulse = int(40 + 30 * abs(math.sin(self._star_t * 3)))
            border_col = (160 + pulse, 30, 30, 80)
            sr = self.safe_rect.move(-int(ox), -int(oy))
            border_s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            # Fill everything red-ish, then cut out the safe zone
            border_s.fill((120, 20, 20, 40))
            pygame.draw.rect(border_s, (0, 0, 0, 0), sr)
            surf.blit(border_s, (0, 0))
            # Safe zone border glow
            pygame.draw.rect(surf, (200, 50, 50), sr, 2)

        # Tiles — use sprites, tiled across each platform rect
        ts = self.tile_size
        from Assets import Assets
        for plat in self.platforms:
            r   = plat.rect.move(-int(ox), -int(oy))
            tid = plat.tile_id
            # Get the tile sprite at the right size
            tile_img = Assets.tile(tid, ts)
            # Tile the sprite across the platform width
            tile_w = tile_img.get_width()
            tile_h = tile_img.get_height()
            cx = r.x
            while cx < r.right:
                draw_w = min(tile_w, r.right - cx)
                clip_r = pygame.Rect(0, 0, draw_w, tile_h)
                surf.blit(tile_img, (cx, r.y), clip_r)
                cx += tile_w

    def draw_foreground(self, surf, cam):
        """Draw grid overlay (debug mode only)."""
        pass

import math   # needed for star animation in draw()