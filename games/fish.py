# # import cv2
# # import mediapipe as mp
# # import numpy as np
# # import json, math, time, random, os
# # from datetime import date
# # from collections import deque

# # # ════════════════════════════════════════════════════════════
# # #  PROGRESS / SCHEDULE
# # # ════════════════════════════════════════════════════════════
# # DATA_FILE = os.path.expanduser("~/.elbow_fish_progress.json")

# # SCHEDULE = {
# #     1: (30,  [10, 15, 25, 35, 45, 50, 55]),
# #     2: (50,  [10, 15, 25, 35, 45, 50, 55]),
# #     3: (70,  [10, 15, 25, 35, 45, 50, 55]),
# #     4: (90,  [10, 15, 25, 35, 45, 50, 55]),
# # }

# # def load_progress():
# #     if os.path.exists(DATA_FILE):
# #         with open(DATA_FILE) as f:
# #             return json.load(f)
# #     return {"week": 1, "day": 1, "history": [], "adaptive_hold": None}

# # def save_progress(p):
# #     with open(DATA_FILE, "w") as f:
# #         json.dump(p, f, indent=2)

# # def get_today_config(progress):
# #     week = min(int(progress["week"]), 4)
# #     day  = min(int(progress["day"]),  7)
# #     target_angle, times = SCHEDULE[week]
# #     hold_t = times[day - 1]
# #     if progress.get("adaptive_hold"):
# #         hold_t = progress["adaptive_hold"]
# #     return week, day, target_angle, hold_t

# # def advance_day(progress, fish_caught):
# #     week, day, _, hold_t = get_today_config(progress)
# #     hist = progress.get("history", [])
# #     hist.append({"week": week, "day": day, "date": str(date.today()),
# #                  "fish": fish_caught, "hold": hold_t})
# #     progress["history"] = hist[-100:]
# #     # regression check
# #     if len(hist) >= 2 and fish_caught < hist[-2]["fish"]:
# #         progress["adaptive_hold"] = max(5, int(hold_t * 0.8))
# #     else:
# #         progress["adaptive_hold"] = None
# #     if day >= 7:
# #         progress["week"] = week + 1
# #         progress["day"]  = 1
# #     else:
# #         progress["day"]  = day + 1
# #     save_progress(progress)

# # # ════════════════════════════════════════════════════════════
# # #  ANGLE SMOOTHING  (Kalman-lite: exponential moving avg)
# # # ════════════════════════════════════════════════════════════
# # class AngleSmoother:
# #     def __init__(self, alpha=0.25):
# #         self.alpha = alpha
# #         self.value = None
# #     def update(self, v):
# #         if self.value is None:
# #             self.value = v
# #         else:
# #             self.value = self.alpha * v + (1 - self.alpha) * self.value
# #         return self.value

# # def elbow_angle(lm, side, W, H):
# #     """
# #     Flexion angle of the elbow:
# #       0 deg = fully straight arm
# #       90 deg = right-angle bend
# #     We use the interior angle at the elbow landmark.
# #     """
# #     mp_pose = mp.solutions.pose.PoseLandmark
# #     if side == 'L':
# #         sh, el, wr = mp_pose.LEFT_SHOULDER, mp_pose.LEFT_ELBOW, mp_pose.LEFT_WRIST
# #     else:
# #         sh, el, wr = mp_pose.RIGHT_SHOULDER, mp_pose.RIGHT_ELBOW, mp_pose.RIGHT_WRIST
# #     s = np.array([lm[sh.value].x * W,  lm[sh.value].y * H])
# #     e = np.array([lm[el.value].x * W,  lm[el.value].y * H])
# #     w = np.array([lm[wr.value].x * W,  lm[wr.value].y * H])
# #     ba = s - e;  bc = w - e
# #     cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
# #     interior = math.degrees(math.acos(np.clip(cosang, -1, 1)))
# #     # flexion = 180 - interior  (0 = straight, 90 = bent 90°)
# #     return 180.0 - interior

# # # ════════════════════════════════════════════════════════════
# # #  FISH
# # # ════════════════════════════════════════════════════════════
# # FISH_PALETTE = [
# #     (0,  200, 255),   # yellow
# #     (255, 100,  0),   # cyan-ish (BGR)
# #     (200,   0, 255),  # magenta
# #     (0,  255, 180),   # spring green
# #     (100, 255,  50),  # lime
# # ]

# # class Fish:
# #     def __init__(self, W, H):
# #         self.W, self.H = W, H
# #         self.reset()

# #     def reset(self):
# #         side = random.choice([-1, 1])
# #         self.x  = float(self.W + 70) if side == -1 else -70.0
# #         # fish swim in the LOWER 60% of screen
# #         self.y  = float(random.randint(int(self.H * 0.35), int(self.H * 0.88)))
# #         speed   = random.uniform(80, 160)          # px/sec
# #         self.vx = speed * (-side)
# #         self.vy = random.uniform(-20, 20)
# #         self.sz = random.randint(24, 44)
# #         self.col= random.choice(FISH_PALETTE)
# #         self.phase = random.uniform(0, math.tau)
# #         self.locked = False
# #         self.caught = False

# #     def update(self, dt):
# #         if self.caught:
# #             return
# #         if not self.locked:
# #             self.x += self.vx * dt
# #             self.y += self.vy * dt
# #             self.vy += random.uniform(-8, 8) * dt
# #             self.vy  = max(-40, min(40, self.vy))
# #             self.y   = max(int(self.H*0.32), min(int(self.H*0.92), self.y))
# #             self.phase += dt * 7
# #         if self.x < -120 or self.x > self.W + 120:
# #             self.reset()

# #     def draw(self, frame):
# #         if self.caught:
# #             return
# #         x, y, s = int(self.x), int(self.y), self.sz
# #         c = self.col
# #         facing = 1 if self.vx > 0 else -1
# #         wag = int(math.sin(self.phase) * s * 0.35)

# #         # ── tail ──
# #         tx = x - facing * s
# #         tail = np.array([[tx, y + wag],
# #                          [tx - facing * (s//2), y - s//2 + wag//2],
# #                          [tx - facing * (s//2), y + s//2 + wag//2]], np.int32)
# #         cv2.fillPoly(frame, [tail], c)

# #         # ── body ──
# #         cv2.ellipse(frame, (x, y), (s, s//2), 0, 0, 360, c, -1)
# #         # belly highlight
# #         hc = tuple(min(255, v + 80) for v in c)
# #         cv2.ellipse(frame, (x - facing*4, y + 3), (s//2, s//4), 0, 0, 360, hc, -1)
# #         # outline
# #         cv2.ellipse(frame, (x, y), (s, s//2), 0, 0, 360, (0,0,0), 1)

# #         # ── dorsal fin ──
# #         fin = np.array([[x,              y - s//2],
# #                         [x + facing*s//3, y - s + 4],
# #                         [x - facing*s//4, y - s//2]], np.int32)
# #         dc = tuple(max(0, v-60) for v in c)
# #         cv2.fillPoly(frame, [fin], dc)

# #         # ── eye ──
# #         ex = x + facing * (s - 6)
# #         cv2.circle(frame, (ex, y - 3), 5, (255,255,255), -1)
# #         cv2.circle(frame, (ex + facing, y - 3), 2, (0,0,0), -1)

# #         # ── scales (small arcs) ──
# #         for sx_off in range(-s//2 + 4, s//2 - 4, 8):
# #             cv2.ellipse(frame, (x + sx_off, y), (5, 3), 0, 0, 180,
# #                         tuple(max(0, v-30) for v in c), 1)

# #         # ── lock glow ──
# #         if self.locked:
# #             cv2.circle(frame, (x, y), s + 10, (0, 255, 255), 2, cv2.LINE_AA)
# #             cv2.circle(frame, (x, y), s + 18, (0, 180, 180), 1, cv2.LINE_AA)

# # # ════════════════════════════════════════════════════════════
# # #  BUBBLES
# # # ════════════════════════════════════════════════════════════
# # class Bubble:
# #     def __init__(self, W, H):
# #         self.x = float(random.randint(0, W))
# #         self.y = float(H)
# #         self.r = random.randint(3, 9)
# #         self.vy= random.uniform(40, 100)
# #         self.alive = True
# #     def update(self, dt):
# #         self.y -= self.vy * dt
# #         self.x += math.sin(self.y * 0.04) * 0.6
# #         if self.y < -20: self.alive = False
# #     def draw(self, frame):
# #         x, y = int(self.x), int(self.y)
# #         cv2.circle(frame, (x, y), self.r, (180, 180, 240), 1, cv2.LINE_AA)
# #         cv2.circle(frame, (x - self.r//3, y - self.r//3),
# #                    max(1, self.r//3), (220, 220, 255), -1)

# # # ════════════════════════════════════════════════════════════
# # #  WATER BACKGROUND  (blue, not green!)
# # # ════════════════════════════════════════════════════════════
# # def draw_water(frame, W, H):
# #     t = time.time()
# #     waterline = int(H * 0.28)

# #     # sky gradient (top portion)
# #     for row in range(waterline):
# #         ratio = row / waterline
# #         b = int(135 + 30 * ratio)
# #         g = int(180 + 20 * ratio)
# #         r = int(220 - 30 * ratio)
# #         frame[row, :] = (b, g, r)  # BGR sky

# #     # deep water (blue, not green)
# #     for row in range(waterline, H):
# #         depth = (row - waterline) / (H - waterline)
# #         b = int(140 - 60 * depth)
# #         g = int(100 - 50 * depth)
# #         r = int(40  - 20 * depth)
# #         frame[row, :] = (max(0,b), max(0,g), max(0,r))

# #     # water surface shimmer
# #     for i in range(0, W, 10):
# #         yo = int(math.sin(t * 2.5 + i * 0.06) * 3)
# #         cv2.line(frame, (i, waterline + yo), (i + 10, waterline + yo),
# #                  (170, 200, 255), 2)

# #     # caustics (subtle light patches underwater)
# #     for k in range(14):
# #         cx = int((math.sin(t * 0.5 + k * 1.7) * 0.5 + 0.5) * W)
# #         cy = int(waterline + 20 + (math.cos(t * 0.4 + k * 1.1) * 0.5 + 0.5)
# #                  * (H - waterline - 40))
# #         r2 = random.randint(2, 6)
# #         cv2.circle(frame, (cx, cy), r2, (160, 200, 255), -1)

# # # ════════════════════════════════════════════════════════════
# # #  ARM MESH
# # # ════════════════════════════════════════════════════════════
# # def draw_arm_mesh(frame, lm, side, W, H, on_target):
# #     mp_pose = mp.solutions.pose.PoseLandmark
# #     if side == 'L':
# #         indices = [mp_pose.LEFT_SHOULDER.value,
# #                    mp_pose.LEFT_ELBOW.value,
# #                    mp_pose.LEFT_WRIST.value]
# #     else:
# #         indices = [mp_pose.RIGHT_SHOULDER.value,
# #                    mp_pose.RIGHT_ELBOW.value,
# #                    mp_pose.RIGHT_WRIST.value]

# #     pts = [(int(lm[i].x * W), int(lm[i].y * H)) for i in indices]

# #     glow = (0, 255, 80)   if on_target else (255, 160, 0)
# #     core = (0, 220, 60)   if on_target else (200, 120, 0)

# #     # thick glow lines
# #     for a, b in zip(pts, pts[1:]):
# #         cv2.line(frame, a, b, glow, 8, cv2.LINE_AA)
# #         cv2.line(frame, a, b, (255,255,255), 2, cv2.LINE_AA)

# #     # joints
# #     for i, p in enumerate(pts):
# #         rad = 10 if i == 1 else 7   # bigger circle at elbow
# #         cv2.circle(frame, p, rad + 3, glow, -1, cv2.LINE_AA)
# #         cv2.circle(frame, p, rad, (255,255,255), -1, cv2.LINE_AA)
# #         cv2.circle(frame, p, rad + 3, (0,0,0), 1)

