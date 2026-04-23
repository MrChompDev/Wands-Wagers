"""
map_builder.py  ─  Wand & Wager level editor
────────────────────────────────────────────
Controls
  Left-click / drag   ─ paint selected tile
  Right-click / drag  ─ erase (set to air)
  Middle-click / drag ─ pan
  Space + drag        ─ pan (alternative)
  Scroll wheel        ─ zoom in / out
  Ctrl+Z / Ctrl+Y     ─ undo / redo
  Ctrl+S              ─ save
  G                   ─ toggle grid lines
  C                   ─ center view
  Delete              ─ clear entire map
"""

import pygame
import json
import os
import sys
import copy
import math

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
MAPS_DIR    = os.path.join(PROJECT_DIR, "Maps")
os.makedirs(MAPS_DIR, exist_ok=True)

# ── Window ────────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720
FPS        = 60
TITLE      = "Wand & Wager  –  Map Builder"
TOOLBAR_H  = 52   # bottom toolbar
SIDEBAR_W  = 220  # right panel

# ── Tile registry ─────────────────────────────────────────────────────────────
# id → (display name, fill colour, border colour)
TILE_DEFS = {
    0: ("Air",      None,              None),
    1: ("Platform", (75,  65,  115),   (110, 95, 165)),
    2: ("Hazard",   (160, 45,  30),    (210, 80,  55)),
    3: ("Ice",      (70,  150, 210),   (110, 195, 250)),
    4: ("Bounce",   (55,  160, 80),    (90,  210, 115)),
}

SPAWN_COLS = [
    (100, 220, 100), (100, 160, 255), (255, 180,  80),
    (255, 100, 180), (180, 100, 255), (100, 220, 200),
]

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG         = (15,  12,  26)
C_CANVAS_BG  = (12,  10,  22)
C_GRID_FINE  = (30,  26,  50)
C_GRID_MAJOR = (50,  44,  78)
C_TOOLBAR    = (20,  17,  36)
C_SIDEBAR    = (18,  15,  32)
C_BORDER     = (55,  46,  85)
C_TEXT       = (225, 215, 255)
C_DIM        = (120, 110, 150)
C_ACTIVE     = (145, 105, 225)
C_BTN        = (38,  30,  62)
C_BTN_HVR    = (58,  46,  95)
C_BTN_ACT    = (88,  66, 148)
C_DANGER     = (170,  45,  45)
C_SUCCESS    = (45,  155,  75)

# ── Map defaults ──────────────────────────────────────────────────────────────
DEFAULT_COLS  = 40
DEFAULT_ROWS  = 22
DEFAULT_TSZ   = 32   # tile size in pixels (display; stored in json for the game)
MIN_TSZ, MAX_TSZ = 6, 80
UNDO_LIMIT    = 60

# ── Tools ─────────────────────────────────────────────────────────────────────
TOOL_PAINT = "paint"
TOOL_ERASE = "erase"
TOOL_SPAWN = "spawn"
TOOL_FILL  = "fill"


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def draw_text(surf, text, font, color, x, y, anchor="topleft"):
    img = font.render(text, True, color)
    r   = img.get_rect(**{anchor: (x, y)})
    surf.blit(img, r)
    return r


def draw_btn(surf, font, label, rect, active=False, danger=False, hover=False):
    col = C_DANGER if danger else (C_BTN_ACT if active else (C_BTN_HVR if hover else C_BTN))
    pygame.draw.rect(surf, col,    rect, border_radius=5)
    pygame.draw.rect(surf, C_BORDER, rect, 1, border_radius=5)
    draw_text(surf, label, font, C_TEXT, rect.centerx, rect.centery, anchor="center")


def flood_fill(grid, col, row, target, replacement, rows, cols):
    """In-place flood fill."""
    if target == replacement:
        return
    stack = [(col, row)]
    visited = set()
    while stack:
        c, r = stack.pop()
        if (c, r) in visited:
            continue
        if not (0 <= c < cols and 0 <= r < rows):
            continue
        if grid[r][c] != target:
            continue
        visited.add((c, r))
        grid[r][c] = replacement
        stack += [(c+1,r),(c-1,r),(c,r+1),(c,r-1)]


# ─────────────────────────────────────────────────────────────────────────────
#  Main editor class
# ─────────────────────────────────────────────────────────────────────────────

