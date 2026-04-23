# vfx.py  ─  Wand & Wager  ─  Particle / VFX system

import pygame
import math
import random


# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    __slots__ = ("x","y","vx","vy","life","max_life","radius","color",
                 "gravity","fade","shrink","alive")

    def __init__(self, x, y, vx, vy, life, radius, color,
                 gravity=0.0, fade=True, shrink=True):
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.life        = float(life)
        self.max_life    = float(life)
        self.radius      = float(radius)
        self.color       = color
        self.gravity     = gravity
        self.fade        = fade
        self.shrink      = shrink
        self.alive       = True

    def update(self, dt):
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.vy += self.gravity * dt
        self.vx *= 0.94   # air drag

    def draw(self, surf, cam):
        if not self.alive:
            return
        t     = self.life / self.max_life   # 1 → 0
        alpha = int(255 * t) if self.fade else 200
        r     = max(1, int(self.radius * (t if self.shrink else 1.0)))
        sx    = int(self.x - cam[0])
        sy    = int(self.y - cam[1])

        s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color[:3], alpha), (r + 1, r + 1), r)
        surf.blit(s, (sx - r - 1, sy - r - 1))


# ─────────────────────────────────────────────────────────────────────────────
class VFXManager:
    """Holds all active particles. Call emit_* to spawn effects."""

    def __init__(self):
        self._particles: list[Particle] = []

    def update(self, dt):
        for p in self._particles:
            p.update(dt)
        self._particles = [p for p in self._particles if p.alive]

    def draw(self, surf, cam):
        for p in self._particles:
            p.draw(surf, cam)

    def clear(self):
        self._particles.clear()

    # ── Emitters ──────────────────────────────────────────────────────────────

    def emit_impact(self, x, y, color, count=18, speed_range=(80, 260), radius=5):
        """Generic spell impact burst."""
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            spd   = random.uniform(*speed_range)
            vx    = math.cos(angle) * spd
            vy    = math.sin(angle) * spd * 0.7
            r     = random.uniform(radius * 0.4, radius)
            life  = random.uniform(0.25, 0.55)
            self._particles.append(Particle(x, y, vx, vy, life, r, color, gravity=200))

    def emit_explosion(self, x, y, color, count=32, radius=8):
        """Big AoE explosion."""
        glow_col = tuple(min(255, c + 60) for c in color)
        # Core flash
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            spd   = random.uniform(60, 340)
            r     = random.uniform(2, radius)
            life  = random.uniform(0.3, 0.7)
            self._particles.append(Particle(
                x, y, math.cos(angle)*spd, math.sin(angle)*spd*0.6,
                life, r, glow_col, gravity=150))
        # Smoke rings
        for _ in range(10):
            angle = random.uniform(0, math.tau)
            spd   = random.uniform(20, 80)
            life  = random.uniform(0.6, 1.1)
            self._particles.append(Particle(
                x, y, math.cos(angle)*spd, math.sin(angle)*spd - 40,
                life, random.uniform(6, 14), (60, 55, 70), gravity=-30, shrink=False))

    def emit_hit_spark(self, x, y, color, count=8):
        """Small hit sparks on player damage."""
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            spd   = random.uniform(120, 300)
            life  = random.uniform(0.12, 0.28)
            self._particles.append(Particle(
                x, y, math.cos(angle)*spd, math.sin(angle)*spd,
                life, random.uniform(1.5, 3.5), color, gravity=400))

    def emit_death(self, x, y, color, count=40):
        """Player death burst."""
        bright = tuple(min(255, c + 80) for c in color)
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            spd   = random.uniform(50, 400)
            r     = random.uniform(3, 9)
            life  = random.uniform(0.4, 1.2)
            self._particles.append(Particle(
                x, y, math.cos(angle)*spd, math.sin(angle)*spd - 80,
                life, r, bright if random.random() < 0.5 else color,
                gravity=300))

    def emit_trail(self, x, y, color, count=4, spread=15, speed=40):
        """Short-lived trail particles (call every frame for moving objects)."""
        for _ in range(count):
            vx   = random.uniform(-spread, spread)
            vy   = random.uniform(-speed, speed * 0.3)
            life = random.uniform(0.08, 0.22)
            r    = random.uniform(2, 5)
            self._particles.append(Particle(x, y, vx, vy, life, r, color))

    def emit_wall_spawn(self, rect, color, count=20):
        """Particles rising from a wall when it spawns."""
        for _ in range(count):
            x    = random.randint(rect.left, rect.right)
            y    = random.randint(rect.top,  rect.bottom)
            life = random.uniform(0.3, 0.8)
            vy   = random.uniform(-120, -40)
            self._particles.append(Particle(
                x, y, random.uniform(-20, 20), vy,
                life, random.uniform(2, 6), color))

    def emit_shield_pop(self, x, y, color, count=16):
        """When a shield absorbs a hit."""
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            spd   = random.uniform(80, 180)
            life  = random.uniform(0.2, 0.45)
            self._particles.append(Particle(
                x, y, math.cos(angle)*spd, math.sin(angle)*spd,
                life, random.uniform(3, 7), color))

    def emit_lightning_bolt(self, x1, y1, x2, y2, color=(200, 220, 255), count=12):
        """Jagged spark trail between two points."""
        for i in range(count):
            t    = i / max(1, count - 1)
            lx   = x1 + (x2 - x1) * t + random.uniform(-18, 18)
            ly   = y1 + (y2 - y1) * t + random.uniform(-18, 18)
            life = random.uniform(0.05, 0.18)
            self._particles.append(Particle(
                lx, ly, random.uniform(-30,30), random.uniform(-30,30),
                life, random.uniform(2, 5), color, fade=True, shrink=True))

    def emit_overcharge(self, x, y, color=(255, 245, 100), count=24):
        """Sparks circling a player during overcharge buff."""
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            r     = random.uniform(30, 55)
            lx    = x + math.cos(angle) * r
            ly    = y + math.sin(angle) * r
            life  = random.uniform(0.3, 0.7)
            self._particles.append(Particle(
                lx, ly, random.uniform(-40, 40), random.uniform(-80, -20),
                life, random.uniform(2, 5), color))

    def emit_root(self, x, y, count=12):
        """Ice shards flying up from a root effect."""
        for _ in range(count):
            vx   = random.uniform(-60, 60)
            vy   = random.uniform(-160, -60)
            life = random.uniform(0.3, 0.6)
            self._particles.append(Particle(
                x + random.uniform(-20, 20), y,
                vx, vy, life, random.uniform(3, 7),
                (120, 200, 255), gravity=300))

    def emit_wind_swirl(self, x, y, color=(80, 210, 175), count=14):
        """Swirling wind particles."""
        for i in range(count):
            angle = i * (math.tau / count)
            r     = random.uniform(30, 70)
            lx    = x + math.cos(angle) * r
            ly    = y + math.sin(angle) * r * 0.5
            tang_x = -math.sin(angle) * 120
            tang_y =  math.cos(angle) * 60
            life  = random.uniform(0.4, 0.9)
            self._particles.append(Particle(
                lx, ly, tang_x, tang_y, life,
                random.uniform(3, 7), color, gravity=-30))

    def emit_earth_crumble(self, x, y, count=16):
        """Rock debris from earth spells."""
        cols = [(120,95,60),(100,80,50),(140,115,75)]
        for _ in range(count):
            vx   = random.uniform(-100, 100)
            vy   = random.uniform(-200, -60)
            col  = random.choice(cols)
            life = random.uniform(0.4, 0.9)
            self._particles.append(Particle(
                x + random.uniform(-20, 20),
                y + random.uniform(-10, 10),
                vx, vy, life, random.uniform(3, 9), col, gravity=500))

    def emit_fire_burst(self, x, y, count=20):
        """Upward fire burst."""
        for _ in range(count):
            vx   = random.uniform(-60, 60)
            vy   = random.uniform(-220, -80)
            t    = random.random()
            col  = (255, int(80 + t*120), int(t*40))
            life = random.uniform(0.3, 0.7)
            self._particles.append(Particle(
                x + random.uniform(-15, 15), y,
                vx, vy, life, random.uniform(3, 9), col, gravity=-60))