# # # ════════════════════════════════════════════════════════════
# # #  SPLASH
# # # ════════════════════════════════════════════════════════════
# # def draw_splash(frame, x, y, age):
# #     alpha = max(0.0, 1.0 - age / 0.7)
# #     r = int(age * 120)
# #     c = (int(0), int(220 * alpha), int(255 * alpha))
# #     cv2.circle(frame, (x, y), r,      c, 3, cv2.LINE_AA)
# #     cv2.circle(frame, (x, y), r // 2, c, 2, cv2.LINE_AA)
# #     for deg in range(0, 360, 40):
# #         rad = math.radians(deg)
# #         ex  = x + int(math.cos(rad) * r * 1.3)
# #         ey  = y + int(math.sin(rad) * r * 1.3)
# #         cv2.line(frame, (x, y), (ex, ey), c, 2, cv2.LINE_AA)

# # # ════════════════════════════════════════════════════════════
# # #  HUD — non-overlapping layout
# # # ════════════════════════════════════════════════════════════
# # def draw_hud(frame, week, day, angle, target, hold_t, hold_prog,
# #              fish_caught, fish_needed, on_target):
# #     H, W = frame.shape[:2]

# #     # ── top bar (semi-transparent) ──
# #     bar = frame.copy()
# #     cv2.rectangle(bar, (0, 0), (W, 58), (10, 20, 10), -1)
# #     cv2.addWeighted(bar, 0.72, frame, 0.28, 0, frame)
# #     cv2.line(frame, (0, 58), (W, 58), (0, 180, 80), 1)

# #     # week / day
# #     cv2.putText(frame, f"W{week} D{day}", (12, 38),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 230, 140), 2, cv2.LINE_AA)

# #     # fish counter — centred
# #     fish_txt = f"Fish  {fish_caught} / {fish_needed}"
# #     (tw, _), _ = cv2.getTextSize(fish_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
# #     cv2.putText(frame, fish_txt, (W // 2 - tw // 2, 38),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 220, 255), 2, cv2.LINE_AA)

# #     # hold time info — right side
# #     hold_txt = f"Hold {hold_t}s"
# #     (tw2, _), _ = cv2.getTextSize(hold_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
# #     cv2.putText(frame, hold_txt, (W - tw2 - 12, 38),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.75, (180, 255, 180), 2, cv2.LINE_AA)

# #     # ── angle panel (left side, below top bar) ──
# #     PAD = 12
# #     PW, PH = 180, 160
# #     px, py = PAD, 68

# #     panel = frame.copy()
# #     cv2.rectangle(panel, (px, py), (px + PW, py + PH), (5, 15, 5), -1)
# #     cv2.addWeighted(panel, 0.70, frame, 0.30, 0, frame)
# #     cv2.rectangle(frame, (px, py), (px + PW, py + PH),
# #                   (0, 200, 80) if on_target else (80, 140, 0), 1)

# #     # arc dial
# #     cx, cy, R = px + PW // 2, py + PH // 2 + 10, 52
# #     cv2.ellipse(frame, (cx, cy), (R, R), -90, 0, 180, (40, 60, 40), 4)
# #     arc_col = (0, 255, 80) if on_target else (0, 160, 255)
# #     arc_end = int(min(angle, 179))
# #     if arc_end > 0:
# #         cv2.ellipse(frame, (cx, cy), (R, R), -90, 0, arc_end, arc_col, 5, cv2.LINE_AA)

# #     # target marker
# #     tx = cx + int(math.cos(math.radians(-90 + target)) * R)
# #     ty = cy + int(math.sin(math.radians(-90 + target)) * R)
# #     cv2.circle(frame, (tx, ty), 6, (0, 255, 200), -1)
# #     cv2.circle(frame, (tx, ty), 6, (255,255,255), 1)

# #     # angle numbers
# #     cv2.putText(frame, f"{angle:.0f}deg", (cx - 28, cy + 6),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.55, arc_col, 2, cv2.LINE_AA)
# #     cv2.putText(frame, "Elbow Flex", (px + 18, py + 18),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 220, 160), 1)
# #     cv2.putText(frame, f"Target: {target}deg", (px + 8, py + PH - 10),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 200, 120), 1)

# #     # "HOLD!" label above dial when locking
# #     if hold_prog > 0:
# #         lbl = f"HOLD! {hold_t * (1 - hold_prog):.1f}s"
# #         cv2.putText(frame, lbl, (px + 8, py + 36),
# #                     cv2.FONT_HERSHEY_SIMPLEX, 0.42,
# #                     (0, 255, 100) if on_target else (0, 200, 255), 1, cv2.LINE_AA)

# #     # ── hold progress bar (bottom strip) ──
# #     if hold_prog > 0:
# #         BH = 22
# #         by = H - BH - 6
# #         cv2.rectangle(frame, (60, by), (W - 60, by + BH), (20, 40, 20), -1)
# #         filled = int((W - 120) * hold_prog)
# #         bar_c  = (0, 255, 100) if hold_prog < 0.8 else (0, 255, 255)
# #         cv2.rectangle(frame, (60, by), (60 + filled, by + BH), bar_c, -1)
# #         cv2.rectangle(frame, (60, by), (W - 60, by + BH), (0, 180, 80), 1)

# # # ════════════════════════════════════════════════════════════
# # #  PER-WEEK PROGRESS PANEL (right side)
# # # ════════════════════════════════════════════════════════════
# # def draw_week_progress(frame, history):
# #     H, W = frame.shape[:2]
# #     PW, PH = 200, 170
# #     px, py = W - PW - 10, 68

# #     panel = frame.copy()
# #     cv2.rectangle(panel, (px, py), (px + PW, py + PH), (5, 15, 5), -1)
# #     cv2.addWeighted(panel, 0.72, frame, 0.28, 0, frame)
# #     cv2.rectangle(frame, (px, py), (px + PW, py + PH), (0, 140, 60), 1)

# #     cv2.putText(frame, "Weekly Progress", (px + 18, py + 18),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 200, 120), 1)

# #     # group by week
# #     by_week = {}
# #     for h in history:
# #         wk = h.get("week", 1)
# #         by_week.setdefault(wk, []).append(h["fish"])

# #     row_h = 32
# #     for wk in sorted(by_week.keys()):
# #         vals  = by_week[wk]
# #         avg   = sum(vals) / len(vals)
# #         best  = max(vals)
# #         ry    = py + 28 + (wk - 1) * row_h

# #         wk_target = SCHEDULE.get(wk, (0, []))[0]
# #         cv2.putText(frame, f"W{wk} ({wk_target}d)", (px + 8, ry + 14),
# #                     cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 220, 180), 1)

# #         # mini bar (avg sessions)
# #         bar_max_w = 90
# #         bar_w = int(min(avg / 5, 1.0) * bar_max_w)
# #         bx = px + 80
# #         cv2.rectangle(frame, (bx, ry + 4), (bx + bar_max_w, ry + 16), (30, 50, 30), -1)
# #         col = (0, 220, 100) if avg >= 4 else (0, 160, 255)
# #         if bar_w > 0:
# #             cv2.rectangle(frame, (bx, ry + 4), (bx + bar_w, ry + 16), col, -1)
# #         cv2.putText(frame, f"{avg:.1f}", (bx + bar_max_w + 4, ry + 14),
# #                     cv2.FONT_HERSHEY_SIMPLEX, 0.34, (200, 255, 200), 1)

# # # ════════════════════════════════════════════════════════════
# # #  END-OF-SESSION OVERLAY
# # # ════════════════════════════════════════════════════════════
# # def draw_session_end(frame, fish_caught, fish_needed, week, day,
# #                      hold_t, history, adapted):
# #     H, W = frame.shape[:2]
# #     # dim background
# #     overlay = frame.copy()
# #     cv2.rectangle(overlay, (0, 0), (W, H), (0, 15, 5), -1)
# #     cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

# #     # card
# #     CW, CH = 560, 360
# #     cx, cy = (W - CW) // 2, (H - CH) // 2
# #     card = frame.copy()
# #     cv2.rectangle(card, (cx, cy), (cx + CW, cy + CH), (8, 30, 12), -1)
# #     cv2.addWeighted(card, 0.88, frame, 0.12, 0, frame)
# #     cv2.rectangle(frame, (cx, cy), (cx + CW, cy + CH), (0, 220, 100), 2)

# #     def txt(s, x, y, scale=0.7, col=(200,255,200), thick=1):
# #         cv2.putText(frame, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
# #                     scale, col, thick, cv2.LINE_AA)

# #     txt("SESSION COMPLETE!", cx + 100, cy + 44, 1.0, (0,255,150), 2)
# #     cv2.line(frame, (cx+20, cy+56), (cx+CW-20, cy+56), (0,180,80), 1)

# #     txt(f"Week {week}  ·  Day {day}", cx + 180, cy + 88, 0.62, (150,255,200))
# #     txt(f"Fish caught :  {fish_caught} / {fish_needed}", cx + 40, cy + 128, 0.78,
# #         (0,255,200) if fish_caught >= fish_needed else (0,180,255), 2)
# #     txt(f"Hold time   :  {hold_t}s", cx + 40, cy + 165, 0.68, (180,230,180))

# #     # last 7 sessions sparkline
# #     recent = history[-7:]
# #     if len(recent) >= 2:
# #         txt("Last 7 sessions:", cx + 40, cy + 205, 0.50, (120,200,120))
# #         gw, gh = CW - 80, 60
# #         gx, gy = cx + 40, cy + 215
# #         cv2.rectangle(frame, (gx, gy), (gx + gw, gy + gh), (20,40,20), -1)
# #         vals = [r["fish"] for r in recent]
# #         top  = max(max(vals), 1)
# #         for i in range(len(vals) - 1):
# #             x1 = gx + int(i * gw / (len(vals)-1))
# #             x2 = gx + int((i+1) * gw / (len(vals)-1))
# #             y1 = gy + gh - int(vals[i] * gh / top) - 2
# #             y2 = gy + gh - int(vals[i+1] * gh / top) - 2
# #             lc = (0,230,100) if vals[i+1] >= vals[i] else (0,80,255)
# #             cv2.line(frame, (x1,y1), (x2,y2), lc, 2, cv2.LINE_AA)
# #             cv2.circle(frame, (x1,y1), 4, (0,200,150), -1)
# #         cv2.circle(frame, (gx + gw, gy + gh - int(vals[-1]*gh/top) - 2), 4, (0,200,150), -1)

# #     if adapted:
# #         txt("* Hold time reduced (adaptive)", cx + 40, cy + CH - 50, 0.44, (0,200,255))

# #     txt("Press Q to save & exit    R to replay", cx + 80, cy + CH - 22,
# #         0.50, (120,200,120))

# # # ════════════════════════════════════════════════════════════
# # #  MAIN
# # # ════════════════════════════════════════════════════════════
# # def main():
# #     progress = load_progress()
# #     week, day, target_angle, hold_t = get_today_config(progress)
# #     adapted = progress.get("adaptive_hold") is not None

# #     FISH_NEEDED   = 5
# #     LOCK_RADIUS   = 999    # lock any visible fish — catching is about holding angle
# #     TOLERANCE     = 12     # ± degrees
# #     SESSION_DONE  = False

# #     print(f"Elbow Fishing  |  Week {week} Day {day}  |  Target {target_angle}°  |  Hold {hold_t}s")

# #     mp_pose  = mp.solutions.pose
# #     pose_est = mp_pose.Pose(min_detection_confidence=0.55,
# #                             min_tracking_confidence=0.55)

# #     cap = cv2.VideoCapture(0)
# #     if not cap.isOpened():
# #         print("No camera found."); return
# #     cap.set(cv2.CAP_PROP_FRAME_WIDTH,  960)
# #     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
# #     W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
# #     H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# #     fishes      = [Fish(W, H) for _ in range(5)]
# #     bubbles     = []
# #     splashes    = []          # (x, y, start_time)
# #     fish_caught = 0
# #     locked_fish = None
# #     hold_start  = None
# #     hold_prog   = 0.0
# #     smoother    = AngleSmoother(alpha=0.2)
# #     angle_val   = 0.0
# #     on_target   = False
# #     prev_t      = time.time()

# #     while True:
# #         ret, frame = cap.read()
# #         if not ret: break
# #         frame = cv2.flip(frame, 1)
# #         now = time.time()
# #         dt  = max(0.001, now - prev_t)
# #         prev_t = now

