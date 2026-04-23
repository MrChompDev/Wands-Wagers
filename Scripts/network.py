# network.py  ─  Wand & Wager  ─  Shared networking protocol
#
# All messages are JSON.  Every message has a "type" key.
#
# Client → Server:
#   {"type":"join",   "name":"P1", "element":"fire", "wand":"oak"}
#   {"type":"ready"}
#   {"type":"input",  "seq":int, "left":bool, "right":bool, "jump":bool,
#                     "cast":[slot,...], "aim_x":float, "aim_y":float}
#   {"type":"aon_decision", "decision":"hold"|"wager", "pick":"heads"|"tails"|null}
#   {"type":"ping",   "t":float}
#
# Server → Client:
#   {"type":"welcome",     "your_id":int, "players":[...]}
#   {"type":"player_join", "id":int, "name":str, "element":str, "wand":str}
#   {"type":"player_leave","id":int}
#   {"type":"start_match", "players":[{id,element,wand,name}], "map":str}
#   {"type":"state",       "seq":int, "tick":int, "players":[...], "projectiles":[...], "effects":[...]}
#   {"type":"round_over",  "winner_id":int, "round_num":int}
#   {"type":"aon_start",   "round_winner":int, "slots":[{pid,cards:[...],is_winner:bool}]}
#   {"type":"aon_result",  "results":{pid:{outcome,final_upgs:[...],wipe:bool}}}
#   {"type":"match_over",  "winner_id":int, "scores":[{pid,wins,dmg}]}
#   {"type":"chat",        "pid":int, "text":str}
#   {"type":"pong",        "t":float}
#   {"type":"error",       "msg":str}

import json
import math


DEFAULT_PORT = 7890
DEFAULT_HOST = "0.0.0.0"


# ── Message builders ──────────────────────────────────────────────────────────

def msg(**kwargs) -> str:
    return json.dumps(kwargs)


def pack_input(seq, left, right, jump, casts, aim_x, aim_y) -> str:
    return json.dumps({
        "type":  "input",
        "seq":   seq,
        "left":  left,
        "right": right,
        "jump":  jump,
        "cast":  casts,      # list of slot indices fired this tick
        "aim_x": round(aim_x, 4),
        "aim_y": round(aim_y, 4),
    })


def pack_state(seq, tick, players, projectiles, effects) -> str:
    return json.dumps({
        "type":        "state",
        "seq":         seq,
        "tick":        tick,
        "players":     players,
        "projectiles": projectiles,
        "effects":     effects,
    })


def unpack(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        return {"type": "invalid"}


# ── State serialisers (server → client) ───────────────────────────────────────

def serialise_player(p) -> dict:
    return {
        "id":          p.player_id,
        "x":           round(p.x, 2),
        "y":           round(p.y, 2),
        "vx":          round(p.vx, 2),
        "vy":          round(p.vy, 2),
        "hp":          round(p.hp, 1),
        "max_hp":      p.max_hp,
        "alive":       p.alive,
        "facing":      p.facing,
        "element":     p.element,
        "wand":        p.wand_id,
        "round_wins":  p.round_wins,
        "upgrades":    p.upgrades,
        "cooldowns":   {k: round(v, 3) for k, v in p.cooldowns.items()},
        "shield":      p.shield_hits,
        "slow":        round(p.slow_factor, 3),
        "root":        round(p.root_timer, 3),
        "debuffs":     {k: round(v, 2) for k, v in p.debuffs.items()},
    }


def serialise_projectile(pr) -> dict:
    return {
        "id":       id(pr),
        "x":        round(pr.x, 2),
        "y":        round(pr.y, 2),
        "vx":       round(pr.vx, 2),
        "vy":       round(pr.vy, 2),
        "r":        pr.radius,
        "color":    pr.color,
        "glow":     pr.glow_col,
        "owner":    pr.owner_id,
        "spell":    pr.spell_id,
    }


def serialise_effect(e) -> dict:
    from spells import WallEntity, AoeEffect, PullZone, DashEffect
    base = {"eid": id(e), "alive": e.alive}
    if isinstance(e, WallEntity):
        base.update({"etype": "wall",
                     "rect": [e.rect.x, e.rect.y, e.rect.w, e.rect.h],
                     "color": e.color, "glow": e.glow_col,
                     "owner": e.owner_id})
    elif isinstance(e, AoeEffect):
        base.update({"etype": "aoe",
                     "x": round(e.x,2), "y": round(e.y,2),
                     "r": e.radius, "color": e.color,
                     "fired": e.fired})
    elif isinstance(e, PullZone):
        base.update({"etype": "pull",
                     "x": round(e.x,2), "y": round(e.y,2),
                     "r": e.radius, "color": e.color})
    else:
        base["etype"] = "other"
    return base


# ── Latency / connection helpers ──────────────────────────────────────────────

import time

class PingTracker:
    def __init__(self):
        self._sent = {}
        self.rtt   = 0.0   # ms

    def send(self, ws_send_fn):
        t = time.monotonic()
        self._sent[round(t, 4)] = t
        return msg(type="ping", t=round(t, 4))

    def receive_pong(self, t):
        if t in self._sent:
            self.rtt = (time.monotonic() - self._sent.pop(t)) * 1000