# main.py  ─  Wand & Wager  ─  Entry point

import sys, os
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import pygame

from constants import BASE_W, BASE_H, SCREEN_W, SCREEN_H, TITLE, FPS, HUD_H
from Assets   import Assets


# ── Scale helpers ─────────────────────────────────────────────────────────────

def _compute_scale(win_w, win_h):
    scale = min(win_w / BASE_W, win_h / BASE_H)
    sw    = int(BASE_W * scale)
    sh    = int(BASE_H * scale)
    ox    = (win_w - sw) // 2
    oy    = (win_h - sh) // 2
    return scale, ox, oy, sw, sh


_real_get_pos = pygame.mouse.get_pos
_win_size     = [SCREEN_W, SCREEN_H]

def _virtual_get_pos():
    mx, my = _real_get_pos()
    scale, ox, oy, sw, sh = _compute_scale(_win_size[0], _win_size[1])
    if scale == 0: return 0, 0
    vx = max(0, min(BASE_W, int((mx - ox) / scale)))
    vy = max(0, min(BASE_H, int((my - oy) / scale)))
    return vx, vy

pygame.mouse.get_pos = _virtual_get_pos


def _blit_scaled(screen, virtual):
    win_w, win_h = screen.get_size()
    scale, ox, oy, sw, sh = _compute_scale(win_w, win_h)
    screen.fill((0, 0, 0))
    if sw > 0 and sh > 0:
        if abs(scale - 1.0) < 0.005:
            screen.blit(virtual, (ox, oy))
        else:
            screen.blit(pygame.transform.smoothscale(virtual, (sw, sh)), (ox, oy))


# ── Mode select screen ────────────────────────────────────────────────────────

