# multiplayer.py  ─  Wand & Wager  ─  Client networking
#
# Runs the websocket connection in a background thread so the Pygame
# main loop never blocks.  Game code calls:
#
#   net = NetworkClient()
#   net.connect("ws://192.168.1.5:7890")
#   net.send_join("fire", "oak")
#   net.send_ready()
#
#   # In game loop:
#   for msg in net.poll():
#       handle(msg)           # msg is a dict
#
#   net.send_input(seq, left, right, jump, casts, aim_x, aim_y)
#   net.disconnect()

import asyncio
import threading
import queue
import time
import math
import logging

import websockets

from network import (msg, unpack, pack_input, DEFAULT_PORT)

log = logging.getLogger("client")


# ─────────────────────────────────────────────────────────────────────────────
class NetworkClient:

    def __init__(self):
        self._loop      = asyncio.new_event_loop()
        self._thread    = None
        self._ws        = None
        self._send_q    = queue.Queue()     # main thread → net thread
        self._recv_q    = queue.Queue()     # net thread  → main thread
        self.connected  = False
        self.connecting = False
        self.error      = None
        self.your_id    = -1
        self.ping_ms    = 0.0
        self._seq       = 0
        self._ping_sent = {}

    # ── Public API (call from main thread) ────────────────────────────────────

    def connect(self, url: str):
        """Start background thread and connect to server."""
        if self._thread and self._thread.is_alive():
            return
        self.connecting = True
        self.error      = None
        self._thread    = threading.Thread(
            target=self._run, args=(url,), daemon=True)
        self._thread.start()

    def disconnect(self):
        self._enqueue(None)   # sentinel → close

    def send_join(self, name: str, element: str, wand: str):
        self._enqueue(msg(type="join", name=name,
                          element=element, wand=wand))

    def send_ready(self):
        self._enqueue(msg(type="ready"))

    def send_input(self, left, right, jump, casts, aim_x, aim_y):
        self._seq += 1
        self._enqueue(pack_input(self._seq, left, right, jump,
                                 casts, aim_x, aim_y))

    def send_aon_decision(self, decision: str, pick: str | None = None):
        self._enqueue(msg(type="aon_decision", decision=decision, pick=pick))

    def send_chat(self, text: str):
        self._enqueue(msg(type="chat", text=text))

    def poll(self) -> list[dict]:
        """Drain the receive queue and return all pending messages."""
        msgs = []
        while not self._recv_q.empty():
            try:
                msgs.append(self._recv_q.get_nowait())
            except queue.Empty:
                break
        return msgs

    def _enqueue(self, data):
        self._send_q.put(data)

    # ── Background thread ─────────────────────────────────────────────────────

    def _run(self, url: str):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop(url))
        except Exception as e:
            self.error = str(e)
            self.connected  = False
            self.connecting = False

    async def _connect_loop(self, url: str):
        try:
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                self._ws        = ws
                self.connected  = True
                self.connecting = False
                log.info(f"Connected to {url}")
                self._recv_q.put({"type": "_connected"})

                sender = asyncio.create_task(self._sender(ws))
                try:
                    async for raw in ws:
                        m = unpack(raw)
                        if m.get("type") == "pong":
                            t = m.get("t", 0)
                            if t in self._ping_sent:
                                self.ping_ms = (time.monotonic() - self._ping_sent.pop(t)) * 1000
                        else:
                            if m.get("type") == "welcome":
                                self.your_id = m.get("your_id", -1)
                            self._recv_q.put(m)
                except websockets.exceptions.ConnectionClosed:
                    pass
                finally:
                    sender.cancel()

        except (OSError, websockets.exceptions.WebSocketException) as e:
            self.error     = f"Connection failed: {e}"
            self.connected = False
            self.connecting = False
            self._recv_q.put({"type": "_error", "msg": str(e)})
            log.warning(self.error)

        self.connected  = False
        self.connecting = False
        self._recv_q.put({"type": "_disconnected"})

    async def _sender(self, ws):
        """Drain the send queue and forward messages over the websocket."""
        loop = asyncio.get_event_loop()
        while True:
            try:
                # Check queue without blocking
                data = await loop.run_in_executor(
                    None, lambda: self._send_q.get(timeout=0.05))
                if data is None:
                    await ws.close()
                    break
                await ws.send(data)
            except queue.Empty:
                # Send a ping every 5 seconds
                t = round(time.monotonic(), 4)
                self._ping_sent[t] = time.monotonic()
                try:
                    await ws.send(msg(type="ping", t=t))
                except Exception:
                    break
            except Exception:
                break


