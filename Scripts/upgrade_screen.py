# upgrade_screen.py  ─  Wand & Wager  ─  All or Nothing: Coin Wager
#
# After every round ALL players receive upgrade cards then face the wager:
#
#   HOLD   → keep your new cards, apply them safely.
#   WAGER  → bet EVERYTHING (new cards + all upgrades earned so far).
#             Pick HEADS or TAILS.
#             Correct  → every upgrade you own is DOUBLED.
#             Wrong    → you lose ALL upgrades (new ones and every old one).
#
# All players decide simultaneously.  CPUs auto-decide after a short delay.
# The screen has four phases:
#   DEAL    → cards fly in for each player
#   DECIDE  → players choose HOLD or WAGER
#   FLIP    → coin spins and reveals (human picks heads/tails if they wagered)
#   RESULTS → outcome shown, then Continue

import pygame
import math
import random
from constants import (BASE_W, BASE_H, UPGRADES, ELEM_COL, ELEM_LABELS,
                       ROUNDS_TO_WIN, SPELLS,
                       DARK_BG, PANEL_BG, BORDER_COL,
                       TEXT_MAIN, TEXT_DIM, GOLD, SILVER,
                       HP_GREEN, HP_YELLOW, HP_RED, WHITE, HUD_H)
from hud import draw_text


# ── How many new cards each player draws ──────────────────────────────────────
WINNER_CARDS = 2
LOSER_CARDS  = 1


# ── Colours ───────────────────────────────────────────────────────────────────
C_HEADS   = (220, 185, 50)    # gold coin face
C_TAILS   = (170, 160, 140)   # silver coin back
C_WIN     = HP_GREEN
C_LOSE    = HP_RED
C_HOLD    = (130, 120, 180)


def _rand_upgrades(n, exclude=None):
    pool = [u for u in UPGRADES if not exclude or u["id"] not in exclude]
    return random.sample(pool, min(n, len(pool)))


def _wrap(text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines or [""]


# ─────────────────────────────────────────────────────────────────────────────
class SmallCard:
    """Compact upgrade card that flies in."""
    W, H = 110, 148

    def __init__(self, upgrade, tx, ty, delay=0.0):
        self.upgrade  = upgrade
        self.tx, self.ty = float(tx), float(ty)
        self.x  = float(tx)
        self.y  = float(ty) - 420
        self.delay    = delay
        self.revealed = delay <= 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - self.W//2,
                           int(self.y) - self.H//2,
                           self.W, self.H)

    def update(self, dt):
        if self.delay > 0:
            self.delay -= dt
            if self.delay <= 0:
                self.revealed = True
            return
        spd = 10.0
        self.x += (self.tx - self.x) * spd * dt
        self.y += (self.ty - self.y) * spd * dt

    def draw(self, surf, fonts):
        if not self.revealed:
            return
        r = self.rect

        # Shadow
        sh = pygame.Surface((self.W + 6, self.H + 6), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0,0,0,70), sh.get_rect(), border_radius=8)
        surf.blit(sh, (r.x - 1, r.y + 4))

        pygame.draw.rect(surf, (28, 22, 48), r, border_radius=8)
        pygame.draw.rect(surf, BORDER_COL, r, 1, border_radius=8)

        wv     = self.upgrade["wv"]
        wv_col = HP_GREEN if wv <= 2 else HP_YELLOW if wv <= 3 else HP_RED

        # WV badge
        bd = pygame.Rect(r.right - 26, r.top + 5, 21, 21)
        pygame.draw.rect(surf, (18, 14, 32), bd, border_radius=4)
        pygame.draw.rect(surf, wv_col, bd, 1, border_radius=4)
        draw_text(surf, str(wv), fonts["xs"], wv_col,
                  bd.centerx, bd.centery, anchor="center")

        ny = r.top + 8
        for line in _wrap(self.upgrade["name"], fonts["sm"], self.W - 18):
            draw_text(surf, line, fonts["sm"], TEXT_MAIN,
                      r.centerx, ny, anchor="midtop")
            ny += 15

        pygame.draw.line(surf, (50, 42, 72), (r.x+8, ny+2), (r.right-8, ny+2), 1)
        ny += 6

        for line in _wrap(self.upgrade["desc"], fonts["xs"], self.W - 14):
            draw_text(surf, line, fonts["xs"], TEXT_DIM,
                      r.centerx, ny, anchor="midtop")
            ny += 12


