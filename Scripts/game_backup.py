# game.py  ─  Wand & Wager  ─  Main game state machine

import pygame
import random
import math
import os
import json

from constants import *
from player import Player
from ai import CPUController
from arena import Arena, MAPS_DIR
from spells import (Projectile, WallEntity, DashEffect, ShieldBuff,
                    TrapEntity, AoeEffect, BuffEffect, PullZone)
from vfx import VFXManager
from hud import HUD, FloatText, draw_text
from upgrade_screen import AllOrNothingScreen


# ─────────────────────────────────────────────────────────────────────────────
class CharSelectScreen:
    """Simple character-select before the match."""

    ELEMENTS = ["fire", "ice"]
    WAND_IDS = ["oak", "willow", "obsidian"]

    def __init__(self):
        self.font_sm   = pygame.font.SysFont("Segoe UI", 13)
        self.font_md   = pygame.font.SysFont("Segoe UI", 16)
        self.font_lg   = pygame.font.SysFont("Segoe UI", 24, bold=True)
        self.font_xl   = pygame.font.SysFont("Segoe UI", 36, bold=True)

        self.elem_idx  = 0
        self.wand_idx  = 0
        self.cpu_count = 1   # 1–3 CPUs
        self.difficulty= "medium"
        self.done      = False
        self.result    = {}  # filled on confirm
        self._age      = 0.0

    def update(self, dt):
        self._age += dt

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.elem_idx = (self.elem_idx - 1) % len(self.ELEMENTS)
            elif event.key == pygame.K_RIGHT:
                self.elem_idx = (self.elem_idx + 1) % len(self.ELEMENTS)
            elif event.key == pygame.K_UP:
                self.wand_idx = (self.wand_idx - 1) % len(self.WAND_IDS)
            elif event.key == pygame.K_DOWN:
                self.wand_idx = (self.wand_idx + 1) % len(self.WAND_IDS)
            elif event.key == pygame.K_q:
                self.cpu_count = max(1, self.cpu_count - 1)
            elif event.key == pygame.K_e:
                self.cpu_count = min(3, self.cpu_count + 1)
            elif event.key == pygame.K_d:
                diffs = ["easy", "medium", "hard"]
                self.difficulty = diffs[(diffs.index(self.difficulty) + 1) % 3]
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.result = {
                    "element":    self.ELEMENTS[self.elem_idx],
                    "wand":       self.WAND_IDS[self.wand_idx],
                    "cpu_count":  self.cpu_count,
                    "difficulty": self.difficulty,
                }
                self.done = True

    def draw(self, surf):
        sw, sh = BASE_W, BASE_H
        surf.fill(DARK_BG)

        # Animated background runes
        for i in range(8):
            a   = self._age * 0.3 + i * math.pi / 4
            r   = 260
            cx  = sw//2 + int(r * math.cos(a))
            cy  = sh//2 + int(r * math.sin(a) * 0.4)
            pygame.draw.circle(surf, (35, 28, 55), (cx, cy), 18 + i * 2)

        draw_text(surf, "WAND  &  WAGER", self.font_xl, GOLD, sw//2, 40, anchor="midtop")
        draw_text(surf, "Choose your wizard", self.font_md, TEXT_DIM, sw//2, 90, anchor="midtop")

        # Element selection
        ey  = 150
        for i, elem in enumerate(self.ELEMENTS):
            sel = i == self.elem_idx
            ex  = sw//2 - (len(self.ELEMENTS)-1)*120 + i * 240
            ec  = ELEM_COL[elem]
            r   = pygame.Rect(ex - 100, ey, 200, 120)
            bg  = (55, 46, 85) if sel else (30, 26, 50)
            pygame.draw.rect(surf, bg, r, border_radius=10)
            pygame.draw.rect(surf, ec if sel else BORDER_COL, r, 2, border_radius=10)
            draw_text(surf, elem.upper(), self.font_lg, ec, r.centerx, r.top + 20, anchor="midtop")

            spells = ELEMENT_SPELLS[elem]
            sy2 = r.top + 52
            for sp in spells:
                draw_text(surf, f"  • {SPELLS[sp]['name']}", self.font_sm, TEXT_DIM if not sel else TEXT_MAIN,
                          r.centerx, sy2, anchor="midtop")
                sy2 += 17

        draw_text(surf, "←  →  select element", self.font_sm, TEXT_DIM, sw//2, ey+130, anchor="midtop")

        # Wand selection
        wy    = 320
        wands = self.WAND_IDS
        for i, wid in enumerate(wands):
            sel = i == self.wand_idx
            wx  = sw//2 - (len(wands)-1)*130 + i * 260
            wd  = WANDS[wid]
            r   = pygame.Rect(wx - 120, wy, 240, 80)
            bg  = (55, 46, 85) if sel else (30, 26, 50)
            pygame.draw.rect(surf, bg, r, border_radius=8)
            pygame.draw.rect(surf, GOLD if sel else BORDER_COL, r, 1+(1 if sel else 0), border_radius=8)
            draw_text(surf, wd["name"], self.font_md, TEXT_MAIN if sel else TEXT_DIM,
                      r.centerx, r.top + 10, anchor="midtop")
            stats = f"DMG ×{wd['dmg']:.2f}  CAST ×{wd['cast']:.2f}  SIZE ×{wd['size']:.2f}"
            draw_text(surf, stats, self.font_sm, TEXT_DIM, r.centerx, r.top + 38, anchor="midtop")
            if wd.get("split"):
                draw_text(surf, "SPLIT shots", self.font_sm, HP_YELLOW, r.centerx, r.top+56, anchor="midtop")
            if wd.get("pierce"):
                draw_text(surf, "PIERCE walls", self.font_sm, HP_YELLOW, r.centerx, r.top+56, anchor="midtop")

        draw_text(surf, "↑  ↓  select wand", self.font_sm, TEXT_DIM, sw//2, wy+88, anchor="midtop")

        # CPU settings
        cy2  = 450
        draw_text(surf, f"CPU opponents:  {self.cpu_count}   [Q/E]",
                  self.font_md, TEXT_MAIN, sw//2, cy2, anchor="midtop")
        draw_text(surf, f"Difficulty:  {self.difficulty.upper()}   [D]",
                  self.font_md, TEXT_MAIN, sw//2, cy2 + 30, anchor="midtop")

        # Confirm
        pulse = 0.6 + 0.4 * abs(math.sin(self._age * 2))
        col   = tuple(int(c * pulse) for c in GOLD)
        draw_text(surf, "ENTER / SPACE  to begin", self.font_lg, col, sw//2, cy2 + 80, anchor="midtop")


# ─────────────────────────────────────────────────────────────────────────────
class Game:

    def __init__(self, screen):
        self.screen = screen
        # Note: clock is owned by main.py; game only holds a ref to the render surface

        self.state      = ST_CHAR_SELECT
        self.char_sel   = CharSelectScreen()

        self.players    = []
        self.cpus       = []    # CPUController list
        self.arena      = None
        self.hud        = HUD()

        self.projectiles   = []
        self.effects       = []    # walls, dashes, shields, traps, aoes
        self.float_texts   = []

        self.round_num     = 1
        self.round_time    = 0.0
        self.round_over_t  = 0.0
        self.round_winner  = None

        self.aon_screen    = None
        self._cam          = [0.0, 0.0]
        self.vfx           = VFXManager()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _load_arena(self):
        maps = [f for f in os.listdir(MAPS_DIR) if f.endswith(".json")]
        if not maps:
            # Fallback: generate a simple map in-memory
            data = self._default_map()
        else:
            path = os.path.join(MAPS_DIR, random.choice(maps))
            with open(path) as f:
                data = json.load(f)
        self.arena = Arena(data)

    def _default_map(self):
        cols, rows = 40, 22
        grid = [[0]*cols for _ in range(rows)]
        for c in range(cols):
            grid[rows-1][c] = 1
        for c, r, l in [(5,16,8),(15,14,6),(27,16,8),(10,11,10),(22,12,6),(14,6,12)]:
            for i in range(l):
                if c+i < cols:
                    grid[r][c+i] = 1
        return {"name":"default","cols":cols,"rows":rows,"tile_size":32,
                "grid":grid,
                "spawn_points":[[3,20],[36,20],[8,15],[32,15],[13,10],[26,10]]}

    def _start_match(self, cfg):
        self._load_arena()
        total    = 1 + cfg["cpu_count"]
        elements = [cfg["element"]] + [random.choice(["fire","ice"]) for _ in range(cfg["cpu_count"])]
        wands    = [cfg["wand"]]    + [random.choice(["oak","willow","obsidian"]) for _ in range(cfg["cpu_count"])]

        self.players = []
        for i in range(total):
            sx, sy = self.arena.get_spawn(i)
            p = Player(sx, sy, i, elements[i], wands[i])
            self.players.append(p)

        self.cpus = []
        for i in range(1, total):
            self.cpus.append(CPUController(self.players[i], cfg["difficulty"]))

        self.round_num   = 1
        self.round_time  = 0.0
        self.projectiles = []
        self.effects     = []
        self.float_texts = []
        self.state       = ST_COMBAT
        self.hud.announce(f"ROUND  {self.round_num}", GOLD, 2.0)

    def _start_round(self):
        self.round_time  = 0.0
        self.projectiles = []
        self.effects     = []
        self.float_texts = []
        self.vfx.clear()
        self.arena.safe_rect  = pygame.Rect(0,0, self.arena.width, self.arena.height)
        self.arena._shrinking = False

        for i, p in enumerate(self.players):
            sx, sy = self.arena.get_spawn(i)
            p.reset_for_round(sx, sy)

        self.state = ST_COMBAT
        self.hud.announce(f"ROUND  {self.round_num}", GOLD, 2.0)

    # ── Main loop (called from main.py) ──────────────────────────────────────

    def handle_events_and_update(self, events, dt):
        self._handle_events(events, dt)
        self._update(dt)

    # Legacy single-process run (for running game.py directly)
    def run(self):
        import sys
        from main import main
        main()

    # ── Event handling ────────────────────────────────────────────────────────

    def _handle_events(self, events, dt):
        if self.state == ST_CHAR_SELECT:
            for e in events:
                self.char_sel.handle_event(e)
            if self.char_sel.done:
                self._start_match(self.char_sel.result)

        elif self.state == ST_COMBAT:
            self._handle_combat_input(events)

        elif self.state == ST_ALL_OR_NOTHING:
            for e in events:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                    self.aon_screen.handle_space()
                self.aon_screen.handle_event(e)

        elif self.state == ST_MATCH_OVER:
            for e in events:
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    self.state = ST_CHAR_SELECT
                    self.char_sel = CharSelectScreen()

    def _handle_combat_input(self, events):
        if not self.players:
            return
        human = self.players[0]
        if not human.alive:
            return

        keys = pygame.key.get_pressed()
        mx, my = pygame.mouse.get_pos()
        cam    = self._cam

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            human.move_left()
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            human.move_right()
        if keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_SPACE]:
            human.jump()

        # Aim vector toward mouse
        world_mx = mx + cam[0]
        world_my = my + cam[1]
        ax = world_mx - human.cx
        ay = world_my - human.cy
        ln = math.hypot(ax, ay)
        if ln > 0:
            ax /= ln; ay /= ln
        else:
            ax, ay = float(human.facing), 0.0

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                slot = None
                if event.button == 1: slot = 0
                elif event.button == 3: slot = 1
                if slot is not None:
                    projs = human.try_cast(slot, ax, ay, self.effects)
                    self.projectiles.extend(projs)
            elif event.type == pygame.KEYDOWN:
                slot = None
                if event.key == pygame.K_q: slot = 2
                elif event.key == pygame.K_e: slot = 3
                if slot is not None:
                    projs = human.try_cast(slot, ax, ay, self.effects)
                    self.projectiles.extend(projs)

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self, dt):
        if self.state == ST_CHAR_SELECT:
            self.char_sel.update(dt)

        elif self.state == ST_COMBAT:
            self._update_combat(dt)

        elif self.state == ST_ROUND_OVER:
            self.round_over_t -= dt
            if self.round_over_t <= 0:
                self._enter_aon()

        elif self.state == ST_ALL_OR_NOTHING:
            self.aon_screen.update(dt)
            if self.aon_screen.done:
                self._post_aon()

        self.hud.update(dt)
        for ft in self.float_texts:
            ft.update(dt)
        self.float_texts = [ft for ft in self.float_texts if ft.alive]

    def _update_combat(self, dt):
        self.round_time += dt
        arena = self.arena

        # Update arena (shrink)
        arena.update(dt, self.round_time)

        # Player updates
        for p in self.players:
            p.update(dt, arena.platforms, arena.safe_rect)

        # OOB damage
        for p in self.players:
            if p.alive and not arena.is_in_safe_zone(p.x, p.y):
                dmg = OOB_DAMAGE * dt
                actual = p.take_damage(dmg)
                if actual > 0 and random.random() < 0.08:
                    self._add_float(p.cx, p.cy - 20, f"-{int(actual)}", HP_RED)

        # Platform hazard damage
        for p in self.players:
            if not p.alive:
                continue
            for plat in arena.platforms:
                if plat.dps > 0 and plat.rect.colliderect(p.feet):
                    dmg = plat.dps * dt
                    actual = p.take_damage(dmg)
                    if actual > 0 and random.random() < 0.05:
                        self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_RED)

        # CPU controllers
        for cpu in self.cpus:
            cpu.update(dt, self.players, self.projectiles, arena.platforms,
                       arena.safe_rect, self.effects)
            # Collect any projectiles the AI cast
            projs = []
            # (AIs call player.try_cast which goes through spawned_effects list we passed)

        # Projectile updates + collisions
        new_projs = []
        for proj in self.projectiles:
            if not proj.alive:
                continue
            proj.update(dt, arena.safe_rect)
            if not proj.alive:
                continue

            hit = False

            # vs players
            for p in self.players:
                if not p.alive or p.player_id == proj.owner_id:
                    continue
                if proj.collides_with(p):
                    owner = next((pl for pl in self.players if pl.player_id == proj.owner_id), None)
                    dmg   = proj.damage
                    actual = p.take_damage(dmg, owner)
                    if actual > 0:
                        self._add_float(p.cx, p.cy - 10, f"-{int(actual)}", HP_RED)
                        if proj.aoe_radius > 0:
                            self._aoe_splash(proj, p)
                        if proj.slow > 0:
                            p.apply_slow(proj.slow, proj.slow_dur)
                        if proj.debuff:
                            p.apply_debuff(proj.debuff, proj.debuff_dur)
                        if proj.blind_dur > 0:
                            p.apply_blind(proj.blind_dur)
                        # Knockback
                        if proj.knockback > 0:
                            kx = proj.vx / max(1, math.hypot(proj.vx, proj.vy))
                            ky = proj.vy / max(1, math.hypot(proj.vx, proj.vy))
                            p.vx += kx * proj.knockback
                            p.vy += ky * proj.knockback * 0.5
                    proj.alive = False
                    hit = True
                    break

            if hit:
                continue

            # vs walls
            for eff in self.effects:
                if not isinstance(eff, __import__('spells').WallEntity):
                    continue
                if not eff.alive:
                    continue
                if proj.collides_wall(eff):
                    if proj.pierce_walls:
                        eff.take_damage(proj.damage * 0.5)
                    else:
                        eff.take_damage(proj.damage)
                        proj.alive = False
                    break

        self.projectiles = [p for p in self.projectiles if p.alive]

        # Effects update
        from spells import WallEntity, DashEffect, ShieldBuff, TrapEntity, AoeEffect
        new_projs_from_walls = []
        for eff in self.effects:
            if not eff.alive:
                continue
            eff.update(dt)

            if isinstance(eff, WallEntity):
                # Wall DPS
                if eff.dps > 0:
                    for p in self.players:
                        if p.alive and p.player_id != eff.owner_id and eff.rect.colliderect(p.feet):
                            dmg = eff.dps * dt
                            actual = p.take_damage(dmg)
                            if actual > 0 and random.random() < 0.05:
                                self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_RED)
                # Combo wall spikes
                spikes = eff.emit_spikes()
                new_projs_from_walls.extend(spikes)

            elif isinstance(eff, DashEffect):
                for p in self.players:
                    if p.alive and eff.collides_player(p):
                        owner = next((pl for pl in self.players if pl.player_id == eff.player.player_id), None)
                        dmg   = eff.trail_dps * dt
                        actual = p.take_damage(dmg, owner)

            elif isinstance(eff, TrapEntity):
                for p in self.players:
                    if p.alive and p.player_id != eff.owner_id and not eff.triggered:
                        if eff.collides_player(p):
                            eff.triggered = True
                            eff.alive     = False
                            owner = next((pl for pl in self.players if pl.player_id == eff.owner_id), None)
                            actual = p.take_damage(eff.damage, owner)
                            p.apply_root(eff.root_dur)
                            if actual > 0:
                                self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_RED)

            elif isinstance(eff, AoeEffect):
                if eff.ready_to_hit():
                    for p in self.players:
                        if p.alive and p.player_id != eff.owner_id and eff.collides_player(p):
                            owner = next((pl for pl in self.players if pl.player_id == eff.owner_id), None)
                            actual = p.take_damage(eff.damage, owner)
                            if eff.slow > 0:
                                p.apply_slow(eff.slow, eff.slow_dur)
                            if actual > 0:
                                self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_RED)

        self.projectiles.extend(new_projs_from_walls)
        self.effects = [e for e in self.effects if e.alive]

        # Death detection
        for p in self.players:
            if not p.alive and p.elim_order == 0:
                alive_count = sum(1 for pl in self.players if pl.alive)
                p.elim_order = len(self.players) - alive_count
                self.hud.add_feed(f"P{p.player_id+1} eliminated!", ELEM_COL[p.element])

        # Check round end
        alive = [p for p in self.players if p.alive]
        if len(alive) <= 1:
            winner = alive[0] if alive else None
            self._end_round(winner)

        # Update camera toward centroid of alive players
        self._update_camera()

    def _aoe_splash(self, proj, hit_player):
        for p in self.players:
            if not p.alive or p == hit_player:
                continue
            dist = math.hypot(p.cx - proj.x, p.cy - proj.y)
            if dist < proj.aoe_radius:
                fall_off = 1.0 - dist / proj.aoe_radius
                owner = next((pl for pl in self.players if pl.player_id == proj.owner_id), None)
                dmg   = proj.aoe_damage * fall_off
                actual = p.take_damage(dmg, owner)
                if actual > 0:
                    self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_YELLOW)

    def _update_camera(self):
        alive = [p for p in self.players if p.alive]
        if not alive:
            return
        cx = sum(p.x for p in alive) / len(alive)
        cy = sum(p.y for p in alive) / len(alive)
        # Clamp camera so arena fits
        arena_w = self.arena.width
        arena_h = self.arena.height
        target_x = cx - SCREEN_W // 2
        target_y = cy - SCREEN_H // 2
        target_x = max(0, min(target_x, arena_w - SCREEN_W))
        target_y = max(0, min(target_y, arena_h - SCREEN_H))
        self._cam[0] += (target_x - self._cam[0]) * 0.06
        self._cam[1] += (target_y - self._cam[1]) * 0.06

    def _end_round(self, winner):
        if self.state != ST_COMBAT:
            return
        self.state        = ST_ROUND_OVER
        self.round_over_t = 2.5
        self.round_winner = winner

        if winner:
            winner.round_wins += 1
            self.hud.announce(f"P{winner.player_id+1}  WINS  ROUND  {self.round_num}!",
                              ELEM_COL[winner.element], 2.5)
            self.hud.add_feed(f"P{winner.player_id+1} wins round {self.round_num}", GOLD)
        else:
            self.hud.announce("DRAW!", WHITE, 2.5)

        # Check match winner
        for p in self.players:
            if p.round_wins >= ROUNDS_TO_WIN:
                self.round_over_t = 3.5
                self.state = ST_ROUND_OVER
                # Override to go to match over instead of AoN
                self._pending_match_winner = p
                return

        self._pending_match_winner = None

    def _enter_aon(self):
        if hasattr(self, "_pending_match_winner") and self._pending_match_winner:
            self.state = ST_MATCH_OVER
            return

        wid = self.round_winner.player_id if self.round_winner else 0

        def on_done(results):
            for pid, upgs in results.items():
                player = next((p for p in self.players if p.player_id == pid), None)
                if player:
                    for upg in upgs:
                        player.apply_upgrade(upg)
                        self.hud.add_feed(f"P{pid+1} +{upg['name']}", GOLD)

        self.aon_screen = AllOrNothingScreen(wid, self.players, on_done)
        self.state      = ST_ALL_OR_NOTHING

    def _post_aon(self):
        self.round_num += 1
        self._start_round()

    def _add_float(self, x, y, text, col):
        self.float_texts.append(FloatText(x, y, text, col))

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self):
        surf = self.screen
        cam  = tuple(self._cam)

        if self.state == ST_CHAR_SELECT:
            self.char_sel.draw(surf)

        elif self.state in (ST_COMBAT, ST_ROUND_OVER):
            self._draw_combat(surf, cam)
            if self.state == ST_ROUND_OVER:
                self._draw_round_over_overlay(surf)

        elif self.state == ST_ALL_OR_NOTHING:
            self._draw_combat(surf, cam)   # world behind
            self.aon_screen.draw(surf)

        elif self.state == ST_MATCH_OVER:
            self._draw_combat(surf, cam)
            self._draw_match_over(surf)

        pygame.display.flip()

    def _draw_combat(self, surf, cam):
        self.arena.draw(surf, cam)

        # Effects behind players
        from spells import DashEffect, TrapEntity
        for eff in self.effects:
            if isinstance(eff, (DashEffect, TrapEntity)):
                eff.draw(surf, cam)

        # Players
        for p in self.players:
            p.draw(surf, cam)
            p.draw_hud_nameplate(surf, cam, f"P{p.player_id+1}")

        # Wall effects on top
        from spells import WallEntity, ShieldBuff, AoeEffect
        for eff in self.effects:
            if isinstance(eff, (WallEntity, ShieldBuff, AoeEffect)):
                eff.draw(surf, cam)

        # Projectiles
        for proj in self.projectiles:
            proj.draw(surf, cam)

        # Float texts
        for ft in self.float_texts:
            ft.draw(surf, cam)

        # HUD
        self.hud.draw(surf, self.players, self.round_num, self.round_time,
                      self.arena._shrinking)

    def _draw_round_over_overlay(self, surf):
        sw, sh = surf.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        surf.blit(overlay, (0,0))

    def _draw_match_over(self, surf):
        sw, sh = surf.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((8, 6, 18, 210))
        surf.blit(overlay, (0,0))

        winner = getattr(self, "_pending_match_winner", None) or \
                 max(self.players, key=lambda p: p.round_wins)

        font_xl = pygame.font.SysFont("Segoe UI", 52, bold=True)
        font_lg = pygame.font.SysFont("Segoe UI", 26)
        font_md = pygame.font.SysFont("Segoe UI", 18)

        ec = ELEM_COL.get(winner.element, GOLD)
        draw_text(surf, f"P{winner.player_id+1}  WINS  THE  MATCH!", font_xl, ec,
                  sw//2, sh//2 - 80, anchor="center")

        # Scoreboard
        for i, p in enumerate(sorted(self.players, key=lambda p: -p.round_wins)):
            col = GOLD if p == winner else TEXT_DIM
            row = f"P{p.player_id+1}  {p.element.title():<12}  {p.round_wins} wins  +{int(p.damage_dealt)} dmg"
            draw_text(surf, row, font_lg, col, sw//2, sh//2 - 10 + i*34, anchor="midtop")

        pulse = 0.6 + 0.4 * abs(math.sin(pygame.time.get_ticks()/500))
        rcol  = tuple(int(c*pulse) for c in SILVER)
        draw_text(surf, "SPACE / R  to play again", font_md, rcol,
                  sw//2, sh//2 + 160, anchor="midtop")