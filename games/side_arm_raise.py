"""
RehabVerse v3 — Rotator Cuff Recovery Tracker
═══════════════════════════════════════════════
Layout (1280×720):
  ┌──────────┬─────────────────────────┬──────────┐
  │ LEFT     │   CAMERA FEED (960px)   │  RIGHT   │
  │ PANEL    │   full, no overlap      │  PANEL   │
  │ (160px)  │                         │ (160px)  │
  └──────────┴─────────────────────────┴──────────┘
  ┌──────────────────────────────────────────────────┐
  │   BOTTOM BAR — milestone illustration + week HUD  │
  └──────────────────────────────────────────────────┘

Fixes:
  • ROM = shoulder_flexion computed from elbow→shoulder→hip angle,
    mapped to 0-180° flexion (arm down = 0, arm up = 180)
  • visibility gate per landmark
  • Zero UI/camera overlap — panels are in dedicated strips
  • Milestone "unlock" shows a stick-figure illustration of the activity
  • 6-week program with hold tracking and day-over-day adaptation
"""

import cv2
import mediapipe as mp
import numpy as np
from collections import deque
import json, os, time, math
from datetime import date

# ══════════════════════════════════════════════════════
#  MediaPipe
# ══════════════════════════════════════════════════════
mp_pose    = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

