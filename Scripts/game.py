# game.py  ─  Wand & Wager

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
from hud import HUD, FloatText, draw_text
from upgrade_screen import AllOrNothingScreen
from vfx import VFXManager


# ─────────────────────────────────────────────────────────────────────────────
#  Character Select
# ─────────────────────────────────────────────────────────────────────────────
class CharSelectScreen:

    ELEMENTS = ["fire", "ice", "lightning", "earth", "wind"]
    WAND_IDS = ["oak", "willow", "obsidian", "crystal", "bone", "iron"]
    DIFFS    = ["easy", "medium", "hard"]

    def __init__(self):
        self.font_sm  = pygame.font.SysFont("Segoe UI", 12)
        self.font_md  = pygame.font.SysFont("Segoe UI", 15)
        self.font_lg  = pygame.font.SysFont("Segoe UI", 20, bold=True)
        self.font_xl  = pygame.font.SysFont("Segoe UI", 34, bold=True)
        self.font_ttl = pygame.font.SysFont("Segoe UI", 46, bold=True)

        self.elem_idx = 0
        self.wand_idx = 0
        self.cpu_count = 1
        self.diff_idx  = 1   # medium
        self.done      = False
        self.result    = {}
        self._age      = 0.0

        # Mouse-hover state (set each frame in draw)
        self._elem_rects = []
        self._wand_rects = []

    def update(self, dt):
        self._age += dt

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            k = event.key
            if   k == pygame.K_LEFT:  self.elem_idx = (self.elem_idx - 1) % len(self.ELEMENTS)
            elif k == pygame.K_RIGHT: self.elem_idx = (self.elem_idx + 1) % len(self.ELEMENTS)
            elif k == pygame.K_UP:    self.wand_idx = (self.wand_idx - 1) % len(self.WAND_IDS)
            elif k == pygame.K_DOWN:  self.wand_idx = (self.wand_idx + 1) % len(self.WAND_IDS)
            elif k == pygame.K_q:     self.cpu_count = max(1, self.cpu_count - 1)
            elif k == pygame.K_e:     self.cpu_count = min(7, self.cpu_count + 1)
            elif k == pygame.K_d:     self.diff_idx  = (self.diff_idx + 1) % 3
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                self._confirm()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = pygame.mouse.get_pos()
            for i, r in enumerate(self._elem_rects):
                if r.collidepoint(mx, my):
                    self.elem_idx = i
            for i, r in enumerate(self._wand_rects):
                if r.collidepoint(mx, my):
                    self.wand_idx = i

    def _confirm(self):
        self.result = {
            "element":    self.ELEMENTS[self.elem_idx],
            "wand":       self.WAND_IDS[self.wand_idx],
            "cpu_count":  self.cpu_count,
            "difficulty": self.DIFFS[self.diff_idx],
        }
        self.done = True

    def draw(self, surf):
        sw, sh = BASE_W, BASE_H
        surf.fill(DARK_BG)

        # ── Animated starfield ────────────────────────────────────────────
        for i in range(80):
            sx = (i * 173 + int(self._age * 8  * (1 + i%3))) % sw
            sy = (i * 97  + int(self._age * 4  * (1 + i%2))) % sh
            r  = 1 + (i % 3 == 0)
            pygame.draw.circle(surf, (60 + i % 60, 55 + i%50, 90 + i%60), (sx, sy), r)

        # Rotating glow orbs
        elem = self.ELEMENTS[self.elem_idx]
        ec   = ELEM_COL[elem]
        for i in range(3):
            a  = self._age * 0.4 + i * math.tau / 3
            rx = sw//2 + int(math.cos(a) * 340)
            ry = sh//2 + int(math.sin(a) * 160)
            gs = pygame.Surface((120, 120), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*ec, 18), (60, 60), 60)
            surf.blit(gs, (rx - 60, ry - 60))

        # ── Title ─────────────────────────────────────────────────────────
        draw_text(surf, "WAND & WAGER", self.font_ttl, GOLD, sw//2, 22, anchor="midtop")
        draw_text(surf, "Build your wizard  ·  Fight  ·  Wager everything",
                  self.font_md, TEXT_DIM, sw//2, 76, anchor="midtop")

        # ── Element cards ─────────────────────────────────────────────────
        n      = len(self.ELEMENTS)
        card_w = 196
        gap    = 14
        total  = n * card_w + (n-1) * gap
        start  = sw//2 - total//2
        self._elem_rects = []
        mx_now, my_now = pygame.mouse.get_pos()

        for i, el in enumerate(self.ELEMENTS):
            sel   = (i == self.elem_idx)
            hover = not sel and pygame.Rect(start + i*(card_w+gap), 105, card_w, 210).collidepoint(mx_now, my_now)
            elc   = ELEM_COL[el]
            label = ELEM_LABELS[el]
            rx    = start + i * (card_w + gap)
            ry    = 105
            r     = pygame.Rect(rx, ry, card_w, 210)
            self._elem_rects.append(r)

            # Card bg
            bg = (52, 42, 82) if sel else ((38, 32, 62) if hover else (26, 22, 44))
            pygame.draw.rect(surf, bg, r, border_radius=11)

            # Glowing border when selected
            border_w = 2 if sel else 1
            bcol = elc if sel else ((80,70,110) if hover else (50,42,78))
            pygame.draw.rect(surf, bcol, r, border_w, border_radius=11)

            # Element colour top strip
            strip = pygame.Rect(rx, ry, card_w, 5)
            pygame.draw.rect(surf, elc, strip, border_radius=2)

            # Wizard preview sprite
            from Assets import Assets
            wiz_img = Assets.wizard_by_element(el, 54, 88)
            if i != self.elem_idx:
                dim = wiz_img.copy(); dim.set_alpha(140); wiz_img = dim
            surf.blit(wiz_img, wiz_img.get_rect(midtop=(rx + card_w//2, ry + 12)))

            # Class name
            draw_text(surf, label, self.font_md, elc if sel else TEXT_DIM,
                      rx + card_w//2, ry + 108, anchor="midtop")

            # Spell list
            spells = ELEMENT_SPELLS[el]
            sy2 = ry + 132
            for sp in spells:
                sname = SPELLS[sp]["name"]
                tcol  = TEXT_MAIN if sel else TEXT_DIM
                draw_text(surf, f"• {sname}", self.font_sm, tcol,
                          rx + 10, sy2)
                sy2 += 16

            # Combo badge
            combo_name = None
            spell_set = frozenset(spells)
            for ck, cv in COMBOS.items():
                if ck.issubset(spell_set):
                    combo_name = SPELLS[cv]["name"]
                    break
            if combo_name:
                cx_badge = rx + card_w//2
                badge_r  = pygame.Rect(rx + 8, ry + 182, card_w - 16, 20)
                pygame.draw.rect(surf, (40, 30, 60), badge_r, border_radius=4)
                pygame.draw.rect(surf, GOLD, badge_r, 1, border_radius=4)
                draw_text(surf, f"⚡ {combo_name}", self.font_sm, GOLD,
                          badge_r.centerx, badge_r.centery, anchor="center")

            # Selected tick
            if sel:
                tick_r = pygame.Rect(rx + card_w - 22, ry + 6, 16, 16)
                pygame.draw.rect(surf, elc, tick_r, border_radius=4)
                draw_text(surf, "✓", self.font_sm, DARK_BG, tick_r.centerx, tick_r.centery, anchor="center")

        draw_text(surf, "← → or click to choose element",
                  self.font_sm, TEXT_DIM, sw//2, 322, anchor="midtop")

        # ── Wand row ──────────────────────────────────────────────────────
        draw_text(surf, "WAND", self.font_lg, TEXT_DIM, sw//2, 348, anchor="midtop")
        nw     = len(self.WAND_IDS)
        wcard  = 170
        wgap   = 10
        wtotal = nw * wcard + (nw-1) * wgap
        wstart = sw//2 - wtotal//2
        self._wand_rects = []

        for i, wid in enumerate(self.WAND_IDS):
            wd   = WANDS[wid]
            sel  = (i == self.wand_idx)
            r    = pygame.Rect(wstart + i*(wcard+wgap), 374, wcard, 84)
            self._wand_rects.append(r)
            hover = not sel and r.collidepoint(mx_now, my_now)

            bg = (52, 42, 82) if sel else ((38, 32, 62) if hover else (26, 22, 44))
            pygame.draw.rect(surf, bg, r, border_radius=8)
            pygame.draw.rect(surf, (GOLD if sel else (50,42,78)), r, (2 if sel else 1), border_radius=8)

            # Wand sprite
            from Assets import Assets
            wand_img = Assets.wand(wid, 44, 11)
            surf.blit(wand_img, wand_img.get_rect(midtop=(r.centerx, r.top + 6)))

            draw_text(surf, wd["name"], self.font_sm, TEXT_MAIN if sel else TEXT_DIM,
                      r.centerx, r.top + 22, anchor="midtop")
            stats = f"×{wd['dmg']:.1f}dmg  ×{wd['cast']:.1f}spd"
            draw_text(surf, stats, self.font_sm, TEXT_DIM, r.centerx, r.top + 40, anchor="midtop")

            special = ("SPLIT" if wd.get("split") else ("PIERCE" if wd.get("pierce") else ""))
            if special:
                draw_text(surf, special, self.font_sm, HP_YELLOW, r.centerx, r.top + 58, anchor="midtop")

        draw_text(surf, "↑ ↓ or click to choose wand",
                  self.font_sm, TEXT_DIM, sw//2, 466, anchor="midtop")

        # ── Match settings ────────────────────────────────────────────────
        sy3 = 492
        diff_cols = {"easy": HP_GREEN, "medium": HP_YELLOW, "hard": HP_RED}
        diff_label = self.DIFFS[self.diff_idx].upper()
        diff_col   = diff_cols[self.DIFFS[self.diff_idx]]

        # CPU count buttons
        btn_y = sy3
        for adj, label, bx in [(-1, "−", sw//2 - 120), (+1, "+", sw//2 + 80)]:
            br = pygame.Rect(bx, btn_y, 36, 30)
            hov = br.collidepoint(mx_now, my_now)
            pygame.draw.rect(surf, (50,42,78) if hov else (34,28,55), br, border_radius=6)
            pygame.draw.rect(surf, BORDER_COL, br, 1, border_radius=6)
            draw_text(surf, label, self.font_lg, TEXT_MAIN, br.centerx, br.centery, anchor="center")

        draw_text(surf, f"CPU opponents:  {self.cpu_count}   [Q/E]",
                  self.font_md, TEXT_MAIN, sw//2, btn_y + 6, anchor="midtop")

        sy3 += 38
        draw_text(surf, f"Difficulty:  ", self.font_md, TEXT_DIM, sw//2 - 60, sy3 + 6, anchor="midtop")
        draw_text(surf, diff_label, self.font_md, diff_col, sw//2 + 30, sy3 + 6, anchor="midtop")
        draw_text(surf, "[D]", self.font_sm, TEXT_DIM, sw//2 + 90, sy3 + 10, anchor="midtop")

        # ── Start button ──────────────────────────────────────────────────
        pulse   = 0.75 + 0.25 * abs(math.sin(self._age * 2.2))
        btn_col = tuple(int(c * pulse) for c in ec)
        start_r = pygame.Rect(sw//2 - 140, 570, 280, 50)
        hover_start = start_r.collidepoint(mx_now, my_now)
        pygame.draw.rect(surf, (60, 50, 95) if hover_start else (40, 32, 65), start_r, border_radius=10)
        pygame.draw.rect(surf, btn_col, start_r, 2, border_radius=10)
        draw_text(surf, "START MATCH   ↵", self.font_lg, btn_col,
                  start_r.centerx, start_r.centery, anchor="center")

        if hover_start and pygame.mouse.get_pressed()[0]:
            self._confirm()

        # Controls footer
        draw_text(surf, "WASD / Arrows  move    Space  jump    1 / 2 / 3 / 4  cast spells    Mouse  aim",
                  self.font_sm, TEXT_DIM, sw//2, sh - 18, anchor="midbottom")


# ─────────────────────────────────────────────────────────────────────────────
#  Game
# ─────────────────────────────────────────────────────────────────────────────
class Game:

    def __init__(self, screen, net=None, match_data=None, my_id=0):
        self.screen   = screen
        self.net      = net        # NetworkClient | None
        self.my_id    = my_id      # local player_id (0 in solo)
        self._online  = net is not None

        if self._online and match_data:
            # Skip char select, go straight to combat with server-provided data
            self.state    = ST_COMBAT
            self._setup_online_match(match_data)
        else:
            self.state    = ST_CHAR_SELECT

        self.char_sel   = CharSelectScreen()

        self.players    = []
        self.cpus       = []
        self.arena      = None
        self.hud        = HUD()
        self.vfx        = VFXManager()

        self.projectiles   = []
        self.effects       = []
        self.float_texts   = []

        self.round_num     = 1
        self.round_time    = 0.0
        self.round_over_t  = 0.0
        self.round_winner  = None
        self.aon_screen    = None
        self._cam          = [0.0, 0.0]
        self._pending_match_winner = None

        # Pre-build fonts used in match-over screen
        self._fxl = pygame.font.SysFont("Segoe UI", 48, bold=True)
        self._flg = pygame.font.SysFont("Segoe UI", 26)
        self._fmd = pygame.font.SysFont("Segoe UI", 18)

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _load_arena(self):
        maps = [f for f in os.listdir(MAPS_DIR) if f.endswith(".json")]
        if maps:
            path = os.path.join(MAPS_DIR, random.choice(maps))
            with open(path) as f:
                data = json.load(f)
        else:
            data = self._default_map()
        self.arena = Arena(data)

    @staticmethod
    def _default_map():
        cols, rows = 40, 22
        grid = [[0]*cols for _ in range(rows)]
        for c in range(cols): grid[rows-1][c] = 1
        for c,r,l in [(5,16,8),(15,14,6),(27,16,8),(10,11,10),(22,12,6),(14,6,12)]:
            for i in range(l):
                if c+i < cols: grid[r][c+i] = 1
        return {"name":"default","cols":cols,"rows":rows,"tile_size":32,
                "grid":grid,"spawn_points":[[3,20],[36,20],[8,15],[32,15],[13,10],[26,10]]}

    # ── Online match setup ────────────────────────────────────────────────────

    def _setup_online_match(self, match_data):
        self._load_arena()
        self.players = []
        self.cpus    = []
        for cfg in match_data.get("players", []):
            sx, sy = self.arena.get_spawn(cfg["id"] % 8)
            p = Player(sx, sy, cfg["id"], cfg["element"], cfg["wand"])
            self.players.append(p)
        self._reset_round_state()
        self.round_num = 1
        self.hud.announce("ROUND  1", GOLD, 2.0)

    def _handle_net_messages(self, msgs):
        for m in msgs:
            t = m.get("type")
            if t == "state":
                for pd in m.get("players", []):
                    p = self._get_player(pd["id"])
                    if p and pd["id"] != self.my_id:
                        p.x  += (pd["x"]  - p.x)  * 0.3
                        p.y  += (pd["y"]  - p.y)  * 0.3
                        p.vx  = pd["vx"]; p.vy = pd["vy"]
                        p.hp  = pd["hp"]; p.alive = pd["alive"]
                        p.facing = pd.get("facing", p.facing)
                        p.shield_hits = pd.get("shield", 0)
                        p.slow_factor = pd.get("slow", 1.0)
                        p.root_timer  = pd.get("root", 0.0)
                        p.debuffs     = pd.get("debuffs", {})
            elif t == "round_over":
                wid = m.get("winner_id", -1)
                w   = self._get_player(wid)
                if w: w.round_wins += 1
                self.hud.announce(
                    f"P{wid+1}  WINS  ROUND  {m.get(chr(39)+'round_num'+chr(39), self.round_num)}!",
                    ELEM_COL.get(w.element if w else "fire", GOLD), 2.8)
                self.state = ST_ROUND_OVER
                self.round_over_t = 2.8
            elif t == "aon_start":
                self._enter_aon_online(m)
            elif t == "aon_result":
                self._apply_aon_results(m.get("results", {}))
            elif t == "match_over":
                self._pending_match_winner = self._get_player(m.get("winner_id",-1))
                self.state = ST_MATCH_OVER
            elif t == "chat":
                self.hud.add_feed(f"P{m.get(chr(39)+'pid'+chr(39),0)+1}: {m.get(chr(39)+'text'+chr(39),chr(39)+chr(39))}", TEXT_DIM)

    def _enter_aon_online(self, aon_msg):
        wid = aon_msg.get("round_winner", 0)
        def on_done(results):
            if self.net:
                my = results.get(self.my_id, {})
                self.net.send_aon_decision(
                    decision=my.get("decision", "hold"),
                    pick=my.get("pick"))
        self.aon_screen = AllOrNothingScreen(wid, self.players, on_done)
        self.state      = ST_ALL_OR_NOTHING

    def _apply_aon_results(self, results):
        for pid_str, data in results.items():
            player = self._get_player(int(pid_str))
            if not player: continue
            if data.get("wipe"):
                player.upgrades.clear()
                wd = WANDS.get(player.wand_id, {})
                player.dmg_mult = wd.get("dmg",1.0); player.cast_mult = wd.get("cast",1.0)
                player.size_mult = wd.get("size",1.0); player.pspd_mult = wd.get("pspd",1.0)
                player.multicast_chance = 0.0; player.life_steal = 0.0
                self.hud.add_feed(f"P{int(pid_str)+1} lost all upgrades!", HP_RED)
            for upg in data.get("upgrades", []):
                player.apply_upgrade(upg)
                self.hud.add_feed(f"P{int(pid_str)+1} +{upg[chr(39)+'name'+chr(39)]}", GOLD)
        self.round_num += 1
        self._start_round()

    def _start_match(self, cfg):
        self._load_arena()
        total = 1 + cfg["cpu_count"]

        cpu_elements = random.choices(list(ELEMENT_SPELLS.keys()), k=cfg["cpu_count"])
        cpu_wands    = random.choices(list(WANDS.keys()),           k=cfg["cpu_count"])

        elements = [cfg["element"]] + cpu_elements
        wands    = [cfg["wand"]]    + cpu_wands

        self.players = []
        for i in range(total):
            sx, sy = self.arena.get_spawn(i)
            self.players.append(Player(sx, sy, i, elements[i], wands[i]))

        self.cpus = [
            CPUController(self.players[i], cfg["difficulty"])
            for i in range(1, total)
        ]

        self.round_num = 1
        self._reset_round_state()
        self.state = ST_COMBAT
        self.hud.announce(f"ROUND  {self.round_num}", GOLD, 2.0)

    def _start_round(self):
        self._reset_round_state()
        for i, p in enumerate(self.players):
            sx, sy = self.arena.get_spawn(i)
            p.reset_for_round(sx, sy)
        self.state = ST_COMBAT
        self.hud.announce(f"ROUND  {self.round_num}", GOLD, 2.0)

    def _reset_round_state(self):
        self.round_time  = 0.0
        self.projectiles = []
        self.effects     = []
        self.float_texts = []
        self.vfx.clear()
        if self.arena:
            self.arena.safe_rect  = pygame.Rect(0, 0, self.arena.width, self.arena.height)
            self.arena._shrinking = False

    # ── Main entry called by main.py ──────────────────────────────────────────

    def handle_events_and_update(self, events, dt, net_msgs=None):
        self._handle_events(events, dt)
        if net_msgs:
            self._handle_net_messages(net_msgs)
        self._update(dt)

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
        cam = self._cam
        keys = pygame.key.get_pressed()

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  human.move_left()
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: human.move_right()
        if keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_SPACE]: human.jump()

        # Aim toward mouse in world space
        wmx = pygame.mouse.get_pos()[0] + cam[0]
        wmy = pygame.mouse.get_pos()[1] + cam[1]
        ax, ay = wmx - human.cx, wmy - human.cy
        ln = math.hypot(ax, ay)
        if ln > 0: ax /= ln; ay /= ln
        else:      ax, ay = float(human.facing), 0.0

        for event in events:
            if event.type == pygame.KEYDOWN:
                slot = {pygame.K_1: 0, pygame.K_2: 1,
                        pygame.K_3: 2, pygame.K_4: 3}.get(event.key)
                if slot is not None:
                    self.projectiles.extend(human.try_cast(slot, ax, ay, self.effects))

        # Online: send our input to the server every frame
        if self._online and self.net:
            pressed = pygame.key.get_pressed()
            casts   = []
            for ev in events:
                if ev.type == pygame.KEYDOWN:
                    s = {pygame.K_1:0,pygame.K_2:1,pygame.K_3:2,pygame.K_4:3}.get(ev.key)
                    if s is not None: casts.append(s)
            self.net.send_input(
                left=bool(pressed[pygame.K_a] or pressed[pygame.K_LEFT]),
                right=bool(pressed[pygame.K_d] or pressed[pygame.K_RIGHT]),
                jump=bool(pressed[pygame.K_w] or pressed[pygame.K_UP] or pressed[pygame.K_SPACE]),
                casts=casts, aim_x=ax, aim_y=ay)

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self, dt):
        if   self.state == ST_CHAR_SELECT:    self.char_sel.update(dt)
        elif self.state in (ST_COMBAT, ST_ROUND_OVER): self._update_combat(dt)
        elif self.state == ST_ROUND_OVER:
            self.round_over_t -= dt
            if self.round_over_t <= 0: self._enter_aon()
        elif self.state == ST_ALL_OR_NOTHING:
            self.aon_screen.update(dt)
            if self.aon_screen.done: self._post_aon()

        self.hud.update(dt)
        self.vfx.update(dt)
        for ft in self.float_texts: ft.update(dt)
        self.float_texts = [ft for ft in self.float_texts if ft.alive]

    def _update_combat(self, dt):
        if self.state == ST_ROUND_OVER:
            self.round_over_t -= dt
            if self.round_over_t <= 0:
                self._enter_aon()
            return

        self.round_time += dt
        arena = self.arena
        arena.update(dt, self.round_time)

        # ── Player physics ────────────────────────────────────────────────
        for p in self.players:
            p.update(dt, arena.platforms, arena.safe_rect)

        # ── OOB damage ────────────────────────────────────────────────────
        for p in self.players:
            if p.alive and not arena.is_in_safe_zone(p.x, p.y):
                dmg = OOB_DAMAGE * dt
                actual = p.take_damage(dmg)
                if actual > 0 and random.random() < 0.12:
                    self.vfx.emit_hit_spark(p.cx, p.cy, HP_RED, 4)
                    self._add_float(p.cx, p.cy - 20, f"-{int(actual)}", HP_RED)

        # ── Hazard tile damage ────────────────────────────────────────────
        for p in self.players:
            if not p.alive: continue
            for plat in arena.platforms:
                if plat.dps > 0 and plat.rect.colliderect(p.feet):
                    actual = p.take_damage(plat.dps * dt)
                    if actual > 0 and random.random() < 0.06:
                        self.vfx.emit_fire_burst(p.cx, p.y, 4)
                        self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_RED)

        # ── CPU ai ────────────────────────────────────────────────────────
        for cpu in self.cpus:
            cpu.update(dt, self.players, self.projectiles,
                       arena.platforms, arena.safe_rect, self.effects)

        # ── Projectile physics + collision ───────────────────────────────
        new_projs = []
        for proj in self.projectiles:
            if not proj.alive: continue
            proj.update(dt, arena.safe_rect)
            if not proj.alive:
                self.vfx.emit_trail(proj.x, proj.y, proj.color, 2)
                continue

            # Trail VFX while flying
            if random.random() < 0.4:
                self.vfx.emit_trail(proj.x, proj.y, proj.glow_col, 2)

            hit = False

            # vs players
            for p in self.players:
                if not p.alive or p.player_id == proj.owner_id: continue
                if not proj.collides_with(p): continue

                owner  = self._get_player(proj.owner_id)
                actual = p.take_damage(proj.damage, owner)

                if actual > 0:
                    # VFX
                    ec = ELEM_COL.get(SPELLS.get(proj.spell_id, {}).get("element","fire"), (255,100,30))
                    self.vfx.emit_impact(proj.x, proj.y, ec, 16)
                    if proj.aoe_radius > 0:
                        self.vfx.emit_explosion(proj.x, proj.y, ec, 28)
                        self._aoe_splash(proj, p)
                    self._add_float(p.cx, p.cy - 14, f"-{int(actual)}", HP_RED)
                    self.vfx.emit_hit_spark(p.cx, p.cy, ec, 6)

                    # Status effects
                    if proj.slow > 0:      p.apply_slow(proj.slow, proj.slow_dur)
                    if proj.debuff:        p.apply_debuff(proj.debuff, proj.debuff_dur)
                    if proj.blind_dur > 0: p.apply_blind(proj.blind_dur)
                    if getattr(proj, "stun_dur", 0) > 0: p.apply_root(proj.stun_dur)

                    # Knockback
                    if proj.knockback > 0:
                        ln = math.hypot(proj.vx, proj.vy) or 1
                        p.vx += (proj.vx/ln) * proj.knockback
                        p.vy += (proj.vy/ln) * proj.knockback * 0.5

                    # Shield absorb VFX
                    if p.shield_hits == 0 and actual == 0:
                        self.vfx.emit_shield_pop(p.cx, p.cy, (180,230,255))

                    # Chain lightning arc
                    chain_count = getattr(proj, "chain_count", 0)
                    chain_range = getattr(proj, "chain_range", 0)
                    if chain_count > 0:
                        new_projs += self._chain_arc(proj, p, chain_count, chain_range)

                proj.alive = False
                hit = True
                break

            if hit: continue

            # vs walls
            for eff in self.effects:
                if not isinstance(eff, WallEntity) or not eff.alive: continue
                if proj.collides_wall(eff):
                    if proj.pierce_walls:
                        eff.take_damage(proj.damage * 0.5)
                    else:
                        eff.take_damage(proj.damage)
                        self.vfx.emit_impact(proj.x, proj.y, eff.color, 10)
                        proj.alive = False
                    break

        self.projectiles = [p for p in self.projectiles if p.alive]
        self.projectiles += new_projs

        # ── Effects update ────────────────────────────────────────────────
        wall_spikes = []
        for eff in self.effects:
            if not eff.alive: continue
            eff.update(dt)

            if isinstance(eff, WallEntity):
                # Wall DPS to players touching it
                if eff.dps > 0:
                    for p in self.players:
                        if p.alive and p.player_id != eff.owner_id and eff.rect.colliderect(p.feet):
                            actual = p.take_damage(eff.dps * dt)
                            if actual > 0 and random.random() < 0.08:
                                self.vfx.emit_fire_burst(p.cx, p.y, 3)
                # Combo wall auto-spikes
                wall_spikes += eff.emit_spikes()
                # Continuous flame VFX
                if random.random() < 0.15:
                    self.vfx.emit_fire_burst(
                        random.randint(eff.rect.left, eff.rect.right),
                        eff.rect.top, 2)

            elif isinstance(eff, DashEffect):
                for p in self.players:
                    if p.alive and eff.collides_player(p):
                        owner  = self._get_player(eff.player.player_id)
                        actual = p.take_damage(eff.trail_dps * dt, owner)
                        if actual > 0:
                            self.vfx.emit_hit_spark(p.cx, p.cy, eff.color, 3)

            elif isinstance(eff, TrapEntity):
                for p in self.players:
                    if p.alive and p.player_id != eff.owner_id and not eff.triggered:
                        if eff.collides_player(p):
                            eff.triggered = True
                            eff.alive     = False
                            owner  = self._get_player(eff.owner_id)
                            actual = p.take_damage(eff.damage, owner)
                            p.apply_root(eff.root_dur)
                            self.vfx.emit_root(p.cx, p.y)
                            if actual > 0:
                                self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_RED)

            elif isinstance(eff, AoeEffect):
                if eff.ready_to_hit():
                    ec = ELEM_COL.get(SPELLS.get(eff.spell_id, {}).get("element","fire"), (255,100,30))
                    self.vfx.emit_explosion(eff.x, eff.y, ec, 28)
                    for p in self.players:
                        if not p.alive or p.player_id == eff.owner_id: continue
                        if not eff.collides_player(p): continue
                        owner  = self._get_player(eff.owner_id)
                        actual = p.take_damage(eff.damage, owner)
                        if eff.slow > 0:     p.apply_slow(eff.slow, eff.slow_dur)
                        if eff.stun_dur > 0: p.apply_root(eff.stun_dur)
                        if eff.knockback > 0:
                            dx = p.cx - eff.x or 1
                            dy = p.cy - eff.y or 1
                            ln = math.hypot(dx, dy) or 1
                            p.vx += (dx/ln) * eff.knockback
                            p.vy += (dy/ln) * eff.knockback * 0.4
                        if actual > 0:
                            self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_RED)

            elif isinstance(eff, PullZone):
                self.vfx.emit_wind_swirl(eff.x, eff.y, eff.color, 2)
                for p in self.players:
                    if p.alive and p.player_id != eff.owner_id and eff.in_range(p):
                        eff.apply_pull(p, dt)
                        actual = p.take_damage(eff.damage * dt)
                        if actual > 0 and random.random() < 0.05:
                            self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_RED)

            elif isinstance(eff, BuffEffect):
                # Overcharge sparks
                if random.random() < 0.1:
                    self.vfx.emit_overcharge(eff.player.cx, eff.player.cy, eff.color, 3)

        self.projectiles += wall_spikes
        self.effects = [e for e in self.effects if e.alive]

        # ── Death detection + VFX ─────────────────────────────────────────
        for p in self.players:
            if not p.alive and p.elim_order == 0:
                alive_count = sum(1 for pl in self.players if pl.alive)
                p.elim_order = len(self.players) - alive_count
                self.vfx.emit_death(p.cx, p.cy, ELEM_COL[p.element])
                self.hud.add_feed(f"P{p.player_id+1} eliminated!", ELEM_COL[p.element])

        # ── Round end check ───────────────────────────────────────────────
        alive = [p for p in self.players if p.alive]
        if len(alive) <= 1:
            self._end_round(alive[0] if alive else None)

        self._update_camera()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_player(self, pid):
        return next((p for p in self.players if p.player_id == pid), None)

    def _aoe_splash(self, proj, primary_hit):
        for p in self.players:
            if not p.alive or p is primary_hit: continue
            dist = math.hypot(p.cx - proj.x, p.cy - proj.y)
            if dist < proj.aoe_radius:
                owner  = self._get_player(proj.owner_id)
                actual = p.take_damage(proj.aoe_damage * (1 - dist/proj.aoe_radius), owner)
                if actual > 0:
                    self._add_float(p.cx, p.cy, f"-{int(actual)}", HP_YELLOW)

    def _chain_arc(self, proj, already_hit, chain_count, chain_range):
        """Spawn chain lightning arcs to nearby players."""
        new_projs = []
        if chain_count <= 0: return new_projs
        cx, cy = already_hit.cx, already_hit.cy
        targets = [
            p for p in self.players
            if p.alive and p is not already_hit
            and p.player_id != proj.owner_id
            and math.hypot(p.cx - cx, p.cy - cy) < chain_range
        ]
        if not targets: return new_projs
        next_t = min(targets, key=lambda p: math.hypot(p.cx - cx, p.cy - cy))
        dx = next_t.cx - cx; dy = next_t.cy - cy
        ln = math.hypot(dx, dy) or 1
        spd = SPELLS.get("chain_lightning", {}).get("speed", 500)
        np = Projectile(cx, cy, dx/ln*spd, dy/ln*spd,
            owner_id=proj.owner_id, spell_id="chain_lightning",
            radius=7, damage=proj.damage * 0.7,
            color=proj.color, glow_col=proj.glow_col,
            lifetime=0.4, knockback=40,
            aoe_radius=0, aoe_damage=0, slow=0, slow_dur=0,
            chain_count=chain_count - 1, chain_range=chain_range)
        new_projs.append(np)
        self.vfx.emit_lightning_bolt(cx, cy, next_t.cx, next_t.cy, proj.color)
        return new_projs

    def _update_camera(self):
        alive = [p for p in self.players if p.alive]
        if not alive: return
        cx = sum(p.x for p in alive) / len(alive)
        cy = sum(p.y for p in alive) / len(alive)
        # Viewport height is reduced by the HUD bar at top
        view_h = BASE_H - HUD_H
        tx = max(0, min(cx - BASE_W // 2,  self.arena.width  - BASE_W))
        ty = max(0, min(cy - view_h // 2,  self.arena.height - view_h))
        self._cam[0] += (tx - self._cam[0]) * 0.07
        self._cam[1] += (ty - self._cam[1]) * 0.07

    def _add_float(self, x, y, text, col):
        self.float_texts.append(FloatText(x, y, text, col))

    # ── Round / match flow ────────────────────────────────────────────────────

    def _end_round(self, winner):
        if self.state != ST_COMBAT: return
        self.state        = ST_ROUND_OVER
        self.round_over_t = 2.8
        self.round_winner = winner

        if winner:
            winner.round_wins += 1
            self.hud.announce(
                f"P{winner.player_id+1}  WINS  ROUND  {self.round_num}!",
                ELEM_COL[winner.element], 2.8)
            self.hud.add_feed(f"P{winner.player_id+1} wins round {self.round_num}", GOLD)

            if winner.round_wins >= ROUNDS_TO_WIN:
                self._pending_match_winner = winner
                return
        else:
            self.hud.announce("DRAW!", WHITE, 2.5)

        self._pending_match_winner = None

    def _enter_aon(self):
        if self._pending_match_winner:
            self.state = ST_MATCH_OVER
            return

        wid = self.round_winner.player_id if self.round_winner else 0

        def on_done(results):
            # results = {pid: {"upgrades": [...], "wipe": bool}}
            for pid, data in results.items():
                player = self._get_player(pid)
                if not player:
                    continue
                # Wipe all existing upgrades if they lost the wager
                if data.get("wipe"):
                    player.upgrades.clear()
                    # Reset all stat multipliers back to wand base
                    from constants import WANDS
                    wd = WANDS.get(player.wand_id, {})
                    player.dmg_mult          = wd.get("dmg",  1.0)
                    player.cast_mult         = wd.get("cast", 1.0)
                    player.size_mult         = wd.get("size", 1.0)
                    player.pspd_mult         = wd.get("pspd", 1.0)
                    player.multicast_chance  = 0.0
                    player.bounce            = wd.get("pierce", False)
                    player.pierce_walls      = wd.get("pierce", False)
                    player.life_steal        = 0.0
                    player.chill_all         = False
                    player.split_shots       = wd.get("split", False)
                    self.hud.add_feed(f"P{pid+1} lost all upgrades!", HP_RED)
                # Apply new upgrades
                for upg in data.get("upgrades", []):
                    player.apply_upgrade(upg)
                    self.hud.add_feed(f"P{pid+1} +{upg['name']}", GOLD)

        self.aon_screen = AllOrNothingScreen(wid, self.players, on_done)
        self.state      = ST_ALL_OR_NOTHING

    def _post_aon(self):
        self.round_num += 1
        self._start_round()

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
            self._draw_combat(surf, cam)
            self.aon_screen.draw(surf)

        elif self.state == ST_MATCH_OVER:
            self._draw_combat(surf, cam)
            self._draw_match_over(surf)

    def _draw_combat(self, surf, cam):
        # Everything in the game world is drawn on a sub-surface that sits
        # below the HUD bar, so nothing ever overlaps the bar.
        view_h  = BASE_H - HUD_H
        game_surf = surf.subsurface(pygame.Rect(0, HUD_H, BASE_W, view_h))

        # World
        self.arena.draw(game_surf, cam)

        # Back-layer effects (trails, traps, pull zones)
        for eff in self.effects:
            if isinstance(eff, (DashEffect, TrapEntity, PullZone)):
                eff.draw(game_surf, cam)

        # VFX particles (behind players)
        self.vfx.draw(game_surf, cam)

        # Players
        for p in self.players:
            p.draw(game_surf, cam)
            p.draw_hud_nameplate(game_surf, cam, f"P{p.player_id+1}")

        # Front-layer effects (walls, shields, aoes, buffs)
        for eff in self.effects:
            if isinstance(eff, (WallEntity, ShieldBuff, AoeEffect, BuffEffect)):
                eff.draw(game_surf, cam)

        # Projectiles
        for proj in self.projectiles:
            proj.draw(game_surf, cam)

        # Floating damage numbers
        for ft in self.float_texts:
            ft.draw(game_surf, cam)

        # HUD bar drawn on the MAIN surface (not the sub-surface)
        self.hud.draw(surf, self.players, self.round_num,
                      self.round_time, self.arena._shrinking)

    def _draw_round_over_overlay(self, surf):
        ov = pygame.Surface((BASE_W, BASE_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 110))
        surf.blit(ov, (0, 0))

    def _draw_match_over(self, surf):
        ov = pygame.Surface((BASE_W, BASE_H), pygame.SRCALPHA)
        ov.fill((8, 6, 18, 215))
        surf.blit(ov, (0, 0))

        winner = self._pending_match_winner or max(self.players, key=lambda p: p.round_wins)
        ec     = ELEM_COL.get(winner.element, GOLD)

        # Winner banner
        draw_text(surf, f"P{winner.player_id+1}  WINS  THE  MATCH!",
                  self._fxl, ec, BASE_W//2, BASE_H//2 - 120, anchor="center")

        # Element label
        label = ELEM_LABELS.get(winner.element, winner.element.title())
        draw_text(surf, label, self._fmd, ec, BASE_W//2, BASE_H//2 - 68, anchor="center")

        # Scoreboard
        pygame.draw.line(surf, BORDER_COL, (BASE_W//2-260, BASE_H//2-44),
                                           (BASE_W//2+260, BASE_H//2-44), 1)
        for i, p in enumerate(sorted(self.players, key=lambda p: -p.round_wins)):
            col  = GOLD if p is winner else TEXT_DIM
            icon = "👑" if p is winner else f"  {i+1}."
            row  = (f"P{p.player_id+1}  {ELEM_LABELS.get(p.element, p.element):<14}"
                    f"{p.round_wins} wins    {int(p.damage_dealt)} dmg dealt")
            draw_text(surf, row, self._flg, col, BASE_W//2, BASE_H//2 - 30 + i*34, anchor="midtop")

        # Replay prompt (pulse)
        t = pygame.time.get_ticks() / 600
        rc = tuple(int(c * (0.7 + 0.3 * abs(math.sin(t)))) for c in SILVER)
        draw_text(surf, "SPACE / R  to play again",
                  self._fmd, rc, BASE_W//2, BASE_H//2 + 120, anchor="midtop")