class ModeSelect:
    """First screen: Solo vs Online."""

    def __init__(self, surf):
        self.surf  = surf
        self.choice = None   # "solo" | "online"
        self.font_xl = pygame.font.SysFont("Segoe UI", 44, bold=True)
        self.font_lg = pygame.font.SysFont("Segoe UI", 22, bold=True)
        self.font_md = pygame.font.SysFont("Segoe UI", 15)
        self._age   = 0.0

    def update(self, dt):
        self._age += dt

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:   self.choice = "solo"
            elif event.key == pygame.K_2: self.choice = "online"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = pygame.mouse.get_pos()
            if self._solo_r.collidepoint(mx, my):   self.choice = "solo"
            elif self._online_r.collidepoint(mx, my): self.choice = "online"

    def draw(self):
        sw, sh = BASE_W, BASE_H
        self.surf.fill((14, 12, 26))
        import math
        from constants import GOLD, TEXT_DIM, TEXT_MAIN, BORDER_COL, ELEM_COL
        from hud import draw_text

        for i in range(70):
            sx = (i*173 + int(self._age*8*(1+i%3))) % sw
            sy = (i*97  + int(self._age*4*(1+i%2))) % sh
            pygame.draw.circle(self.surf, (50+i%40,44+i%36,78+i%40),(sx,sy),1+(i%4==0))

        pulse = 0.75 + 0.25 * abs(math.sin(self._age * 1.8))
        tc    = tuple(int(c*pulse) for c in GOLD)
        draw_text(self.surf, "WAND & WAGER", self.font_xl, tc, sw//2, 80, anchor="midtop")
        draw_text(self.surf, "Choose mode", self.font_md, TEXT_DIM, sw//2, 140, anchor="midtop")

        mx, my = pygame.mouse.get_pos()
        bw, bh = 280, 70

        self._solo_r   = pygame.Rect(sw//2 - bw - 20, sh//2 - bh//2, bw, bh)
        self._online_r = pygame.Rect(sw//2 + 20,       sh//2 - bh//2, bw, bh)

        for r, lbl, sub, col in [
            (self._solo_r,   "1  SOLO",   "vs CPU players",   ELEM_COL["fire"]),
            (self._online_r, "2  ONLINE", "join / host match", ELEM_COL["ice"]),
        ]:
            hov = r.collidepoint(mx, my)
            bg  = tuple(min(255, c//3 + (20 if hov else 0)) for c in col)
            pygame.draw.rect(self.surf, bg, r, border_radius=12)
            pygame.draw.rect(self.surf, col, r, 2, border_radius=12)
            draw_text(self.surf, lbl, self.font_lg, col, r.centerx, r.top+14, anchor="midtop")
            draw_text(self.surf, sub, self.font_md, TEXT_DIM, r.centerx, r.top+44, anchor="midtop")

        draw_text(self.surf, "Press 1 for Solo, 2 for Online",
                  self.font_md, TEXT_DIM, sw//2, sh - 24, anchor="midbottom")


# ─────────────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()

    screen      = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
    pygame.display.set_caption(TITLE)
    render_surf = pygame.Surface((BASE_W, BASE_H))

    # Loading splash
    render_surf.fill((14, 12, 26))
    f   = pygame.font.SysFont("Segoe UI", 28, bold=True)
    lbl = f.render("Loading…", True, (180, 160, 240))
    render_surf.blit(lbl, lbl.get_rect(center=(BASE_W//2, BASE_H//2)))
    _blit_scaled(screen, render_surf)
    pygame.display.flip()

    Assets.load()
    Assets.start_music()

    clock   = pygame.time.Clock()
    running = True

    # ── Mode select ───────────────────────────────────────────────────────────
    mode_sel = ModeSelect(render_surf)
    while running:
        dt = min(clock.tick(FPS)/1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: running = False
            else: mode_sel.handle_event(event)
        if not running: break
        mode_sel.update(dt)
        mode_sel.draw()
        win_w, win_h = screen.get_size()
        _win_size[0] = win_w; _win_size[1] = win_h
        _blit_scaled(screen, render_surf)
        pygame.display.flip()
        if mode_sel.choice: break

    if not running:
        pygame.quit(); return

    # ── Launch chosen mode ────────────────────────────────────────────────────
    if mode_sel.choice == "online":
        _run_online(screen, render_surf, clock)
    else:
        _run_solo(screen, render_surf, clock)

    pygame.quit()


def _run_solo(screen, render_surf, clock):
    from game import Game
    game    = Game(render_surf)
    running = True
    while running:
        dt         = min(clock.tick(FPS)/1000.0, 0.05)
        raw_events = pygame.event.get()
        for event in raw_events:
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: running = False
            elif event.type == pygame.VIDEORESIZE:
                _win_size[0]=event.w; _win_size[1]=event.h
                Assets.flush_scale_cache()
        if not running: break
        game.handle_events_and_update(raw_events, dt)
        game.draw()
        win_w, win_h = screen.get_size()
        _win_size[0]=win_w; _win_size[1]=win_h
        _blit_scaled(screen, render_surf)
        pygame.display.flip()


def _run_online(screen, render_surf, clock):
    from multiplayer import NetworkClient, LobbyScreen
    from game import Game

    net     = NetworkClient()
    lobby   = LobbyScreen(net)
    game    = None
    running = True

    while running:
        dt         = min(clock.tick(FPS)/1000.0, 0.05)
        raw_events = pygame.event.get()

        for event in raw_events:
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if game is None:
                    running = False
                else:
                    game = None  # back to lobby
            elif event.type == pygame.VIDEORESIZE:
                _win_size[0]=event.w; _win_size[1]=event.h
                Assets.flush_scale_cache()

        if not running: break

        if game is None:
            lobby.update(dt)
            if lobby.done:
                # Start networked game
                game = Game(render_surf, net=net,
                            match_data=lobby.match_data,
                            my_id=net.your_id)
                lobby = LobbyScreen(net)   # reset for next time
            else:
                lobby.draw(render_surf)
                for ev in raw_events:
                    lobby.handle_event(ev)
        else:
            net_msgs = net.poll()
            game.handle_events_and_update(raw_events, dt, net_msgs=net_msgs)
            game.draw()

        win_w, win_h = screen.get_size()
        _win_size[0]=win_w; _win_size[1]=win_h
        _blit_scaled(screen, render_surf)
        pygame.display.flip()

    net.disconnect()


if __name__ == "__main__":
    main()