# #         # ── background ──
# #         draw_water(frame, W, H)

# #         # ── bubbles ──
# #         if random.random() < 0.06:
# #             bubbles.append(Bubble(W, H))
# #         for b in bubbles[:]:
# #             b.update(dt); b.draw(frame)
# #             if not b.alive: bubbles.remove(b)

# #         # ── fish ──
# #         for f in fishes:
# #             f.update(dt)
# #             f.draw(frame)

# #         # ── pose ──
# #         rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
# #         res = pose_est.process(rgb)
# #         active_side = None

# #         if res.pose_landmarks:
# #             lm = res.pose_landmarks.landmark

# #             # choose side: whichever wrist is higher (lower y)
# #             lw = lm[mp_pose.PoseLandmark.LEFT_WRIST.value]
# #             rw = lm[mp_pose.PoseLandmark.RIGHT_WRIST.value]
# #             side = 'L' if lw.y < rw.y else 'R'
# #             active_side = side

# #             raw_angle = elbow_angle(lm, side, W, H)
# #             angle_val = smoother.update(raw_angle)
# #             on_target = abs(angle_val - target_angle) <= TOLERANCE

# #             draw_arm_mesh(frame, lm, side, W, H, on_target)

# #             # elbow pixel
# #             el_idx = (mp_pose.PoseLandmark.LEFT_ELBOW.value if side == 'L'
# #                       else mp_pose.PoseLandmark.RIGHT_ELBOW.value)
# #             elbow_px = (int(lm[el_idx].x * W), int(lm[el_idx].y * H))

# #             # ── lock + catch logic ──
# #             if on_target and not SESSION_DONE:
# #                 # find nearest alive fish
# #                 nearest, best_d = None, float('inf')
# #                 for f in fishes:
# #                     if f.caught: continue
# #                     d = math.hypot(f.x - elbow_px[0], f.y - elbow_px[1])
# #                     if d < best_d:
# #                         best_d = d; nearest = f

# #                 if nearest:
# #                     if locked_fish is not nearest:
# #                         locked_fish = nearest
# #                         hold_start  = now
# #                     nearest.locked = True
# #                     elapsed   = now - hold_start
# #                     hold_prog = min(1.0, elapsed / hold_t)

# #                     if elapsed >= hold_t:
# #                         splashes.append((int(nearest.x), int(nearest.y), now))
# #                         nearest.caught = True
# #                         fish_caught   += 1
# #                         locked_fish    = None
# #                         hold_start     = None
# #                         hold_prog      = 0.0
# #                         fishes.append(Fish(W, H))
# #                         if fish_caught >= FISH_NEEDED:
# #                             SESSION_DONE = True
# #                 else:
# #                     hold_prog = 0.0
# #             else:
# #                 if locked_fish:
# #                     locked_fish.locked = False
# #                 locked_fish = None
# #                 hold_start  = None
# #                 hold_prog   = 0.0
# #         else:
# #             # no detection — decay angle display
# #             angle_val = smoother.update(angle_val * 0.9)

# #         # ── splashes ──
# #         for sp in splashes[:]:
# #             sx, sy, st = sp
# #             age = now - st
# #             if age > 0.7: splashes.remove(sp)
# #             else: draw_splash(frame, sx, sy, age)

# #         # ── HUD ──
# #         if not SESSION_DONE:
# #             draw_hud(frame, week, day, angle_val, target_angle, hold_t,
# #                      hold_prog, fish_caught, FISH_NEEDED, on_target)
# #             draw_week_progress(frame, progress.get("history", []))
# #         else:
# #             draw_session_end(frame, fish_caught, FISH_NEEDED, week, day,
# #                              hold_t, progress.get("history", []), adapted)

# #         # "no pose" warning
# #         if active_side is None and not SESSION_DONE:
# #             cv2.putText(frame, "Stand back — full arm must be visible",
# #                         (W//2 - 200, H//2),
# #                         cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,200,255), 2, cv2.LINE_AA)

# #         cv2.imshow("Elbow Fishing Rehab", frame)
# #         key = cv2.waitKey(1) & 0xFF

# #         if key == ord('q'):
# #             if fish_caught > 0 or SESSION_DONE:
# #                 advance_day(progress, fish_caught)
# #                 print(f"Saved. Fish: {fish_caught}. Next: W{progress['week']} D{progress['day']}")
# #             break
# #         elif key == ord('r'):
# #             fish_caught = 0
# #             fishes = [Fish(W, H) for _ in range(5)]
# #             bubbles.clear(); splashes.clear()
# #             SESSION_DONE = False
# #             locked_fish  = None
# #             hold_start   = None
# #             hold_prog    = 0.0
# #             smoother     = AngleSmoother(0.2)
# #         elif key == ord('s'):   # debug: skip day
# #             advance_day(progress, fish_caught)
# #             progress = load_progress()
# #             week, day, target_angle, hold_t = get_today_config(progress)
# #             adapted = progress.get("adaptive_hold") is not None
# #             SESSION_DONE = False; fish_caught = 0
# #             print(f"Skipped to W{week} D{day}")

# #     cap.release()
# #     cv2.destroyAllWindows()

# # if __name__ == "__main__":
# #     main()

# import cv2
# import mediapipe as mp
# import numpy as np
# import json, math, time, random, os
# from datetime import date
# from collections import deque

# # ════════════════════════════════════════════════════════════
# #  PROGRESS / SCHEDULE
# # ════════════════════════════════════════════════════════════
# DATA_FILE = os.path.expanduser("~/.elbow_fish_progress.json")

# SCHEDULE = {
#     1: (30,  [10, 15, 25, 35, 45, 50, 55]),
#     2: (50,  [10, 15, 25, 35, 45, 50, 55]),
#     3: (70,  [10, 15, 25, 35, 45, 50, 55]),
#     4: (90,  [10, 15, 25, 35, 45, 50, 55]),
# }

# def load_progress():
#     if os.path.exists(DATA_FILE):
#         with open(DATA_FILE) as f:
#             return json.load(f)
#     return {"week": 1, "day": 1, "history": [], "adaptive_hold": None}

# def save_progress(p):
#     with open(DATA_FILE, "w") as f:
#         json.dump(p, f, indent=2)

# def get_today_config(progress):
#     week = min(int(progress["week"]), 4)
#     day  = min(int(progress["day"]),  7)
#     target_angle, times = SCHEDULE[week]
#     hold_t = times[day - 1]
#     if progress.get("adaptive_hold"):
#         hold_t = progress["adaptive_hold"]
#     return week, day, target_angle, hold_t

# def advance_day(progress, fish_caught, avg_stability):
#     week, day, _, hold_t = get_today_config(progress)
#     hist = progress.get("history", [])
#     hist.append({"week": week, "day": day, "date": str(date.today()),
#                  "fish": fish_caught, "hold": hold_t,
#                  "stability": round(avg_stability, 1)})
#     progress["history"] = hist[-100:]
#     # regression check
#     if len(hist) >= 2 and fish_caught < hist[-2]["fish"]:
#         progress["adaptive_hold"] = max(5, int(hold_t * 0.8))
#     else:
#         progress["adaptive_hold"] = None
#     if day >= 7:
#         progress["week"] = week + 1
#         progress["day"]  = 1
#     else:
#         progress["day"]  = day + 1
#     save_progress(progress)

# # ════════════════════════════════════════════════════════════
# #  ANGLE SMOOTHING  (Kalman-lite: exponential moving avg)
# # ════════════════════════════════════════════════════════════
# class AngleSmoother:
#     def __init__(self, alpha=0.25):
#         self.alpha = alpha
#         self.value = None
#     def update(self, v):
#         if self.value is None:
#             self.value = v
#         else:
#             self.value = self.alpha * v + (1 - self.alpha) * self.value
#         return self.value

# def elbow_angle(lm, side, W, H):
#     """
#     Flexion angle of the elbow:
#       0 deg = fully straight arm
#       90 deg = right-angle bend
#     We use the interior angle at the elbow landmark.
#     """
#     mp_pose = mp.solutions.pose.PoseLandmark
#     if side == 'L':
#         sh, el, wr = mp_pose.LEFT_SHOULDER, mp_pose.LEFT_ELBOW, mp_pose.LEFT_WRIST
#     else:
#         sh, el, wr = mp_pose.RIGHT_SHOULDER, mp_pose.RIGHT_ELBOW, mp_pose.RIGHT_WRIST
#     s = np.array([lm[sh.value].x * W,  lm[sh.value].y * H])
#     e = np.array([lm[el.value].x * W,  lm[el.value].y * H])
#     w = np.array([lm[wr.value].x * W,  lm[wr.value].y * H])
#     ba = s - e;  bc = w - e
#     cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
#     interior = math.degrees(math.acos(np.clip(cosang, -1, 1)))
#     # flexion = 180 - interior  (0 = straight, 90 = bent 90°)
#     return 180.0 - interior

# # ════════════════════════════════════════════════════════════
# #  STABILITY TRACKER
# #  Converts angle variance during a hold attempt into a 0-100
# #  "steadiness" score. A perfectly still arm scores ~100;
# #  a wobbling arm (std dev >= ~15deg) scores near 0.
# # ════════════════════════════════════════════════════════════
# class StabilityTracker:
#     def __init__(self, window=90):
#         self.samples = deque(maxlen=window)

#     def reset(self):
#         self.samples.clear()

#     def add(self, angle):
#         self.samples.append(angle)

#     def score(self):
#         if len(self.samples) < 3:
#             return 100.0
#         std = float(np.std(self.samples))
#         return float(max(0.0, 100.0 - (std / 15.0) * 100.0))

#     def speed_factor(self):
#         """How fast hold-progress should fill given current steadiness."""
#         s = self.score()
#         if s >= 70:
#             return 1.0
#         elif s >= 40:
#             return 0.6
#         else:
#             return 0.25

# # ════════════════════════════════════════════════════════════
# #  FISH
# # ════════════════════════════════════════════════════════════
# FISH_PALETTE = [
#     (0,  200, 255),   # yellow
#     (255, 100,  0),   # cyan-ish (BGR)
#     (200,   0, 255),  # magenta
#     (0,  255, 180),   # spring green
#     (100, 255,  50),  # lime
# ]

# class Fish:
#     def __init__(self, W, H):
#         self.W, self.H = W, H
#         self.reset()

#     def reset(self):
#         side = random.choice([-1, 1])
#         self.x  = float(self.W + 70) if side == -1 else -70.0
#         # fish swim in the LOWER 60% of screen
#         self.y  = float(random.randint(int(self.H * 0.35), int(self.H * 0.88)))
#         speed   = random.uniform(80, 160)          # px/sec
#         self.vx = speed * (-side)
#         self.vy = random.uniform(-20, 20)
#         self.sz = random.randint(24, 44)
#         self.col= random.choice(FISH_PALETTE)
#         self.phase = random.uniform(0, math.tau)
#         self.locked = False
#         self.caught = False

#     def update(self, dt):
#         if self.caught:
#             return
#         if not self.locked:
#             self.x += self.vx * dt
#             self.y += self.vy * dt
#             self.vy += random.uniform(-8, 8) * dt
#             self.vy  = max(-40, min(40, self.vy))
#             self.y   = max(int(self.H*0.32), min(int(self.H*0.92), self.y))
#             self.phase += dt * 7
#         if self.x < -120 or self.x > self.W + 120:
#             self.reset()

#     def draw(self, frame):
#         if self.caught:
#             return
#         x, y, s = int(self.x), int(self.y), self.sz
#         c = self.col
#         facing = 1 if self.vx > 0 else -1
#         wag = int(math.sin(self.phase) * s * 0.35)

#         # ── tail ──
#         tx = x - facing * s
#         tail = np.array([[tx, y + wag],
#                          [tx - facing * (s//2), y - s//2 + wag//2],
#                          [tx - facing * (s//2), y + s//2 + wag//2]], np.int32)
#         cv2.fillPoly(frame, [tail], c)

