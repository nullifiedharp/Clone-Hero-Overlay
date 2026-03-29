#!/usr/bin/env python3
"""
Clone Hero Guitar Controller Overlay
=====================================
Transparent always-on-top overlay with authentic GH note shapes and per-fret counters.

Controls:
  Left-click + drag       → move the window
  Right-click             → close
  Scroll wheel            → resize
  Click RESET button      → zero all counters

Default key bindings (Clone Hero keyboard defaults):
  Green  : 1 / A
  Red    : 2 / S
  Yellow : 3 / D / J
  Blue   : 4 / F / K
  Orange : 5 / G / L
  Strum↑ : Up Arrow
  Strum↓ : Down Arrow
  Whammy : Right Shift
  SP     : Space / Backspace

Requirements:
  pip install pynput
"""

import tkinter as tk
import threading
from pynput import keyboard as kb

# ─── Key Bindings ─────────────────────────────────────────────────────────────

FRETS = [
    {"name": "G", "keys": {"1", "a"},       "color": "#00dd44"},
    {"name": "R", "keys": {"2", "s"},       "color": "#ff2222"},
    {"name": "Y", "keys": {"3", "d", "j"}, "color": "#ffe600"},
    {"name": "B", "keys": {"4", "f", "k"}, "color": "#2299ff"},
    {"name": "O", "keys": {"5", "g", "l"}, "color": "#ff8800"},
]

STRUM_UP_KEYS   = {"up"}
STRUM_DOWN_KEYS = {"down"}
WHAMMY_KEYS     = {"shift_r"}
SP_KEYS         = {"space", "backspace"}

STRUM_FLASH_MS  = 130

# ─── Color Utilities ──────────────────────────────────────────────────────────

def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )

def brighten(color, f):
    r, g, b = hex_to_rgb(color)
    return rgb_to_hex(r * f, g * f, b * f)

def blend_white(color, t):
    r, g, b = hex_to_rgb(color)
    return rgb_to_hex(r + (255-r)*t, g + (255-g)*t, b + (255-b)*t)

def desaturate(color, f):
    r, g, b = hex_to_rgb(color)
    gray = 0.299*r + 0.587*g + 0.114*b
    return rgb_to_hex(gray + (r-gray)*f, gray + (g-gray)*f, gray + (b-gray)*f)

def dim(color):
    return desaturate(brighten(color, 0.28), 0.45)

# ─── GH Note Shape ────────────────────────────────────────────────────────────

def draw_gh_note(canvas, cx, cy, r, base_color, pressed):
    color    = base_color if pressed else dim(base_color)
    c_bright = blend_white(color, 0.55)
    c_mid    = blend_white(color, 0.20)
    c_shadow = brighten(color, 0.55)
    c_deep   = brighten(color, 0.30)
    ring_hi  = blend_white(color, 0.40)

    if pressed:
        gw = max(3, int(r * 0.18))
        canvas.create_oval(cx-r-gw, cy-r-gw, cx+r+gw, cy+r+gw,
                           fill="", outline=base_color, width=gw)

    canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                       fill="#050505", outline="#000000", width=1)

    re = int(r * 0.93)
    canvas.create_oval(cx-re, cy-re, cx+re, cy+re, fill=ring_hi, outline="")

    rb = int(r * 0.86)
    canvas.create_oval(cx-rb, cy-rb, cx+rb, cy+rb, fill=color, outline="")

    rs = int(r * 0.66)
    canvas.create_oval(cx-rs, cy-rs, cx+rs, cy+rs, fill=c_shadow, outline="")

    rw = int(r * 0.56)
    canvas.create_oval(cx-rw, cy-rw, cx+rw, cy+rw, fill="#080808", outline="")

    dome_r = int(r * 0.48)
    for frac, col in [
        (1.00, c_deep),
        (0.84, brighten(color, 0.50)),
        (0.68, brighten(color, 0.72)),
        (0.52, color),
        (0.37, c_mid),
        (0.22, c_bright),
        (0.10, blend_white(color, 0.82)),
    ]:
        dr = max(1, int(dome_r * frac))
        canvas.create_oval(cx-dr, cy-dr, cx+dr, cy+dr, fill=col, outline="")

    sr  = max(2, int(r * 0.09))
    sox = int(r * 0.15)
    soy = int(r * 0.14)
    canvas.create_oval(cx-sox-sr, cy-soy-sr, cx-sox+sr, cy-soy+sr,
                       fill="#ffffff" if pressed else blend_white(color, 0.5),
                       outline="")

