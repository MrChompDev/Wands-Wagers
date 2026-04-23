# spells.py  ─  Wand & Wager
# All live spell/effect entities.  Created by Player._cast(), updated by Game.

import pygame
import math
import random
from constants import *


def _rot_surf(surf, angle):
    return pygame.transform.rotate(surf, math.degrees(-angle))


# ─────────────────────────────────────────────────────────────────────────────
class Projectile:
    """Travelling projectile."""

    def __init__(self, x, y, vx, vy, *, owner_id, spell_id, radius, damage,
                 color, glow_col, lifetime, knockback=0,
                 aoe_radius=0, aoe_damage=0,
                 slow=0, slow_dur=0,
                 bounce=False, pierce_walls=False,
                 debuff=None, debuff_dur=0,
                 blind_dur=0,
                 chain_count=0, chain_range=0,
                 stun_dur=0):
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.owner_id    = owner_id
        self.spell_id    = spell_id
        self.radius      = radius
        self.damage      = damage
        self.color       = color
        self.glow_col    = glow_col
        self.lifetime    = lifetime
        self.knockback   = knockback
        self.aoe_radius  = aoe_radius
        self.aoe_damage  = aoe_damage
        self.slow        = slow
        self.slow_dur    = slow_dur
        self.bounce      = bounce
        self.bounce_count = 0
        self.pierce_walls = pierce_walls
        self.debuff      = debuff
        self.debuff_dur  = debuff_dur
        self.blind_dur   = blind_dur
        self.chain_count = chain_count   # arcs remaining after first hit
        self.chain_range = chain_range
        self.stun_dur    = stun_dur
        self.alive       = True
        self.age         = 0.0

    @property
    def pos(self):
        return (self.x, self.y)

    def update(self, dt, arena_safe):
        self.age += dt
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False
            return

        self.x += self.vx * dt
        self.y += self.vy * dt

        # Bounce off arena side walls
        if self.bounce and self.bounce_count < 2:
            if self.x < arena_safe.left or self.x > arena_safe.right:
                self.vx *= -1
                self.bounce_count += 1
            if self.y < arena_safe.top:
                self.vy *= -1
                self.bounce_count += 1
        else:
            # Kill if out of bounds
            if not arena_safe.inflate(100, 200).collidepoint(self.x, self.y):
                self.alive = False

    def collides_with(self, player):
        dx = player.cx - self.x
        dy = player.cy - self.y
        return math.hypot(dx, dy) < self.radius + player.w // 2

    def collides_wall(self, wall):
        """Rough circle–rect collision."""
        r = wall.rect
        cx = max(r.left, min(self.x, r.right))
        cy = max(r.top,  min(self.y, r.bottom))
        return math.hypot(self.x - cx, self.y - cy) < self.radius

    def draw(self, surf, cam):
        sx = int(self.x - cam[0])
        sy = int(self.y - cam[1])
        r  = self.radius

        # Glow (larger, dimmer circle)
        if r >= 5:
            gs = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*self.glow_col, 60), (r*2, r*2), r*2)
            surf.blit(gs, (sx - r*2, sy - r*2))

        pygame.draw.circle(surf, self.color, (sx, sy), r)

        # Tail
        spd = math.hypot(self.vx, self.vy)
        if spd > 10:
            tx = sx - int(self.vx / spd * r * 2.2)
            ty = sy - int(self.vy / spd * r * 2.2)
            pygame.draw.line(surf, self.glow_col, (sx, sy), (tx, ty), max(1, r//2))


# ─────────────────────────────────────────────────────────────────────────────
class WallEntity:
    """Stationary spell barrier (flame wall, frost wall, combo walls)."""

    def __init__(self, x, bottom_y, *, owner_id, spell_id,
                 width, height, duration, wall_hp,
                 dps, color, glow_col,
                 fire_rate=0, spike_dmg=0, spike_spd=0):
        self.owner_id   = owner_id
        self.spell_id   = spell_id
        self.color      = color
        self.glow_col   = glow_col
        self.dps        = dps
        self.wall_hp    = wall_hp
        self.duration   = duration
        self.alive      = True
        self.age        = 0.0

        # Firing (combo walls)
        self.fire_rate   = fire_rate
        self.fire_timer  = 0.0
        self.spike_dmg   = spike_dmg
        self.spike_spd   = spike_spd

        self.rect = pygame.Rect(
            int(x - width // 2),
            int(bottom_y - height),
            width, height
        )

        # Flicker
        self._flicker = 0.0

    def update(self, dt):
        self.age      += dt
        self.duration -= dt
        if self.duration <= 0:
            self.alive = False
            return

        self._flicker = random.uniform(0.7, 1.0)

        if self.fire_rate > 0:
            self.fire_timer += dt

    def emit_spikes(self):
        """Return list of spike Projectile objects if ready to fire."""
        if self.fire_rate <= 0 or self.fire_timer < self.fire_rate:
            return []
        self.fire_timer = 0.0
        spikes = []
        cx = self.rect.centerx
        cy = self.rect.centery
        for dx in (-1, 1):
            p = Projectile(
                cx, cy, dx * self.spike_spd, 0,
                owner_id=self.owner_id, spell_id="wall_spike",
                radius=7, damage=self.spike_dmg,
                color=self.color, glow_col=self.glow_col,
                lifetime=1.4, knockback=60,
            )
            spikes.append(p)
        return spikes

    def take_damage(self, amount):
        self.wall_hp -= amount
        if self.wall_hp <= 0:
            self.alive = False

    def draw(self, surf, cam):
        r  = self.rect.move(-cam[0], -cam[1])
        fc = tuple(min(255, int(c * self._flicker)) for c in self.color)

        # Glow
        gs = pygame.Surface((r.width + 20, r.height + 20), pygame.SRCALPHA)
        pygame.draw.rect(gs, (*self.glow_col, 50),
                         pygame.Rect(10, 10, r.width, r.height), border_radius=4)
        surf.blit(gs, (r.x - 10, r.y - 10))

        pygame.draw.rect(surf, fc, r, border_radius=3)

        # Fire-particle-like streaks
        for _ in range(3):
            py = random.randint(r.top, r.bottom)
            pw = random.randint(2, max(2, r.width - 2))
            streak_col = tuple(min(255, c + 40) for c in fc)
            pygame.draw.line(surf, streak_col, (r.x, py), (r.x + pw, py), 1)


# ─────────────────────────────────────────────────────────────────────────────
class DashEffect:
    """Attached to player during dash; leaves a burning trail."""

    def __init__(self, player, data):
        self.player    = player
        self.force     = data["force"]
        self.trail_dps = data["trail_dps"]
        self.trail_dur = data["trail_dur"]
        self.trail_w   = data["trail_w"]
        self.color     = data["color"]
        self.alive     = True
        self.trail_segs = []   # list of (x, y, lifetime_remaining)
        self._active   = True
        self._timer    = 0.12  # dash lasts this long

    def activate(self, aim_x, aim_y):
        p = self.player
        spd = math.hypot(p.vx, p.vy)
        p.vx = aim_x * self.force
        p.vy = aim_y * self.force * 0.5

    def update(self, dt):
        if self._active:
            self._timer -= dt
            # Record trail segment at player pos
            p = self.player
            self.trail_segs.append([p.cx, p.cy, self.trail_dur])
            if self._timer <= 0:
                self._active = False

        for seg in self.trail_segs:
            seg[2] -= dt
        self.trail_segs = [s for s in self.trail_segs if s[2] > 0]

        if not self._active and not self.trail_segs:
            self.alive = False

    def collides_player(self, player):
        if player.player_id == self.player.player_id:
            return False
        for seg in self.trail_segs:
            if math.hypot(seg[0] - player.cx, seg[1] - player.cy) < self.trail_w + player.w // 2:
                return True
        return False

    def draw(self, surf, cam):
        for sx, sy, rem in self.trail_segs:
            alpha = int(180 * (rem / self.trail_dur))
            r     = max(3, int(self.trail_w * (rem / self.trail_dur)))
            s     = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (r+1, r+1), r)
            surf.blit(s, (int(sx - cam[0]) - r - 1, int(sy - cam[1]) - r - 1))


# ─────────────────────────────────────────────────────────────────────────────
class ShieldBuff:
    """Attached shield that absorbs hits."""

    def __init__(self, player, data):
        self.player   = player
        self.color    = data["color"]
        self.duration = data["duration"]
        self.alive    = True
        self.age      = 0.0

    def update(self, dt):
        self.age += dt
        if self.age >= self.duration or not self.player.alive:
            self.alive = False
            self.player.shield_hits = 0

    def draw(self, surf, cam):
        p  = self.player
        sx = int(p.cx - cam[0])
        sy = int(p.cy - cam[1])
        r  = p.w + 6 + int(math.sin(self.age * 5) * 2)
        s  = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, 100), (r+2, r+2), r, 3)
        surf.blit(s, (sx - r - 2, sy - r - 2))