#         # ── body ──
#         cv2.ellipse(frame, (x, y), (s, s//2), 0, 0, 360, c, -1)
#         # belly highlight
#         hc = tuple(min(255, v + 80) for v in c)
#         cv2.ellipse(frame, (x - facing*4, y + 3), (s//2, s//4), 0, 0, 360, hc, -1)
#         # outline
#         cv2.ellipse(frame, (x, y), (s, s//2), 0, 0, 360, (0,0,0), 1)

#         # ── dorsal fin ──
#         fin = np.array([[x,              y - s//2],
#                         [x + facing*s//3, y - s + 4],
#                         [x - facing*s//4, y - s//2]], np.int32)
#         dc = tuple(max(0, v-60) for v in c)
#         cv2.fillPoly(frame, [fin], dc)

#         # ── eye ──
#         ex = x + facing * (s - 6)
#         cv2.circle(frame, (ex, y - 3), 5, (255,255,255), -1)
#         cv2.circle(frame, (ex + facing, y - 3), 2, (0,0,0), -1)

#         # ── scales (small arcs) ──
#         for sx_off in range(-s//2 + 4, s//2 - 4, 8):
#             cv2.ellipse(frame, (x + sx_off, y), (5, 3), 0, 0, 180,
#                         tuple(max(0, v-30) for v in c), 1)

#         # ── lock glow ──
#         if self.locked:
#             cv2.circle(frame, (x, y), s + 10, (0, 255, 255), 2, cv2.LINE_AA)
#             cv2.circle(frame, (x, y), s + 18, (0, 180, 180), 1, cv2.LINE_AA)

# # ════════════════════════════════════════════════════════════
# #  BUBBLES
# # ════════════════════════════════════════════════════════════
# class Bubble:
#     def __init__(self, W, H):
#         self.x = float(random.randint(0, W))
#         self.y = float(H)
#         self.r = random.randint(3, 9)
#         self.vy= random.uniform(40, 100)
#         self.alive = True
#     def update(self, dt):
#         self.y -= self.vy * dt
#         self.x += math.sin(self.y * 0.04) * 0.6
#         if self.y < -20: self.alive = False
#     def draw(self, frame):
#         x, y = int(self.x), int(self.y)
#         cv2.circle(frame, (x, y), self.r, (180, 180, 240), 1, cv2.LINE_AA)
#         cv2.circle(frame, (x - self.r//3, y - self.r//3),
#                    max(1, self.r//3), (220, 220, 255), -1)

# # ════════════════════════════════════════════════════════════
# #  WATER BACKGROUND  (blue, not green!)
# # ════════════════════════════════════════════════════════════
# def draw_water(frame, W, H):
#     t = time.time()
#     waterline = int(H * 0.28)

#     # sky gradient (top portion)
#     for row in range(waterline):
#         ratio = row / waterline
#         b = int(135 + 30 * ratio)
#         g = int(180 + 20 * ratio)
#         r = int(220 - 30 * ratio)
#         frame[row, :] = (b, g, r)  # BGR sky

#     # deep water (blue, not green)
#     for row in range(waterline, H):
#         depth = (row - waterline) / (H - waterline)
#         b = int(140 - 60 * depth)
#         g = int(100 - 50 * depth)
#         r = int(40  - 20 * depth)
#         frame[row, :] = (max(0,b), max(0,g), max(0,r))

#     # water surface shimmer
#     for i in range(0, W, 10):
#         yo = int(math.sin(t * 2.5 + i * 0.06) * 3)
#         cv2.line(frame, (i, waterline + yo), (i + 10, waterline + yo),
#                  (170, 200, 255), 2)

#     # caustics (subtle light patches underwater)
#     for k in range(14):
#         cx = int((math.sin(t * 0.5 + k * 1.7) * 0.5 + 0.5) * W)
#         cy = int(waterline + 20 + (math.cos(t * 0.4 + k * 1.1) * 0.5 + 0.5)
#                  * (H - waterline - 40))
#         r2 = random.randint(2, 6)
#         cv2.circle(frame, (cx, cy), r2, (160, 200, 255), -1)

# # ════════════════════════════════════════════════════════════
# #  ARM MESH
# #  NOTE: colors are in OpenCV's BGR order. The original off-target
# #  color (255,160,0) was actually sky-blue in BGR, which vanished
# #  against the blue water background — that's why the arm looked
# #  "invisible". Fixed to a high-contrast orange/red here, with a
# #  visibility check so low-confidence joints don't draw at junk
# #  positions.
# # ════════════════════════════════════════════════════════════
# def draw_arm_mesh(frame, lm, side, W, H, on_target):
#     mp_pose = mp.solutions.pose.PoseLandmark
#     if side == 'L':
#         indices = [mp_pose.LEFT_SHOULDER.value,
#                    mp_pose.LEFT_ELBOW.value,
#                    mp_pose.LEFT_WRIST.value]
#     else:
#         indices = [mp_pose.RIGHT_SHOULDER.value,
#                    mp_pose.RIGHT_ELBOW.value,
#                    mp_pose.RIGHT_WRIST.value]

#     pts = [(int(lm[i].x * W), int(lm[i].y * H)) for i in indices]
#     vis = [lm[i].visibility for i in indices]

#     # FIXED: true BGR orange (0,140,255) / red-orange when off target,
#     # bright green when on target — both pop against blue water.
#     glow = (0, 255, 80)   if on_target else (0, 140, 255)
#     core = (0, 220, 60)   if on_target else (0, 90, 230)

#     # thick glow lines (skip a segment only if BOTH ends are low-confidence)
#     for (a, b), (va, vb) in zip(zip(pts, pts[1:]), zip(vis, vis[1:])):
#         if va < 0.3 and vb < 0.3:
#             continue
#         cv2.line(frame, a, b, glow, 10, cv2.LINE_AA)
#         cv2.line(frame, a, b, (255, 255, 255), 3, cv2.LINE_AA)
#         cv2.line(frame, a, b, core, 4, cv2.LINE_AA)

#     # joints
#     for i, (p, v) in enumerate(zip(pts, vis)):
#         if v < 0.25:
#             continue
#         rad = 12 if i == 1 else 9   # bigger circle at elbow
#         cv2.circle(frame, p, rad + 4, glow, -1, cv2.LINE_AA)
#         cv2.circle(frame, p, rad, (255, 255, 255), -1, cv2.LINE_AA)
#         cv2.circle(frame, p, rad + 4, (0, 0, 0), 2)

#     # "ON TARGET" badge floating above the elbow
#     if on_target:
#         ex, ey = pts[1]
#         label = "ON TARGET"
#         (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
#         bx, by = ex - tw // 2 - 8, ey - 50
#         cv2.rectangle(frame, (bx, by), (bx + tw + 16, by + th + 14), (0, 60, 0), -1)
#         cv2.rectangle(frame, (bx, by), (bx + tw + 16, by + th + 14), (0, 255, 100), 2)
#         cv2.putText(frame, label, (bx + 8, by + th + 4),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 120), 2, cv2.LINE_AA)

# # ════════════════════════════════════════════════════════════
# #  SPLASH
# # ════════════════════════════════════════════════════════════
# def draw_splash(frame, x, y, age):
#     alpha = max(0.0, 1.0 - age / 0.7)
#     r = int(age * 120)
#     c = (int(0), int(220 * alpha), int(255 * alpha))
#     cv2.circle(frame, (x, y), r,      c, 3, cv2.LINE_AA)
#     cv2.circle(frame, (x, y), r // 2, c, 2, cv2.LINE_AA)
#     for deg in range(0, 360, 40):
#         rad = math.radians(deg)
#         ex  = x + int(math.cos(rad) * r * 1.3)
#         ey  = y + int(math.sin(rad) * r * 1.3)
#         cv2.line(frame, (x, y), (ex, ey), c, 2, cv2.LINE_AA)

# def draw_catch_banner(frame, text, age, life=1.0):
#     H, W = frame.shape[:2]
#     alpha = max(0.0, 1.0 - age / life)
#     if alpha <= 0:
#         return
#     scale = 1.0 + 0.15 * math.sin(age * 12)
#     (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)
#     x = W // 2 - tw // 2
#     y = int(H * 0.42)
#     overlay = frame.copy()
#     cv2.rectangle(overlay, (x - 20, y - th - 16), (x + tw + 20, y + 16), (0, 40, 0), -1)
#     cv2.addWeighted(overlay, 0.55 * alpha, frame, 1 - 0.55 * alpha, 0, frame)
#     col = (0, int(255 * alpha), int(150 * alpha))
#     cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, col, 3, cv2.LINE_AA)

# # ════════════════════════════════════════════════════════════
# #  HUD — non-overlapping layout
# # ════════════════════════════════════════════════════════════
# def draw_hud(frame, week, day, angle, target, hold_t, hold_prog,
#              fish_caught, fish_needed, on_target, stability):
#     H, W = frame.shape[:2]

#     # ── top bar (semi-transparent) ──
#     bar = frame.copy()
#     cv2.rectangle(bar, (0, 0), (W, 58), (10, 20, 10), -1)
#     cv2.addWeighted(bar, 0.72, frame, 0.28, 0, frame)
#     cv2.line(frame, (0, 58), (W, 58), (0, 180, 80), 1)

#     # week / day
#     cv2.putText(frame, f"W{week} D{day}", (12, 38),
#                 cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 230, 140), 2, cv2.LINE_AA)

#     # fish counter — centred
#     fish_txt = f"Fish  {fish_caught} / {fish_needed}"
#     (tw, _), _ = cv2.getTextSize(fish_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
#     cv2.putText(frame, fish_txt, (W // 2 - tw // 2, 38),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 220, 255), 2, cv2.LINE_AA)

#     # hold time info — right side
#     hold_txt = f"Hold {hold_t}s"
#     (tw2, _), _ = cv2.getTextSize(hold_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
#     cv2.putText(frame, hold_txt, (W - tw2 - 12, 38),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.75, (180, 255, 180), 2, cv2.LINE_AA)

#     # ── angle panel (left side, below top bar) ──
#     PAD = 12
#     PW, PH = 180, 160
#     px, py = PAD, 68

#     panel = frame.copy()
#     cv2.rectangle(panel, (px, py), (px + PW, py + PH), (5, 15, 5), -1)
#     cv2.addWeighted(panel, 0.70, frame, 0.30, 0, frame)
#     cv2.rectangle(frame, (px, py), (px + PW, py + PH),
#                   (0, 200, 80) if on_target else (80, 140, 0), 1)

#     # arc dial
#     cx, cy, R = px + PW // 2, py + PH // 2 + 10, 52
#     cv2.ellipse(frame, (cx, cy), (R, R), -90, 0, 180, (40, 60, 40), 4)
#     arc_col = (0, 255, 80) if on_target else (0, 160, 255)
#     arc_end = int(min(angle, 179))
#     if arc_end > 0:
#         cv2.ellipse(frame, (cx, cy), (R, R), -90, 0, arc_end, arc_col, 5, cv2.LINE_AA)

#     # target marker
#     tx = cx + int(math.cos(math.radians(-90 + target)) * R)
#     ty = cy + int(math.sin(math.radians(-90 + target)) * R)
#     cv2.circle(frame, (tx, ty), 6, (0, 255, 200), -1)
#     cv2.circle(frame, (tx, ty), 6, (255,255,255), 1)

#     # angle numbers
#     cv2.putText(frame, f"{angle:.0f}deg", (cx - 28, cy + 6),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.55, arc_col, 2, cv2.LINE_AA)
#     cv2.putText(frame, "Elbow Flex", (px + 18, py + 18),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 220, 160), 1)
#     cv2.putText(frame, f"Target: {target}deg", (px + 8, py + PH - 10),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 200, 120), 1)

#     # "HOLD!" label above dial when locking
#     if hold_prog > 0:
#         lbl = f"HOLD! {hold_t * (1 - hold_prog):.1f}s"
#         cv2.putText(frame, lbl, (px + 8, py + 36),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.42,
#                     (0, 255, 100) if on_target else (0, 200, 255), 1, cv2.LINE_AA)