# ─────────────────────────────────────────────────────────────────────────────
class CoinFlip:
    """Animated coin that spins and lands heads or tails."""

    SPIN_DUR  = 1.8    # seconds of spinning
    LAND_DUR  = 0.5    # slow-down phase

    def __init__(self, cx, cy, result_heads):
        self.cx, self.cy    = cx, cy
        self.result_heads   = result_heads
        self.age            = 0.0
        self.done           = False
        self._total         = self.SPIN_DUR + self.LAND_DUR
        self.radius         = 44

    def update(self, dt):
        self.age += dt
        if self.age >= self._total:
            self.age  = self._total
            self.done = True

    def draw(self, surf):
        t = self.age / self._total
        # Spin speed slows as t → 1
        spins    = 6.0
        angle    = t * spins * math.pi * 2
        # Squish factor: cos gives the "flip" look (0 = edge-on)
        squish   = abs(math.cos(angle))
        # Which face?
        showing_heads = (math.cos(angle) >= 0) == self.result_heads
        face_col  = C_HEADS if showing_heads else C_TAILS
        edge_col  = tuple(max(0, c-40) for c in face_col)

        r      = self.radius
        draw_w = max(4, int(r * 2 * squish))
        draw_h = r * 2

        # Glow
        gs = pygame.Surface((draw_w + 40, draw_h + 40), pygame.SRCALPHA)
        alpha = int(60 * (1 - t * 0.5))
        pygame.draw.ellipse(gs, (*face_col, alpha),
                            pygame.Rect(20, 20, draw_w, draw_h))
        surf.blit(gs, (self.cx - draw_w//2 - 20, self.cy - r - 20))

        # Coin body
        coin_r = pygame.Rect(self.cx - draw_w//2, self.cy - r, draw_w, draw_h)
        pygame.draw.ellipse(surf, face_col, coin_r)
        pygame.draw.ellipse(surf, edge_col, coin_r, 3)

        # Label
        if squish > 0.35:
            lbl = "H" if showing_heads else "T"
            f   = pygame.font.SysFont("Segoe UI", int(r * 0.9), bold=True)
            img = f.render(lbl, True, edge_col)
            img.set_alpha(int(255 * squish))
            surf.blit(img, img.get_rect(center=(self.cx, self.cy)))

    @property
    def settled(self):
        return self.done


# ─────────────────────────────────────────────────────────────────────────────
class PlayerSlot:
    """
    Represents one player's section of the All or Nothing screen.
    Tracks their state through all four phases.
    """

    # Per-player phases
    PH_WAIT    = "wait"     # cards still flying in
    PH_DECIDE  = "decide"   # choose HOLD or WAGER
    PH_PICK    = "pick"     # (wagerers) pick heads or tails
    PH_FLIP    = "flip"     # coin spinning
    PH_RESULT  = "result"   # outcome displayed

    def __init__(self, player, new_upgrades, panel_rect, is_human):
        self.player       = player
        self.new_upgrades = new_upgrades   # list of upgrade dicts (new cards this round)
        self.panel        = panel_rect
        self.is_human     = is_human

        self.phase        = self.PH_WAIT
        self.decision     = None    # "hold" | "wager"
        self.pick         = None    # "heads" | "tails"
        self.coin_result  = None    # True = heads, False = tails
        self.outcome      = None    # "win" | "lose" | "hold"
        self.final_upgs   = []      # upgrades to apply after screen

        self._coin        = None    # CoinFlip instance
        self._cpu_timer   = random.uniform(1.0, 2.2) if not is_human else None
        self._result_age  = 0.0

        # Build card objects
        self.cards = []
        cx0 = panel_rect.x + 14 + SmallCard.W // 2
        cy0 = panel_rect.y + 64
        for i, upg in enumerate(new_upgrades):
            self.cards.append(SmallCard(upg, cx0 + i * (SmallCard.W + 8), cy0,
                                        delay=0.15 + i * 0.2))

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt, global_phase):
        for c in self.cards:
            c.update(dt)

        # Cards settle → move to DECIDE
        if self.phase == self.PH_WAIT:
            if global_phase == "decide" and all(c.revealed for c in self.cards):
                self.phase = self.PH_DECIDE

        # CPU auto-decides
        if self.phase == self.PH_DECIDE and not self.is_human:
            self._cpu_timer -= dt
            if self._cpu_timer <= 0:
                # CPUs are slightly risk-averse if they have many upgrades
                existing = len(self.player.upgrades)
                wager_chance = 0.55 - existing * 0.04
                if random.random() < max(0.2, wager_chance):
                    self.decision = "wager"
                    self.pick     = random.choice(["heads", "tails"])
                    self.phase    = self.PH_FLIP
                    self._coin    = CoinFlip(self.panel.centerx,
                                             self.panel.y + self.panel.h // 2,
                                             random.random() < 0.5)
                else:
                    self.decision = "hold"
                    self.phase    = self.PH_RESULT
                    self.outcome  = "hold"
                    self.final_upgs = list(self.new_upgrades)

        if self.phase == self.PH_FLIP:
            if self._coin:
                self._coin.update(dt)
                if self._coin.settled and self.outcome is None:
                    self._resolve_flip()

        if self.phase == self.PH_RESULT:
            self._result_age += dt

    def _resolve_flip(self):
        result_heads = self._coin.result_heads
        self.coin_result = result_heads
        picked_heads = (self.pick == "heads")
        won = (picked_heads == result_heads)

        if won:
            self.outcome    = "win"
            # Double all existing upgrades + new ones
            # We return the new cards doubled; game.py handles re-applying existing
            self.final_upgs = list(self.new_upgrades) * 2
        else:
            self.outcome    = "lose"
            self.final_upgs = []

        self.phase = self.PH_RESULT

    # ── Human input ───────────────────────────────────────────────────────────

    def on_hold(self):
        if self.phase != self.PH_DECIDE: return
        self.decision   = "hold"
        self.phase      = self.PH_RESULT
        self.outcome    = "hold"
        self.final_upgs = list(self.new_upgrades)

    def on_wager(self):
        if self.phase != self.PH_DECIDE: return
        self.decision = "wager"
        self.phase    = self.PH_PICK   # human still needs to pick H/T

    def on_pick(self, choice):
        if self.phase != self.PH_PICK: return
        self.pick  = choice   # "heads" or "tails"
        self.phase = self.PH_FLIP
        self._coin = CoinFlip(self.panel.centerx,
                              self.panel.y + self.panel.h // 2 + 10,
                              random.random() < 0.5)

    @property
    def resolved(self):
        return self.phase == self.PH_RESULT and self._result_age > 0.3

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf, fonts, age, mx, my):
        p    = self.panel
        ec   = ELEM_COL.get(self.player.element, SILVER)
        live = self.player.alive

        # ── Panel background ──────────────────────────────────────────────
        bg_col = (28, 22, 46) if live else (18, 14, 30)
        if self.outcome == "win":
            bg_col = (18, 36, 20)
        elif self.outcome == "lose":
            bg_col = (38, 14, 14)

        bg = pygame.Surface((p.w, p.h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (*bg_col, 220), bg.get_rect(), border_radius=10)
        bc = ec if self.is_human else BORDER_COL
        bw = 2 if self.is_human else 1
        pygame.draw.rect(bg, (*bc, 200), bg.get_rect(), bw, border_radius=10)
        surf.blit(bg, (p.x, p.y))

        # Element stripe
        pygame.draw.rect(surf, ec, pygame.Rect(p.x, p.y+4, 4, p.h-8), border_radius=2)

        # ── Header: name + existing upgrade count ─────────────────────────
        lbl = ELEM_LABELS.get(self.player.element, self.player.element.title())
        draw_text(surf, f"P{self.player.player_id+1}  {lbl}",
                  fonts["md"], ec, p.x+10, p.y+7)

        # Round-win pips
        for wi in range(ROUNDS_TO_WIN):
            col = GOLD if wi < self.player.round_wins else (40, 34, 58)
            pygame.draw.circle(surf, col,
                               (p.right - 12 - wi * 13, p.y + 14), 5)

        # Existing upgrade tally
        ex_count = len(self.player.upgrades)
        if ex_count > 0:
            draw_text(surf, f"{ex_count} upgrades at stake",
                      fonts["xs"], TEXT_DIM, p.x+10, p.y+24)

        # ── New cards ─────────────────────────────────────────────────────
        for c in self.cards:
            c.draw(surf, fonts)

        # ── Phase-specific overlays ───────────────────────────────────────
        if self.phase == self.PH_DECIDE:
            self._draw_decide(surf, fonts, mx, my)

        elif self.phase == self.PH_PICK:
            self._draw_pick(surf, fonts, mx, my)

        elif self.phase == self.PH_FLIP:
            if self._coin:
                self._coin.draw(surf)

        elif self.phase == self.PH_RESULT:
            self._draw_result(surf, fonts, age)

        # CPU "thinking" dots
        if self.phase == self.PH_DECIDE and not self.is_human:
            dots = "." * (1 + int(age * 3) % 3)
            draw_text(surf, f"Thinking{dots}", fonts["xs"], TEXT_DIM,
                      p.centerx, p.bottom - 16, anchor="midbottom")

    def _draw_decide(self, surf, fonts, mx, my):
        p   = self.panel
        bw  = 100
        bh  = 34
        by  = p.bottom - bh - 10
        hbx = p.centerx - bw - 8
        wbx = p.centerx + 8

        hold_r  = pygame.Rect(hbx, by, bw, bh)
        wager_r = pygame.Rect(wbx, by, bw, bh)

        hh = hold_r.collidepoint(mx, my)
        hw = wager_r.collidepoint(mx, my)

        # HOLD button (blue-grey, safe)
        pygame.draw.rect(surf, (40,50,70) if hh else (28,36,52), hold_r, border_radius=7)
        pygame.draw.rect(surf, (80,120,180), hold_r, 2, border_radius=7)
        draw_text(surf, "HOLD", fonts["lg"], (140,180,230),
                  hold_r.centerx, hold_r.centery, anchor="center")

        # WAGER button (red/gold, risky)
        pygame.draw.rect(surf, (60,36,16) if hw else (44,24,10), wager_r, border_radius=7)
        pygame.draw.rect(surf, GOLD, wager_r, 2, border_radius=7)
        draw_text(surf, "WAGER", fonts["lg"], GOLD,
                  wager_r.centerx, wager_r.centery, anchor="center")

    def _draw_pick(self, surf, fonts, mx, my):
        p   = self.panel
        bw  = 94
        bh  = 32
        by  = p.bottom - bh - 12
        hbx = p.centerx - bw - 6
        tbx = p.centerx + 6

        hr = pygame.Rect(hbx, by, bw, bh)
        tr = pygame.Rect(tbx, by, bw, bh)

        hh = hr.collidepoint(mx, my)
        ht = tr.collidepoint(mx, my)

        draw_text(surf, "Pick a side:", fonts["sm"], GOLD,
                  p.centerx, by - 18, anchor="midbottom")

        # HEADS
        pygame.draw.rect(surf, (60,52,16) if hh else (40,34,10), hr, border_radius=7)
        pygame.draw.rect(surf, C_HEADS, hr, 2, border_radius=7)
        draw_text(surf, "HEADS", fonts["md"], C_HEADS,
                  hr.centerx, hr.centery, anchor="center")

        # TAILS
        pygame.draw.rect(surf, (46,42,36) if ht else (30,28,24), tr, border_radius=7)
        pygame.draw.rect(surf, C_TAILS, tr, 2, border_radius=7)
        draw_text(surf, "TAILS", fonts["md"], C_TAILS,
                  tr.centerx, tr.centery, anchor="center")

    def _draw_result(self, surf, fonts, age):
        p = self.panel
        reveal_t = min(1.0, self._result_age / 0.4)

        if self.outcome == "hold":
            msg  = f"HELD  +{len(self.final_upgs)} upgrades"
            col  = C_HOLD
        elif self.outcome == "win":
            msg  = f"WIN!  DOUBLED!"
            col  = C_WIN
        else:
            msg  = "BUST!  ALL LOST"
            col  = C_LOSE

        alpha = int(255 * reveal_t)
        img   = fonts["xl"].render(msg, True, col)
        img.set_alpha(alpha)
        surf.blit(img, img.get_rect(center=(p.centerx, p.centery + 24)))

        # Coin face for wagers
        if self.outcome in ("win", "lose") and self._coin:
            face = "HEADS" if self._coin.result_heads else "TAILS"
            pick_lbl = self.pick.upper() if self.pick else "?"
            correct  = (self.outcome == "win")
            sc = C_WIN if correct else C_LOSE
            draw_text(surf, f"Coin: {face}  |  You picked: {pick_lbl}",
                      fonts["xs"], sc, p.centerx, p.centery + 48, anchor="midtop")


# ─────────────────────────────────────────────────────────────────────────────
class AllOrNothingScreen:
    """
    Post-round wager screen.

    winner_id : int           — player_id of the round winner
    players   : list[Player]
    on_done   : callable      — called with dict {player_id: {"upgrades": [...], "wipe": bool}}
                                upgrades = new cards to apply
                                wipe = True means clear all existing upgrades first (lost wager)
    """

    # Global phases
    GP_DEAL    = "deal"
    GP_DECIDE  = "decide"
    GP_RESULTS = "results"

    def __init__(self, winner_id, players, on_done):
        self.winner_id = winner_id
        self.players   = players
        self.on_done   = on_done
        self.done      = False

        self._f = {
            "xs":  pygame.font.SysFont("Segoe UI", 11),
            "sm":  pygame.font.SysFont("Segoe UI", 13),
            "md":  pygame.font.SysFont("Segoe UI", 15),
            "lg":  pygame.font.SysFont("Segoe UI", 18, bold=True),
            "xl":  pygame.font.SysFont("Segoe UI", 24, bold=True),
            "ttl": pygame.font.SysFont("Segoe UI", 40, bold=True),
            "sub": pygame.font.SysFont("Segoe UI", 20, bold=True),
        }

        self.age        = 0.0
        self.g_phase    = self.GP_DEAL
        self._done      = False
        self._result_t  = 0.0   # timer once all resolved

        # Build player slots in a responsive grid
        self._slots = self._build_slots(players, winner_id)

        # Start deal phase; transition to decide after 1.2s
        self._deal_timer = 1.2

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_slots(self, players, winner_id):
        n   = len(players)
        sw  = BASE_W
        sh  = BASE_H
        pad = 14
        gap = 10

        # Compute grid: try to fit in 2 columns max 4 rows
        cols = 1 if n == 1 else (2 if n <= 4 else 3)
        rows = math.ceil(n / cols)

        avail_w = sw - pad * 2 - gap * (cols - 1)
        avail_h = sh - HUD_H - pad * 2 - gap * (rows - 1) - 60  # 60 for title
        pw = avail_w // cols
        ph = avail_h // rows

        slots = []
        for i, player in enumerate(players):
            col = i % cols
            row = i // cols
            rx  = pad + col * (pw + gap)
            ry  = HUD_H + 52 + row * (ph + gap)
            panel = pygame.Rect(rx, ry, pw, ph)

            n_cards = WINNER_CARDS if player.player_id == winner_id else LOSER_CARDS
            # player.upgrades stores id strings, not dicts
            upgs    = _rand_upgrades(n_cards, exclude=player.upgrades or None)
            slots.append(PlayerSlot(player, upgs, panel,
                                    is_human=(player.player_id == 0)))
        return slots

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        self.age += dt

        for slot in self._slots:
            slot.update(dt, self.g_phase)

        if self.g_phase == self.GP_DEAL:
            self._deal_timer -= dt
            if self._deal_timer <= 0:
                self.g_phase = self.GP_DECIDE
                # Unlock decide phase for all slots
                for s in self._slots:
                    if s.phase == s.PH_WAIT:
                        s.phase = s.PH_DECIDE

        elif self.g_phase == self.GP_DECIDE:
            # Move to results phase when all players have resolved
            if all(s.resolved for s in self._slots):
                self.g_phase = self.GP_RESULTS

        elif self.g_phase == self.GP_RESULTS:
            self._result_t += dt
            if self._result_t > 3.0 and not self._done:
                self._finalise()

    # ── Finalise ──────────────────────────────────────────────────────────────

    def _finalise(self):
        if self._done: return
        self._done = True

        results = {}
        for slot in self._slots:
            pid = slot.player.player_id
            results[pid] = {
                "upgrades": slot.final_upgs,   # new cards to apply (possibly x2 or empty)
                "wipe":     slot.outcome == "lose",  # wipe existing upgrades
            }

        self.done = True
        self.on_done(results)

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if self._done: return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        mx, my = pygame.mouse.get_pos()

        for slot in self._slots:
            if not slot.is_human: continue

            if slot.phase == slot.PH_DECIDE:
                p   = slot.panel
                bw  = 100
                bh  = 34
                by  = p.bottom - bh - 10
                hold_r  = pygame.Rect(p.centerx - bw - 8, by, bw, bh)
                wager_r = pygame.Rect(p.centerx + 8,       by, bw, bh)
                if hold_r.collidepoint(mx, my):
                    slot.on_hold()
                elif wager_r.collidepoint(mx, my):
                    slot.on_wager()

            elif slot.phase == slot.PH_PICK:
                p   = slot.panel
                bw  = 94
                bh  = 32
                by  = p.bottom - bh - 12
                hr = pygame.Rect(p.centerx - bw - 6, by, bw, bh)
                tr = pygame.Rect(p.centerx + 6,      by, bw, bh)
                if hr.collidepoint(mx, my):
                    slot.on_pick("heads")
                elif tr.collidepoint(mx, my):
                    slot.on_pick("tails")

    def handle_space(self):
        if self.g_phase == self.GP_RESULTS and not self._done:
            self._finalise()

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf):
        sw, sh = BASE_W, BASE_H
        mx, my = pygame.mouse.get_pos()

        # Dark overlay
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((6, 4, 14, 228))
        surf.blit(ov, (0, 0))

        # Felt texture
        for i in range(0, sw, 44):
            pygame.draw.line(surf, (10, 8, 18), (i, 0), (i, sh), 1)
        for i in range(0, sh, 44):
            pygame.draw.line(surf, (10, 8, 18), (0, i), (sw, i), 1)

        # Title
        draw_text(surf, "ALL  OR  NOTHING", self._f["ttl"], GOLD,
                  sw//2, HUD_H + 10, anchor="midtop")

        # Subtitle based on phase
        if self.g_phase == self.GP_DEAL:
            sub = "New upgrades incoming…"
            sc  = TEXT_DIM
        elif self.g_phase == self.GP_DECIDE:
            sub = "HOLD to keep them  ·  WAGER to risk everything on a coin flip"
            sc  = TEXT_MAIN
        else:
            sub = "Results"
            sc  = TEXT_DIM
        draw_text(surf, sub, self._f["sm"], sc, sw//2, HUD_H + 52, anchor="midtop")

        # Draw all player slots
        for slot in self._slots:
            slot.draw(surf, self._f, self.age, mx, my)

        # Continue hint
        if self.g_phase == self.GP_RESULTS:
            blink = int(self.age * 3) % 2 == 0
            draw_text(surf, "SPACE  or  Continue  to proceed",
                      self._f["md"], GOLD if blink else TEXT_DIM,
                      sw//2, sh - 14, anchor="midbottom")
            cb = pygame.Rect(sw//2 - 80, sh - 50, 160, 30)
            hcb = cb.collidepoint(mx, my)
            pygame.draw.rect(surf, (50,42,78) if hcb else (30,26,48), cb, border_radius=7)
            pygame.draw.rect(surf, GOLD, cb, 1, border_radius=7)
            draw_text(surf, "Continue →", self._f["md"], GOLD,
                      cb.centerx, cb.centery, anchor="center")
            if hcb and pygame.mouse.get_pressed()[0] and not self._done:
                self._finalise()