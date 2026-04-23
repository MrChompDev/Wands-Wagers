#!/usr/bin/env python3
# server.py  ─  Wand & Wager  ─  Authoritative online game server
#
# Usage:
#   python Scripts/server.py                   # default port 7890
#   python Scripts/server.py --port 8000
#   python Scripts/server.py --host 0.0.0.0 --port 7890

import asyncio
import json
import logging
import sys
import os
import time
import argparse
import random
import math

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── Headless pygame stub (server has no display) ──────────────────────────────
try:
    import pygame
except ImportError:
    import pygame_stub as pygame
    sys.modules["pygame"] = pygame
    sys.modules["pygame.font"]      = pygame.font
    sys.modules["pygame.mixer"]     = pygame.mixer
    sys.modules["pygame.image"]     = pygame.image
    sys.modules["pygame.draw"]      = pygame.draw
    sys.modules["pygame.transform"] = pygame.transform
    sys.modules["pygame.display"]   = pygame.display

import websockets
from websockets.server import serve

from network import (msg, unpack, pack_state,
                     serialise_player, serialise_projectile, serialise_effect,
                     DEFAULT_PORT)
from constants import *

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SERVER] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("server")

SIM_HZ        = 60
BROADCAST_HZ  = 20
MAX_PLAYERS   = 8
LOBBY_TIMEOUT = 120.0


class ClientConn:
    def __init__(self, ws, pid):
        self.ws          = ws
        self.pid         = pid
        self.name        = f"P{pid + 1}"
        self.element     = "fire"
        self.wand        = "oak"
        self.ready       = False
        self.connected   = True
        self.last_input  = {}
        self.last_seq    = -1
        self.ping_ms     = 0.0

    async def send(self, data: str):
        try:
            await self.ws.send(data)
        except Exception:
            self.connected = False

    async def send_obj(self, **kwargs):
        await self.send(msg(**kwargs))