# ─── Shared State ─────────────────────────────────────────────────────────────

pressed_keys      = set()
press_counts      = [0] * len(FRETS)   # per-fret press counter
strum_up_active   = False
strum_down_active = False
whammy_active     = False
sp_active         = False
_su_timer         = None
_sd_timer         = None

# ─── Input Handlers ───────────────────────────────────────────────────────────

def normalize_key(key):
    try:
        c = key.char
        return c.lower() if c else None
    except AttributeError:
        return str(key).replace("Key.", "").lower()


def on_press(key):
    global strum_up_active, strum_down_active, whammy_active, sp_active
    global _su_timer, _sd_timer

    k = normalize_key(key)
    if not k:
        return

    # Count each fret on the leading edge (not while held)
    if k not in pressed_keys:
        for i, fret in enumerate(FRETS):
            if k in fret["keys"]:
                press_counts[i] += 1

    pressed_keys.add(k)

    if k in STRUM_UP_KEYS:
        strum_up_active = True
        if _su_timer:
            _su_timer.cancel()
        def _clear_up():
            global strum_up_active
            strum_up_active = False
        _su_timer = threading.Timer(STRUM_FLASH_MS / 1000, _clear_up)
        _su_timer.start()

    if k in STRUM_DOWN_KEYS:
        strum_down_active = True
        if _sd_timer:
            _sd_timer.cancel()
        def _clear_dn():
            global strum_down_active
            strum_down_active = False
        _sd_timer = threading.Timer(STRUM_FLASH_MS / 1000, _clear_dn)
        _sd_timer.start()

    if k in WHAMMY_KEYS:
        whammy_active = True
    if k in SP_KEYS:
        sp_active = True


def on_release(key):
    global whammy_active, sp_active
    k = normalize_key(key)
    if not k:
        return
    pressed_keys.discard(k)
    if k in WHAMMY_KEYS:
        whammy_active = False
    if k in SP_KEYS:
        sp_active = False


def reset_counts():
    for i in range(len(press_counts)):
        press_counts[i] = 0


def start_listeners():
    def run():
        with kb.Listener(on_press=on_press, on_release=on_release) as l:
            l.join()
    threading.Thread(target=run, daemon=True).start()

# ─── Overlay ──────────────────────────────────────────────────────────────────

TRANSPARENT = "#010101"