#     # ── hold progress bar + stability bar (bottom strip) ──
#     if hold_prog > 0:
#         BH = 22
#         by = H - BH - 6
#         cv2.rectangle(frame, (60, by), (W - 60, by + BH), (20, 40, 20), -1)
#         filled = int((W - 120) * hold_prog)
#         bar_c  = (0, 255, 100) if hold_prog < 0.8 else (0, 255, 255)
#         cv2.rectangle(frame, (60, by), (60 + filled, by + BH), bar_c, -1)
#         cv2.rectangle(frame, (60, by), (W - 60, by + BH), (0, 180, 80), 1)
#         cv2.putText(frame, "HOLD PROGRESS", (64, by - 6),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 255, 180), 1)

#         # stability bar, just above the hold bar
#         sby = by - 30
#         SBH = 16
#         cv2.rectangle(frame, (60, sby), (W - 60, sby + SBH), (20, 30, 40), -1)
#         s_filled = int((W - 120) * (stability / 100.0))
#         if stability >= 70:
#             s_col = (0, 220, 100)
#         elif stability >= 40:
#             s_col = (0, 200, 255)
#         else:
#             s_col = (0, 80, 255)
#         cv2.rectangle(frame, (60, sby), (60 + s_filled, sby + SBH), s_col, -1)
#         cv2.rectangle(frame, (60, sby), (W - 60, sby + SBH), (80, 80, 120), 1)
#         cv2.putText(frame, f"STABILITY {stability:.0f}%", (64, sby - 4),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.34, (200, 220, 255), 1)

# # ════════════════════════════════════════════════════════════
# #  PER-WEEK PROGRESS PANEL (right side)
# # ════════════════════════════════════════════════════════════
# def draw_week_progress(frame, history):
#     H, W = frame.shape[:2]
#     PW, PH = 220, 190
#     px, py = W - PW - 10, 68

#     panel = frame.copy()
#     cv2.rectangle(panel, (px, py), (px + PW, py + PH), (5, 15, 5), -1)
#     cv2.addWeighted(panel, 0.72, frame, 0.28, 0, frame)
#     cv2.rectangle(frame, (px, py), (px + PW, py + PH), (0, 140, 60), 1)

#     cv2.putText(frame, "Weekly Progress", (px + 18, py + 18),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 200, 120), 1)

#     # group by week
#     by_week = {}
#     for h in history:
#         wk = h.get("week", 1)
#         by_week.setdefault(wk, []).append(h)

#     row_h = 38
#     for wk in sorted(by_week.keys()):
#         rows  = by_week[wk]
#         vals  = [r["fish"] for r in rows]
#         stabs = [r.get("stability", 100.0) for r in rows]
#         avg   = sum(vals) / len(vals)
#         avg_s = sum(stabs) / len(stabs)
#         ry    = py + 28 + (wk - 1) * row_h

#         wk_target = SCHEDULE.get(wk, (0, []))[0]
#         cv2.putText(frame, f"W{wk} ({wk_target}d)", (px + 8, ry + 14),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 220, 180), 1)

#         # mini bar (avg fish caught)
#         bar_max_w = 90
#         bar_w = int(min(avg / 5, 1.0) * bar_max_w)
#         bx = px + 80
#         cv2.rectangle(frame, (bx, ry + 2), (bx + bar_max_w, ry + 13), (30, 50, 30), -1)
#         col = (0, 220, 100) if avg >= 4 else (0, 160, 255)
#         if bar_w > 0:
#             cv2.rectangle(frame, (bx, ry + 2), (bx + bar_w, ry + 13), col, -1)
#         cv2.putText(frame, f"{avg:.1f} fish", (bx + bar_max_w + 4, ry + 12),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.32, (200, 255, 200), 1)

#         # mini bar (avg stability)
#         sb_w = int(min(avg_s / 100.0, 1.0) * bar_max_w)
#         cv2.rectangle(frame, (bx, ry + 17), (bx + bar_max_w, ry + 26), (25, 35, 45), -1)
#         s_col = (0, 220, 100) if avg_s >= 70 else ((0, 200, 255) if avg_s >= 40 else (0, 80, 255))
#         if sb_w > 0:
#             cv2.rectangle(frame, (bx, ry + 17), (bx + sb_w, ry + 26), s_col, -1)
#         cv2.putText(frame, f"{avg_s:.0f}% stab", (bx + bar_max_w + 4, ry + 25),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.30, (200, 220, 255), 1)

# # ════════════════════════════════════════════════════════════
# #  END-OF-SESSION OVERLAY
# # ════════════════════════════════════════════════════════════
# def draw_session_end(frame, fish_caught, fish_needed, week, day,
#                      hold_t, history, adapted, avg_stability):
#     H, W = frame.shape[:2]
#     # dim background
#     overlay = frame.copy()
#     cv2.rectangle(overlay, (0, 0), (W, H), (0, 15, 5), -1)
#     cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

#     # card
#     CW, CH = 560, 390
#     cx, cy = (W - CW) // 2, (H - CH) // 2
#     card = frame.copy()
#     cv2.rectangle(card, (cx, cy), (cx + CW, cy + CH), (8, 30, 12), -1)
#     cv2.addWeighted(card, 0.88, frame, 0.12, 0, frame)
#     cv2.rectangle(frame, (cx, cy), (cx + CW, cy + CH), (0, 220, 100), 2)

#     def txt(s, x, y, scale=0.7, col=(200,255,200), thick=1):
#         cv2.putText(frame, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
#                     scale, col, thick, cv2.LINE_AA)

#     txt("SESSION COMPLETE!", cx + 100, cy + 44, 1.0, (0,255,150), 2)
#     cv2.line(frame, (cx+20, cy+56), (cx+CW-20, cy+56), (0,180,80), 1)

#     txt(f"Week {week}  ·  Day {day}", cx + 180, cy + 88, 0.62, (150,255,200))
#     txt(f"Fish caught :  {fish_caught} / {fish_needed}", cx + 40, cy + 128, 0.78,
#         (0,255,200) if fish_caught >= fish_needed else (0,180,255), 2)
#     txt(f"Hold time   :  {hold_t}s", cx + 40, cy + 165, 0.68, (180,230,180))
#     s_col = (0,255,150) if avg_stability >= 70 else ((0,200,255) if avg_stability >= 40 else (0,100,255))
#     txt(f"Avg stability:  {avg_stability:.0f}%", cx + 40, cy + 198, 0.68, s_col)

#     # last 7 sessions sparkline
#     recent = history[-7:]
#     if len(recent) >= 2:
#         txt("Last 7 sessions (fish):", cx + 40, cy + 232, 0.48, (120,200,120))
#         gw, gh = CW - 80, 55
#         gx, gy = cx + 40, cy + 240
#         cv2.rectangle(frame, (gx, gy), (gx + gw, gy + gh), (20,40,20), -1)
#         vals = [r["fish"] for r in recent]
#         top  = max(max(vals), 1)
#         for i in range(len(vals) - 1):
#             x1 = gx + int(i * gw / (len(vals)-1))
#             x2 = gx + int((i+1) * gw / (len(vals)-1))
#             y1 = gy + gh - int(vals[i] * gh / top) - 2
#             y2 = gy + gh - int(vals[i+1] * gh / top) - 2
#             lc = (0,230,100) if vals[i+1] >= vals[i] else (0,80,255)
#             cv2.line(frame, (x1,y1), (x2,y2), lc, 2, cv2.LINE_AA)
#             cv2.circle(frame, (x1,y1), 4, (0,200,150), -1)
#         cv2.circle(frame, (gx + gw, gy + gh - int(vals[-1]*gh/top) - 2), 4, (0,200,150), -1)

#     if adapted:
#         txt("* Hold time reduced (adaptive)", cx + 40, cy + CH - 50, 0.44, (0,200,255))

#     txt("Press Q to save & exit    R to replay", cx + 80, cy + CH - 22,
#         0.50, (120,200,120))

# # ════════════════════════════════════════════════════════════
# #  MAIN
# # ════════════════════════════════════════════════════════════
# def main():
#     progress = load_progress()
#     week, day, target_angle, hold_t = get_today_config(progress)
#     adapted = progress.get("adaptive_hold") is not None

#     FISH_NEEDED   = 5
#     TOLERANCE     = 12     # ± degrees
#     SESSION_DONE  = False

#     print(f"Elbow Fishing  |  Week {week} Day {day}  |  Target {target_angle}°  |  Hold {hold_t}s")

#     mp_pose  = mp.solutions.pose
#     pose_est = mp_pose.Pose(min_detection_confidence=0.55,
#                             min_tracking_confidence=0.55)

#     cap = cv2.VideoCapture(0)
#     if not cap.isOpened():
#         print("No camera found."); return
#     cap.set(cv2.CAP_PROP_FRAME_WIDTH,  960)
#     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

#     # IMPORTANT: many webcams ignore the requested resolution above and
#     # hand back frames at a different size. If we trust cap.get() instead
#     # of the real frame, every landmark gets scaled to the wrong canvas
#     # and the arm overlay draws off-screen or squashed into a corner —
#     # which looks exactly like "no arm visible". So grab one real frame
#     # first and measure it directly.
#     ret0, probe_frame = cap.read()
#     if not ret0:
#         print("Could not read a frame from the camera."); cap.release(); return
#     H, W = probe_frame.shape[:2]
#     print(f"Camera actual frame size: {W}x{H}")

#     fishes      = [Fish(W, H) for _ in range(5)]
#     bubbles     = []
#     splashes    = []          # (x, y, start_time)
#     catch_banner = None       # (text, start_time)
#     fish_caught = 0
#     locked_fish = None
#     hold_accum  = 0.0         # accumulated effective hold seconds
#     hold_prog   = 0.0
#     catch_stabilities = []    # stability score recorded at each catch
#     smoother    = AngleSmoother(alpha=0.2)
#     stability   = StabilityTracker()
#     stab_score  = 100.0
#     angle_val   = 0.0
#     on_target   = False
#     prev_t      = time.time()

#     while True:
#         ret, frame = cap.read()
#         if not ret: break
#         frame = cv2.flip(frame, 1)
#         # safety net: if the camera ever hands back a different frame
#         # size mid-stream, keep H/W in sync so landmark math never
#         # drifts off the visible canvas
#         H, W = frame.shape[:2]
#         now = time.time()
#         dt  = max(0.001, now - prev_t)
#         prev_t = now

#         # ── background ──
#         draw_water(frame, W, H)

#         # ── bubbles ──
#         if random.random() < 0.06:
#             bubbles.append(Bubble(W, H))
#         for b in bubbles[:]:
#             b.update(dt); b.draw(frame)
#             if not b.alive: bubbles.remove(b)

#         # ── fish ──
#         for f in fishes:
#             f.update(dt)
#             f.draw(frame)

#         # ── pose ──
#         rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#         res = pose_est.process(rgb)
#         active_side = None

#         if res.pose_landmarks:
#             lm = res.pose_landmarks.landmark

#             # choose side: whichever wrist is higher (lower y)
#             lw = lm[mp_pose.PoseLandmark.LEFT_WRIST.value]
#             rw = lm[mp_pose.PoseLandmark.RIGHT_WRIST.value]
#             side = 'L' if lw.y < rw.y else 'R'
#             active_side = side

#             raw_angle = elbow_angle(lm, side, W, H)
#             angle_val = smoother.update(raw_angle)
#             on_target = abs(angle_val - target_angle) <= TOLERANCE

#             draw_arm_mesh(frame, lm, side, W, H, on_target)

#             # elbow pixel
#             el_idx = (mp_pose.PoseLandmark.LEFT_ELBOW.value if side == 'L'
#                       else mp_pose.PoseLandmark.RIGHT_ELBOW.value)
#             elbow_px = (int(lm[el_idx].x * W), int(lm[el_idx].y * H))

#             # ── lock + catch logic ──
#             if on_target and not SESSION_DONE:
#                 # find nearest alive fish
#                 nearest, best_d = None, float('inf')
#                 for f in fishes:
#                     if f.caught: continue
#                     d = math.hypot(f.x - elbow_px[0], f.y - elbow_px[1])
#                     if d < best_d:
#                         best_d = d; nearest = f

#                 if nearest:
#                     if locked_fish is not nearest:
#                         locked_fish = nearest
#                         hold_accum  = 0.0
#                         stability.reset()
#                     nearest.locked = True