pose = mp_pose.Pose(
    model_complexity=1,
    min_detection_confidence=0.55,
    min_tracking_confidence=0.55,
    smooth_landmarks=True,
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
cap.set(cv2.CAP_PROP_FPS, 30)

# ══════════════════════════════════════════════════════
#  Layout constants
# ══════════════════════════════════════════════════════
WIN_W, WIN_H   = 1280, 720
CAM_W, CAM_H   = 960, 540
SIDE_W         = (WIN_W - CAM_W) // 2   # 160 px each side
CAM_X          = SIDE_W                  # 160
CAM_Y          = 0
BOT_H          = WIN_H - CAM_H          # 180 px bottom bar
BOT_Y          = CAM_H

# ══════════════════════════════════════════════════════
#  6-Week programme  (rom_target°, hold_target_sec)
# ══════════════════════════════════════════════════════
WEEK_PROG = [
    (40,  3),
    (60,  5),
    (80,  7),
    (100, 10),
    (120, 12),
    (150, 15),
]

# ══════════════════════════════════════════════════════
#  Milestones  (lo°, hi°, name, activity_line, color_BGR)
# ══════════════════════════════════════════════════════
MS = [
    (0,   30,  "REST",     "Resting — gentle motion",       (140,140,140)),
    (30,  60,  "STARTER",  "Shake hands / Lift a cup",      (255,200, 80)),
    (60,  90,  "DAILY",    "Wear a shirt / Open doors",     ( 80,210,120)),
    (90,  120, "ACTIVE",   "Comb hair / Eye-level shelf",   (100,200,255)),
    (120, 150, "CAPABLE",  "Overhead cabinet / Hang clothes",(255,130, 50)),
    (150, 181, "SUMMIT",   "Full overhead / Swimming",      ( 80, 80,255)),
]

def get_ms(rom):
    for lo,hi,name,act,col in MS:
        if rom < hi:
            return lo,hi,name,act,tuple(int(c) for c in col)
    m=MS[-1]; return m[0],m[1],m[2],m[3],tuple(int(c) for c in m[4])

# ══════════════════════════════════════════════════════
#  Persistence
# ══════════════════════════════════════════════════════
DATA = "rehabverse_data.json"

def load():
    if os.path.exists(DATA):
        with open(DATA) as f: return json.load(f)
    return {"week":1,"hold_target":3,"trend":"STEADY","days":[]}

def save(d):
    with open(DATA,"w") as f: json.dump(d,f,indent=2)

prog = load()

def week_cfg():
    return WEEK_PROG[min(prog["week"]-1, len(WEEK_PROG)-1)]

def end_session(arm, max_rom, best_hold):
    today = str(date.today())
    days  = prog["days"]
    entry = next((d for d in days if d["date"]==today and d["arm"]==arm), None)
    if entry is None:
        entry = {"date":today,"arm":arm,"rom":0,"hold":0.0}
        days.append(entry)
    entry["rom"]  = max(entry["rom"],  max_rom)
    entry["hold"] = max(entry["hold"], best_hold)

    arm_hist = sorted([d for d in days if d["arm"]==arm and d["date"]!=today],
                      key=lambda x:x["date"])
    wrom,_   = week_cfg()
    ht       = prog["hold_target"]

    if arm_hist:
        prev_rom = arm_hist[-1]["rom"]
        if max_rom < prev_rom:
            prog["hold_target"] = max(2, int(ht*0.80))
            prog["trend"] = "DROP"
        elif max_rom > prev_rom and max_rom > wrom:
            nxt = WEEK_PROG[min(prog["week"], len(WEEK_PROG)-1)][1]
            prog["hold_target"] = min(ht+2, nxt+5)
            prog["trend"] = "UP"
        else:
            prog["trend"] = "STEADY"

    # auto-advance week
    recent = [d for d in days if d["arm"]==arm][-3:]
    if len(recent)==3 and all(d["rom"]>=wrom for d in recent) and prog["week"]<6:
        prog["week"] += 1
        prog["hold_target"] = WEEK_PROG[prog["week"]-1][1]

    save(prog)

# ══════════════════════════════════════════════════════
#  Maths
# ══════════════════════════════════════════════════════
def angle3(a,b,c):
    a,b,c = np.array(a,float),np.array(b,float),np.array(c,float)
    ba,bc = a-b, c-b
    cos   = np.dot(ba,bc)/(np.linalg.norm(ba)*np.linalg.norm(bc)+1e-8)
    return float(np.degrees(np.arccos(np.clip(cos,-1,1))))

def shoulder_flexion(elbow_xy, shoulder_xy, hip_xy):
    """
    Shoulder flexion 0-180° using the arm vector relative to the
    torso's 'down' direction.

    Strategy:
      - torso_down = hip - shoulder  (points downward along the body)
      - arm_vec    = elbow - shoulder
      - flexion    = angle between arm_vec and torso_down
        → arm hanging alongside body  → ~0°
        → arm raised forward/up       → up to 180°

    This is robust because it's body-relative, not screen-relative.
    Works whether the person is standing, leaning, or at any camera angle.
    """
    sh  = np.array(shoulder_xy, float)
    el  = np.array(elbow_xy,    float)
    hip = np.array(hip_xy,      float)

    # "down" direction along the torso
    torso_down = hip - sh

    # arm vector from shoulder to elbow
    arm_vec = el - sh

    # angle between them
    norm_t = np.linalg.norm(torso_down)
    norm_a = np.linalg.norm(arm_vec)
    if norm_t < 1e-6 or norm_a < 1e-6:
        return 0

    cos_val = np.dot(arm_vec, torso_down) / (norm_t * norm_a)
    raw     = float(np.degrees(np.arccos(np.clip(cos_val, -1, 1))))

    # raw=0   → arm pointing straight down (along torso_down) → 0° flexion
    # raw=90  → arm pointing forward horizontally → 90° flexion
    # raw=180 → arm pointing straight up → 180° flexion
    return int(np.clip(raw, 0, 180))

class Smoother:
    def __init__(self, n=3):
        self.buf = deque(maxlen=n)
    def __call__(self, v):
        self.buf.append(v)
        return int(np.median(self.buf))

class RepCounter:
    def __init__(self, up=70, dn=20):
        self.up,self.dn = up,dn
        self.stage="DOWN"; self.count=0
    def update(self,rom):
        if rom<self.dn:  self.stage="DOWN"
        if rom>self.up and self.stage=="DOWN":
            self.stage="UP"; self.count+=1
        return self.count,self.stage

class HoldTracker:
    MIN_ROM = 50   # must be above this to count a hold
    def __init__(self):
        self.active=False; self.t0=None
        self.cur=0.0; self.best=0.0
    def update(self,rom):
        now=time.time()
        if rom>=self.MIN_ROM:
            if not self.active: self.active=True; self.t0=now
            self.cur = now-self.t0
            self.best= max(self.best,self.cur)
        else:
            self.active=False; self.t0=None; self.cur=0.0
        return self.cur,self.best

class ArmTracker:
    def __init__(self,label):
        self.label   = label
        self.smooth  = Smoother(6)
        self.reps    = RepCounter()
        self.hold    = HoldTracker()
        self.rom     = 0
        self.max_rom = 0
    def update(self,elbow,shoulder,hip,ok):
        if not ok: return
        raw       = shoulder_flexion(elbow,shoulder,hip)
        self.rom  = self.smooth(raw)
        self.max_rom = max(self.max_rom,self.rom)
        self.reps.update(self.rom)
        self.hold.update(self.rom)

left_arm  = ArmTracker("L")
right_arm = ArmTracker("R")

VIS_THR = 0.55
def lm_xy(lms, idx):
    lm = lms[idx.value]
    return [lm.x,lm.y], lm.visibility>=VIS_THR

# ══════════════════════════════════════════════════════
#  Palette
# ══════════════════════════════════════════════════════
BG     = (14, 16, 22)
PANEL  = (22, 26, 34)
WHITE  = (240,240,240)
CYAN   = (0, 220,200)
ORANGE = (30,160,255)
GREEN  = (60,210,100)
GOLD   = (40,190,255)
DIM    = (100,100,110)
RED    = (60, 80,240)

# ══════════════════════════════════════════════════════
#  Draw utilities
# ══════════════════════════════════════════════════════
def filled_rect(img,x1,y1,x2,y2,col,alpha=0.88):
    ov = img.copy()
    cv2.rectangle(ov,(x1,y1),(x2,y2),col,-1)
    cv2.addWeighted(ov,alpha,img,1-alpha,0,img)

def hbar(img,x,y,w,h,val,mx,col):
    pct = np.clip(val/mx,0,1)
    cv2.rectangle(img,(x,y),(x+w,y+h),(40,43,52),-1)
    fw = int(w*pct)
    if fw>2:
        for i in range(fw):
            t=i/max(fw-1,1)
            c=tuple(int(col[j]*(0.3+0.7*t)) for j in range(3))
            cv2.line(img,(x+i,y+1),(x+i,y+h-1),c,1)
    cv2.rectangle(img,(x,y),(x+w,y+h),(70,72,80),1)

def arc(img,cx,cy,r,pct,col,thick=4):
    cv2.circle(img,(cx,cy),r,(40,43,52),thick)
    if pct>0.01:
        ea = int(-90+360*min(pct,1.0))
        cv2.ellipse(img,(cx,cy),(r,r),0,-90,ea,col,thick)

def txt(img,s,x,y,scale,col,bold=1):
    cv2.putText(img,s,(x,y),cv2.FONT_HERSHEY_SIMPLEX,scale,col,bold,cv2.LINE_AA)

def txt2(img,s,x,y,scale,col,bold=2):
    cv2.putText(img,s,(x,y),cv2.FONT_HERSHEY_DUPLEX,scale,col,bold,cv2.LINE_AA)

# ══════════════════════════════════════════════════════
#  Stick-figure activity illustrations
#  Each draws into a sub-image region (w×h)
# ══════════════════════════════════════════════════════
def draw_stick(img, x, y, w, h, activity_idx, col, t):
    """
    Draw an animated stick figure doing the milestone activity.
    activity_idx: 0=rest,1=handshake,2=shirt,3=comb,4=overhead,5=swim
    t: time float for animation
    """
    # Head
    hx = x + w//2
    hy = y + int(h*0.18)
    hr = max(int(h*0.09),8)
    cv2.circle(img,(hx,hy),hr,col,2,cv2.LINE_AA)

    # Body
    bx1,by1 = hx, hy+hr
    bx2,by2 = hx, hy+hr+int(h*0.28)
    cv2.line(img,(bx1,by1),(bx2,by2),col,2,cv2.LINE_AA)

    # Legs
    swing = math.sin(t*2)*12 if activity_idx==5 else 0
    cv2.line(img,(bx2,by2),(bx2-10+int(swing),by2+int(h*0.26)),col,2,cv2.LINE_AA)
    cv2.line(img,(bx2,by2),(bx2+10-int(swing),by2+int(h*0.26)),col,2,cv2.LINE_AA)

    # Arms — vary by activity
    arm_y = by1 + int(h*0.10)

    if activity_idx == 0:  # REST — arms down
        cv2.line(img,(bx2-5,arm_y),(bx2-18,arm_y+int(h*0.22)),col,2,cv2.LINE_AA)
        cv2.line(img,(bx2+5,arm_y),(bx2+18,arm_y+int(h*0.22)),col,2,cv2.LINE_AA)

    elif activity_idx == 1:  # HANDSHAKE — one arm extends forward
        wave = int(math.sin(t*3)*5)
        # Left arm out
        cv2.line(img,(bx1,arm_y),(bx1-28,arm_y+wave),col,2,cv2.LINE_AA)
        # Second stick figure (other person), offset right
        ox = bx1+38
        cv2.circle(img,(ox,hy),hr,col,2,cv2.LINE_AA)
        cv2.line(img,(ox,hy+hr),(ox,by2),col,2,cv2.LINE_AA)
        cv2.line(img,(ox,arm_y),(ox+28,arm_y-wave),col,2,cv2.LINE_AA)  # their arm
        cv2.line(img,(ox,by2),(ox-8,by2+int(h*0.26)),col,2,cv2.LINE_AA)
        cv2.line(img,(ox,by2),(ox+8,by2+int(h*0.26)),col,2,cv2.LINE_AA)
        # Clasped hands in center
        cv2.circle(img,(bx1+14,arm_y+wave//2),4,col,-1,cv2.LINE_AA)

    elif activity_idx == 2:  # SHIRT — both arms at ~60° putting on shirt
        ang = math.sin(t*2)*8
        cv2.line(img,(bx1,arm_y),(bx1-22,arm_y+int(h*0.12)+int(ang)),col,2,cv2.LINE_AA)
        cv2.line(img,(bx1,arm_y),(bx1+22,arm_y+int(h*0.12)-int(ang)),col,2,cv2.LINE_AA)
        # Draw shirt shape (trapezoid)
        pts = np.array([[bx1-20,arm_y+8],[bx1+20,arm_y+8],
                         [bx1+24,by2-4],[bx1-24,by2-4]],np.int32)
        cv2.polylines(img,[pts],True,col,1,cv2.LINE_AA)

    elif activity_idx == 3:  # COMB HAIR — one arm raised to head
        bob = int(math.sin(t*4)*4)
        cv2.line(img,(bx1,arm_y),(bx1-8,hy-hr+bob),col,2,cv2.LINE_AA)   # arm up to head
        cv2.line(img,(bx1,arm_y),(bx1+20,arm_y+int(h*0.18)),col,2,cv2.LINE_AA)
        # comb
        for ci in range(4):
            cx2 = bx1-14+ci*4
            cv2.line(img,(cx2,hy-hr-4+bob),(cx2,hy-hr-10+bob),col,1,cv2.LINE_AA)
        cv2.line(img,(bx1-16,hy-hr-4+bob),(bx1-2,hy-hr-4+bob),col,1,cv2.LINE_AA)

    elif activity_idx == 4:  # OVERHEAD REACH — one arm full up
        reach = int(math.sin(t*2)*5)
        cv2.line(img,(bx1,arm_y),(bx1-6,hy-hr-20-reach),col,2,cv2.LINE_AA)   # arm straight up
        cv2.line(img,(bx1,arm_y),(bx1+22,arm_y+int(h*0.15)),col,2,cv2.LINE_AA)
        # shelf
        shelf_y = hy-hr-28-reach
        cv2.line(img,(bx1-20,shelf_y),(bx1+20,shelf_y),col,2,cv2.LINE_AA)
        # box on shelf
        cv2.rectangle(img,(bx1-4,shelf_y-10),(bx1+10,shelf_y),col,1,cv2.LINE_AA)

    elif activity_idx == 5:  # SWIM — both arms cycling
        ang = math.sin(t*3)
        lx = int(-20*math.cos(t*3))
        ly = int(10*math.sin(t*3))
        rx = int(-20*math.cos(t*3+math.pi))
        ry = int(10*math.sin(t*3+math.pi))
        cv2.line(img,(bx1,arm_y),(bx1+lx,arm_y+ly),col,2,cv2.LINE_AA)
        cv2.line(img,(bx1,arm_y),(bx1+rx,arm_y+ry),col,2,cv2.LINE_AA)
        # water line
        for wi in range(0,w-20,10):
            wy = int(by2+int(h*0.15)+math.sin((wi+t*60)*0.4)*3)
            cv2.line(img,(x+10+wi,wy),(x+10+wi+6,wy),col,1,cv2.LINE_AA)

# ══════════════════════════════════════════════════════
#  Side panel (LEFT or RIGHT) — pure stats, no camera overlap
# ══════════════════════════════════════════════════════
def draw_side_panel(canvas, tracker, is_left):
    x = 0 if is_left else WIN_W - SIDE_W
    y = 0
    W = SIDE_W
    H = CAM_H   # 540

    filled_rect(canvas, x,y,x+W,y+H, PANEL, alpha=1.0)
    cv2.line(canvas,(x,0),(x,H),(50,54,66),1)

    col  = CYAN if is_left else ORANGE
    wrom,whold = week_cfg()
    ht   = prog["hold_target"]
    _,__,ms_name,_,ms_col = get_ms(tracker.rom)

    P = 8  # padding

    # ARM label
    txt2(canvas, f"{'L' if is_left else 'R'} ARM",
         x+P, 28, 0.7, col, 2)
    cv2.line(canvas,(x+P,34),(x+W-P,34),(50,54,66),1)

    # ROM
    txt(canvas,"ROM", x+P, 54, 0.40, DIM)
    rom_col = ms_col if tracker.rom >= wrom else WHITE
    txt2(canvas, f"{tracker.rom}°", x+P, 98, 1.55, rom_col, 3)

    # progress bar
    hbar(canvas, x+P, 108, W-P*2, 10, tracker.rom, 180, ms_col)
    # week target tick
    tw = W-P*2
    tx = x+P + int(tw * wrom/180)
    cv2.line(canvas,(tx,106),(tx,120),(255,220,60),2)
    txt(canvas,f"tgt {wrom}°",tx-14,132,0.28,GOLD)

    # REPS
    cv2.line(canvas,(x+P,140),(x+W-P,140),(50,54,66),1)
    txt(canvas,"REPS",x+P,156,0.40,DIM)
    stage_c = GREEN if tracker.reps.stage=="UP" else DIM
    txt2(canvas,f"{tracker.reps.count}",x+P,196,1.55,WHITE,3)
    txt(canvas,tracker.reps.stage, x+P,212,0.40,stage_c)

    # HOLD arc
    cv2.line(canvas,(x+P,222),(x+W-P,222),(50,54,66),1)
    txt(canvas,"HOLD",x+P,238,0.40,DIM)
    hold_pct = tracker.hold.cur / max(ht,1)
    hold_done= tracker.hold.cur >= ht
    hold_col = GREEN if hold_done else ms_col
    arc(canvas, x+W//2, 275, 28, hold_pct, hold_col, 5)
    cv2.putText(canvas,f"{tracker.hold.cur:.1f}s",
                (x+W//2-14,279),cv2.FONT_HERSHEY_SIMPLEX,0.40,hold_col,1,cv2.LINE_AA)
    txt(canvas,f"goal:{ht}s",x+P,310,0.35,DIM)
    txt(canvas,f"best:{tracker.hold.best:.1f}s",x+P,326,0.35,DIM)

    # BEST ROM
    cv2.line(canvas,(x+P,334),(x+W-P,334),(50,54,66),1)
    txt(canvas,f"Session best",x+P,350,0.36,DIM)
    txt2(canvas,f"{tracker.max_rom}°",x+P,376,1.1,WHITE,2)

    # TREND
    cv2.line(canvas,(x+P,386),(x+W-P,386),(50,54,66),1)
    tr     = prog.get("trend","STEADY")
    tr_col = GREEN if tr=="UP" else RED if tr=="DROP" else DIM
    tr_sym = "▲ IMPROVING" if tr=="UP" else "▼ DROPPED" if tr=="DROP" else "● STEADY"
    txt(canvas,tr_sym, x+P, 404, 0.38, tr_col)

    # Milestone name
    cv2.line(canvas,(x+P,412),(x+W-P,412),(50,54,66),1)
    txt2(canvas,ms_name, x+P, 432, 0.55, ms_col, 2)

    # Milestone dots
    dot_y = 452
    for lo,hi,name,act,col_ in MS[1:]:
        unlocked = tracker.max_rom >= lo
        cur_ms   = tracker.rom>=lo and tracker.rom<hi
        dc = tuple(int(c) for c in col_) if unlocked else (50,50,58)
        r  = 5 if cur_ms else 3
        cv2.circle(canvas,(x+P+5,dot_y),r,dc,-1,cv2.LINE_AA)
        if cur_ms:
            cv2.circle(canvas,(x+P+5,dot_y),r+2,dc,1,cv2.LINE_AA)
        txt(canvas,name,(x+P+14),dot_y+4,0.33,dc)
        dot_y += 17

# ══════════════════════════════════════════════════════
#  Bottom bar — activity illustration + week tracker
# ══════════════════════════════════════════════════════
def draw_bottom(canvas, left_tracker, right_tracker, t):
    y = BOT_Y
    filled_rect(canvas, 0,y,WIN_W,WIN_H, (16,18,26), alpha=1.0)
    cv2.line(canvas,(0,y),(WIN_W,y),(50,54,66),1)

    # Current milestone activity (use whichever arm has higher ROM)
    best_tracker = left_tracker if left_tracker.rom >= right_tracker.rom else right_tracker
    lo,hi,ms_name,ms_act,ms_col = get_ms(best_tracker.rom)

    # Unlock glow label
    txt2(canvas,f"UNLOCKED: {ms_name}",
         12, y+26, 0.65, ms_col, 2)
    txt(canvas,ms_act, 12, y+46, 0.42, (180,180,190))

    # Stick figure illustrations for this milestone
    ms_idx = next(i for i,(lo_,hi_,*_) in enumerate(MS) if lo_==lo)

    # Draw 3 side-by-side activity figures
    fig_w = 120
    fig_h = BOT_H - 20
    activities_for_ms = {
        0: [0],
        1: [1],
        2: [2],
        3: [3],
        4: [3,4],
        5: [4,5],
    }
    act_ids = activities_for_ms.get(ms_idx, [ms_idx])

    fig_x_start = WIN_W//2 - (len(act_ids)*fig_w)//2
    for fi,aid in enumerate(act_ids):
        fx = fig_x_start + fi*(fig_w+20)
        fy = y + 10
        draw_stick(canvas, fx, fy, fig_w, fig_h, aid, ms_col, t)

    # Week strip on right side of bottom bar
    wx = WIN_W - 360
    txt2(canvas,"6-WEEK", wx, y+22, 0.50, GOLD, 2)
    for i,(rt,ht_) in enumerate(WEEK_PROG):
        wk    = i+1
        is_cur= wk == prog["week"]
        done  = wk < prog["week"]
        col   = GOLD if is_cur else GREEN if done else DIM
        sym   = "▶" if is_cur else "✔" if done else "○"
        label = f"{sym} W{wk}:{rt}° {ht_}s"
        bw    = 2 if is_cur else 1
        bx    = wx + (i%3)*120
        by    = y + 40 + (i//3)*30
        txt(canvas, label, bx, by, 0.36, col, bw)

    # Today's session snapshot
    txt(canvas,f"Today L:{left_tracker.max_rom}° R:{right_tracker.max_rom}°",
        wx, y+112, 0.38, DIM)
    last3 = prog["days"][-3:]
    log_y = y+130
    for d in last3:
        arm_c = CYAN if d["arm"]=="L" else ORANGE
        txt(canvas,f"{d['date'][-5:]} [{d['arm']}] {d['rom']}° hold:{d['hold']:.0f}s",
            wx, log_y, 0.33, arm_c)
        log_y += 14

# ══════════════════════════════════════════════════════
#  Top header bar (over camera region only)
# ══════════════════════════════════════════════════════
def draw_header(canvas, w_rom):
    # Semi-transparent bar over camera top edge
    overlay = canvas.copy()
    cv2.rectangle(overlay,(CAM_X,0),(CAM_X+CAM_W,38),(14,16,22),-1)
    cv2.addWeighted(overlay,0.75,canvas,0.25,0,canvas)

    txt2(canvas,"REHABVERSE", CAM_X+10,28,0.85,CYAN,2)
    txt(canvas,"Rotator Cuff Recovery Tracker",
        CAM_X+160,22,0.48,(170,170,180))
    txt(canvas,f"Week {prog['week']}  |  Hold target: {prog['hold_target']}s",
        CAM_X+160,36,0.40,GOLD)
    txt(canvas,"R=reset  ESC=save & quit",
        CAM_X+CAM_W-200,28,0.35,DIM)

# ══════════════════════════════════════════════════════
#  Main loop
# ══════════════════════════════════════════════════════
t_start = time.time()

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break

    frame   = cv2.flip(frame, 1)
    frame   = cv2.resize(frame, (CAM_W, CAM_H))
    frame   = cv2.convertScaleAbs(frame, alpha=0.80, beta=5)

    rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb)

    if results.pose_landmarks:
        lms = results.pose_landmarks.landmark

        ls,ls_v = lm_xy(lms, mp_pose.PoseLandmark.LEFT_SHOULDER)
        le,le_v = lm_xy(lms, mp_pose.PoseLandmark.LEFT_ELBOW)
        lh,lh_v = lm_xy(lms, mp_pose.PoseLandmark.LEFT_HIP)
        left_arm.update(le, ls, lh, ls_v and le_v and lh_v)

        rs,rs_v = lm_xy(lms, mp_pose.PoseLandmark.RIGHT_SHOULDER)
        re,re_v = lm_xy(lms, mp_pose.PoseLandmark.RIGHT_ELBOW)
        rh,rh_v = lm_xy(lms, mp_pose.PoseLandmark.RIGHT_HIP)
        right_arm.update(re, rs, rh, rs_v and re_v and rh_v)

        mp_drawing.draw_landmarks(
            frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing.DrawingSpec(
                color=(0,230,200), thickness=2, circle_radius=4),
            connection_drawing_spec=mp_drawing.DrawingSpec(
                color=(80,80,200), thickness=2),
        )

        # Coloured arm lines over skeleton
        for (sh,el,col_,vis) in [
            (ls,le,(0,220,200), ls_v and le_v),
            (rs,re,(30,160,255), rs_v and re_v),
        ]:
            if vis:
                px = (int(sh[0]*CAM_W), int(sh[1]*CAM_H))
                ex = (int(el[0]*CAM_W), int(el[1]*CAM_H))
                cv2.line(frame, px, ex, col_, 3, cv2.LINE_AA)
                cv2.circle(frame, px, 10, col_, -1, cv2.LINE_AA)
                cv2.circle(frame, ex,  6, WHITE, -1, cv2.LINE_AA)
    else:
        cv2.putText(frame,"No pose — step back or improve lighting",
                    (CAM_W//2-260, CAM_H//2),
                    cv2.FONT_HERSHEY_SIMPLEX,0.75,(80,80,255),2,cv2.LINE_AA)

    # ── Compose final canvas ──────────────────────────────────────────
    canvas = np.full((WIN_H, WIN_W, 3), BG, dtype=np.uint8)

    # Camera into center slot
    canvas[0:CAM_H, CAM_X:CAM_X+CAM_W] = frame

    # Side panels (pure background, no overlap with camera)
    draw_side_panel(canvas, left_arm,  is_left=True)
    draw_side_panel(canvas, right_arm, is_left=False)

    # Bottom bar
    t_anim = time.time() - t_start
    draw_bottom(canvas, left_arm, right_arm, t_anim)

    # Header (light overlay on camera top)
    draw_header(canvas, week_cfg()[0])

    cv2.imshow("RehabVerse — Rotator Cuff Tracker", canvas)

    key = cv2.waitKey(1) & 0xFF
    if key == 27:                                    # ESC — save & quit
        end_session("L", left_arm.max_rom,  left_arm.hold.best)
        end_session("R", right_arm.max_rom, right_arm.hold.best)
        print(f"\n✓ Session saved | Week {prog['week']} | "
              f"Hold target: {prog['hold_target']}s | Trend: {prog['trend']}")
        break

    if key == ord('r'):                              # reset session
        for arm in (left_arm, right_arm):
            arm.rom=0; arm.max_rom=0
            arm.smooth  = Smoother(3)
            arm.reps    = RepCounter()
            arm.hold    = HoldTracker()

cap.release()
cv2.destroyAllWindows()