import os
os.environ['SDL_DISABLE_IME'] = '1'
import pygame
import math
import os
import random

# Global state to communicate between threads
current_state = 'booting'
is_hidden = False

def set_state(state: str):
    global current_state
    current_state = state
    

def get_state() -> str:
    return current_state

def hide_ui():
    global is_hidden
    is_hidden = True

def show_ui():
    global is_hidden
    is_hidden = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _lerp(a, b, t):
    return a + (b - a) * t

def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )

def _draw_glow_ring(surf, color, center, radius, thickness, layers=4):
    """Draw a circle ring with soft outward glow on an SRCALPHA surface."""
    if radius < 2:
        return
    for i in range(layers, 0, -1):
        alpha = int(55 / i)
        r = max(2, radius + i * 5)
        pygame.draw.circle(surf, (*color, alpha), center, r, thickness + i * 2)
    pygame.draw.circle(surf, (*color, 240), center, radius, thickness)

def _draw_glow_arc(surf, color, cx, cy, radius, start_a, end_a, thickness, layers=3):
    """Draw an arc with soft glow on an SRCALPHA surface."""
    if radius < 4:
        return
    for i in range(layers, 0, -1):
        alpha = int(50 / i)
        r = max(4, radius + i * 4)
        rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        pygame.draw.arc(surf, (*color, alpha), rect, start_a, end_a, thickness + i * 2)
    rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
    pygame.draw.arc(surf, (*color, 230), rect, start_a, end_a, thickness)