#                     stability.add(angle_val)
#                     stab_score = stability.score()
#                     factor = stability.speed_factor()
#                     hold_accum += dt * factor
#                     hold_prog = min(1.0, hold_accum / hold_t)

#                     if hold_accum >= hold_t:
#                         splashes.append((int(nearest.x), int(nearest.y), now))
#                         catch_banner = (f"FISH CAUGHT!  Stability {stab_score:.0f}%", now)
#                         catch_stabilities.append(stab_score)
#                         nearest.caught = True
#                         fish_caught   += 1
#                         locked_fish    = None
#                         hold_accum     = 0.0
#                         hold_prog      = 0.0
#                         stability.reset()
#                         fishes.append(Fish(W, H))
#                         if fish_caught >= FISH_NEEDED:
#                             SESSION_DONE = True
#                 else:
#                     hold_prog = 0.0
#             else:
#                 if locked_fish:
#                     locked_fish.locked = False
#                 locked_fish = None
#                 hold_accum  = 0.0
#                 hold_prog   = 0.0
#                 stability.reset()
#         else:
#             # no detection — decay angle display
#             angle_val = smoother.update(angle_val * 0.9)

#         # ── splashes ──
#         for sp in splashes[:]:
#             sx, sy, st = sp
#             age = now - st
#             if age > 0.7: splashes.remove(sp)
#             else: draw_splash(frame, sx, sy, age)

#         # ── catch banner ──
#         if catch_banner:
#             text, st = catch_banner
#             age = now - st
#             if age > 1.1:
#                 catch_banner = None
#             else:
#                 draw_catch_banner(frame, text, age, life=1.1)

#         avg_stability = (sum(catch_stabilities) / len(catch_stabilities)
#                           if catch_stabilities else 100.0)

#         # ── HUD ──
#         if not SESSION_DONE:
#             draw_hud(frame, week, day, angle_val, target_angle, hold_t,
#                      hold_prog, fish_caught, FISH_NEEDED, on_target, stab_score)
#             draw_week_progress(frame, progress.get("history", []))
#         else:
#             draw_session_end(frame, fish_caught, FISH_NEEDED, week, day,
#                              hold_t, progress.get("history", []), adapted,
#                              avg_stability)

#         # "no pose" warning
#         if active_side is None and not SESSION_DONE:
#             cv2.putText(frame, "Stand back - full arm must be visible",
#                         (W//2 - 210, H//2),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,200,255), 2, cv2.LINE_AA)

#         cv2.imshow("Elbow Fishing Rehab", frame)
#         key = cv2.waitKey(1) & 0xFF

#         if key == ord('q'):
#             if fish_caught > 0 or SESSION_DONE:
#                 advance_day(progress, fish_caught, avg_stability)
#                 print(f"Saved. Fish: {fish_caught}, Stability: {avg_stability:.0f}%. "
#                       f"Next: W{progress['week']} D{progress['day']}")
#             break
#         elif key == ord('r'):
#             fish_caught = 0
#             fishes = [Fish(W, H) for _ in range(5)]
#             bubbles.clear(); splashes.clear()
#             catch_banner = None
#             catch_stabilities = []
#             SESSION_DONE = False
#             locked_fish  = None
#             hold_accum   = 0.0
#             hold_prog    = 0.0
#             stability.reset()
#             smoother     = AngleSmoother(0.2)
#         elif key == ord('s'):   # debug: skip day
#             advance_day(progress, fish_caught, avg_stability)
#             progress = load_progress()
#             week, day, target_angle, hold_t = get_today_config(progress)
#             adapted = progress.get("adaptive_hold") is not None
#             SESSION_DONE = False; fish_caught = 0
#             catch_stabilities = []
#             print(f"Skipped to W{week} D{day}")

#     cap.release()
#     cv2.destroyAllWindows()

# if __name__ == "__main__":
#     main()


import cv2
import mediapipe as mp
import numpy as np
import json, math, time, random, os
from datetime import date
from collections import deque

# ════════════════════════════════════════════════════════════
#  PROGRESS / SCHEDULE
#  Week -> (target elbow-flexion angle, [hold seconds for day 1..7])
#  This is the core of the exercise design:
#    - angle target increases WEEK over week
#    - hold duration increases DAY over day within a week
# ════════════════════════════════════════════════════════════
DATA_FILE = os.path.expanduser("~/.elbow_fish_progress.json")

SCHEDULE = {
    1: (30,  [10, 15, 25, 35, 45, 50, 55]),
    2: (50,  [10, 15, 25, 35, 45, 50, 55]),
    3: (70,  [10, 15, 25, 35, 45, 50, 55]),
    4: (90,  [10, 15, 25, 35, 45, 50, 55]),
}

def load_progress():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"week": 1, "day": 1, "history": [], "adaptive_hold": None}

def save_progress(p):
    with open(DATA_FILE, "w") as f:
        json.dump(p, f, indent=2)

def get_today_config(progress):
    week = min(int(progress["week"]), 4)
    day  = min(int(progress["day"]),  7)
    target_angle, times = SCHEDULE[week]
    hold_t = times[day - 1]
    if progress.get("adaptive_hold"):
        hold_t = progress["adaptive_hold"]
    return week, day, target_angle, hold_t

def advance_day(progress, fish_caught, avg_stability):
    week, day, _, hold_t = get_today_config(progress)
    hist = progress.get("history", [])
    hist.append({"week": week, "day": day, "date": str(date.today()),
                 "fish": fish_caught, "hold": hold_t,
                 "stability": round(avg_stability, 1)})
    progress["history"] = hist[-100:]
    # regression check: if today's catch count dropped vs last session,
    # ease the hold requirement next time instead of punishing progress
    if len(hist) >= 2 and fish_caught < hist[-2]["fish"]:
        progress["adaptive_hold"] = max(5, int(hold_t * 0.8))
    else:
        progress["adaptive_hold"] = None
    if day >= 7:
        progress["week"] = week + 1
        progress["day"]  = 1
    else:
        progress["day"]  = day + 1
    save_progress(progress)

# ════════════════════════════════════════════════════════════
#  ANGLE SMOOTHING  (exponential moving average)
# ════════════════════════════════════════════════════════════
class AngleSmoother:
    def __init__(self, alpha=0.25):
        self.alpha = alpha
        self.value = None
    def update(self, v):
        if self.value is None:
            self.value = v
        else:
            self.value = self.alpha * v + (1 - self.alpha) * self.value
        return self.value

def elbow_angle(lm, side, W, H):
    """
    Flexion angle of the elbow:
      0 deg   = fully straight arm
      90 deg  = right-angle bend
    Interior angle at the elbow joint, converted to flexion.
    """
    mp_pose = mp.solutions.pose.PoseLandmark
    if side == 'L':
        sh, el, wr = mp_pose.LEFT_SHOULDER, mp_pose.LEFT_ELBOW, mp_pose.LEFT_WRIST
    else:
        sh, el, wr = mp_pose.RIGHT_SHOULDER, mp_pose.RIGHT_ELBOW, mp_pose.RIGHT_WRIST
    s = np.array([lm[sh.value].x * W,  lm[sh.value].y * H])
    e = np.array([lm[el.value].x * W,  lm[el.value].y * H])
    w = np.array([lm[wr.value].x * W,  lm[wr.value].y * H])
    ba = s - e;  bc = w - e
    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    interior = math.degrees(math.acos(np.clip(cosang, -1, 1)))
    return 180.0 - interior

# ════════════════════════════════════════════════════════════
#  STABILITY TRACKER
#  Converts angle variance during a hold attempt into a 0-100
#  "steadiness" score. A perfectly still arm scores ~100;
#  a wobbling arm (std dev >= ~28deg) scores near 0.
#  RECALIBRATED: the old 15deg cutoff punished normal hand tremor
#  and MediaPipe's own frame-to-frame landmark jitter, so the bar
#  looked "shaky"/red even while holding still. Raised the cutoff
#  and shortened the reaction window to ~1s of recent motion.
# ════════════════════════════════════════════════════════════
class StabilityTracker:
    def __init__(self, window=30):
        self.samples = deque(maxlen=window)

    def reset(self):
        self.samples.clear()

    def add(self, angle):
        self.samples.append(angle)

    def score(self):
        if len(self.samples) < 3:
            return 100.0
        std = float(np.std(self.samples))
        return float(max(0.0, 100.0 - (std / 28.0) * 100.0))

    def speed_factor(self):
        """How fast hold-progress should fill given current steadiness."""
        s = self.score()
        if s >= 70:
            return 1.0
        elif s >= 40:
            return 0.6
        else:
            return 0.25

# ════════════════════════════════════════════════════════════
#  FISH
# ════════════════════════════════════════════════════════════
FISH_PALETTE = [
    (0,  200, 255),   # yellow          (BGR)
    (255, 100,  0),   # blue-ish
    (200,   0, 255),  # magenta
    (0,  255, 180),   # spring green
    (100, 255,  50),  # lime
]