# ─────────────────────────────────────────────────────────────────────────────
class TrapEntity:
    """Hidden ground trap (permafrost)."""

    def __init__(self, x, y, *, owner_id, spell_id, radius, damage, root_dur, color):
        self.x, self.y  = float(x), float(y)
        self.owner_id   = owner_id
        self.spell_id   = spell_id
        self.radius     = radius
        self.damage     = damage
        self.root_dur   = root_dur
        self.color      = color
        self.alive      = True
        self.triggered  = False
        self.age        = 0.0
        self.duration   = 20.0   # despawn if not triggered

    def update(self, dt):
        self.age += dt
        if self.age > self.duration:
            self.alive = False

    def collides_player(self, player):
        return math.hypot(player.cx - self.x, player.cy - self.y) < self.radius + player.w // 2

    def draw(self, surf, cam):
        sx = int(self.x - cam[0])
        sy = int(self.y - cam[1])
        # Barely visible indicator
        s = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, 60), (self.radius, self.radius), self.radius)
        surf.blit(s, (sx - self.radius, sy - self.radius))


# ─────────────────────────────────────────────────────────────────────────────
class AoeEffect:
    """Delayed AoE explosion / blizzard zone."""

    def __init__(self, x, y, *, owner_id, spell_id, radius, damage,
                 delay, count, color, slow=0, slow_dur=0, blind_dur=0,
                 knockback=0, stun_dur=0):
        self.x, self.y  = float(x), float(y)
        self.owner_id   = owner_id
        self.spell_id   = spell_id
        self.radius     = radius
        self.damage     = damage
        self.delay      = delay
        self.count      = count
        self.color      = color
        self.slow       = slow
        self.slow_dur   = slow_dur
        self.blind_dur  = blind_dur
        self.knockback  = knockback
        self.stun_dur   = stun_dur
        self.alive      = True
        self.age        = 0.0
        self.fired      = False
        self.visual_t   = 0.6   # how long the visual lingers after hit

    def update(self, dt):
        self.age += dt
        if self.age >= self.delay and not self.fired:
            self.fired = True
        if self.fired:
            self.visual_t -= dt
            if self.visual_t <= 0:
                self.alive = False

    def ready_to_hit(self):
        return self.fired and self.visual_t > 0.55   # only hit on first frame it's ready

    def collides_player(self, player):
        return math.hypot(player.cx - self.x, player.cy - self.y) < self.radius + player.w // 2

    def draw(self, surf, cam):
        sx = int(self.x - cam[0])
        sy = int(self.y - cam[1])
        r  = self.radius

        if not self.fired:
            # Warning indicator
            alpha = int(80 + 60 * math.sin(self.age * 8))
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (r, r), r, 3)
            surf.blit(s, (sx - r, sy - r))
        else:
            # Impact burst
            alpha = int(200 * (self.visual_t / 0.55))
            s = pygame.Surface(((r+20)*2, (r+20)*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (r+20, r+20), r+20)
            surf.blit(s, (sx - r - 20, sy - r - 20))


# ─────────────────────────────────────────────────────────────────────────────
class BuffEffect:
    """Temporary stat buff attached to caster (overcharge, iron_hide)."""

    def __init__(self, player, data, spell_id):
        self.player     = player
        self.spell_id   = spell_id
        self.color      = data["color"]
        self.duration   = data["duration"]
        self.alive      = True
        self.age        = 0.0

        # Store what we changed so we can undo it on expiry
        self._dmg_bonus   = data.get("dmg_bonus",      0.0)
        self._cast_bonus  = data.get("cast_bonus",     0.0)
        self._dmg_reduce  = data.get("dmg_reduction",  0.0)
        self._spd_penalty = data.get("speed_penalty",  0.0)

        player.dmg_mult  += self._dmg_bonus
        player.cast_mult += self._cast_bonus
        player._dmg_reduction = getattr(player, "_dmg_reduction", 0.0) + self._dmg_reduce
        player.slow_factor    = max(0.1, player.slow_factor - self._spd_penalty)

    def update(self, dt):
        self.age += dt
        if self.age >= self.duration or not self.player.alive:
            self._expire()

    def _expire(self):
        p = self.player
        p.dmg_mult  = max(0.1, p.dmg_mult  - self._dmg_bonus)
        p.cast_mult = max(0.1, p.cast_mult - self._cast_bonus)
        p._dmg_reduction = max(0.0, getattr(p,"_dmg_reduction",0) - self._dmg_reduce)
        p.slow_factor = min(1.0, p.slow_factor + self._spd_penalty)
        self.alive = False

    def draw(self, surf, cam):
        import math
        p  = self.player
        sx = int(p.cx - cam[0])
        sy = int(p.cy - cam[1])
        t  = self.age / max(0.001, self.duration)
        r  = p.w + 10 + int(math.sin(self.age * 6) * 3)
        s  = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
        alpha = int(180 * (1 - t * 0.7))
        pygame.draw.circle(s, (*self.color, alpha), (r+2, r+2), r, 3)
        surf.blit(s, (sx - r - 2, sy - r - 2))


# ─────────────────────────────────────────────────────────────────────────────
class PullZone:
    """Vortex / pull zone — sucks nearby players toward its centre."""

    def __init__(self, x, y, *, owner_id, spell_id, radius, pull_force,
                 duration, damage, color):
        self.x, self.y  = float(x), float(y)
        self.owner_id   = owner_id
        self.spell_id   = spell_id
        self.radius     = radius
        self.pull_force = pull_force
        self.duration   = duration
        self.damage     = damage
        self.color      = color
        self.alive      = True
        self.age        = 0.0

    def update(self, dt):
        self.age += dt
        if self.age >= self.duration:
            self.alive = False

    def in_range(self, player):
        return math.hypot(player.cx - self.x, player.cy - self.y) < self.radius

    def apply_pull(self, player, dt):
        dx = self.x - player.cx
        dy = self.y - player.cy
        dist = math.hypot(dx, dy) + 0.001
        strength = self.pull_force * (1.0 - dist / self.radius)
        player.vx += (dx / dist) * strength * dt
        player.vy += (dy / dist) * strength * dt

    def draw(self, surf, cam):
        sx = int(self.x - cam[0])
        sy = int(self.y - cam[1])
        t  = self.age / max(0.001, self.duration)
        r  = int(self.radius)
        rot = self.age * 3.0

        s  = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
        alpha = int(80 * (1 - t))
        pygame.draw.circle(s, (*self.color, alpha), (r+2, r+2), r)

        # Spiral arms
        for i in range(3):
            a = rot + i * (2 * math.pi / 3)
            ex = (r+2) + int(math.cos(a) * r * 0.8)
            ey = (r+2) + int(math.sin(a) * r * 0.8)
            pygame.draw.line(s, (*self.color, 160), (r+2, r+2), (ex, ey), 2)

        surf.blit(s, (sx - r - 2, sy - r - 2))