# ai.py  ─  Wand & Wager CPU controller
# Finite-state machine with: HUNT → ENGAGE → EVADE → DODGE

import math
import random
from constants import *


class CPUController:
    """
    Drives a Player using the same move/jump/try_cast interface as human input.
    Runs once per frame and calls player methods directly.
    """

    # Tunable per-difficulty
    DIFFICULTY = {
        "easy":   {"react":0.45, "aim_err":0.22, "cast_delay":0.5,  "jump_chance":0.4, "dodge_chance":0.3},
        "medium": {"react":0.22, "aim_err":0.12, "cast_delay":0.22, "jump_chance":0.6, "dodge_chance":0.55},
        "hard":   {"react":0.10, "aim_err":0.05, "cast_delay":0.08, "jump_chance":0.8, "dodge_chance":0.80},
    }

    STATE_HUNT   = "hunt"
    STATE_ENGAGE = "engage"
    STATE_EVADE  = "evade"
    STATE_DODGE  = "dodge"
    STATE_JUMP   = "jump"

    def __init__(self, player, difficulty="medium"):
        self.player     = player
        self.diff       = self.DIFFICULTY[difficulty]
        self.state      = self.STATE_HUNT
        self.target     = None   # Player reference

        # Internal timers
        self._react_t       = 0.0   # reaction delay before acting
        self._cast_delay    = 0.0   # delay before next cast attempt
        self._state_timer   = 0.0   # time in current state
        self._jump_cd       = 0.0   # jump cooldown
        self._reposition_t  = 0.0   # when to reconsider position
        self._last_hp       = player.max_hp
        self._dodge_dir     = 0     # -1 or +1 for dodge direction
        self._stuck_t       = 0.0   # detect if stuck against wall
        self._stuck_x       = 0.0

        # Memory: last known target position
        self._mem_x   = 0.0
        self._mem_y   = 0.0
        self._mem_age = 999.0

        # Preferred vertical platform target
        self._plat_target_y = None

    # ── Main update ───────────────────────────────────────────────────────────

    def update(self, dt, players, projectiles, platforms, arena_safe, spawned_effects):
        p = self.player
        if not p.alive:
            return

        # Pick target (nearest alive enemy)
        self.target = self._pick_target(players)

        # Cooldowns
        self._cast_delay   = max(0, self._cast_delay  - dt)
        self._jump_cd      = max(0, self._jump_cd     - dt)
        self._state_timer += dt
        self._mem_age     += dt

        # Detect if stuck
        self._stuck_t += dt
        if self._stuck_t > 0.4:
            if abs(p.x - self._stuck_x) < 4 and not p.on_ground:
                p.jump()   # try to un-stuck
            self._stuck_x = p.x
            self._stuck_t = 0.0

        if self.target is None:
            return

        # Update memory
        self._mem_x = self.target.x
        self._mem_y = self.target.y
        self._mem_age = 0.0

        # Choose FSM state
        self._update_state(dt, projectiles, arena_safe)

        # Execute state
        getattr(self, f"_state_{self.state}")(dt, platforms, spawned_effects)

    # ── State selection ───────────────────────────────────────────────────────

    def _update_state(self, dt, projectiles, arena_safe):
        p  = self.player
        t  = self.target
        dist = math.hypot(p.x - t.x, p.y - t.y)

        # Danger from incoming projectiles
        danger = self._nearest_threat(projectiles)

        if danger and random.random() < self.diff["dodge_chance"]:
            if self.state != self.STATE_DODGE:
                self.state = self.STATE_DODGE
                self._state_timer = 0.0
                # Dodge perpendicular to threat
                dx = p.x - danger.x
                self._dodge_dir = 1 if dx > 0 else -1
            return

        hp_ratio = p.hp / p.max_hp
        if hp_ratio < 0.3 and dist < 300:
            self.state = self.STATE_EVADE
        elif dist < 380:
            self.state = self.STATE_ENGAGE
        else:
            self.state = self.STATE_HUNT

    def _nearest_threat(self, projectiles):
        """Return most dangerous incoming projectile, or None."""
        p = self.player
        best = None
        best_dist = 160
        for proj in projectiles:
            if proj.owner_id == p.player_id:
                continue
            if not proj.alive:
                continue
            dist = math.hypot(proj.x - p.x, proj.y - p.y)
            if dist > best_dist:
                continue
            # Check if it's heading toward us
            to_us_x = p.x - proj.x
            to_us_y = p.y - proj.y
            spd = math.hypot(proj.vx, proj.vy) + 0.001
            dot = (proj.vx * to_us_x + proj.vy * to_us_y) / spd
            if dot > 0:
                best = proj
                best_dist = dist
        return best

    # ── States ────────────────────────────────────────────────────────────────

    def _state_hunt(self, dt, platforms, spawned_effects):
        """Move toward target."""
        p, t = self.player, self.target
        if t.x < p.x:
            p.move_left()
        else:
            p.move_right()

        self._platform_jump(p, platforms)
        self._try_cast_at(p, t, spawned_effects, max_range=420)

    def _state_engage(self, dt, platforms, spawned_effects):
        """At combat range: orbit and cast."""
        p, t = self.player, self.target
        dist = math.hypot(p.x - t.x, p.y - t.y)

        # Keep preferred horizontal distance
        ideal_dist = 200 + random.uniform(-40, 40)
        if dist < ideal_dist - 30:
            # Back off
            if t.x < p.x:
                p.move_right()
            else:
                p.move_left()
        elif dist > ideal_dist + 50:
            if t.x < p.x:
                p.move_left()
            else:
                p.move_right()

        self._platform_jump(p, platforms)
        self._try_cast_at(p, t, spawned_effects)

        # Occasionally strafe
        if self._state_timer > 1.2:
            self._state_timer = 0.0
            if random.random() < 0.4:
                if random.random() < 0.5:
                    p.move_left()
                else:
                    p.move_right()

    def _state_evade(self, dt, platforms, spawned_effects):
        """Low HP: run away and still cast."""
        p, t = self.player, self.target
        if t.x < p.x:
            p.move_right()
        else:
            p.move_left()

        if self._jump_cd <= 0 and p.on_ground and random.random() < 0.4:
            p.jump()
            self._jump_cd = 0.6

        # Still try to cast defensively
        self._try_cast_at(p, t, spawned_effects, prefer_slot=2)  # Q = dash

    def _state_dodge(self, dt, platforms, spawned_effects):
        """Dodge incoming projectile."""
        p = self.player
        if self._dodge_dir > 0:
            p.move_right()
        else:
            p.move_left()

        if random.random() < 0.35 and self._jump_cd <= 0:
            p.jump()
            self._jump_cd = 0.5

        # Exit dodge after brief moment
        if self._state_timer > 0.3:
            self.state = self.STATE_ENGAGE
            self._state_timer = 0.0

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _platform_jump(self, p, platforms):
        """Jump toward target's height if they're above."""
        t = self.target
        if t is None:
            return
        if not p.on_ground:
            return
        if self._jump_cd > 0:
            return

        # Target is significantly above us
        if t.y < p.y - 60 and random.random() < self.diff["jump_chance"]:
            p.jump()
            self._jump_cd = 0.55
            return

        # Approaching a gap: jump if edge is near
        r = p.feet
        ahead_x = p.x + p.facing * (p.w + 8)
        ground_below = any(
            pl.rect.top > p.y and
            pl.rect.left < ahead_x < pl.rect.right
            for pl in platforms
        )
        if not ground_below and random.random() < 0.6:
            p.jump()
            self._jump_cd = 0.5

    def _aim_at(self, p, t, lead=True):
        """
        Return (ax, ay) normalised aim vector, optionally leading the target.
        Adds configurable aim error.
        """
        tx, ty = t.x, t.y - t.h // 2

        if lead and hasattr(t, "vx"):
            # Estimate travel time and lead
            dist = math.hypot(tx - p.cx, ty - p.cy) + 0.001
            # Grab speed of primary projectile for this spell
            slot0 = p.spell_slots[0] if p.spell_slots else None
            pspd  = SPELLS.get(slot0, {}).get("speed", 400) * p.pspd_mult if slot0 else 400
            t_flight = dist / max(pspd, 1)
            tx += t.vx * t_flight * 0.5
            ty += t.vy * t_flight * 0.3

        # Aim error
        err = self.diff["aim_err"]
        tx += random.uniform(-err, err) * 200
        ty += random.uniform(-err, err) * 100

        dx = tx - p.cx
        dy = ty - p.cy
        ln = math.hypot(dx, dy)
        if ln < 0.001:
            return (1.0, 0.0)
        return (dx / ln, dy / ln)

    def _try_cast_at(self, p, t, spawned_effects, max_range=999, prefer_slot=None):
        if self._cast_delay > 0:
            return

        dist = math.hypot(p.x - t.x, p.y - t.y)
        if dist > max_range:
            return

        ax, ay = self._aim_at(p, t)

        # Slot priority
        slot_order = [0, 1, 2]
        if self.combo_slot_idx(p) is not None:
            slot_order.append(3)
        if prefer_slot is not None:
            slot_order = [prefer_slot] + [s for s in slot_order if s != prefer_slot]

        for slot in slot_order:
            projs = p.try_cast(slot, ax, ay, spawned_effects)
            if projs is not None and len(projs) > 0:
                self._cast_delay = self.diff["cast_delay"] + random.uniform(0, 0.15)
                return
            # Even if 0 projs (wall/effect), count as cast attempt
            # Check if cooldown changed (means it fired)
            if self._did_cast(p, slot):
                self._cast_delay = self.diff["cast_delay"] + random.uniform(0, 0.1)
                return

    def _did_cast(self, p, slot):
        """Rough check: did cast happen (for non-projectile spells)."""
        return False  # projectile return is sufficient for now

    def combo_slot_idx(self, p):
        if p.combo_slot:
            return 3
        return None

    def _pick_target(self, players):
        p = self.player
        best = None
        best_dist = 1e9
        for other in players:
            if other.player_id == p.player_id or not other.alive:
                continue
            d = math.hypot(p.x - other.x, p.y - other.y)
            # Prefer low-HP targets
            d *= (other.hp / max(1, other.max_hp))
            if d < best_dist:
                best_dist = d
                best = other
        return best