class GameServer:

    ST_LOBBY   = "lobby"
    ST_PLAYING = "playing"
    ST_AON     = "aon"

    def __init__(self):
        self.clients:  dict[int, ClientConn] = {}
        self._next_pid = 0
        self.state     = self.ST_LOBBY
        self.players    = []
        self.cpus       = []
        self.arena      = None
        self.projectiles = []
        self.effects    = []
        self.round_num  = 1
        self.round_time = 0.0
        self._tick      = 0
        self._broadcast_acc = 0.0
        self._aon_decisions = {}
        self._aon_results   = {}
        log.info("Server initialised")

    async def register(self, ws) -> ClientConn | None:
        if len(self.clients) >= MAX_PLAYERS:
            await ws.send(msg(type="error", msg="Server full"))
            return None
        if self.state != self.ST_LOBBY:
            await ws.send(msg(type="error", msg="Match already in progress"))
            return None

        pid    = self._next_pid
        self._next_pid += 1
        client = ClientConn(ws, pid)
        self.clients[pid] = client

        existing = [{"id": c.pid, "name": c.name,
                     "element": c.element, "wand": c.wand}
                    for c in self.clients.values() if c.pid != pid]
        await client.send_obj(type="welcome", your_id=pid, players=existing)
        await self._broadcast(msg(type="player_join", id=pid,
                                  name=client.name,
                                  element=client.element,
                                  wand=client.wand), exclude=pid)
        log.info(f"Player {pid} connected  ({len(self.clients)} in lobby)")
        return client

    async def unregister(self, pid):
        if pid in self.clients:
            self.clients[pid].connected = False
            del self.clients[pid]
            await self._broadcast(msg(type="player_leave", id=pid))
            log.info(f"Player {pid} disconnected  ({len(self.clients)} remaining)")
            if self.state == self.ST_PLAYING and len(self.clients) < 1:
                log.info("All players disconnected — resetting")
                self._reset()

    async def handle_message(self, client: ClientConn, raw: str):
        m = unpack(raw)
        t = m.get("type")

        if t == "join":
            client.name    = m.get("name", client.name)[:20]
            client.element = m.get("element", "fire")
            client.wand    = m.get("wand", "oak")
            await self._broadcast(msg(type="player_join",
                                      id=client.pid,
                                      name=client.name,
                                      element=client.element,
                                      wand=client.wand))
        elif t == "ready":
            client.ready = True
            await self._broadcast(msg(type="player_ready", id=client.pid))
            log.info(f"P{client.pid} ready  "
                     f"({sum(1 for c in self.clients.values() if c.ready)}/{len(self.clients)} ready)")
            await self._check_start()
        elif t == "input":
            if m.get("seq", -1) > client.last_seq:
                client.last_seq   = m["seq"]
                client.last_input = m
        elif t == "aon_decision":
            self._aon_decisions[client.pid] = {
                "decision": m.get("decision", "hold"),
                "pick":     m.get("pick"),
            }
            await self._check_aon_complete()
        elif t == "ping":
            await client.send_obj(type="pong", t=m.get("t", 0))
        elif t == "chat":
            text = str(m.get("text", ""))[:120]
            await self._broadcast(msg(type="chat", pid=client.pid, text=text))

    async def _check_start(self):
        ready = [c for c in self.clients.values() if c.ready]
        total = len(self.clients)
        if total >= 2 and len(ready) == total:
            await self._start_match()
        elif total == 1 and len(ready) == 1:
            await self._start_match()

    async def _start_match(self):
        self.state = self.ST_PLAYING
        log.info(f"Starting match with {len(self.clients)} human player(s)")

        from player import Player
        from ai import CPUController
        from arena import Arena, MAPS_DIR

        player_configs = []
        for c in self.clients.values():
            player_configs.append({"pid": c.pid, "element": c.element,
                                   "wand": c.wand, "name": c.name, "is_cpu": False})

        cpu_pids = []
        while len(player_configs) < 2:
            cpid = self._next_pid
            self._next_pid += 1
            elem = random.choice(list(ELEMENT_SPELLS.keys()))
            player_configs.append({"pid": cpid, "element": elem,
                                   "wand": random.choice(list(WANDS.keys())),
                                   "name": f"CPU{cpid}", "is_cpu": True})
            cpu_pids.append(cpid)

        import json as _json
        maps = [f for f in os.listdir(MAPS_DIR) if f.endswith(".json")]
        map_name = random.choice(maps) if maps else None
        if map_name:
            with open(os.path.join(MAPS_DIR, map_name)) as f:
                map_data = _json.load(f)
        else:
            map_data = self._default_map()
        self.arena = Arena(map_data)

        self.players = []
        for cfg in player_configs:
            sx, sy = self.arena.get_spawn(cfg["pid"] % 8)
            p = Player(sx, sy, cfg["pid"], cfg["element"], cfg["wand"])
            self.players.append(p)

        self.cpus = [CPUController(p, "medium")
                     for p in self.players
                     if p.player_id in cpu_pids]

        self.projectiles = []
        self.effects     = []
        self.round_num   = 1
        self.round_time  = 0.0

        await self._broadcast(msg(
            type="start_match",
            players=[{"id": cfg["pid"], "element": cfg["element"],
                      "wand": cfg["wand"], "name": cfg["name"],
                      "is_cpu": cfg["is_cpu"]}
                     for cfg in player_configs],
            map=map_data.get("name", "unknown")
        ))
        log.info("Match started")

    def tick(self, dt: float):
        if self.state != self.ST_PLAYING or not self.arena:
            return

        self._tick      += 1
        self.round_time += dt

        from spells import Projectile
        for pid, client in list(self.clients.items()):
            inp = client.last_input
            if not inp: continue
            player = self._player_by_id(pid)
            if not player or not player.alive: continue

            if inp.get("left"):   player.move_left()
            if inp.get("right"):  player.move_right()
            if inp.get("jump"):   player.jump()

            ax = float(inp.get("aim_x", player.facing))
            ay = float(inp.get("aim_y", 0.0))
            for slot in inp.get("cast", []):
                projs = player.try_cast(slot, ax, ay, self.effects)
                self.projectiles.extend(projs)

        for cpu in self.cpus:
            cpu.update(dt, self.players, self.projectiles,
                       self.arena.platforms, self.arena.safe_rect, self.effects)

        self.arena.update(dt, self.round_time)
        for p in self.players:
            p.update(dt, self.arena.platforms, self.arena.safe_rect)

        for p in self.players:
            if p.alive and not self.arena.is_in_safe_zone(p.x, p.y):
                p.take_damage(OOB_DAMAGE * dt)

        for p in self.players:
            if not p.alive: continue
            for plat in self.arena.platforms:
                if plat.dps > 0 and plat.rect.colliderect(p.feet):
                    p.take_damage(plat.dps * dt)

        from spells import WallEntity, DashEffect, TrapEntity, AoeEffect, BuffEffect, PullZone
        new_projs = []
        for proj in self.projectiles:
            if not proj.alive: continue
            proj.update(dt, self.arena.safe_rect)
            if not proj.alive: continue
            for p in self.players:
                if not p.alive or p.player_id == proj.owner_id: continue
                if proj.collides_with(p):
                    owner = self._player_by_id(proj.owner_id)
                    actual = p.take_damage(proj.damage, owner)
                    if actual > 0:
                        if proj.slow > 0: p.apply_slow(proj.slow, proj.slow_dur)
                        if proj.debuff:   p.apply_debuff(proj.debuff, proj.debuff_dur)
                        kn = proj.knockback
                        if kn > 0:
                            ln = math.hypot(proj.vx, proj.vy) or 1
                            p.vx += proj.vx/ln * kn
                            p.vy += proj.vy/ln * kn * 0.5
                        if getattr(proj,"chain_count",0) > 0:
                            new_projs += self._chain_arc(proj, p)
                    proj.alive = False
                    break
            for eff in self.effects:
                if isinstance(eff, WallEntity) and eff.alive:
                    if proj.collides_wall(eff):
                        if proj.pierce_walls:
                            eff.take_damage(proj.damage * 0.5)
                        else:
                            eff.take_damage(proj.damage)
                            proj.alive = False
                        break
        self.projectiles = [p for p in self.projectiles if p.alive] + new_projs

        wall_spikes = []
        for eff in self.effects:
            if not eff.alive: continue
            eff.update(dt)
            if isinstance(eff, WallEntity):
                if eff.dps > 0:
                    for p in self.players:
                        if p.alive and p.player_id != eff.owner_id and eff.rect.colliderect(p.feet):
                            p.take_damage(eff.dps * dt)
                wall_spikes += eff.emit_spikes()
            elif isinstance(eff, TrapEntity):
                for p in self.players:
                    if p.alive and p.player_id != eff.owner_id and not eff.triggered:
                        if eff.collides_player(p):
                            eff.triggered = True; eff.alive = False
                            owner = self._player_by_id(eff.owner_id)
                            actual = p.take_damage(eff.damage, owner)
                            p.apply_root(eff.root_dur)
            elif isinstance(eff, AoeEffect):
                if eff.ready_to_hit():
                    for p in self.players:
                        if p.alive and p.player_id != eff.owner_id and eff.collides_player(p):
                            owner = self._player_by_id(eff.owner_id)
                            actual = p.take_damage(eff.damage, owner)
                            if eff.slow > 0: p.apply_slow(eff.slow, eff.slow_dur)
            elif isinstance(eff, PullZone):
                for p in self.players:
                    if p.alive and p.player_id != eff.owner_id and eff.in_range(p):
                        eff.apply_pull(p, dt)
                        p.take_damage(eff.damage * dt)
        self.projectiles += wall_spikes
        self.effects = [e for e in self.effects if e.alive]

    def _chain_arc(self, proj, hit):
        from spells import Projectile
        cr = getattr(proj,"chain_range",140)
        targets = [p for p in self.players
                   if p.alive and p is not hit and p.player_id != proj.owner_id
                   and math.hypot(p.cx-hit.cx,p.cy-hit.cy) < cr]
        if not targets: return []
        t = min(targets, key=lambda p: math.hypot(p.cx-hit.cx,p.cy-hit.cy))
        dx=t.cx-hit.cx; dy=t.cy-hit.cy; ln=math.hypot(dx,dy) or 1
        spd = SPELLS.get("chain_lightning",{}).get("speed",500)
        np = Projectile(hit.cx,hit.cy, dx/ln*spd,dy/ln*spd,
            owner_id=proj.owner_id, spell_id="chain_lightning",
            radius=7, damage=proj.damage*0.7,
            color=proj.color, glow_col=proj.glow_col,
            lifetime=0.4, knockback=40,
            aoe_radius=0, aoe_damage=0, slow=0, slow_dur=0,
            chain_count=proj.chain_count-1, chain_range=cr)
        return [np]

    async def check_round_end(self):
        if self.state != self.ST_PLAYING: return
        alive = [p for p in self.players if p.alive]
        if len(alive) > 1: return

        winner = alive[0] if alive else None
        if winner:
            winner.round_wins += 1
        wid = winner.player_id if winner else -1
        log.info(f"Round {self.round_num} over — winner P{wid}")

        await self._broadcast(msg(type="round_over",
                                  winner_id=wid,
                                  round_num=self.round_num))

        for p in self.players:
            if p.round_wins >= ROUNDS_TO_WIN:
                await self._broadcast(msg(type="match_over",
                    winner_id=p.player_id,
                    scores=[{"pid":pl.player_id,"wins":pl.round_wins,
                             "dmg":int(pl.damage_dealt)} for pl in self.players]))
                self._reset()
                return

        await self._start_aon(wid)

    async def _start_aon(self, winner_id):
        self.state = self.ST_AON
        self._aon_decisions.clear()
        self._aon_results.clear()

        from upgrade_screen import WINNER_CARDS, LOSER_CARDS

        slots = []
        for p in self.players:
            n    = WINNER_CARDS if p.player_id == winner_id else LOSER_CARDS
            pool = [u for u in UPGRADES]
            random.shuffle(pool)
            cards = pool[:n]
            slots.append({"pid": p.player_id,
                          "cards": cards,
                          "is_winner": p.player_id == winner_id})

        self._aon_slots = {s["pid"]: s for s in slots}
        await self._broadcast(msg(type="aon_start",
                                  round_winner=winner_id,
                                  slots=slots))
        log.info("AON phase started")

    async def _check_aon_complete(self):
        human_pids = set(self.clients.keys())
        decided    = set(self._aon_decisions.keys())
        if not human_pids.issubset(decided):
            return

        for p in self.players:
            if p.player_id not in self.clients:
                ex = len(p.upgrades)
                wager = random.random() < max(0.2, 0.55 - ex * 0.04)
                self._aon_decisions[p.player_id] = {
                    "decision": "wager" if wager else "hold",
                    "pick":     random.choice(["heads","tails"]) if wager else None
                }

        results = {}
        for p in self.players:
            pid  = p.player_id
            dec  = self._aon_decisions.get(pid, {"decision":"hold","pick":None})
            slot = self._aon_slots.get(pid, {})
            cards = slot.get("cards", [])

            if dec["decision"] == "hold":
                results[pid] = {"outcome":"hold", "upgrades":cards, "wipe":False}
                for upg in cards:
                    p.apply_upgrade(upg)
            else:
                coin = random.random() < 0.5
                pick_heads = (dec.get("pick") == "heads")
                won  = (pick_heads == coin)
                if won:
                    doubled = cards * 2
                    results[pid] = {"outcome":"win", "upgrades":doubled, "wipe":False}
                    for upg in doubled:
                        p.apply_upgrade(upg)
                else:
                    results[pid] = {"outcome":"lose", "upgrades":[], "wipe":True}
                    p.upgrades.clear()
                    wd = WANDS.get(p.wand_id, {})
                    p.dmg_mult = wd.get("dmg",1.0)
                    p.cast_mult = wd.get("cast",1.0)
                    p.size_mult = wd.get("size",1.0)
                    p.pspd_mult = wd.get("pspd",1.0)
                    p.multicast_chance = 0.0
                    p.life_steal = 0.0

        await self._broadcast(msg(type="aon_result", results=results))
        log.info("AON resolved — starting next round")
        self._start_round()

    def _start_round(self):
        self.state      = self.ST_PLAYING
        self.round_num += 1
        self.round_time = 0.0
        self.projectiles.clear()
        self.effects.clear()
        if self.arena:
            # Use the already-imported pygame (real or stub)
            import pygame as _pg
            self.arena.safe_rect  = _pg.Rect(0, 0, self.arena.width, self.arena.height)
            self.arena._shrinking = False
        for i, p in enumerate(self.players):
            sx, sy = self.arena.get_spawn(i)
            p.reset_for_round(sx, sy)

    async def broadcast_state(self):
        if self.state != self.ST_PLAYING: return
        ps = [serialise_player(p) for p in self.players]
        pr = [serialise_projectile(p) for p in self.projectiles[:64]]
        ef = [serialise_effect(e) for e in self.effects[:32]]
        payload = pack_state(self._tick, self._tick, ps, pr, ef)
        await self._broadcast(payload)

    async def _broadcast(self, data: str, exclude: int = -1):
        dead = []
        for pid, c in list(self.clients.items()):
            if pid == exclude: continue
            if c.connected:
                try:
                    await c.ws.send(data)
                except Exception:
                    dead.append(pid)
        for pid in dead:
            await self.unregister(pid)

    def _player_by_id(self, pid):
        return next((p for p in self.players if p.player_id == pid), None)

    def _reset(self):
        self.state      = self.ST_LOBBY
        self.players    = []
        self.cpus       = []
        self.arena      = None
        self.projectiles= []
        self.effects    = []
        self.round_num  = 1
        self.round_time = 0.0
        self._tick      = 0
        for c in self.clients.values():
            c.ready = False
        log.info("Server reset to lobby")

    @staticmethod
    def _default_map():
        cols, rows = 40, 22
        grid = [[0]*cols for _ in range(rows)]
        for c in range(cols): grid[rows-1][c] = 1
        for c,r,l in [(5,16,8),(15,14,6),(27,16,8),(10,11,10),(22,12,6),(14,6,12)]:
            for i in range(l):
                if c+i<cols: grid[r][c+i]=1
        return {"name":"default","cols":cols,"rows":rows,"tile_size":32,
                "grid":grid,"spawn_points":[[3,20],[36,20],[8,15],[32,15],[13,10],[26,10]]}


