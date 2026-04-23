# hud.py  ─  Wand & Wager HUD
#
# Layout: single semi-transparent bar pinned to the TOP of the virtual surface.
# Height = HUD_H (72px).  The map camera is offset down by HUD_H so the arena
# is never drawn under the bar.
#
# Left section  : player panels (all players, compact row)
# Centre section: round number + timer
# Right section : kill feed

import pygame
import math
from constants import (BASE_W, BASE_H, ROUNDS_TO_WIN, SPELLS, ELEM_COL,
                       ELEM_LABELS, PANEL_BG, BORDER_COL,
                       TEXT_MAIN, TEXT_DIM, GOLD, SILVER, WHITE,
                       HP_GREEN, HP_YELLOW, HP_RED, HUD_H)


def _lerp_col(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_text(surf, text, font, color, x, y, anchor="topleft"):
    img = font.render(str(text), True, color)
    r   = img.get_rect(**{anchor: (x, y)})
    surf.blit(img, r)
    return r


# ─────────────────────────────────────────────────────────────────────────────
class HUD:

    # Width reserved in the centre for round info
    _CENTRE_W = 130

    def __init__(self):
        self.font_xs  = pygame.font.SysFont("Segoe UI", 10)
        self.font_sm  = pygame.font.SysFont("Segoe UI", 12)
        self.font_md  = pygame.font.SysFont("Segoe UI", 13)
        self.font_lg  = pygame.font.SysFont("Segoe UI", 17, bold=True)
        self.font_xl  = pygame.font.SysFont("Segoe UI", 22, bold=True)
        self.font_ann = pygame.font.SysFont("Segoe UI", 36, bold=True)

        self.feed     = []       # [text, col, timer]
        self.FEED_DUR = 4.0

        self.announce_text = ""
        self.announce_t    = 0.0
        self.announce_col  = WHITE

    # ── Public API ────────────────────────────────────────────────────────────

    def add_feed(self, text, col=TEXT_MAIN):
        self.feed.append([text, col, self.FEED_DUR])

    def announce(self, text, col=WHITE, duration=2.5):
        self.announce_text = text
        self.announce_t    = duration
        self.announce_col  = col

    def update(self, dt):
        self.feed = [[t, c, r - dt] for t, c, r in self.feed if r - dt > 0]
        if self.announce_t > 0:
            self.announce_t -= dt

    # ── Main draw ─────────────────────────────────────────────────────────────

    def draw(self, surf, players, round_num, round_time, shrinking=False):
        w = BASE_W

        # ── Background bar ────────────────────────────────────────────────
        bar = pygame.Surface((w, HUD_H), pygame.SRCALPHA)
        bar.fill((10, 8, 20, 210))
        pygame.draw.line(bar, (*BORDER_COL, 200), (0, HUD_H - 1), (w, HUD_H - 1), 1)
        surf.blit(bar, (0, 0))

        # ── Centre: round info ────────────────────────────────────────────
        cx = w // 2
        draw_text(surf, f"ROUND {round_num}", self.font_sm, TEXT_DIM,
                  cx, 4, anchor="midtop")
        mins  = int(round_time) // 60
        secs  = int(round_time) % 60
        tcol  = HP_RED if shrinking else TEXT_MAIN
        draw_text(surf, f"{mins}:{secs:02d}", self.font_xl, tcol,
                  cx, 18, anchor="midtop")
        if shrinking:
            pulse = 0.6 + 0.4 * abs(math.sin(round_time * 4))
            wc    = tuple(int(c * pulse) for c in HP_RED)
            draw_text(surf, "ZONE CLOSING", self.font_xs, wc,
                      cx, 50, anchor="midtop")

        # ── Player panels (left side, skip centre region) ─────────────────
        centre_left  = cx - self._CENTRE_W // 2
        centre_right = cx + self._CENTRE_W // 2

        # Distribute panels: left half then right half, skipping centre
        panel_w = 170
        gap     = 6
        pad     = 8   # left edge padding

        # Build slot list: left of centre, then right of centre
        # Fit as many as possible on each side
        left_slots  = max(0, (centre_left - pad) // (panel_w + gap))
        right_space = w - centre_right - pad
        right_slots = max(0, right_space // (panel_w + gap))

        # Kill feed sits top-right; reserve 160px for it
        feed_reserve = 160
        right_slots  = max(0, (right_space - feed_reserve) // (panel_w + gap))

        all_slots = left_slots + right_slots
        n         = len(players)

        # If more players than slots, shrink panels
        if n > all_slots and all_slots > 0:
            panel_w = min(panel_w, (centre_left - pad * 2) // max(1, n // 2) - gap)
            panel_w = max(100, panel_w)

        # Assign x positions
        positions = []
        lx = pad
        for i in range(min(left_slots, n)):
            positions.append(lx)
            lx += panel_w + gap

        rx = centre_right + gap
        for i in range(min(right_slots, n - len(positions))):
            positions.append(rx)
            rx += panel_w + gap

        for i, p in enumerate(players):
            if i >= len(positions):
                break
            self._draw_panel(surf, p, positions[i], 2, panel_w,
                             is_human=(p.player_id == 0))

        # ── Kill feed (top-right) ─────────────────────────────────────────
        fy = 4
        for text, col, timer in reversed(self.feed[-5:]):
            alpha = min(255, int(timer * 180))
            img   = self.font_sm.render(text, True, col)
            img.set_alpha(alpha)
            surf.blit(img, img.get_rect(topright=(w - 8, fy)))
            fy += 16

        # ── Big announce overlay ──────────────────────────────────────────
        if self.announce_t > 0:
            t     = self.announce_t
            alpha = min(255, int(t * 255))
            img   = self.font_ann.render(self.announce_text, True, self.announce_col)
            img.set_alpha(alpha)
            # Place below HUD bar so it's over the gameplay area
            surf.blit(img, img.get_rect(center=(w // 2, HUD_H + 60)))

    # ── Single player panel ───────────────────────────────────────────────────

    def _draw_panel(self, surf, p, px, py, pw, is_human=False):
        ph  = HUD_H - 4
        ec  = ELEM_COL.get(p.element, (150, 150, 150))

        # Background
        bg  = pygame.Surface((pw, ph), pygame.SRCALPHA)
        if is_human:
            pygame.draw.rect(bg, (30, 24, 50, 220), bg.get_rect(), border_radius=6)
        else:
            pygame.draw.rect(bg, (18, 14, 32, 190), bg.get_rect(), border_radius=6)

        # Border — human gets element-coloured glow, CPUs get dim border
        bc  = (*ec, 200) if is_human else (*BORDER_COL, 140)
        bw  = 2 if is_human else 1
        pygame.draw.rect(bg, bc, bg.get_rect(), bw, border_radius=6)
        surf.blit(bg, (px, py))

        # Left element stripe
        pygame.draw.rect(surf, ec, pygame.Rect(px, py + 2, 3, ph - 4), border_radius=1)

        inner_x = px + 7
        inner_w = pw - 14

        # ── Row 1: name + round-win pips ──────────────────────────────────
        name = f"P{p.player_id + 1} {p.element[:3].upper()}"
        if not p.alive:
            name += " ✗"
        name_col = ec if is_human else (TEXT_MAIN if p.alive else TEXT_DIM)
        draw_text(surf, name, self.font_sm, name_col, inner_x, py + 3)

        # Win pips (right-aligned)
        for wi in range(ROUNDS_TO_WIN):
            col = GOLD if wi < p.round_wins else (40, 36, 58)
            pygame.draw.circle(surf, col,
                               (px + pw - 8 - wi * 11, py + 8), 4)

        # ── Row 2: HP bar ─────────────────────────────────────────────────
        bar_y  = py + 18
        bar_h  = 9
        ratio  = max(0.0, p.hp / p.max_hp) if p.alive else 0.0

        if ratio > 0.5:
            hp_col = _lerp_col(HP_YELLOW, HP_GREEN, (ratio - 0.5) * 2)
        else:
            hp_col = _lerp_col(HP_RED, HP_YELLOW, ratio * 2)

        pygame.draw.rect(surf, (30, 26, 46),
                         (inner_x, bar_y, inner_w, bar_h), border_radius=3)
        if ratio > 0:
            pygame.draw.rect(surf, hp_col,
                             (inner_x, bar_y, int(inner_w * ratio), bar_h),
                             border_radius=3)
        pygame.draw.rect(surf, BORDER_COL,
                         (inner_x, bar_y, inner_w, bar_h), 1, border_radius=3)

        # HP numbers
        hp_str = f"{int(p.hp)}/{p.max_hp}"
        draw_text(surf, hp_str, self.font_xs, TEXT_DIM,
                  inner_x + inner_w // 2, bar_y + 1, anchor="midtop")

        # ── Row 3: spell cooldown pips ────────────────────────────────────
        slots   = p.spell_slots + ([p.combo_slot] if p.combo_slot else [])
        pip_y   = bar_y + bar_h + 6
        n_slots = min(len(slots), 4)
        if n_slots > 0:
            pip_w = (inner_w - (n_slots - 1) * 3) // n_slots
            pip_h = 5

            for si in range(n_slots):
                sid   = slots[si]
                if sid is None:
                    continue
                cd     = p.cooldowns.get(sid, 0)
                max_cd = SPELLS.get(sid, {}).get("cooldown", 1) / max(0.1, p.cast_mult)
                ready  = (cd <= 0)
                ratio2 = 1.0 - min(1.0, cd / max(0.001, max_cd))
                pip_x  = inner_x + si * (pip_w + 3)

                pygame.draw.rect(surf, (30, 26, 46),
                                 (pip_x, pip_y, pip_w, pip_h), border_radius=2)
                fill_col = ec if ready else _lerp_col((60, 50, 80), ec, ratio2)
                if ratio2 > 0:
                    pygame.draw.rect(surf, fill_col,
                                     (pip_x, pip_y, int(pip_w * ratio2), pip_h),
                                     border_radius=2)

                # Key label below pip — only for human player
                if is_human:
                    draw_text(surf, str(si + 1), self.font_xs, TEXT_DIM,
                              pip_x + pip_w // 2, pip_y + pip_h + 1, anchor="midtop")
                else:
                    # Tiny spell initial for CPU
                    sname = SPELLS.get(sid, {}).get("name", "?")[:3]
                    draw_text(surf, sname, self.font_xs, TEXT_DIM,
                              pip_x + pip_w // 2, pip_y + pip_h + 1, anchor="midtop")

        # Upgrade badge
        if p.upgrades:
            draw_text(surf, f"+{len(p.upgrades)}",
                      self.font_xs, GOLD,
                      px + pw - 5, py + ph - 4, anchor="bottomright")


# ─────────────────────────────────────────────────────────────────────────────
class FloatText:
    """Floating damage number that rises and fades."""

    def __init__(self, x, y, text, col, size=14):
        self.x, self.y = float(x), float(y)
        self.text  = text
        self.col   = col
        self.life  = 1.0
        self._font = pygame.font.SysFont("Segoe UI", size, bold=True)
        self.alive = True

    def update(self, dt):
        self.y    -= 38 * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, surf, cam):
        alpha = int(255 * max(0, self.life))
        img   = self._font.render(self.text, True, self.col)
        img.set_alpha(alpha)
        surf.blit(img, img.get_rect(
            center=(int(self.x - cam[0]), int(self.y - cam[1]))))