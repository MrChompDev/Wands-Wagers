# pygame_stub.py  ─  Wand & Wager server
# Dropped into sys.modules as "pygame" before the game modules load.
# The server only needs Rect, basic math, and no rendering.

class Rect:
    __slots__ = ("x","y","width","height")
    def __init__(self, x, y, w, h):
        self.x = int(x); self.y = int(y)
        self.width = int(w); self.height = int(h)

    @property
    def w(self): return self.width
    @property
    def h(self): return self.height
    @property
    def left(self):   return self.x
    @property
    def right(self):  return self.x + self.width
    @property
    def top(self):    return self.y
    @property
    def bottom(self): return self.y + self.height
    @property
    def centerx(self):return self.x + self.width  // 2
    @property
    def centery(self):return self.y + self.height // 2
    @property
    def center(self): return (self.centerx, self.centery)

    def colliderect(self, other):
        return (self.x < other.x + other.width  and
                self.x + self.width  > other.x  and
                self.y < other.y + other.height and
                self.y + self.height > other.y)

    def collidepoint(self, x, y=None):
        if y is None: x, y = x
        return self.x <= x < self.x+self.width and self.y <= y < self.y+self.height

    def inflate(self, dx, dy):
        return Rect(self.x-dx//2, self.y-dy//2,
                    self.width+dx, self.height+dy)

    def move(self, dx, dy):
        return Rect(self.x+dx, self.y+dy, self.width, self.height)

    def __repr__(self):
        return f"Rect({self.x},{self.y},{self.width},{self.height})"


class Surface:
    def __init__(self, *a, **k): pass
    def get_rect(self): return Rect(0,0,1,1)
    def fill(self,*a): pass
    def blit(self,*a): pass
    def get_size(self): return (1,1)
    def get_width(self): return 1
    def get_height(self): return 1
    def set_alpha(self,*a): pass
    def copy(self): return Surface()
    def subsurface(self,*a): return Surface()


class _Stub:
    def __getattr__(self, name):
        return _Stub()
    def __call__(self, *a, **k):
        return _Stub()
    def __iter__(self):
        return iter([])
    def __bool__(self):
        return False
    def __int__(self):
        return 0


# Module-level stubs
def init(): pass
def quit(): pass

# Key constants used by player.py / ai.py
class K:
    pass

# Inject all K_ constants as plain ints so server code doesn't crash
import sys as _sys
_mod = _sys.modules[__name__]
for _i, _name in enumerate([
    "K_LEFT","K_RIGHT","K_UP","K_DOWN","K_SPACE",
    "K_a","K_d","K_w","K_s","K_1","K_2","K_3","K_4",
    "K_q","K_e","K_r","K_RETURN","K_ESCAPE","K_TAB",
    "K_BACKSPACE","K_LSHIFT","K_RSHIFT","K_LCTRL",
    "KMOD_CTRL","KMOD_SHIFT",
    "QUIT","KEYDOWN","KEYUP","MOUSEBUTTONDOWN","MOUSEBUTTONUP","MOUSEMOTION",
    "VIDEORESIZE","SRCALPHA","RESIZABLE",
    "BLEND_RGBA_ADD","BLEND_RGBA_MULT",
]):
    setattr(_mod, _name, _i + 1000)

font   = _Stub()
image  = _Stub()
draw   = _Stub()
event  = _Stub()
mixer  = _Stub()
mouse  = _Stub()
key    = _Stub()
time   = _Stub()
transform = _Stub()
display   = _Stub()

class SysFont:
    def __init__(self,*a,**k): pass
    def render(self,*a,**k): return Surface()
    def size(self,text): return (len(text)*8, 14)

font.SysFont = SysFont
font.Font    = SysFont