# ─────────────────────────────────────────────────────────────────────────────

server = GameServer()


async def handle_client(ws):
    client = await server.register(ws)
    if client is None:
        return
    try:
        async for raw in ws:
            await server.handle_message(client, raw)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await server.unregister(client.pid)


async def sim_loop():
    dt          = 1.0 / SIM_HZ
    bc_interval = 1.0 / BROADCAST_HZ
    acc         = 0.0
    last        = time.monotonic()

    while True:
        now   = time.monotonic()
        delta = now - last
        last  = now

        server.tick(delta)
        await server.check_round_end()

        acc += delta
        if acc >= bc_interval:
            acc -= bc_interval
            await server.broadcast_state()

        elapsed = time.monotonic() - now
        sleep   = max(0.0, dt - elapsed)
        await asyncio.sleep(sleep)


async def main_async(host, port):
    log.info(f"Starting Wand & Wager server on {host}:{port}")
    async with serve(handle_client, host, port):
        await sim_loop()


def main():
    # Railway requires 0.0.0.0 and reads port from the PORT env var
    default_host = os.environ.get("HOST", "0.0.0.0")
    default_port = int(os.environ.get("PORT", DEFAULT_PORT))

    parser = argparse.ArgumentParser(description="Wand & Wager server")
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=default_port)
    args = parser.parse_args()

    log.info(f"Binding to {args.host}:{args.port}")
    try:
        asyncio.run(main_async(args.host, args.port))
    except KeyboardInterrupt:
        log.info("Server stopped")


if __name__ == "__main__":
    main()