class MapBuilder:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.clock  = pygame.time.Clock()

        self.font_sm = pygame.font.SysFont("Segoe UI",    12)
        self.font_md = pygame.font.SysFont("Segoe UI",    14)
        self.font_lg = pygame.font.SysFont("Segoe UI",    18, bold=True)
        self.font_xl = pygame.font.SysFont("Segoe UI",    22, bold=True)

        # ── Map state ─────────────────────────────────────────────────────────
        self.map_name   = "untitled"
        self.cols       = DEFAULT_COLS
        self.rows       = DEFAULT_ROWS
        self.tile_sz    = DEFAULT_TSZ   # zoom-level tile size (pixels on screen)
        self.game_tile_sz = 32          # actual tile size saved in JSON (for game)
        self.grid       = self._blank_grid()
        self.spawn_pts  = []            # list of [col, row]

        # ── View ──────────────────────────────────────────────────────────────
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.center_view()

        # ── Tools / interaction ───────────────────────────────────────────────
        self.tool       = TOOL_PAINT
        self.paint_tile = 1
        self.drawing    = False
        self.erasing    = False
        self.panning    = False
        self.space_held = False
        self._pan_origin = (0, 0)
        self._pan_cam    = (0.0, 0.0)
        self.hover_tile  = None   # (col, row)

        # ── Undo / redo ───────────────────────────────────────────────────────
        self.undo_stack = []
        self.redo_stack = []

        # ── Dialogs ───────────────────────────────────────────────────────────
        # active dialog: None | "save" | "load" | "new" | "resize"
        self.dialog      = None
        self.dlg_inputs  = ["", ""]   # [name_field, extra_field]
        self.dlg_focus   = 0          # which input is focused
        self.load_files  = []
        self.load_sel    = 0
        self.new_cols_s  = str(DEFAULT_COLS)
        self.new_rows_s  = str(DEFAULT_ROWS)

        # ── Status bar ────────────────────────────────────────────────────────
        self.status      = "Welcome!  Left-click to paint  ·  Right-click to erase  ·  Ctrl+S to save"
        self.status_t    = 5.0

        # ── Toggles ───────────────────────────────────────────────────────────
        self.show_grid   = True
        self.show_spawns = True

    # ── Grid helpers ──────────────────────────────────────────────────────────

    def _blank_grid(self, cols=None, rows=None):
        c = cols or self.cols
        r = rows or self.rows
        return [[0]*c for _ in range(r)]

    def _snap_grid(self, new_cols, new_rows):
        """Resize grid, preserving existing tiles."""
        new = [[0]*new_cols for _ in range(new_rows)]
        for r in range(min(new_rows, self.rows)):
            for c in range(min(new_cols, self.cols)):
                new[r][c] = self.grid[r][c]
        self.grid = new
        self.cols = new_cols
        self.rows = new_rows

    def center_view(self):
        w, h = self.screen.get_size()
        cw   = w - SIDEBAR_W
        ch   = h - TOOLBAR_H
        self.cam_x = (cw - self.cols * self.tile_sz) / 2
        self.cam_y = (ch - self.rows * self.tile_sz) / 2

    # ── Coordinate conversion ─────────────────────────────────────────────────

    def canvas_rect(self):
        w, h = self.screen.get_size()
        return pygame.Rect(0, 0, w - SIDEBAR_W, h - TOOLBAR_H)

    def tile_to_screen(self, col, row):
        return (int(self.cam_x + col * self.tile_sz),
                int(self.cam_y + row * self.tile_sz))

    def screen_to_tile(self, sx, sy):
        col = int((sx - self.cam_x) // self.tile_sz)
        row = int((sy - self.cam_y) // self.tile_sz)
        return col, row

    def tile_in_bounds(self, col, row):
        return 0 <= col < self.cols and 0 <= row < self.rows

    # ── Undo / redo ───────────────────────────────────────────────────────────

    def _push_undo(self):
        snap = copy.deepcopy(self.grid)
        self.undo_stack.append(snap)
        if len(self.undo_stack) > UNDO_LIMIT:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            self.set_status("Nothing to undo.")
            return
        self.redo_stack.append(copy.deepcopy(self.grid))
        self.grid = self.undo_stack.pop()
        self.set_status("Undo.")

    def redo(self):
        if not self.redo_stack:
            self.set_status("Nothing to redo.")
            return
        self.undo_stack.append(copy.deepcopy(self.grid))
        self.grid = self.redo_stack.pop()
        self.set_status("Redo.")

    # ── Tile painting ─────────────────────────────────────────────────────────

    def _paint(self, col, row, value):
        if self.tile_in_bounds(col, row):
            if self.grid[row][col] != value:
                self.grid[row][col] = value

    def _start_draw(self, col, row, value):
        self._push_undo()
        self._paint(col, row, value)

    def _apply_tool_at(self, sx, sy):
        col, row = self.screen_to_tile(sx, sy)
        if self.tool == TOOL_FILL:
            if self.tile_in_bounds(col, row):
                target = self.grid[row][col]
                flood_fill(self.grid, col, row, target, self.paint_tile,
                           self.rows, self.cols)
            return
        if self.drawing:
            self._paint(col, row, self.paint_tile)
        elif self.erasing:
            self._paint(col, row, 0)

    # ── Spawn points ─────────────────────────────────────────────────────────

    def _toggle_spawn(self, col, row):
        if not self.tile_in_bounds(col, row):
            return
        pt = [col, row]
        for i, sp in enumerate(self.spawn_pts):
            if sp == pt:
                self.spawn_pts.pop(i)
                self.set_status(f"Removed spawn point {i+1}.")
                return
        if len(self.spawn_pts) >= 8:
            self.set_status("Maximum 8 spawn points.")
            return
        self.spawn_pts.append(pt)
        self.set_status(f"Added spawn point {len(self.spawn_pts)}.")

    # ── Save / Load ───────────────────────────────────────────────────────────

    def _build_json(self):
        return {
            "name":      self.map_name,
            "cols":      self.cols,
            "rows":      self.rows,
            "tile_size": self.game_tile_sz,
            "grid":      self.grid,
            "spawn_points": self.spawn_pts,
        }

    def save_map(self, name=None):
        if name:
            self.map_name = name.strip() or "untitled"
        safe_name = "".join(c for c in self.map_name if c.isalnum() or c in "_- ")
        path = os.path.join(MAPS_DIR, safe_name + ".json")
        with open(path, "w") as f:
            json.dump(self._build_json(), f, indent=2)
        self.set_status(f"Saved → Maps/{safe_name}.json")

    def load_map(self, path):
        try:
            with open(path) as f:
                data = json.load(f)
            self.map_name  = data.get("name", "untitled")
            self.cols      = data["cols"]
            self.rows      = data["rows"]
            self.game_tile_sz = data.get("tile_size", 32)
            self.grid      = data["grid"]
            self.spawn_pts = data.get("spawn_points", [])
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.center_view()
            self.set_status(f"Loaded  '{self.map_name}'")
        except Exception as e:
            self.set_status(f"Load error: {e}")

    def _refresh_load_list(self):
        self.load_files = sorted(
            f for f in os.listdir(MAPS_DIR) if f.endswith(".json")
        )

    # ── Status bar ────────────────────────────────────────────────────────────

    def set_status(self, msg, duration=3.0):
        self.status   = msg
        self.status_t = duration

    # ─────────────────────────────────────────────────────────────────────────
    #  Event handling
    # ─────────────────────────────────────────────────────────────────────────

    def handle_events(self):
        mx, my = pygame.mouse.get_pos()
        canvas  = self.canvas_rect()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # ── Window resize ─────────────────────────────────────────────
            if event.type == pygame.VIDEORESIZE:
                pass   # pygame handles it; next frame will recalc

            # ── Keyboard ──────────────────────────────────────────────────
            if event.type == pygame.KEYDOWN:
                if self.dialog:
                    self._handle_dialog_key(event)
                else:
                    self._handle_global_key(event)

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    self.space_held = False
                    self.panning    = False

            # ── Mouse wheel (zoom) ─────────────────────────────────────────
            if event.type == pygame.MOUSEWHEEL and not self.dialog:
                if canvas.collidepoint(mx, my):
                    old_tsz = self.tile_sz
                    self.tile_sz = clamp(self.tile_sz + event.y * 2,
                                        MIN_TSZ, MAX_TSZ)
                    # zoom toward cursor
                    scale = self.tile_sz / old_tsz
                    self.cam_x = mx - (mx - self.cam_x) * scale
                    self.cam_y = my - (my - self.cam_y) * scale

            # ── Mouse button down ──────────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN and not self.dialog:
                if event.button == 2 or self.space_held:     # middle / space pan
                    self.panning    = True
                    self._pan_origin = (mx, my)
                    self._pan_cam    = (self.cam_x, self.cam_y)

                elif canvas.collidepoint(mx, my):
                    col, row = self.screen_to_tile(mx, my)

                    if event.button == 1:   # left ─ paint / spawn
                        if self.tool == TOOL_SPAWN:
                            self._toggle_spawn(col, row)
                        elif self.tool == TOOL_FILL:
                            self._push_undo()
                            if self.tile_in_bounds(col, row):
                                target = self.grid[row][col]
                                flood_fill(self.grid, col, row, target,
                                           self.paint_tile, self.rows, self.cols)
                        else:
                            self.drawing = True
                            self._start_draw(col, row, self.paint_tile)

                    elif event.button == 3:  # right ─ erase
                        if self.tool != TOOL_SPAWN:
                            self.erasing = True
                            self._start_draw(col, row, 0)

                    # Sidebar button clicks handled in draw pass (below)

            # ── Mouse button up ────────────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button in (1, 3):
                    self.drawing = False
                    self.erasing = False
                if event.button == 2:
                    self.panning = False

            # ── Mouse motion ──────────────────────────────────────────────
            if event.type == pygame.MOUSEMOTION:
                if self.panning:
                    dx = mx - self._pan_origin[0]
                    dy = my - self._pan_origin[1]
                    self.cam_x = self._pan_cam[0] + dx
                    self.cam_y = self._pan_cam[1] + dy
                elif (self.drawing or self.erasing) and canvas.collidepoint(mx, my):
                    self._apply_tool_at(mx, my)

        # Handle sidebar button clicks this frame
        if pygame.mouse.get_pressed()[0] and not self.dialog:
            self._handle_sidebar_click(mx, my)

        return True

    def _handle_global_key(self, event):
        ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL

        if event.key == pygame.K_SPACE:
            self.space_held = True

        elif ctrl and event.key == pygame.K_z:
            self.undo()
        elif ctrl and event.key == pygame.K_y:
            self.redo()
        elif ctrl and event.key == pygame.K_s:
            if self.map_name == "untitled":
                self._open_save_dialog()
            else:
                self.save_map()

        elif event.key == pygame.K_g:
            self.show_grid = not self.show_grid
            self.set_status("Grid " + ("on" if self.show_grid else "off"), 1.5)

        elif event.key == pygame.K_c:
            self.center_view()
            self.set_status("View centred.", 1.5)

        elif event.key == pygame.K_DELETE:
            self._push_undo()
            self.grid = self._blank_grid()
            self.set_status("Map cleared.")

        elif event.key == pygame.K_1:
            self.tool = TOOL_PAINT;  self.paint_tile = 1
        elif event.key == pygame.K_2:
            self.tool = TOOL_PAINT;  self.paint_tile = 2
        elif event.key == pygame.K_3:
            self.tool = TOOL_PAINT;  self.paint_tile = 3
        elif event.key == pygame.K_4:
            self.tool = TOOL_PAINT;  self.paint_tile = 4
        elif event.key == pygame.K_0:
            self.tool = TOOL_ERASE

        elif event.key == pygame.K_f:
            self.tool = TOOL_FILL
        elif event.key == pygame.K_p:
            self.tool = TOOL_PAINT
        elif event.key == pygame.K_e:
            self.tool = TOOL_ERASE

    def _handle_dialog_key(self, event):
        dlg = self.dialog

        if event.key == pygame.K_ESCAPE:
            self.dialog = None
            return

        if event.key == pygame.K_RETURN:
            self._confirm_dialog()
            return

        if event.key == pygame.K_TAB and dlg in ("new", "resize"):
            self.dlg_focus = 1 - self.dlg_focus
            return

        # Text input routing
        if dlg == "save":
            field = self.dlg_inputs
            fi = 0
        elif dlg in ("new", "resize"):
            field = [self.new_cols_s, self.new_rows_s]
            fi = self.dlg_focus
        elif dlg == "load":
            # arrow navigation
            if event.key == pygame.K_UP:
                self.load_sel = max(0, self.load_sel - 1)
            elif event.key == pygame.K_DOWN:
                self.load_sel = min(len(self.load_files)-1, self.load_sel+1)
            return
        else:
            return

        target = self.dlg_inputs if dlg == "save" else (
            [self.new_cols_s, self.new_rows_s]
        )

        if event.key == pygame.K_BACKSPACE:
            if dlg == "save":
                self.dlg_inputs[0] = self.dlg_inputs[0][:-1]
            elif dlg in ("new", "resize"):
                if fi == 0:
                    self.new_cols_s = self.new_cols_s[:-1]
                else:
                    self.new_rows_s = self.new_rows_s[:-1]
        elif event.unicode.isprintable():
            if dlg == "save":
                self.dlg_inputs[0] += event.unicode
            elif dlg in ("new", "resize"):
                if fi == 0:
                    self.new_cols_s += event.unicode
                else:
                    self.new_rows_s += event.unicode

    def _confirm_dialog(self):
        dlg = self.dialog
        self.dialog = None

        if dlg == "save":
            name = self.dlg_inputs[0].strip() or "untitled"
            self.save_map(name)

        elif dlg == "new":
            try:
                nc = clamp(int(self.new_cols_s), 5, 200)
                nr = clamp(int(self.new_rows_s), 5, 100)
            except ValueError:
                self.set_status("Invalid dimensions."); return
            self._push_undo()
            self.cols = nc; self.rows = nr
            self.grid = self._blank_grid()
            self.spawn_pts = []
            self.map_name = "untitled"
            self.center_view()
            self.set_status(f"New map  {nc}×{nr}.")

        elif dlg == "resize":
            try:
                nc = clamp(int(self.new_cols_s), 5, 200)
                nr = clamp(int(self.new_rows_s), 5, 100)
            except ValueError:
                self.set_status("Invalid dimensions."); return
            self._push_undo()
            self._snap_grid(nc, nr)
            self.center_view()
            self.set_status(f"Resized to  {nc}×{nr}.")

        elif dlg == "load":
            if self.load_files:
                path = os.path.join(MAPS_DIR, self.load_files[self.load_sel])
                self.load_map(path)

    def _open_save_dialog(self):
        self.dialog = "save"
        self.dlg_inputs = [self.map_name, ""]
        self.dlg_focus  = 0

    def _handle_sidebar_click(self, mx, my):
        """Detect clicks on sidebar buttons (called each frame when LMB down)."""
        pass   # handled via draw_sidebar returning button rects & checking

    # ─────────────────────────────────────────────────────────────────────────
    #  Drawing
    # ─────────────────────────────────────────────────────────────────────────

    def draw(self):
        w, h = self.screen.get_size()
        self.screen.fill(C_BG)

        canvas = self.canvas_rect()
        canvas_surf = self.screen.subsurface(canvas)

        self._draw_canvas(canvas_surf)
        self._draw_toolbar(w, h)
        self._draw_sidebar(w, h)

        if self.dialog:
            self._draw_dialog(w, h)

        pygame.display.flip()

    # ── Canvas ────────────────────────────────────────────────────────────────

    def _draw_canvas(self, surf):
        surf.fill(C_CANVAS_BG)
        tsz = self.tile_sz

        # ── Tiles ─────────────────────────────────────────────────────────
        for r in range(self.rows):
            for c in range(self.cols):
                tid = self.grid[r][c]
                if tid == 0:
                    continue
                name, fill, border = TILE_DEFS.get(tid, ("?", (80,80,80), (120,120,120)))
                sx = int(self.cam_x + c * tsz)
                sy = int(self.cam_y + r * tsz)
                rect = pygame.Rect(sx, sy, tsz, tsz)
                if not surf.get_rect().colliderect(rect):
                    continue
                pygame.draw.rect(surf, fill, rect)
                if border and tsz >= 10:
                    pygame.draw.rect(surf, border, rect, max(1, tsz//20))

        # ── Grid lines ────────────────────────────────────────────────────
        if self.show_grid and tsz >= 6:
            cr = surf.get_rect()
            major = 5  # every N tiles draw a brighter line

            # Verticals
            for c in range(self.cols + 1):
                x = int(self.cam_x + c * tsz)
                if not (cr.left <= x <= cr.right):
                    continue
                col = C_GRID_MAJOR if c % major == 0 else C_GRID_FINE
                pygame.draw.line(surf, col,
                                 (x, int(self.cam_y)),
                                 (x, int(self.cam_y + self.rows * tsz)))
            # Horizontals
            for r in range(self.rows + 1):
                y = int(self.cam_y + r * tsz)
                if not (cr.top <= y <= cr.bottom):
                    continue
                col = C_GRID_MAJOR if r % major == 0 else C_GRID_FINE
                pygame.draw.line(surf, col,
                                 (int(self.cam_x), y),
                                 (int(self.cam_x + self.cols * tsz), y))

        # ── Arena border ──────────────────────────────────────────────────
        arena_rect = pygame.Rect(
            int(self.cam_x), int(self.cam_y),
            self.cols * tsz, self.rows * tsz
        )
        pygame.draw.rect(surf, (90, 75, 140), arena_rect, 2)

        # ── Spawn points ──────────────────────────────────────────────────
        if self.show_spawns:
            for i, (sc, sr) in enumerate(self.spawn_pts):
                sx = int(self.cam_x + sc * tsz) + tsz // 2
                sy = int(self.cam_y + sr * tsz) + tsz // 2
                rad = max(4, tsz // 3)
                col = SPAWN_COLS[i % len(SPAWN_COLS)]
                pygame.draw.circle(surf, col,        (sx, sy), rad)
                pygame.draw.circle(surf, (255,255,255), (sx, sy), rad, 1)
                if tsz >= 14:
                    lbl = self.font_sm.render(str(i+1), True, (10, 10, 10))
                    surf.blit(lbl, lbl.get_rect(center=(sx, sy)))

        # ── Hover highlight ───────────────────────────────────────────────
        mx, my = pygame.mouse.get_pos()
        # adjust for canvas offset (canvas starts at 0,0 in subsurface)
        canvas = self.canvas_rect()
        lx, ly = mx - canvas.left, my - canvas.top
        hc, hr = self.screen_to_tile(lx, ly)
        if self.tile_in_bounds(hc, hr):
            self.hover_tile = (hc, hr)
            hsx = int(self.cam_x + hc * tsz)
            hsy = int(self.cam_y + hr * tsz)
            hs  = pygame.Surface((tsz, tsz), pygame.SRCALPHA)
            if self.tool == TOOL_ERASE or self.erasing:
                hs.fill((255, 60, 60, 55))
            elif self.tool == TOOL_SPAWN:
                hs.fill((100, 220, 100, 60))
            elif self.tool == TOOL_FILL:
                hs.fill((180, 140, 255, 60))
            else:
                _, fc, _ = TILE_DEFS.get(self.paint_tile, ("?", (80,80,80), None))
                if fc:
                    hs.fill((*fc, 100))
            surf.blit(hs, (hsx, hsy))
        else:
            self.hover_tile = None

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _draw_toolbar(self, w, h):
        tb_rect = pygame.Rect(0, h - TOOLBAR_H, w, TOOLBAR_H)
        pygame.draw.rect(self.screen, C_TOOLBAR, tb_rect)
        pygame.draw.line(self.screen, C_BORDER, tb_rect.topleft, tb_rect.topright, 1)

        # Coords display
        ht = self.hover_tile
        coord_str = (f"col {ht[0]}  row {ht[1]}" if ht else "—  —")
        draw_text(self.screen, coord_str, self.font_md, C_DIM, 12, h - TOOLBAR_H + 8)

        # Map info
        info = f"'{self.map_name}'   {self.cols}×{self.rows} tiles   zoom {self.tile_sz}px"
        draw_text(self.screen, info, self.font_md, C_DIM, 12, h - TOOLBAR_H + 26)

        # Status message
        if self.status_t > 0:
            alpha = min(255, int(self.status_t * 160))
            col   = (*C_TEXT[:3],)
            draw_text(self.screen, self.status, self.font_md, col,
                      w // 2, h - TOOLBAR_H // 2, anchor="center")

        # Quick-key hints
        hints = "[P] Paint  [E] Erase  [F] Fill  [S] Spawn  [G] Grid  [C] Centre  [Del] Clear  Ctrl+S Save"
        draw_text(self.screen, hints, self.font_sm, C_DIM,
                  w - SIDEBAR_W - 8, h - 14, anchor="bottomright")

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _draw_sidebar(self, w, h):
        sb_x = w - SIDEBAR_W
        sb_rect = pygame.Rect(sb_x, 0, SIDEBAR_W, h - TOOLBAR_H)
        pygame.draw.rect(self.screen, C_SIDEBAR, sb_rect)
        pygame.draw.line(self.screen, C_BORDER, (sb_x, 0), (sb_x, h - TOOLBAR_H), 1)

        mx, my = pygame.mouse.get_pos()
        clicked = pygame.mouse.get_pressed()[0]
        # We track if click is fresh to avoid holding triggering repeatedly
        # (Simple approach: check mouse button state with just-pressed via event system above)

        y = 14
        x = sb_x + 12

        draw_text(self.screen, "TOOLS", self.font_sm, C_DIM, x, y)
        y += 20

        tools = [
            (TOOL_PAINT,  "Paint  [P]",  "(1–4 to select tile)"),
            (TOOL_ERASE,  "Erase  [E]",  "(or right-click)"),
            (TOOL_FILL,   "Fill   [F]",  "(flood fill region)"),
            (TOOL_SPAWN,  "Spawn  [S]",  "(place player spawns)"),
        ]
        self._sidebar_buttons = {}

        for tool_id, label, hint in tools:
            r = pygame.Rect(x, y, SIDEBAR_W - 24, 30)
            active  = self.tool == tool_id
            hovering = r.collidepoint(mx, my)
            draw_btn(self.screen, self.font_md, label, r, active=active, hover=hovering)
            if hint and self.tile_sz >= 8:
                draw_text(self.screen, hint, self.font_sm, C_DIM, x+4, y + 32)
            self._sidebar_buttons[tool_id] = r
            # click detection
            if hovering and clicked and not self.dialog:
                self.tool = tool_id
            y += 46

        y += 8
        pygame.draw.line(self.screen, C_BORDER, (x, y), (x + SIDEBAR_W - 24, y), 1)
        y += 10

        # ── Tile palette ──────────────────────────────────────────────────
        draw_text(self.screen, "TILES", self.font_sm, C_DIM, x, y)
        y += 20

        for tid in range(1, len(TILE_DEFS)):
            name, fill, border = TILE_DEFS[tid]
            r = pygame.Rect(x, y, SIDEBAR_W - 24, 28)
            is_sel  = self.tool == TOOL_PAINT and self.paint_tile == tid
            hovering = r.collidepoint(mx, my)

            col = C_BTN_ACT if is_sel else (C_BTN_HVR if hovering else C_BTN)
            pygame.draw.rect(self.screen, col, r, border_radius=4)
            pygame.draw.rect(self.screen, C_BORDER, r, 1, border_radius=4)

            # Colour swatch
            if fill:
                sw = pygame.Rect(r.x + 6, r.y + 6, 16, 16)
                pygame.draw.rect(self.screen, fill, sw, border_radius=2)
                if border:
                    pygame.draw.rect(self.screen, border, sw, 1, border_radius=2)

            draw_text(self.screen, f"[{tid}] {name}", self.font_md, C_TEXT,
                      r.x + 28, r.centery, anchor="midleft")

            if hovering and clicked and not self.dialog:
                self.tool = TOOL_PAINT
                self.paint_tile = tid

            y += 34

        y += 8
        pygame.draw.line(self.screen, C_BORDER, (x, y), (x + SIDEBAR_W - 24, y), 1)
        y += 10

        # ── Spawn count ───────────────────────────────────────────────────
        draw_text(self.screen, f"Spawns: {len(self.spawn_pts)}/8", self.font_md, C_DIM, x, y)
        y += 18
        for i, (sc, sr) in enumerate(self.spawn_pts):
            col = SPAWN_COLS[i % len(SPAWN_COLS)]
            draw_text(self.screen, f"  P{i+1}: col {sc}, row {sr}",
                      self.font_sm, col, x, y)
            y += 16

        y += 8
        pygame.draw.line(self.screen, C_BORDER, (x, y), (x + SIDEBAR_W - 24, y), 1)
        y += 10

        # ── File operations ───────────────────────────────────────────────
        draw_text(self.screen, "FILE", self.font_sm, C_DIM, x, y)
        y += 20

        file_btns = [
            ("save",   f"Save '{self.map_name}'",  False),
            ("save_as","Save As…",                  False),
            ("load",   "Load map…",                 False),
            ("new",    "New map…",                  False),
            ("resize", "Resize…",                   False),
        ]
        for btn_id, label, danger in file_btns:
            r = pygame.Rect(x, y, SIDEBAR_W - 24, 28)
            hovering = r.collidepoint(mx, my)
            draw_btn(self.screen, self.font_md, label, r, danger=danger, hover=hovering)
            if hovering and clicked and not self.dialog:
                self._sidebar_action(btn_id)
            y += 34

        # ── Undo/redo row ─────────────────────────────────────────────────
        y += 4
        half = (SIDEBAR_W - 24 - 6) // 2
        for bx, label, bid in [(x, "⟵ Undo", "undo"), (x + half + 6, "Redo ⟶", "redo")]:
            r = pygame.Rect(bx, y, half, 28)
            hovering = r.collidepoint(mx, my)
            disabled = (bid == "undo" and not self.undo_stack) or \
                       (bid == "redo" and not self.redo_stack)
            col = C_BTN if disabled else (C_BTN_HVR if hovering else C_BTN)
            pygame.draw.rect(self.screen, col, r, border_radius=4)
            pygame.draw.rect(self.screen, C_BORDER, r, 1, border_radius=4)
            tcol = C_DIM if disabled else C_TEXT
            draw_text(self.screen, label, self.font_md, tcol, r.centerx, r.centery, anchor="center")
            if hovering and clicked and not self.dialog and not disabled:
                if bid == "undo":
                    self.undo()
                else:
                    self.redo()

    def _sidebar_action(self, btn_id):
        if btn_id == "save":
            if self.map_name == "untitled":
                self._open_save_dialog()
            else:
                self.save_map()
        elif btn_id == "save_as":
            self._open_save_dialog()
        elif btn_id == "load":
            self._refresh_load_list()
            self.dialog   = "load"
            self.load_sel = 0
        elif btn_id == "new":
            self.dialog      = "new"
            self.new_cols_s  = str(self.cols)
            self.new_rows_s  = str(self.rows)
            self.dlg_focus   = 0
        elif btn_id == "resize":
            self.dialog      = "resize"
            self.new_cols_s  = str(self.cols)
            self.new_rows_s  = str(self.rows)
            self.dlg_focus   = 0

    # ── Dialogs ───────────────────────────────────────────────────────────────

    def _draw_dialog(self, w, h):
        # Dim overlay
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        dlg = self.dialog
        dw, dh = (420, 180)
        if dlg == "load":
            dh = min(80 + len(self.load_files) * 28 + 60, 500)
        dr = pygame.Rect((w - dw)//2, (h - dh)//2, dw, dh)

        pygame.draw.rect(self.screen, C_TOOLBAR, dr, border_radius=10)
        pygame.draw.rect(self.screen, C_ACTIVE,  dr, 2, border_radius=10)

        cx, cy = dr.centerx, dr.top + 20
        draw_text(self.screen, {
            "save":   "Save Map",
            "new":    "New Map",
            "resize": "Resize Map",
            "load":   "Load Map",
        }.get(dlg, ""), self.font_lg, C_TEXT, cx, cy, anchor="midtop")

        if dlg in ("save",):
            draw_text(self.screen, "Map name:", self.font_md, C_DIM, dr.x+20, cy+36)
            inp = self._draw_input(dr.x+20, cy+54, dw-40, self.dlg_inputs[0], True)
            self._draw_dialog_buttons(dr, "Save", "Cancel")

        elif dlg in ("new", "resize"):
            label = "Create" if dlg == "new" else "Resize"
            draw_text(self.screen, "Columns:", self.font_md, C_DIM, dr.x+20, cy+36)
            self._draw_input(dr.x+20, cy+54, dw//2-30, self.new_cols_s, self.dlg_focus==0)
            draw_text(self.screen, "Rows:", self.font_md, C_DIM, dr.x+dw//2+10, cy+36)
            self._draw_input(dr.x+dw//2+10, cy+54, dw//2-30, self.new_rows_s, self.dlg_focus==1)
            draw_text(self.screen, "[Tab] switches field", self.font_sm, C_DIM, cx, cy+88, anchor="midtop")
            self._draw_dialog_buttons(dr, label, "Cancel")

        elif dlg == "load":
            if not self.load_files:
                draw_text(self.screen, "No maps found in Maps/", self.font_md, C_DIM,
                          cx, cy+40, anchor="midtop")
                self._draw_dialog_buttons(dr, "", "Close")
            else:
                ly = cy + 36
                for i, fname in enumerate(self.load_files):
                    fr = pygame.Rect(dr.x+12, ly + i*28, dw-24, 26)
                    sel = i == self.load_sel
                    pygame.draw.rect(self.screen, C_BTN_ACT if sel else C_BTN, fr, border_radius=4)
                    mx, my = pygame.mouse.get_pos()
                    if fr.collidepoint(mx, my):
                        if pygame.mouse.get_pressed()[0]:
                            self.load_sel = i
                    draw_text(self.screen, fname, self.font_md, C_TEXT, fr.x+8, fr.centery, anchor="midleft")
                self._draw_dialog_buttons(dr, "Load", "Cancel")

    def _draw_input(self, x, y, width, value, focused):
        r = pygame.Rect(x, y, width, 28)
        col = C_BTN_HVR if focused else C_BTN
        pygame.draw.rect(self.screen, col, r, border_radius=4)
        pygame.draw.rect(self.screen, C_ACTIVE if focused else C_BORDER, r, 1, border_radius=4)
        disp = value + ("|" if focused and (pygame.time.get_ticks() // 500) % 2 == 0 else "")
        draw_text(self.screen, disp, self.font_md, C_TEXT, r.x+6, r.centery, anchor="midleft")
        return r

    def _draw_dialog_buttons(self, dr, confirm_label, cancel_label):
        bw = 110
        by = dr.bottom - 42
        mx, my = pygame.mouse.get_pos()

        if confirm_label:
            cr = pygame.Rect(dr.centerx - bw - 6, by, bw, 32)
            hov = cr.collidepoint(mx, my)
            draw_btn(self.screen, self.font_md, confirm_label, cr, hover=hov)
            if hov and pygame.mouse.get_pressed()[0]:
                self._confirm_dialog()

        xr = pygame.Rect(dr.centerx + 6, by, bw, 32)
        hov = xr.collidepoint(mx, my)
        draw_btn(self.screen, self.font_md, cancel_label, xr, danger=True, hover=hov)
        if hov and pygame.mouse.get_pressed()[0]:
            self.dialog = None

    # ─────────────────────────────────────────────────────────────────────────
    #  Main loop
    # ─────────────────────────────────────────────────────────────────────────

    def update(self, dt):
        if self.status_t > 0:
            self.status_t -= dt

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            running = self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    MapBuilder().run()