# ---------------------------------------------------------------------------
# Main UI loop
# ---------------------------------------------------------------------------
def run_ui():
    pygame.init()
    pygame.font.init()

    WIDTH, HEIGHT = 440, 440
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME)
    pygame.display.set_caption("S.E.V.E.N.")

    # Win32 transparency and non-interactive setup
    try:
        import win32api, win32con, win32gui
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
        hwnd = pygame.display.get_wm_info()["window"]
        exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        
        # WS_EX_NOACTIVATE (0x08000000) prevents stealing focus
        # WS_EX_TRANSPARENT (0x00000020) makes it click-through
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               exstyle | win32con.WS_EX_LAYERED | 0x00000080 | 0x08000000 | 0x00000020)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(0, 0, 0), 0, win32con.LWA_COLORKEY)
    except ImportError:
        print("pywin32 not installed — window will not be transparent.")
        screen_w, screen_h = 1920, 1080
        hwnd = None

    clock = pygame.time.Clock()
    font_label = pygame.font.SysFont("Consolas", 12, bold=True)
    font_tiny  = pygame.font.SysFont("Consolas", 9)

    BLACK = (0, 0, 0)
    CX, CY = WIDTH // 2, HEIGHT // 2
    CENTER = (CX, CY)
    BASE_R = 108

    # State → target color
    STATE_COLORS = {
        'idle':      (20,  140, 255),
        'listening': (0,   220, 255),
        'thinking':  (255, 165,   0),
        'speaking':  (190, 230, 255),
        'booting':   (20,  140, 255),
        'sleep':     (10,   60, 130),
    }
    STATE_LABELS = {
        'idle':      'STANDBY',
        'listening': 'LISTENING',
        'thinking':  'PROCESSING',
        'speaking':  'RESPONDING',
        'booting':   'INITIALIZING',
        'sleep':     'SLEEP',
    }

    # Animation state
    t             = 0.0          # time accumulator (seconds)
    cur_color     = list(STATE_COLORS['booting'])
    cur_radius    = 0.0
    visibility    = 1.0
    current_scale = 1.0
    cur_x         = float(screen_w // 2 - WIDTH // 2)
    cur_y         = float(screen_h // 2 - HEIGHT // 2)
    last_hide     = False
    
    # Particle system: list of dicts {x, y, angle, dist, speed, size, alpha}
    particles = []

    import tts # For RMS volume

    while True:
        dt = clock.tick(60) / 1000.0
        dt = min(dt, 0.05)       # clamp so big pauses don't jump animation
        t += dt

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); os._exit(0)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit(); os._exit(0)

        state = get_state()

        # --- Visibility fade ---
        target_vis = 0.0 if (state == 'sleep' or is_hidden) else 1.0
        visibility = _lerp(visibility, target_vis, 0.08)
        if state == 'sleep' and visibility < 0.04:
            pygame.quit()
            return

        # --- Smooth color transition ---
        tgt_col = STATE_COLORS.get(state, STATE_COLORS['idle'])
        cur_color[0] = int(_lerp(cur_color[0], tgt_col[0], 0.04))
        cur_color[1] = int(_lerp(cur_color[1], tgt_col[1], 0.04))
        cur_color[2] = int(_lerp(cur_color[2], tgt_col[2], 0.04))
        col = tuple(cur_color)

        # --- Audio-Reactive Pulse ---
        vol = tts.get_current_volume()
        
        if state == 'booting':
            progress = min(1.0, t / 2.5)
            pulse = (BASE_R * progress) - BASE_R
            cur_radius = (BASE_R + pulse) * visibility
        elif state == 'idle':
            pulse = math.sin(t * 1.8) * 6
        elif state == 'listening':
            pulse = math.sin(t * 4.5) * 18 + math.sin(t * 11.3) * 5
        elif state == 'thinking':
            pulse = math.sin(t * 7.5) * 12 + math.sin(t * 3.2) * 4
        elif state == 'speaking':
            # Audio reactive pulse based on TTS RMS volume
            audio_pulse = (vol / 1000.0) * 12
            pulse = min(60.0, audio_pulse + math.sin(t * 3.5) * 4)
        else:
            pulse = 0

        if state != 'booting':
            target_r = (BASE_R + pulse) * visibility
            lerp_k = 0.4 if state == 'speaking' else 0.22 # Faster reaction when speaking
            cur_radius = _lerp(cur_radius, target_r, lerp_k)

        r = max(1, int(cur_radius))

        # --- Particle System Update ---
        if state in ['listening', 'thinking', 'speaking'] and visibility > 0.5:
            # Spawn particles based on volume/state
            spawn_rate = 2 if state == 'speaking' and vol > 1000 else (1 if random.random() < 0.3 else 0)
            for _ in range(spawn_rate):
                particles.append({
                    'angle': random.uniform(0, math.pi * 2),
                    'dist': r + random.uniform(5, 15),
                    'speed': random.uniform(20, 60),
                    'size': random.uniform(1, 3.5),
                    'alpha': 255
                })
        
        for p in particles:
            p['dist'] += p['speed'] * dt
            p['angle'] += dt * 0.5 # Slow orbit
            p['alpha'] -= 180 * dt
        particles = [p for p in particles if p['alpha'] > 0]

        # ---------------------------------------------------------------
        # Draw everything onto an SRCALPHA surface for glow compositing
        # ---------------------------------------------------------------
        screen.fill(BLACK)
        surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        # Draw Particles
        for p in particles:
            px = CX + p['dist'] * math.cos(p['angle'])
            py = CY + p['dist'] * math.sin(p['angle'])
            pygame.draw.circle(surf, (*col, int(max(0, p['alpha']))), (int(px), int(py)), int(p['size']))

        # 1. Outermost decorative ring + tick marks
        OUTER_R = r + 48
        if OUTER_R > 10:
            pygame.draw.circle(surf, (*col, 35), CENTER, OUTER_R, 1)
            num_ticks = 36
            for i in range(num_ticks):
                angle = (2 * math.pi * i / num_ticks) - math.pi / 2
                major = (i % 9 == 0)
                tlen  = 9 if major else (5 if i % 3 == 0 else 3)
                talpha = 200 if major else (100 if i % 3 == 0 else 50)
                ox = CX + OUTER_R * math.cos(angle)
                oy = CY + OUTER_R * math.sin(angle)
                ix = CX + (OUTER_R - tlen) * math.cos(angle)
                iy = CY + (OUTER_R - tlen) * math.sin(angle)
                pygame.draw.line(surf, (*col, talpha),
                                 (int(ix), int(iy)), (int(ox), int(oy)),
                                 2 if major else 1)

        # 2. Three rotating arc segments
        segs = [
            (r + 24, t * 0.9,           math.pi / 3.5, 2),   
            (r + 24, -t * 1.3 + 2.1,   math.pi / 4.5, 2),   
            (r + 14, t * 2.1 + 1.0,    math.pi / 6,   1),   
        ]
        for (seg_r, seg_t, seg_span, seg_thick) in segs:
            if seg_r > 4:
                _draw_glow_arc(surf, col, CX, CY, seg_r,
                               seg_t, seg_t + seg_span, seg_thick, layers=2)

        # 3. Second inner static ring (subtle)
        INNER_STATIC = max(2, int(r * 0.58))
        pygame.draw.circle(surf, (*col, 55), CENTER, INNER_STATIC, 1)

        # 4. Main ring — multi-layer glow
        ring_thick = 5 if state in ('listening', 'speaking') else 3
        _draw_glow_ring(surf, col, CENTER, r, ring_thick, layers=5)

        # 5. Crosshair lines (ultra-subtle)
        clen = max(8, int(r * 0.28))
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            x0, y0 = CX + dx * 6,        CY + dy * 6
            x1, y1 = CX + dx * (6+clen), CY + dy * (6+clen)
            pygame.draw.line(surf, (*col, 35), (x0,y0), (x1,y1), 1)

        # 6. Corner brackets (4 corners around outer ring)
        br = OUTER_R + 8
        blen = 12
        bthick = 1
        brackets = [
            (-math.pi * 3/4, -math.pi/2),  # TL
            (-math.pi/4,      0),            # TR
            (math.pi/4,       math.pi/2),   # BR
            (math.pi * 3/4,   math.pi),     # BL
        ]
        for (sa, ea) in brackets:
            if br > 4:
                brect = pygame.Rect(CX - br, CY - br, br*2, br*2)
                pygame.draw.arc(surf, (*col, 120), brect, sa, ea, bthick + 1)

        # 7. Center pulsing dot
        dot_r = max(2, int(3 + math.sin(t * 3.5) * 1.5))
        pygame.draw.circle(surf, (*col, 255), CENTER, dot_r + 4, 0)   # soft halo
        surf_dot = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(surf_dot, (*col, 80), CENTER, dot_r + 8, 0)
        surf.blit(surf_dot, (0, 0))
        pygame.draw.circle(surf, (255, 255, 255, 240), CENTER, dot_r, 0)  # bright core

        # 8. State label below the ring
        label_text = STATE_LABELS.get(state, state.upper())
        label_surf = font_label.render(label_text, True, col)
        label_surf.set_alpha(int(180 * visibility))
        label_x = CX - label_surf.get_width() // 2
        label_y = CY + r + 32
        surf.blit(label_surf, (label_x, label_y))

        # Tiny "J.A.R.V.I.S." text above ring
        title_surf = font_tiny.render("J.A.R.V.I.S.", True, col)
        title_surf.set_alpha(int(90 * visibility))
        surf.blit(title_surf, (CX - title_surf.get_width()//2, CY - r - 24))

        # ---------------------------------------------------------------
        # Scale & Position Logic
        # ---------------------------------------------------------------
        if state == 'booting':
            target_scale = 1.0
            tx = screen_w / 2 - WIDTH / 2
            ty = screen_h / 2 - HEIGHT / 2
        else:
            target_scale = 0.55
            # Position near the middle-right edge of the screen
            # Shift the window to account for the transparent padding around the scaled circle
            padding_right = (WIDTH * (1 - target_scale)) / 2
            tx = screen_w - WIDTH + padding_right - 40
            ty = screen_h / 2 - HEIGHT / 2

        # Ignore target if asleep
        if state == 'sleep':
            tx, ty = cur_x, cur_y

        current_scale = _lerp(current_scale, target_scale, 0.05)

        if current_scale < 0.99:
            scaled_w = int(WIDTH * current_scale)
            scaled_h = int(HEIGHT * current_scale)
            scaled_surf = pygame.transform.smoothscale(surf, (scaled_w, scaled_h))
            screen.blit(scaled_surf, (WIDTH//2 - scaled_w//2, HEIGHT//2 - scaled_h//2))
        else:
            screen.blit(surf, (0, 0))

        cur_x = _lerp(cur_x, tx, 0.05)
        cur_y = _lerp(cur_y, ty, 0.05)

        if hwnd:
            should_hide = is_hidden and visibility < 0.05
            if should_hide != last_hide:
                last_hide = should_hide
                import win32con as _wc, win32gui as _wg
                _wg.ShowWindow(hwnd, _wc.SW_HIDE if should_hide else _wc.SW_SHOWNOACTIVATE)
            if not should_hide:
                import win32con as _wc, win32gui as _wg
                _wg.SetWindowPos(hwnd, _wc.HWND_TOPMOST,
                                 int(cur_x), int(cur_y), 0, 0, _wc.SWP_NOSIZE | _wc.SWP_NOACTIVATE)

        pygame.display.flip()

if __name__ == "__main__":
    run_ui()