class Overlay:
    FRET_D  = 58
    FRET_G  = 10
    PAD     = 12
    H       = 120   # taller than before to fit counters + reset button
    SIDE_W  = 68

    # Reset button hit area (stored as canvas coords after each draw)
    _reset_box = None

    def __init__(self):
        self.scale      = 1.0
        self._hovering  = False
        self.root       = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.configure(bg=TRANSPARENT)
        self._build_canvas()
        self._position_window()
        self._drag_ox = self._drag_oy = 0
        self.canvas.bind("<ButtonPress-1>", self._on_click)
        self.canvas.bind("<B1-Motion>",     self._drag_move)
        self.canvas.bind("<ButtonPress-3>", lambda e: self.root.destroy())
        self.canvas.bind("<MouseWheel>",    self._on_scroll)
        self.canvas.bind("<Motion>",        self._on_motion)
        self._tick()

    # ── Dims ────────────────────────────────────────────────────────────────

    def _dims(self):
        s  = self.scale
        fd = int(self.FRET_D * s)
        fg = int(self.FRET_G * s)
        p  = int(self.PAD    * s)
        h  = int(self.H      * s)
        sw = int(self.SIDE_W * s)
        fstrip = p + 5 * fd + 4 * fg + p
        tw     = fstrip + fg + sw + fg + sw + p
        return fd, fg, p, h, sw, fstrip, tw

    # ── Canvas ──────────────────────────────────────────────────────────────

    def _build_canvas(self):
        fd, fg, p, h, sw, fstrip, tw = self._dims()
        if hasattr(self, "canvas"):
            self.canvas.destroy()
        self.canvas = tk.Canvas(self.root, width=tw, height=h,
                                bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()
        self.root.geometry(f"{tw}x{h}")
        self.canvas.bind("<ButtonPress-1>", self._on_click)
        self.canvas.bind("<B1-Motion>",     self._drag_move)
        self.canvas.bind("<ButtonPress-3>", lambda e: self.root.destroy())
        self.canvas.bind("<MouseWheel>",    self._on_scroll)
        self.canvas.bind("<Motion>",        self._on_motion)
        self._draw()

    def _position_window(self):
        fd, fg, p, h, sw, fstrip, tw = self._dims()
        sw_s = self.root.winfo_screenwidth()
        sh_s = self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw_s - tw)//2}+{sh_s - h - 60}")

    # ── Draw ────────────────────────────────────────────────────────────────

    def _rrect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
               x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
               x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def _draw(self):
        self.canvas.delete("all")
        fd, fg, p, h, sw, fstrip, tw = self._dims()
        s      = self.scale
        rr     = max(5, int(11 * s))
        note_r = fd // 2

        # Layout rows
        note_cy    = p + note_r + int(4 * s)          # centre of note circles
        count_y    = note_cy + note_r + int(14 * s)   # counter text baseline
        reset_y    = h - int(10 * s)                  # reset button centre

        # ── Panel backgrounds ─────────────────────────────────────────────
        self._rrect(p//2, p//2, fstrip - p//2, h - p//2,
                    rr, fill="#101010", outline="#1e1e1e", width=1)
        sx0 = fstrip + fg // 2
        sx1 = sx0 + sw
        self._rrect(sx0, p//2, sx1, h - p//2,
                    rr, fill="#101010", outline="#1e1e1e", width=1)
        wx0 = sx1 + fg
        wx1 = wx0 + sw
        self._rrect(wx0, p//2, wx1, h - p//2,
                    rr, fill="#101010", outline="#1e1e1e", width=1)

        # ── GH note frets ─────────────────────────────────────────────────
        for i, fret in enumerate(FRETS):
            pressed = any(k in pressed_keys for k in fret["keys"])
            ncx = p + note_r + i * (fd + fg)
            draw_gh_note(self.canvas, ncx, note_cy, note_r, fret["color"], pressed)

            # Counter
            count = press_counts[i]
            color = fret["color"] if pressed else brighten(fret["color"], 0.5)
            fsz   = max(8, int(11 * s))
            self.canvas.create_text(
                ncx, count_y,
                text=str(count),
                fill=color,
                font=("Consolas", fsz, "bold")
            )

        # ── Reset button ──────────────────────────────────────────────────
        btn_w  = int(60 * s)
        btn_h  = int(16 * s)
        btn_cx = fstrip // 2
        bx0    = btn_cx - btn_w // 2
        bx1    = btn_cx + btn_w // 2
        by0    = reset_y - btn_h // 2
        by1    = reset_y + btn_h // 2

        hover = self._hovering
        btn_fill    = "#2a1a1a" if hover else "#1a1a1a"
        btn_outline = "#cc3333" if hover else "#3a2222"
        btn_text    = "#ff5555" if hover else "#663333"

        self._rrect(bx0, by0, bx1, by1,
                    max(3, int(5 * s)),
                    fill=btn_fill, outline=btn_outline, width=1,
                    tags="reset_btn")
        self.canvas.create_text(btn_cx, reset_y,
                                text="⟳  RESET",
                                fill=btn_text,
                                font=("Consolas", max(6, int(7 * s)), "bold"),
                                tags="reset_btn")

        # Store hit area for click detection
        self._reset_box = (bx0, by0, bx1, by1)

        # ── Strum arrows ──────────────────────────────────────────────────
        scx   = (sx0 + sx1) // 2
        ah    = max(12, int(19 * s))
        aw    = max(10, int(17 * s))
        gap   = max(3,  int(6  * s))
        arrow_cy = int(h * 0.42)
        up_cy = arrow_cy - gap - ah // 2
        dn_cy = arrow_cy + gap + ah // 2

        up_col = "#ffffff" if strum_up_active   else "#2a2a2a"
        dn_col = "#ffffff" if strum_down_active else "#2a2a2a"
        self.canvas.create_polygon(
            scx, up_cy - ah//2,
            scx - aw//2, up_cy + ah//2,
            scx + aw//2, up_cy + ah//2,
            fill=up_col, outline=""
        )
        self.canvas.create_polygon(
            scx, dn_cy + ah//2,
            scx - aw//2, dn_cy - ah//2,
            scx + aw//2, dn_cy - ah//2,
            fill=dn_col, outline=""
        )
        lsz = max(6, int(7 * s))
        self.canvas.create_text(scx, h - int(9*s), text="STRUM",
                                fill="#333333", font=("Consolas", lsz))

        # ── SP & Whammy ───────────────────────────────────────────────────
        wcx   = (wx0 + wx1) // 2
        br    = max(10, int(15 * s))
        sp_cy = int(h * 0.30)
        wh_cy = int(h * 0.62)

        draw_gh_note(self.canvas, wcx, sp_cy, br, "#ffe600", sp_active)
        self.canvas.create_text(wcx, sp_cy, text="★",
                                fill="#332800" if sp_active else "#1a1600",
                                font=("Consolas", max(7, int(9*s)), "bold"))

        draw_gh_note(self.canvas, wcx, wh_cy, br, "#cc44ff", whammy_active)
        self.canvas.create_text(wcx, wh_cy, text="W",
                                fill="#1a0022" if whammy_active else "#0d0011",
                                font=("Consolas", max(7, int(9*s)), "bold"))

        self.canvas.create_text(wcx, h - int(9*s), text="SP/WHM",
                                fill="#333333", font=("Consolas", lsz))

    # ── Events ──────────────────────────────────────────────────────────────

    def _in_reset(self, ex, ey):
        if not self._reset_box:
            return False
        bx0, by0, bx1, by1 = self._reset_box
        return bx0 <= ex <= bx1 and by0 <= ey <= by1

    def _on_click(self, e):
        if self._in_reset(e.x, e.y):
            reset_counts()
        else:
            self._drag_ox, self._drag_oy = e.x, e.y

    def _drag_move(self, e):
        if self._in_reset(e.x, e.y):
            return
        x = self.root.winfo_x() + e.x - self._drag_ox
        y = self.root.winfo_y() + e.y - self._drag_oy
        self.root.geometry(f"+{x}+{y}")

    def _on_motion(self, e):
        h = self._in_reset(e.x, e.y)
        if h != self._hovering:
            self._hovering = h
            self.canvas.config(cursor="hand2" if h else "")

    def _on_scroll(self, e):
        self.scale = max(0.5, min(2.5, self.scale + (0.08 if e.delta > 0 else -0.08)))
        fd, fg, p, h, sw, fstrip, tw = self._dims()
        ox, oy = self.root.winfo_x(), self.root.winfo_y()
        self.root.geometry(f"{tw}x{h}+{ox}+{oy}")
        self.canvas.config(width=tw, height=h)
        self._draw()

    # ── Loop ────────────────────────────────────────────────────────────────

    def _tick(self):
        self._draw()
        self.root.after(16, self._tick)

    def run(self):
        self.root.mainloop()

# ─── Entry ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_listeners()
    Overlay().run()