class Fish:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.reset()

    def reset(self):
        side = random.choice([-1, 1])
        # side == -1 -> spawn off the RIGHT edge, must swim LEFT (negative vx)
        # side ==  1 -> spawn off the LEFT  edge, must swim RIGHT (positive vx)
        self.x  = float(self.W + 70) if side == -1 else -70.0
        # fish swim in the LOWER 60% of screen
        self.y  = float(random.randint(int(self.H * 0.35), int(self.H * 0.88)))
        speed   = random.uniform(80, 160)          # px/sec
        # FIXED: previously `speed * (-side)` sent every fish swimming
        # AWAY from the screen the instant it spawned, so it re-triggered
        # reset() on the very next frame and never became visible.
        # It must move TOWARD the screen, i.e. in the direction of `side`.
        self.vx = speed * side
        self.vy = random.uniform(-20, 20)
        self.sz = random.randint(24, 44)
        self.col= random.choice(FISH_PALETTE)
        self.phase = random.uniform(0, math.tau)
        self.locked = False
        self.caught = False

    def update(self, dt):
        if self.caught:
            return
        if not self.locked:
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.vy += random.uniform(-8, 8) * dt
            self.vy  = max(-40, min(40, self.vy))
            self.y   = max(int(self.H*0.32), min(int(self.H*0.92), self.y))
            self.phase += dt * 7
        if self.x < -120 or self.x > self.W + 120:
            self.reset()

    def draw(self, frame):
        if self.caught:
            return
        x, y, s = int(self.x), int(self.y), self.sz
        c = self.col
        facing = 1 if self.vx > 0 else -1
        wag = int(math.sin(self.phase) * s * 0.35)

        # ── tail ──
        tx = x - facing * s
        tail = np.array([[tx, y + wag],
                         [tx - facing * (s//2), y - s//2 + wag//2],
                         [tx - facing * (s//2), y + s//2 + wag//2]], np.int32)
        cv2.fillPoly(frame, [tail], c)

        # ── body ──
        cv2.ellipse(frame, (x, y), (s, s//2), 0, 0, 360, c, -1)
        hc = tuple(min(255, v + 80) for v in c)
        cv2.ellipse(frame, (x - facing*4, y + 3), (s//2, s//4), 0, 0, 360, hc, -1)
        cv2.ellipse(frame, (x, y), (s, s//2), 0, 0, 360, (0,0,0), 1)

        # ── dorsal fin ──
        fin = np.array([[x,              y - s//2],
                        [x + facing*s//3, y - s + 4],
                        [x - facing*s//4, y - s//2]], np.int32)
        dc = tuple(max(0, v-60) for v in c)
        cv2.fillPoly(frame, [fin], dc)

        # ── eye ──
        ex = x + facing * (s - 6)
        cv2.circle(frame, (ex, y - 3), 5, (255,255,255), -1)
        cv2.circle(frame, (ex + facing, y - 3), 2, (0,0,0), -1)

        # ── scales ──
        for sx_off in range(-s//2 + 4, s//2 - 4, 8):
            cv2.ellipse(frame, (x + sx_off, y), (5, 3), 0, 0, 180,
                        tuple(max(0, v-30) for v in c), 1)

        # ── lock glow ──
        if self.locked:
            cv2.circle(frame, (x, y), s + 10, (0, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(frame, (x, y), s + 18, (0, 180, 180), 1, cv2.LINE_AA)

# ════════════════════════════════════════════════════════════
#  BUBBLES
# ════════════════════════════════════════════════════════════
class Bubble:
    def __init__(self, W, H):
        self.x = float(random.randint(0, W))
        self.y = float(H)
        self.r = random.randint(3, 9)
        self.vy= random.uniform(40, 100)
        self.alive = True
    def update(self, dt):
        self.y -= self.vy * dt
        self.x += math.sin(self.y * 0.04) * 0.6
        if self.y < -20: self.alive = False
    def draw(self, frame):
        x, y = int(self.x), int(self.y)
        cv2.circle(frame, (x, y), self.r, (180, 180, 240), 1, cv2.LINE_AA)
        cv2.circle(frame, (x - self.r//3, y - self.r//3),
                   max(1, self.r//3), (220, 220, 255), -1)

# ════════════════════════════════════════════════════════════
#  WATER BACKGROUND
#  FIXED: this used to do `frame[row, :] = (...)`, which HARD
#  OVERWRITES every camera pixel with a flat gradient — the real
#  video of you (and your hand/arm) was being erased every frame
#  before anything else was drawn. Now we build the gradient on a
#  separate overlay buffer and blend it over the real frame with
#  addWeighted, so you stay visible underneath an underwater tint.
# ════════════════════════════════════════════════════════════
def draw_water(frame, W, H, tint_strength=0.40):
    t = time.time()
    waterline = int(H * 0.28)

    overlay = frame.copy()
    for row in range(waterline):
        ratio = row / waterline
        b = int(135 + 30 * ratio)
        g = int(180 + 20 * ratio)
        r = int(220 - 30 * ratio)
        overlay[row, :] = (b, g, r)

    for row in range(waterline, H):
        depth = (row - waterline) / (H - waterline)
        b = int(140 - 60 * depth)
        g = int(100 - 50 * depth)
        r = int(40  - 20 * depth)
        overlay[row, :] = (max(0,b), max(0,g), max(0,r))

    # blend tint over the REAL camera image instead of replacing it
    cv2.addWeighted(overlay, tint_strength, frame, 1 - tint_strength, 0, frame)

    # shimmer + caustics drawn directly onto the (now tinted) real frame
    for i in range(0, W, 10):
        yo = int(math.sin(t * 2.5 + i * 0.06) * 3)
        cv2.line(frame, (i, waterline + yo), (i + 10, waterline + yo),
                 (170, 200, 255), 1, cv2.LINE_AA)

    for k in range(14):
        cx = int((math.sin(t * 0.5 + k * 1.7) * 0.5 + 0.5) * W)
        cy = int(waterline + 20 + (math.cos(t * 0.4 + k * 1.1) * 0.5 + 0.5)
                 * (H - waterline - 40))
        r2 = random.randint(2, 6)
        cv2.circle(frame, (cx, cy), r2, (160, 200, 255), 1, cv2.LINE_AA)

# ════════════════════════════════════════════════════════════
#  ARM MESH
# ════════════════════════════════════════════════════════════
def draw_arm_mesh(frame, lm, side, W, H, on_target):
    mp_pose = mp.solutions.pose.PoseLandmark
    if side == 'L':
        indices = [mp_pose.LEFT_SHOULDER.value,
                   mp_pose.LEFT_ELBOW.value,
                   mp_pose.LEFT_WRIST.value]
    else:
        indices = [mp_pose.RIGHT_SHOULDER.value,
                   mp_pose.RIGHT_ELBOW.value,
                   mp_pose.RIGHT_WRIST.value]

    pts = [(int(lm[i].x * W), int(lm[i].y * H)) for i in indices]
    vis = [lm[i].visibility for i in indices]

    glow = (0, 255, 80)   if on_target else (0, 140, 255)
    core = (0, 220, 60)   if on_target else (0, 90, 230)

    for (a, b), (va, vb) in zip(zip(pts, pts[1:]), zip(vis, vis[1:])):
        if va < 0.3 and vb < 0.3:
            continue
        cv2.line(frame, a, b, glow, 10, cv2.LINE_AA)
        cv2.line(frame, a, b, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.line(frame, a, b, core, 4, cv2.LINE_AA)

    for i, (p, v) in enumerate(zip(pts, vis)):
        if v < 0.25:
            continue
        rad = 12 if i == 1 else 9
        cv2.circle(frame, p, rad + 4, glow, -1, cv2.LINE_AA)
        cv2.circle(frame, p, rad, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, p, rad + 4, (0, 0, 0), 2)

    if on_target:
        ex, ey = pts[1]
        label = "ON TARGET"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        bx, by = ex - tw // 2 - 8, ey - 50
        cv2.rectangle(frame, (bx, by), (bx + tw + 16, by + th + 14), (0, 60, 0), -1)
        cv2.rectangle(frame, (bx, by), (bx + tw + 16, by + th + 14), (0, 255, 100), 2)
        cv2.putText(frame, label, (bx + 8, by + th + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 120), 2, cv2.LINE_AA)

# ════════════════════════════════════════════════════════════
#  SPLASH
# ════════════════════════════════════════════════════════════
def draw_splash(frame, x, y, age):
    alpha = max(0.0, 1.0 - age / 0.7)
    r = int(age * 120)
    c = (int(0), int(220 * alpha), int(255 * alpha))
    cv2.circle(frame, (x, y), r,      c, 3, cv2.LINE_AA)
    cv2.circle(frame, (x, y), r // 2, c, 2, cv2.LINE_AA)
    for deg in range(0, 360, 40):
        rad = math.radians(deg)
        ex  = x + int(math.cos(rad) * r * 1.3)
        ey  = y + int(math.sin(rad) * r * 1.3)
        cv2.line(frame, (x, y), (ex, ey), c, 2, cv2.LINE_AA)

def draw_catch_banner(frame, text, age, life=1.0):
    H, W = frame.shape[:2]
    alpha = max(0.0, 1.0 - age / life)
    if alpha <= 0:
        return
    scale = 1.0 + 0.15 * math.sin(age * 12)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)
    x = W // 2 - tw // 2
    y = int(H * 0.42)
    overlay = frame.copy()
    cv2.rectangle(overlay, (x - 20, y - th - 16), (x + tw + 20, y + 16), (0, 40, 0), -1)
    cv2.addWeighted(overlay, 0.55 * alpha, frame, 1 - 0.55 * alpha, 0, frame)
    col = (0, int(255 * alpha), int(150 * alpha))
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, col, 3, cv2.LINE_AA)

# ════════════════════════════════════════════════════════════
#  HUD
# ════════════════════════════════════════════════════════════
def draw_hud(frame, week, day, angle, target, hold_t, hold_prog,
             fish_caught, fish_needed, on_target, stability):
    H, W = frame.shape[:2]

    bar = frame.copy()
    cv2.rectangle(bar, (0, 0), (W, 58), (10, 20, 10), -1)
    cv2.addWeighted(bar, 0.72, frame, 0.28, 0, frame)
    cv2.line(frame, (0, 58), (W, 58), (0, 180, 80), 1)

    cv2.putText(frame, f"W{week} D{day}", (12, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 230, 140), 2, cv2.LINE_AA)

    fish_txt = f"Fish  {fish_caught} / {fish_needed}"
    (tw, _), _ = cv2.getTextSize(fish_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
    cv2.putText(frame, fish_txt, (W // 2 - tw // 2, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 220, 255), 2, cv2.LINE_AA)

    hold_txt = f"Hold {hold_t}s"
    (tw2, _), _ = cv2.getTextSize(hold_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
    cv2.putText(frame, hold_txt, (W - tw2 - 12, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (180, 255, 180), 2, cv2.LINE_AA)

    PAD = 12
    PW, PH = 180, 160
    px, py = PAD, 68

    panel = frame.copy()
    cv2.rectangle(panel, (px, py), (px + PW, py + PH), (5, 15, 5), -1)
    cv2.addWeighted(panel, 0.70, frame, 0.30, 0, frame)
    cv2.rectangle(frame, (px, py), (px + PW, py + PH),
                  (0, 200, 80) if on_target else (80, 140, 0), 1)

    cx, cy, R = px + PW // 2, py + PH // 2 + 10, 52
    cv2.ellipse(frame, (cx, cy), (R, R), -90, 0, 180, (40, 60, 40), 4)
    arc_col = (0, 255, 80) if on_target else (0, 160, 255)
    arc_end = int(min(angle, 179))
    if arc_end > 0:
        cv2.ellipse(frame, (cx, cy), (R, R), -90, 0, arc_end, arc_col, 5, cv2.LINE_AA)

    tx = cx + int(math.cos(math.radians(-90 + target)) * R)
    ty = cy + int(math.sin(math.radians(-90 + target)) * R)
    cv2.circle(frame, (tx, ty), 6, (0, 255, 200), -1)
    cv2.circle(frame, (tx, ty), 6, (255,255,255), 1)

    cv2.putText(frame, f"{angle:.0f}deg", (cx - 28, cy + 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, arc_col, 2, cv2.LINE_AA)
    cv2.putText(frame, "Elbow Flex", (px + 18, py + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 220, 160), 1)
    cv2.putText(frame, f"Target: {target}deg", (px + 8, py + PH - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 200, 120), 1)

    if hold_prog > 0:
        lbl = f"HOLD! {hold_t * (1 - hold_prog):.1f}s"
        cv2.putText(frame, lbl, (px + 8, py + 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (0, 255, 100) if on_target else (0, 200, 255), 1, cv2.LINE_AA)

    if hold_prog > 0:
        BH = 22
        by = H - BH - 6
        cv2.rectangle(frame, (60, by), (W - 60, by + BH), (20, 40, 20), -1)
        filled = int((W - 120) * hold_prog)
        bar_c  = (0, 255, 100) if hold_prog < 0.8 else (0, 255, 255)
        cv2.rectangle(frame, (60, by), (60 + filled, by + BH), bar_c, -1)
        cv2.rectangle(frame, (60, by), (W - 60, by + BH), (0, 180, 80), 1)
        cv2.putText(frame, "HOLD PROGRESS", (64, by - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 255, 180), 1)

        sby = by - 30
        SBH = 16
        cv2.rectangle(frame, (60, sby), (W - 60, sby + SBH), (20, 30, 40), -1)
        s_filled = int((W - 120) * (stability / 100.0))
        if stability >= 70:
            s_col = (0, 220, 100)
        elif stability >= 40:
            s_col = (0, 200, 255)
        else:
            s_col = (0, 80, 255)
        cv2.rectangle(frame, (60, sby), (60 + s_filled, sby + SBH), s_col, -1)
        cv2.rectangle(frame, (60, sby), (W - 60, sby + SBH), (80, 80, 120), 1)
        cv2.putText(frame, f"STABILITY {stability:.0f}%", (64, sby - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.34, (200, 220, 255), 1)

# ════════════════════════════════════════════════════════════
#  PER-WEEK PROGRESS PANEL
# ════════════════════════════════════════════════════════════
def draw_week_progress(frame, history):
    H, W = frame.shape[:2]
    PW, PH = 220, 190
    px, py = W - PW - 10, 68

    panel = frame.copy()
    cv2.rectangle(panel, (px, py), (px + PW, py + PH), (5, 15, 5), -1)
    cv2.addWeighted(panel, 0.72, frame, 0.28, 0, frame)
    cv2.rectangle(frame, (px, py), (px + PW, py + PH), (0, 140, 60), 1)

    cv2.putText(frame, "Weekly Progress", (px + 18, py + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 200, 120), 1)

    by_week = {}
    for h in history:
        wk = h.get("week", 1)
        by_week.setdefault(wk, []).append(h)

    row_h = 38
    for wk in sorted(by_week.keys()):
        rows  = by_week[wk]
        vals  = [r["fish"] for r in rows]
        stabs = [r.get("stability", 100.0) for r in rows]
        avg   = sum(vals) / len(vals)
        avg_s = sum(stabs) / len(stabs)
        ry    = py + 28 + (wk - 1) * row_h

        wk_target = SCHEDULE.get(wk, (0, []))[0]
        cv2.putText(frame, f"W{wk} ({wk_target}d)", (px + 8, ry + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 220, 180), 1)

        bar_max_w = 90
        bar_w = int(min(avg / 5, 1.0) * bar_max_w)
        bx = px + 80
        cv2.rectangle(frame, (bx, ry + 2), (bx + bar_max_w, ry + 13), (30, 50, 30), -1)
        col = (0, 220, 100) if avg >= 4 else (0, 160, 255)
        if bar_w > 0:
            cv2.rectangle(frame, (bx, ry + 2), (bx + bar_w, ry + 13), col, -1)
        cv2.putText(frame, f"{avg:.1f} fish", (bx + bar_max_w + 4, ry + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (200, 255, 200), 1)

        sb_w = int(min(avg_s / 100.0, 1.0) * bar_max_w)
        cv2.rectangle(frame, (bx, ry + 17), (bx + bar_max_w, ry + 26), (25, 35, 45), -1)
        s_col = (0, 220, 100) if avg_s >= 70 else ((0, 200, 255) if avg_s >= 40 else (0, 80, 255))
        if sb_w > 0:
            cv2.rectangle(frame, (bx, ry + 17), (bx + sb_w, ry + 26), s_col, -1)
        cv2.putText(frame, f"{avg_s:.0f}% stab", (bx + bar_max_w + 4, ry + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, (200, 220, 255), 1)

# ════════════════════════════════════════════════════════════
#  END-OF-SESSION OVERLAY
# ════════════════════════════════════════════════════════════
def draw_session_end(frame, fish_caught, fish_needed, week, day,
                     hold_t, history, adapted, avg_stability):
    H, W = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (W, H), (0, 15, 5), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    CW, CH = 560, 390
    cx, cy = (W - CW) // 2, (H - CH) // 2
    card = frame.copy()
    cv2.rectangle(card, (cx, cy), (cx + CW, cy + CH), (8, 30, 12), -1)
    cv2.addWeighted(card, 0.88, frame, 0.12, 0, frame)
    cv2.rectangle(frame, (cx, cy), (cx + CW, cy + CH), (0, 220, 100), 2)

    def txt(s, x, y, scale=0.7, col=(200,255,200), thick=1):
        cv2.putText(frame, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, col, thick, cv2.LINE_AA)

    txt("SESSION COMPLETE!", cx + 100, cy + 44, 1.0, (0,255,150), 2)
    cv2.line(frame, (cx+20, cy+56), (cx+CW-20, cy+56), (0,180,80), 1)

    txt(f"Week {week}  ·  Day {day}", cx + 180, cy + 88, 0.62, (150,255,200))
    txt(f"Fish caught :  {fish_caught} / {fish_needed}", cx + 40, cy + 128, 0.78,
        (0,255,200) if fish_caught >= fish_needed else (0,180,255), 2)
    txt(f"Hold time   :  {hold_t}s", cx + 40, cy + 165, 0.68, (180,230,180))
    s_col = (0,255,150) if avg_stability >= 70 else ((0,200,255) if avg_stability >= 40 else (0,100,255))
    txt(f"Avg stability:  {avg_stability:.0f}%", cx + 40, cy + 198, 0.68, s_col)

    recent = history[-7:]
    if len(recent) >= 2:
        txt("Last 7 sessions (fish):", cx + 40, cy + 232, 0.48, (120,200,120))
        gw, gh = CW - 80, 55
        gx, gy = cx + 40, cy + 240
        cv2.rectangle(frame, (gx, gy), (gx + gw, gy + gh), (20,40,20), -1)
        vals = [r["fish"] for r in recent]
        top  = max(max(vals), 1)
        for i in range(len(vals) - 1):
            x1 = gx + int(i * gw / (len(vals)-1))
            x2 = gx + int((i+1) * gw / (len(vals)-1))
            y1 = gy + gh - int(vals[i] * gh / top) - 2
            y2 = gy + gh - int(vals[i+1] * gh / top) - 2
            lc = (0,230,100) if vals[i+1] >= vals[i] else (0,80,255)
            cv2.line(frame, (x1,y1), (x2,y2), lc, 2, cv2.LINE_AA)
            cv2.circle(frame, (x1,y1), 4, (0,200,150), -1)
        cv2.circle(frame, (gx + gw, gy + gh - int(vals[-1]*gh/top) - 2), 4, (0,200,150), -1)

    if adapted:
        txt("* Hold time reduced (adaptive)", cx + 40, cy + CH - 50, 0.44, (0,200,255))

    txt("Press Q/Esc to save & exit    R to replay", cx + 55, cy + CH - 22,
        0.48, (120,200,120))

# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
def main():
    progress = load_progress()
    week, day, target_angle, hold_t = get_today_config(progress)
    adapted = progress.get("adaptive_hold") is not None

    FISH_NEEDED   = 5
    TOLERANCE     = 12     # ± degrees
    SESSION_DONE  = False

    print(f"Elbow Fishing  |  Week {week} Day {day}  |  Target {target_angle}°  |  Hold {hold_t}s")

    mp_pose  = mp.solutions.pose
    pose_est = mp_pose.Pose(min_detection_confidence=0.55,
                            min_tracking_confidence=0.55)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("No camera found."); return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Many webcams ignore the requested resolution above, so trust a real
    # captured frame's shape rather than cap.get(), or landmarks get
    # scaled to the wrong canvas and everything draws off-screen.
    ret0, probe_frame = cap.read()
    if not ret0:
        print("Could not read a frame from the camera."); cap.release(); return
    H, W = probe_frame.shape[:2]
    print(f"Camera actual frame size: {W}x{H}")

    # ── detect the real screen size so we can fill it properly ──
    # NOTE: previously the window just opened at raw camera size
    # (often 640x480) with no fullscreen call at all, hence "random
    # small window". We now query the OS screen resolution and put
    # the app into a real fullscreen window, letterboxed (not
    # stretched/distorted) to fit.
    try:
        import tkinter as _tk
        _root = _tk.Tk()
        SCREEN_W, SCREEN_H = _root.winfo_screenwidth(), _root.winfo_screenheight()
        _root.destroy()
    except Exception:
        SCREEN_W, SCREEN_H = 1920, 1080   # sane fallback if tkinter isn't available

    WINDOW_NAME = "Elbow Fishing Rehab"
    cv2.namedWindow(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    def fit_to_screen(img):
        """Scale + letterbox img to fill the screen without distortion."""
        h, w = img.shape[:2]
        scale = min(SCREEN_W / w, SCREEN_H / h)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
        xo, yo = (SCREEN_W - nw) // 2, (SCREEN_H - nh) // 2
        canvas[yo:yo + nh, xo:xo + nw] = resized
        return canvas

    fishes      = [Fish(W, H) for _ in range(5)]
    bubbles     = []
    splashes    = []
    catch_banner = None
    fish_caught = 0
    locked_fish = None
    hold_accum  = 0.0
    hold_prog   = 0.0
    catch_stabilities = []
    smoother    = AngleSmoother(alpha=0.14)   # was 0.2 — heavier smoothing = less jitter
    stability   = StabilityTracker()
    stab_score  = 100.0
    angle_val   = 0.0
    on_target   = False
    prev_t      = time.time()

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        H, W = frame.shape[:2]
        now = time.time()
        dt  = max(0.001, now - prev_t)
        prev_t = now

        draw_water(frame, W, H)

        if random.random() < 0.06:
            bubbles.append(Bubble(W, H))
        for b in bubbles[:]:
            b.update(dt); b.draw(frame)
            if not b.alive: bubbles.remove(b)

        for f in fishes:
            f.update(dt)
            f.draw(frame)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose_est.process(rgb)
        active_side = None

        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark

            lw = lm[mp_pose.PoseLandmark.LEFT_WRIST.value]
            rw = lm[mp_pose.PoseLandmark.RIGHT_WRIST.value]
            side = 'L' if lw.y < rw.y else 'R'
            active_side = side

            raw_angle = elbow_angle(lm, side, W, H)
            angle_val = smoother.update(raw_angle)
            on_target = abs(angle_val - target_angle) <= TOLERANCE

            draw_arm_mesh(frame, lm, side, W, H, on_target)

            el_idx = (mp_pose.PoseLandmark.LEFT_ELBOW.value if side == 'L'
                      else mp_pose.PoseLandmark.RIGHT_ELBOW.value)
            elbow_px = (int(lm[el_idx].x * W), int(lm[el_idx].y * H))

            if on_target and not SESSION_DONE:
                nearest, best_d = None, float('inf')
                for f in fishes:
                    if f.caught: continue
                    d = math.hypot(f.x - elbow_px[0], f.y - elbow_px[1])
                    if d < best_d:
                        best_d = d; nearest = f

                if nearest:
                    if locked_fish is not nearest:
                        locked_fish = nearest
                        hold_accum  = 0.0
                        stability.reset()
                    nearest.locked = True

                    stability.add(angle_val)
                    stab_score = stability.score()
                    factor = stability.speed_factor()
                    hold_accum += dt * factor
                    hold_prog = min(1.0, hold_accum / hold_t)

                    if hold_accum >= hold_t:
                        splashes.append((int(nearest.x), int(nearest.y), now))
                        catch_banner = (f"FISH CAUGHT!  Stability {stab_score:.0f}%", now)
                        catch_stabilities.append(stab_score)
                        nearest.caught = True
                        fish_caught   += 1
                        locked_fish    = None
                        hold_accum     = 0.0
                        hold_prog      = 0.0
                        stability.reset()
                        fishes.append(Fish(W, H))
                        if fish_caught >= FISH_NEEDED:
                            SESSION_DONE = True
                else:
                    hold_prog = 0.0
            else:
                if locked_fish:
                    locked_fish.locked = False
                locked_fish = None
                hold_accum  = 0.0
                hold_prog   = 0.0
                stability.reset()
        else:
            angle_val = smoother.update(angle_val * 0.9)

        for sp in splashes[:]:
            sx, sy, st = sp
            age = now - st
            if age > 0.7: splashes.remove(sp)
            else: draw_splash(frame, sx, sy, age)

        if catch_banner:
            text, st = catch_banner
            age = now - st
            if age > 1.1:
                catch_banner = None
            else:
                draw_catch_banner(frame, text, age, life=1.1)

        avg_stability = (sum(catch_stabilities) / len(catch_stabilities)
                          if catch_stabilities else 100.0)

        if not SESSION_DONE:
            draw_hud(frame, week, day, angle_val, target_angle, hold_t,
                     hold_prog, fish_caught, FISH_NEEDED, on_target, stab_score)
            draw_week_progress(frame, progress.get("history", []))
        else:
            draw_session_end(frame, fish_caught, FISH_NEEDED, week, day,
                             hold_t, progress.get("history", []), adapted,
                             avg_stability)

        if active_side is None and not SESSION_DONE:
            cv2.putText(frame, "Stand back - full arm must be visible",
                        (W//2 - 210, H//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,200,255), 2, cv2.LINE_AA)

        cv2.imshow(WINDOW_NAME, fit_to_screen(frame))
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q') or key == 27:   # 27 = Esc
            if fish_caught > 0 or SESSION_DONE:
                advance_day(progress, fish_caught, avg_stability)
                print(f"Saved. Fish: {fish_caught}, Stability: {avg_stability:.0f}%. "
                      f"Next: W{progress['week']} D{progress['day']}")
            break
        elif key == ord('r'):
            fish_caught = 0
            fishes = [Fish(W, H) for _ in range(5)]
            bubbles.clear(); splashes.clear()
            catch_banner = None
            catch_stabilities = []
            SESSION_DONE = False
            locked_fish  = None
            hold_accum   = 0.0
            hold_prog    = 0.0
            stability.reset()
            smoother     = AngleSmoother(0.14)
        elif key == ord('s'):   # debug: skip day
            advance_day(progress, fish_caught, avg_stability)
            progress = load_progress()
            week, day, target_angle, hold_t = get_today_config(progress)
            adapted = progress.get("adaptive_hold") is not None
            SESSION_DONE = False; fish_caught = 0
            catch_stabilities = []
            print(f"Skipped to W{week} D{day}")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()