# player.py  ─  Wand & Wager

import pygame
import math
import random
from constants import *
from spells import Projectile, WallEntity, DashEffect, ShieldBuff, TrapEntity, AoeEffect, BuffEffect, PullZone


class Player:

    def __init__(self, x, y, player_id, element, wand_id="oak"):
        self.player_id = player_id
        self.element   = element
        self.wand_id   = wand_id
        w_data         = WANDS[wand_id]

        # ── Position / physics ────────────────────────────────────────────
        self.x, self.y  = float(x), float(y)
        self.vx, self.vy = 0.0, 0.0
        self.w, self.h  = PLAYER_W, PLAYER_H
        self.on_ground  = False
        self.facing     = 1     # +1 = right, -1 = left
        self.coyote_t   = 0.0   # coyote time for jumps

        # ── Health ────────────────────────────────────────────────────────
        self.max_hp  = BASE_HP
        self.hp      = float(self.max_hp)
        self.alive   = True

        # ── Stat multipliers ─────────────────────────────────────────────
        self.dmg_mult   = w_data["dmg"]
        self.cast_mult  = w_data["cast"]   # higher → shorter cooldowns
        self.size_mult  = w_data["size"]
        self.pspd_mult  = w_data.get("pspd", 1.0)

        # ── Upgrade flags ─────────────────────────────────────────────────
        self.multicast_chance = 0.0
        self.bounce           = w_data.get("pierce", False) is False and False  # upgrade only
        self.pierce_walls     = w_data.get("pierce", False)
        self.life_steal       = 0.0
        self.chill_all        = False
        self.split_shots      = w_data.get("split", False)

        # ── Spells ────────────────────────────────────────────────────────
        base_spells       = ELEMENT_SPELLS[element][:]   # 3 base spells
        self.spell_slots  = base_spells                  # up to 4 (slot 3 = combo)
        self.combo_slot   = None                         # set if combo unlocked
        self.cooldowns    = {s: 0.0 for s in self.spell_slots}

        # Check for combo on build
        self._check_combo()

        # ── Status effects ────────────────────────────────────────────────
        self.slow_factor  = 1.0
        self.slow_timer   = 0.0
        self.shield_hits  = 0    # absorb remaining
        self.invincible_t = SPAWN_INVINCIBLE
        self.root_timer   = 0.0  # permafrost root
        self.blind_timer  = 0.0
        self.ignite_timer = 0.0  # +30% fire dmg taken
        self.debuffs      = {}   # debuff_id → timer

        # ── Round tracking ────────────────────────────────────────────────
        self.round_wins   = 0
        self.elim_order   = 0    # 1 = first to die, higher = survived longer
        self.damage_dealt = 0.0  # for XP
        self.upgrades     = []   # list of upgrade ids applied this match

        # ── Visuals ───────────────────────────────────────────────────────
        self.color       = ELEM_COL[element]
        self.anim_t      = 0.0
        self.hit_flash_t = 0.0
        self.land_squash = 1.0   # scale y on landing

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def cx(self):
        return self.x

    @property
    def cy(self):
        return self.y - self.h // 2

    @property
    def feet(self):
        return pygame.Rect(int(self.x - self.w//2), int(self.y - self.h), self.w, self.h)

    # ── Combo check ───────────────────────────────────────────────────────────

    def _check_combo(self):
        spell_set = frozenset(self.spell_slots)
        for combo_key, combo_id in COMBOS.items():
            if combo_key.issubset(spell_set):
                self.combo_slot = combo_id
                if combo_id not in self.cooldowns:
                    self.cooldowns[combo_id] = 0.0
                return

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt, platforms, arena_safe):
        if not self.alive:
            return

        self.anim_t += dt

        # Timers
        if self.invincible_t > 0:
            self.invincible_t -= dt
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow_factor = 1.0
        if self.root_timer > 0:
            self.root_timer -= dt
        if self.blind_timer > 0:
            self.blind_timer -= dt
        if self.ignite_timer > 0:
            self.ignite_timer -= dt
        if self.hit_flash_t > 0:
            self.hit_flash_t -= dt
        if self.land_squash != 1.0:
            self.land_squash += (1.0 - self.land_squash) * 8 * dt

        for k in list(self.debuffs):
            self.debuffs[k] -= dt
            if self.debuffs[k] <= 0:
                del self.debuffs[k]

        # Cooldowns
        for k in list(self.cooldowns):
            if self.cooldowns[k] > 0:
                self.cooldowns[k] = max(0.0, self.cooldowns[k] - dt)

        # Physics
        if self.root_timer <= 0:
            self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
            if self.on_ground:
                self.vx *= GROUND_FRIC
            else:
                self.vx *= AIR_FRIC
        else:
            self.vx = 0

        was_on_ground = self.on_ground
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.on_ground = False

        self._resolve_platforms(platforms)
        self._resolve_arena(arena_safe)

        if self.on_ground and not was_on_ground and self.vy > 200:
            self.land_squash = 0.65
        if self.on_ground:
            self.coyote_t = 0.1
        else:
            self.coyote_t = max(0, self.coyote_t - dt)

        # Fall death
        if self.y > arena_safe.bottom + 150:
            self.die()

    def _resolve_platforms(self, platforms):
        rect = self.feet
        for plat in platforms:
            pr = plat.rect
            if not rect.colliderect(pr):
                continue
            overlap_x = min(rect.right, pr.right) - max(rect.left, pr.left)
            overlap_y = min(rect.bottom, pr.bottom) - max(rect.top, pr.top)
            if overlap_y <= overlap_x:
                if self.vy >= 0 and rect.bottom > pr.top and (rect.bottom - pr.top) < 20:
                    self.y = float(pr.top)
                    self.vy = 0
                    self.on_ground = True
                elif self.vy < 0 and rect.top < pr.bottom:
                    self.y = float(pr.bottom + self.h)
                    self.vy = 0
            else:
                if rect.centerx < pr.centerx:
                    self.x = float(pr.left - self.w // 2)
                else:
                    self.x = float(pr.right + self.w // 2)
                self.vx = 0

    def _resolve_arena(self, arena_safe):
        half = self.w // 2
        if self.x < arena_safe.left + half:
            self.x = float(arena_safe.left + half)
            self.vx = abs(self.vx) * 0.2
        elif self.x > arena_safe.right - half:
            self.x = float(arena_safe.right - half)
            self.vx = -abs(self.vx) * 0.2

    # ── Movement interface (called by human input or AI) ──────────────────────

    def move_left(self):
        if self.root_timer > 0:
            return
        spd = PLAYER_SPEED * self.slow_factor
        self.vx = max(self.vx - spd * 0.18, -spd)
        self.facing = -1

    def move_right(self):
        if self.root_timer > 0:
            return
        spd = PLAYER_SPEED * self.slow_factor
        self.vx = min(self.vx + spd * 0.18, spd)
        self.facing = 1

    def jump(self):
        if self.root_timer > 0:
            return
        if self.on_ground or self.coyote_t > 0:
            self.vy = PLAYER_JUMP
            self.on_ground = False
            self.coyote_t  = 0

    # ── Spell casting interface ───────────────────────────────────────────────

    def try_cast(self, slot, aim_x, aim_y, spawned_effects):
        """
        slot: 0=LMB, 1=RMB, 2=Q, 3=E(combo)
        Returns list of Projectile objects spawned (to be added to game's projectile list).
        WallEntity / effects are appended to spawned_effects in-place.
        """
        if not self.alive:
            return []
        if self.blind_timer > 0 and random.random() < 0.5:
            return []    # blinded: 50% miss

        slots = self.spell_slots[:]
        if self.combo_slot:
            slots.append(self.combo_slot)

        if slot >= len(slots):
            return []

        sid = slots[slot]
        if self.cooldowns.get(sid, 0) > 0:
            return []

        data = SPELLS.get(sid)
        if not data:
            return []

        cd = data["cooldown"] / max(0.1, self.cast_mult)
        self.cooldowns[sid] = cd

        projs = self._create_effect(sid, data, aim_x, aim_y, spawned_effects)

        # Multicast
        if random.random() < self.multicast_chance and projs:
            spread_x = aim_x + random.uniform(-0.15, 0.15)
            spread_y = aim_y + random.uniform(-0.15, 0.15)
            ln = math.hypot(spread_x, spread_y)
            if ln > 0:
                spread_x /= ln; spread_y /= ln
            projs += self._create_effect(sid, data, spread_x, spread_y, spawned_effects)

        return projs

    def _create_effect(self, sid, data, ax, ay, spawned_effects):
        cx, cy = self.cx, self.cy
        typ = data["type"]
        projs = []

        if typ in ("projectile", "combo_projectile"):
            spd = data["speed"] * self.pspd_mult
            r   = max(3, int(data["radius"] * self.size_mult))
            dmg = data["damage"] * self.dmg_mult
            if "ignite" in (self.debuffs or {}):
                dmg *= 1.3

            kwargs = dict(
                owner_id=self.player_id, spell_id=sid,
                radius=r, damage=dmg,
                color=data["color"], glow_col=data.get("glow", data["color"]),
                lifetime=data["lifetime"], knockback=data.get("knockback", 0),
                aoe_radius=data.get("aoe_radius", 0),
                aoe_damage=data.get("aoe_damage", 0) * self.dmg_mult,
                slow=data.get("slow", 0) if not self.chill_all else max(data.get("slow",0), 0.3),
                slow_dur=data.get("slow_dur", 0) if not self.chill_all else max(data.get("slow_dur",0), 1.5),
                bounce=self.bounce,
                pierce_walls=self.pierce_walls,
                debuff=data.get("debuff"),
                debuff_dur=data.get("debuff_dur", 0),
                blind_dur=data.get("blind_dur", 0),
            )

            p = Projectile(cx, cy, ax * spd, ay * spd, **kwargs)
            projs.append(p)

            if self.split_shots:
                for ang in (-0.18, 0.18):
                    cos_a, sin_a = math.cos(ang), math.sin(ang)
                    svx = ax * cos_a - ay * sin_a
                    svy = ax * sin_a + ay * cos_a
                    sp = Projectile(cx, cy, svx * spd * 0.85, svy * spd * 0.85, **kwargs)
                    projs.append(sp)

        elif typ in ("wall", "combo_wall"):
            wx = cx + ax * data["place_offset"]
            wy = self.y
            wall = WallEntity(
                wx, wy,
                owner_id=self.player_id, spell_id=sid,
                width=data["width"], height=data["height"],
                duration=data["duration"], wall_hp=data["wall_hp"],
                dps=data.get("dps", 0),
                color=data["color"], glow_col=data.get("glow", data["color"]),
                fire_rate=data.get("fire_rate", 0),
                spike_dmg=data.get("spike_dmg", 0) * self.dmg_mult,
                spike_spd=data.get("spike_spd", 0),
            )
            spawned_effects.append(wall)

        elif typ == "dash":
            dash = DashEffect(self, data)
            dash.activate(ax, ay)
            spawned_effects.append(dash)

        elif typ == "shield":
            self.shield_hits = data["absorb"]
            buff = ShieldBuff(self, data)
            spawned_effects.append(buff)

        elif typ == "trap":
            trap = TrapEntity(
                cx + ax * 40, self.y,
                owner_id=self.player_id, spell_id=sid,
                radius=data["radius"], damage=data["damage"] * self.dmg_mult,
                root_dur=data["root_dur"], color=data["color"],
            )
            spawned_effects.append(trap)

        elif typ in ("aoe", "melee_aoe"):
            tx = cx if typ == "melee_aoe" else cx + ax * data["radius"] * 0.5
            ty = cy if typ == "melee_aoe" else cy + ay * data["radius"] * 0.5
            spd_d = data.get("slow", 0) if not self.chill_all else max(data.get("slow",0), 0.3)
            aoe = AoeEffect(
                tx, ty,
                owner_id=self.player_id, spell_id=sid,
                radius=data["radius"], damage=data["damage"] * self.dmg_mult,
                delay=data.get("delay", 0.0), count=data.get("count", 1),
                color=data["color"],
                slow=spd_d, slow_dur=data.get("slow_dur", 0),
                knockback=data.get("knockback", 0),
                stun_dur=data.get("stun_dur", 0),
            )
            spawned_effects.append(aoe)

        elif typ == "chain":
            spd = data["speed"] * self.pspd_mult
            r   = max(3, int(data["radius"] * self.size_mult))
            dmg = data["damage"] * self.dmg_mult
            p = Projectile(
                cx, cy, ax * spd, ay * spd,
                owner_id=self.player_id, spell_id=sid,
                radius=r, damage=dmg,
                color=data["color"], glow_col=data.get("glow", data["color"]),
                lifetime=data["lifetime"], knockback=data.get("knockback", 0),
                aoe_radius=0, aoe_damage=0, slow=0, slow_dur=0,
                chain_count=data.get("chain_count", 2),
                chain_range=data.get("chain_range", 140),
            )
            projs.append(p)

        elif typ == "buff":
            buff = BuffEffect(self, data, sid)
            spawned_effects.append(buff)

        elif typ == "pull":
            pull = PullZone(
                cx + ax * data["radius"] * 0.4,
                cy + ay * data["radius"] * 0.4,
                owner_id=self.player_id, spell_id=sid,
                radius=data["radius"],
                pull_force=data["pull_force"],
                duration=data["duration"],
                damage=data.get("damage", 0) * self.dmg_mult,
                color=data["color"],
            )
            spawned_effects.append(pull)

        return projs

    # ── Damage / healing ──────────────────────────────────────────────────────

    def take_damage(self, amount, attacker=None):
        if not self.alive:
            return 0.0
        if self.invincible_t > 0:
            return 0.0
        if self.shield_hits > 0:
            self.shield_hits -= 1
            self.hit_flash_t = 0.1
            return 0.0

        if "ignite" in self.debuffs:
            amount *= 1.3

        self.hp -= amount
        self.hit_flash_t = 0.15
        if self.hp <= 0:
            self.hp = 0
            self.die()

        if attacker:
            attacker.damage_dealt += amount
            heal = amount * attacker.life_steal
            if heal > 0:
                attacker.heal(heal)

        return amount

    def apply_slow(self, factor, duration):
        if factor < self.slow_factor:
            self.slow_factor = factor
        self.slow_timer = max(self.slow_timer, duration)

    def apply_root(self, duration):
        self.root_timer = max(self.root_timer, duration)

    def apply_blind(self, duration):
        self.blind_timer = max(self.blind_timer, duration)

    def apply_debuff(self, debuff_id, duration):
        self.debuffs[debuff_id] = max(self.debuffs.get(debuff_id, 0), duration)

    def heal(self, amount):
        self.hp = min(self.hp + amount, self.max_hp)

    def die(self):
        self.alive = False
        self.vx = 0; self.vy = 0

    # ── Upgrade application ───────────────────────────────────────────────────

    def apply_upgrade(self, upg):
        self.upgrades.append(upg["id"])
        stat = upg["stat"]
        amt  = upg["amount"]
        if   stat == "dmg_mult":         self.dmg_mult         += amt
        elif stat == "cast_mult":        self.cast_mult         += amt
        elif stat == "size_mult":        self.size_mult         += amt
        elif stat == "pspd_mult":        self.pspd_mult         += amt
        elif stat == "max_hp":
            self.max_hp += int(amt)
            self.hp      = min(self.hp + int(amt), self.max_hp)
        elif stat == "multicast_chance": self.multicast_chance  = min(0.6, self.multicast_chance + amt)
        elif stat == "bounce":           self.bounce             = True
        elif stat == "pierce_walls":     self.pierce_walls       = True
        elif stat == "life_steal":       self.life_steal         = min(0.25, self.life_steal + amt)
        elif stat == "chill_all":        self.chill_all          = True

    def reset_for_round(self, x, y):
        self.x, self.y  = float(x), float(y)
        self.vx, self.vy = 0.0, 0.0
        self.hp          = float(self.max_hp)
        self.alive       = True
        self.on_ground   = False
        self.invincible_t = SPAWN_INVINCIBLE
        self.slow_factor  = 1.0
        self.slow_timer   = 0.0
        self.root_timer   = 0.0
        self.blind_timer  = 0.0
        self.ignite_timer = 0.0
        self.shield_hits  = 0
        self.debuffs      = {}
        self.hit_flash_t  = 0.0
        self.land_squash  = 1.0
        self.cooldowns    = {s: 0.0 for s in (self.spell_slots + ([self.combo_slot] if self.combo_slot else []))}

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, surf, cam):
        if not self.alive:
            return

        from Assets import Assets

        sx = int(self.x - cam[0])
        sy = int(self.y - cam[1])
        w, h = self.w, self.h

        # Squash/stretch factor
        dh = max(6, int(h * self.land_squash))
        dw = int(w * (1.0 + (1.0 - self.land_squash) * 0.5))  # squash widens
        dy = sy - dh

        # ── Ground shadow ─────────────────────────────────────────────────
        shadow_s = pygame.Surface((dw + 8, 7), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_s, (0, 0, 0, 80), shadow_s.get_rect())
        surf.blit(shadow_s, (sx - dw//2 - 4, sy - 4))

        # ── Status aura rings (drawn behind sprite) ───────────────────────
        cy_mid = dy + dh // 2
        if self.shield_hits > 0:
            _draw_ring(surf, sx, cy_mid, dw//2 + 9, (180, 230, 255), 3, self.anim_t * 3)
        if self.slow_timer > 0:
            _draw_ring(surf, sx, cy_mid, dw//2 + 13, (100, 160, 255), 1, -self.anim_t * 2)
        if "ignite" in self.debuffs:
            _draw_ring(surf, sx, cy_mid, dw//2 + 7, (255, 120, 0), 2, self.anim_t * 5)

        # ── Wizard sprite ─────────────────────────────────────────────────
        sprite = Assets.wizard(self.player_id, dw, dh)

        # Flip horizontally when facing left
        if self.facing < 0:
            sprite = pygame.transform.flip(sprite, True, False)

        # Hit flash: tint white
        if self.hit_flash_t > 0:
            tinted = sprite.copy()
            tinted.fill((255, 255, 255, 160), special_flags=pygame.BLEND_RGBA_ADD)
            sprite = tinted

        # Spawn invincibility: blink by skipping every other frame
        if self.invincible_t > 0 and int(self.anim_t * 10) % 2 == 0:
            sprite = sprite.copy()
            sprite.set_alpha(120)

        surf.blit(sprite, (sx - dw//2, dy))

        # ── Wand glow tip ─────────────────────────────────────────────────
        wand_tx = sx + self.facing * (dw//2 + 6)
        wand_ty = dy + int(dh * 0.52)
        glow_col = self.color
        glow_s = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(glow_s, (*glow_col, 140), (9, 9), 7)
        pygame.draw.circle(glow_s, (255, 255, 255, 180), (9, 9), 3)
        surf.blit(glow_s, (wand_tx - 9, wand_ty - 9))

        # ── Cooldown-ready sparkles ───────────────────────────────────────
        for i, sid in enumerate(self.spell_slots[:3]):
            if self.cooldowns.get(sid, 0) <= 0:
                angle = self.anim_t * 2.5 + i * 2.1
                px = sx + int(math.cos(angle) * (dw//2 + 4))
                py = cy_mid + int(math.sin(angle) * (dh//2 + 4))
                ec = ELEM_COL.get(self.element, WHITE)
                pygame.draw.circle(surf, (*ec, 180), (px, py), 2)

        # ── Root ice block ────────────────────────────────────────────────
        if self.root_timer > 0:
            ice_surf = pygame.Surface((dw + 6, 10), pygame.SRCALPHA)
            pygame.draw.rect(ice_surf, (100, 195, 255, 200), ice_surf.get_rect(), border_radius=3)
            surf.blit(ice_surf, (sx - dw//2 - 3, sy - 6))

    def draw_hud_nameplate(self, surf, cam, name):
        sx  = int(self.x  - cam[0])
        sy  = int(self.y - self.h - 14 - cam[1])
        ec  = ELEM_COL.get(self.element, TEXT_MAIN)
        fnt = pygame.font.SysFont("Segoe UI", 11, bold=True)
        lbl = fnt.render(name, True, ec)
        # Small bg pill
        pill = pygame.Surface((lbl.get_width() + 8, lbl.get_height() + 4), pygame.SRCALPHA)
        pygame.draw.rect(pill, (10, 8, 22, 160), pill.get_rect(), border_radius=4)
        surf.blit(pill, pill.get_rect(midbottom=(sx, sy + pill.get_height()//2 + 2)))
        surf.blit(lbl, lbl.get_rect(midbottom=(sx, sy)))


# ── Module-level drawing helpers ──────────────────────────────────────────────

def _draw_ring(surf, cx, cy, radius, color, width, phase=0.0):
    """Animated dotted ring around a wizard."""
    import math
    for i in range(12):
        angle = phase + i * (2 * math.pi / 12)
        rx = cx + int(math.cos(angle) * radius)
        ry = cy + int(math.sin(angle) * radius)
        pygame.draw.circle(surf, color, (rx, ry), width)