# ─────────────────────────────────────────────────────────────────────────────
#  Lobby / connect screen (rendered on BASE_W × BASE_H virtual surface)
# ─────────────────────────────────────────────────────────────────────────────

import pygame
from constants import (BASE_W, BASE_H, HUD_H, ELEM_COL, ELEM_LABELS,
                       ELEMENT_SPELLS, SPELLS, WANDS, COMBOS,
                       DARK_BG, BORDER_COL, TEXT_MAIN, TEXT_DIM,
                       GOLD, SILVER, HP_GREEN, HP_RED, WHITE)
from hud import draw_text


class LobbyScreen:
    """
    Shown instead of the char select when multiplayer is chosen.
    Handles:
      - Server IP / port entry
      - Element + wand pick (same as char select)
      - Ready button
      - Player list with ready status
    Transitions to the game once the server sends "start_match".
    """

    ELEMENTS = list(ELEMENT_SPELLS.keys())
    WAND_IDS = list(WANDS.keys())

    def __init__(self, net: NetworkClient):
        self.net      = net
        self.done     = False          # True when match starts
        self.match_data = None         # the "start_match" message

        self.font_sm  = pygame.font.SysFont("Segoe UI", 12)
        self.font_md  = pygame.font.SysFont("Segoe UI", 15)
        self.font_lg  = pygame.font.SysFont("Segoe UI", 20, bold=True)
        self.font_xl  = pygame.font.SysFont("Segoe UI", 32, bold=True)

        # Input state
        self.ip_text      = "localhost"
        self.port_text    = str(DEFAULT_PORT)
        self.name_text    = "Player"
        self.focus_field  = "ip"   # "ip" | "port" | "name"

        self.elem_idx     = 0
        self.wand_idx     = 0

        self._age         = 0.0
        self._status      = "Enter server IP and click Connect"
        self._status_col  = TEXT_DIM
        self._players     = []   # list of {id, name, element, wand, ready}
        self._ready       = False
        self._connected   = False

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                fields = ["name", "ip", "port"]
                i = fields.index(self.focus_field) if self.focus_field in fields else 0
                self.focus_field = fields[(i + 1) % len(fields)]

            elif event.key == pygame.K_BACKSPACE:
                if   self.focus_field == "ip":   self.ip_text   = self.ip_text[:-1]
                elif self.focus_field == "port":  self.port_text = self.port_text[:-1]
                elif self.focus_field == "name":  self.name_text = self.name_text[:-1]

            elif event.key == pygame.K_RETURN:
                if not self._connected:
                    self._do_connect()
                elif not self._ready:
                    self._do_ready()

            elif event.unicode.isprintable():
                ch = event.unicode
                if   self.focus_field == "ip"   and len(self.ip_text)   < 40: self.ip_text   += ch
                elif self.focus_field == "port"  and len(self.port_text) < 6:  self.port_text += ch
                elif self.focus_field == "name"  and len(self.name_text) < 16: self.name_text += ch

            elif event.key == pygame.K_LEFT:
                self.elem_idx = (self.elem_idx - 1) % len(self.ELEMENTS)
                self._send_join()
            elif event.key == pygame.K_RIGHT:
                self.elem_idx = (self.elem_idx + 1) % len(self.ELEMENTS)
                self._send_join()
            elif event.key == pygame.K_UP:
                self.wand_idx = (self.wand_idx - 1) % len(self.WAND_IDS)
                self._send_join()
            elif event.key == pygame.K_DOWN:
                self.wand_idx = (self.wand_idx + 1) % len(self.WAND_IDS)
                self._send_join()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = pygame.mouse.get_pos()
            self._handle_click(mx, my)

    def _handle_click(self, mx, my):
        # Field focus
        for field, r in self._field_rects.items():
            if r.collidepoint(mx, my):
                self.focus_field = field

        # Connect / Ready buttons handled in draw loop (hover+click)

    def _do_connect(self):
        try:
            port = int(self.port_text)
        except ValueError:
            self._set_status("Invalid port number", HP_RED); return

        ip   = self.ip_text.strip()
        url  = f"ws://{ip}:{port}"
        self._set_status(f"Connecting to {url}…", TEXT_DIM)
        self.net.connect(url)

    def _do_ready(self):
        self._ready = True
        self._send_join()
        self.net.send_ready()
        self._set_status("Ready! Waiting for others…", HP_GREEN)

    def _send_join(self):
        if not self._connected: return
        self.net.send_join(
            self.name_text,
            self.ELEMENTS[self.elem_idx],
            self.WAND_IDS[self.wand_idx],
        )

    def _set_status(self, text, col=TEXT_DIM):
        self._status     = text
        self._status_col = col

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        self._age += dt

        for m in self.net.poll():
            t = m.get("type")
            if t == "_connected":
                self._connected = True
                self._set_status("Connected! Choose your wizard and click Ready.", HP_GREEN)
                self._send_join()
            elif t == "_error":
                self._set_status(f"Error: {m.get('msg','?')}", HP_RED)
            elif t == "_disconnected":
                self._connected = False
                self._ready     = False
                self._set_status("Disconnected.", HP_RED)
            elif t == "welcome":
                self.net.your_id = m.get("your_id", -1)
                for p in m.get("players", []):
                    self._upsert_player(p)
            elif t == "player_join":
                self._upsert_player(m)
            elif t == "player_leave":
                self._players = [p for p in self._players if p["id"] != m.get("id")]
            elif t == "player_ready":
                for p in self._players:
                    if p["id"] == m.get("id"):
                        p["ready"] = True
            elif t == "start_match":
                self.match_data = m
                self.done       = True

    def _upsert_player(self, data):
        pid = data.get("id")
        for p in self._players:
            if p["id"] == pid:
                p.update(data); return
        self._players.append({**data, "ready": False})

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf):
        sw, sh = BASE_W, BASE_H
        surf.fill(DARK_BG)
        mx, my = pygame.mouse.get_pos()
        self._field_rects = {}

        # Animated background
        for i in range(60):
            sx = (i * 173 + int(self._age * 7 * (1+i%3))) % sw
            sy = (i * 97  + int(self._age * 3 * (1+i%2))) % sh
            pygame.draw.circle(surf, (40+i%40, 36+i%36, 65+i%40), (sx, sy), 1+(i%3==0))

        draw_text(surf, "WAND & WAGER", self.font_xl, GOLD, sw//2, 20, anchor="midtop")
        draw_text(surf, "Online Multiplayer", self.font_md, TEXT_DIM, sw//2, 62, anchor="midtop")

        # ── Connection fields ─────────────────────────────────────────────
        fy = 92
        for label, key, val, fw in [
            ("Name",        "name", self.name_text, 180),
            ("Server IP",   "ip",   self.ip_text,   260),
            ("Port",        "port", self.port_text,  80),
        ]:
            fx = {"name": sw//2-280, "ip": sw//2-70, "port": sw//2+200}[key]
            draw_text(surf, label, self.font_sm, TEXT_DIM, fx, fy)
            r = pygame.Rect(fx, fy+16, fw, 28)
            self._field_rects[key] = r
            focused = self.focus_field == key
            pygame.draw.rect(surf, (38,30,60) if focused else (22,18,38), r, border_radius=5)
            pygame.draw.rect(surf, GOLD if focused else BORDER_COL, r, 1+(focused), border_radius=5)
            caret  = "|" if focused and int(self._age*2.5)%2==0 else ""
            draw_text(surf, val+caret, self.font_md, TEXT_MAIN, r.x+6, r.centery, anchor="midleft")

        # Connect / Ready button
        if not self._connected:
            btn_lbl = "Connect"
            btn_col = (50,80,130)
            btn_bc  = (100,160,220)
        elif not self._ready:
            btn_lbl = "Ready!"
            btn_col = (30,70,35)
            btn_bc  = HP_GREEN
        else:
            btn_lbl = "Waiting…"
            btn_col = (30,28,50)
            btn_bc  = TEXT_DIM

        br  = pygame.Rect(sw//2+298, fy+16, 100, 28)
        bhov = br.collidepoint(mx,my)
        pygame.draw.rect(surf, tuple(min(255,c+20) for c in btn_col) if bhov else btn_col, br, border_radius=6)
        pygame.draw.rect(surf, btn_bc, br, 1, border_radius=6)
        draw_text(surf, btn_lbl, self.font_md, WHITE, br.centerx, br.centery, anchor="center")
        if bhov and pygame.mouse.get_pressed()[0]:
            if not self._connected: self._do_connect()
            elif not self._ready:   self._do_ready()

        # Status
        draw_text(surf, self._status, self.font_sm, self._status_col,
                  sw//2, fy+52, anchor="midtop")

        # ── Element picker ────────────────────────────────────────────────
        ey  = 175
        ew  = (sw - 28) // len(self.ELEMENTS)
        for i, el in enumerate(self.ELEMENTS):
            sel  = i == self.elem_idx
            ec   = ELEM_COL[el]
            r    = pygame.Rect(14 + i*ew, ey, ew-6, 155)
            bg   = (48,40,76) if sel else (22,18,38)
            pygame.draw.rect(surf, bg, r, border_radius=8)
            pygame.draw.rect(surf, ec if sel else BORDER_COL, r, (2 if sel else 1), border_radius=8)
            pygame.draw.rect(surf, ec, pygame.Rect(r.x, r.y, r.w, 4), border_radius=2)
            draw_text(surf, ELEM_LABELS[el], self.font_md, ec if sel else TEXT_DIM,
                      r.centerx, r.top+12, anchor="midtop")
            sy2 = r.top + 34
            for sp in ELEMENT_SPELLS[el]:
                draw_text(surf, f"• {SPELLS[sp]['name']}", self.font_sm,
                          TEXT_MAIN if sel else TEXT_DIM, r.centerx, sy2, anchor="midtop")
                sy2 += 15
            if r.collidepoint(mx,my) and pygame.mouse.get_pressed()[0]:
                if self.elem_idx != i:
                    self.elem_idx = i; self._send_join()

        draw_text(surf, "← → choose element", self.font_sm, TEXT_DIM, sw//2, ey+162, anchor="midtop")

        # ── Wand picker ───────────────────────────────────────────────────
        wy  = 355
        ww  = (sw - 28) // len(self.WAND_IDS)
        for i, wid in enumerate(self.WAND_IDS):
            wd   = WANDS[wid]
            sel  = i == self.wand_idx
            r    = pygame.Rect(14 + i*ww, wy, ww-6, 56)
            pygame.draw.rect(surf, (44,38,70) if sel else (22,18,38), r, border_radius=6)
            pygame.draw.rect(surf, GOLD if sel else BORDER_COL, r, (2 if sel else 1), border_radius=6)
            draw_text(surf, wd["name"], self.font_sm, TEXT_MAIN if sel else TEXT_DIM,
                      r.centerx, r.top+6, anchor="midtop")
            stats = f"×{wd['dmg']:.1f}dmg  ×{wd['cast']:.1f}spd"
            draw_text(surf, stats, self.font_sm, TEXT_DIM, r.centerx, r.top+24, anchor="midtop")
            if r.collidepoint(mx,my) and pygame.mouse.get_pressed()[0]:
                if self.wand_idx != i:
                    self.wand_idx = i; self._send_join()

        draw_text(surf, "↑ ↓ choose wand", self.font_sm, TEXT_DIM, sw//2, wy+62, anchor="midtop")

        # ── Player list ───────────────────────────────────────────────────
        pl_y = 434
        draw_text(surf, "Players in lobby:", self.font_lg, TEXT_DIM, 20, pl_y)
        pl_y += 26
        # Show self
        my_elem = self.ELEMENTS[self.elem_idx]
        my_ec   = ELEM_COL[my_elem]
        rdylbl  = "READY" if self._ready else "not ready"
        rdycol  = HP_GREEN if self._ready else TEXT_DIM
        draw_text(surf, f"  YOU  ({self.name_text}) — {ELEM_LABELS[my_elem]}  [{rdylbl}]",
                  self.font_md, my_ec, 20, pl_y)
        pl_y += 22
        for p in self._players:
            if p.get("id") == self.net.your_id: continue
            ec  = ELEM_COL.get(p.get("element","fire"), SILVER)
            lbl = ELEM_LABELS.get(p.get("element","fire"), "?")
            rdy = "READY" if p.get("ready") else "waiting"
            rc  = HP_GREEN if p.get("ready") else TEXT_DIM
            draw_text(surf, f"  P{p['id']+1} ({p.get('name','?')}) — {lbl}  [{rdy}]",
                      self.font_md, ec, 20, pl_y)
            pl_y += 22

        # Ping
        if self.net.ping_ms > 0:
            draw_text(surf, f"Ping: {int(self.net.ping_ms)} ms",
                      self.font_sm, TEXT_DIM, sw-12, sh-14, anchor="bottomright")

        # Footer
        draw_text(surf, "Tab  cycle fields    ←→  element    ↑↓  wand    Enter  connect / ready",
                  self.font_sm, TEXT_DIM, sw//2, sh-14, anchor="midbottom")