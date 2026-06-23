"""
Debug script — prints raw angle values live so we can see what's happening
"""
import cv2
import mediapipe as mp
import numpy as np

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv2.VideoCapture(0)

def angle3(a, b, c):
    a, b, c = np.array(a, float), np.array(b, float), np.array(c, float)
    ba, bc = a - b, c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos, -1, 1))))

while cap.isOpened():
    ok, frame = cap.read()
    if not ok: break
    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = pose.process(rgb)

    if res.pose_landmarks:
        lms = res.pose_landmarks.landmark

        def xy(idx):
            lm = lms[idx.value]
            return [lm.x, lm.y], lm.visibility

        # LEFT side
        ls, ls_v = xy(mp_pose.PoseLandmark.LEFT_SHOULDER)
        le, le_v = xy(mp_pose.PoseLandmark.LEFT_ELBOW)
        lh, lh_v = xy(mp_pose.PoseLandmark.LEFT_HIP)
        lw, lw_v = xy(mp_pose.PoseLandmark.LEFT_WRIST)

        raw_l = angle3(le, ls, lh)     # elbow-shoulder-hip
        raw_l2= angle3(lw, ls, lh)     # wrist-shoulder-hip (alternative)

        # RIGHT side
        rs, rs_v = xy(mp_pose.PoseLandmark.RIGHT_SHOULDER)
        re, re_v = xy(mp_pose.PoseLandmark.RIGHT_ELBOW)
        rh, rh_v = xy(mp_pose.PoseLandmark.RIGHT_HIP)

        raw_r = angle3(re, rs, rh)

        # Draw landmarks
        mp.solutions.drawing_utils.draw_landmarks(
            frame, res.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        # Print values on screen
        y0 = 30
        for label, val in [
            (f"L elbow-sh-hip angle: {raw_l:.1f}  ->  flexion = {180-raw_l:.1f}", (0,220,180)),
            (f"L wrist-sh-hip angle: {raw_l2:.1f} ->  flexion = {180-raw_l2:.1f}", (0,180,220)),
            (f"R elbow-sh-hip angle: {raw_r:.1f}  ->  flexion = {180-raw_r:.1f}", (30,160,255)),
            (f"L sh vis:{ls_v:.2f}  el vis:{le_v:.2f}  hip vis:{lh_v:.2f}", (200,200,100)),
            (f"L shoulder XY: {ls[0]:.3f},{ls[1]:.3f}", (150,150,150)),
            (f"L elbow   XY: {le[0]:.3f},{le[1]:.3f}", (150,150,150)),
            (f"L hip     XY: {lh[0]:.3f},{lh[1]:.3f}", (150,150,150)),
        ]:
            cv2.putText(frame, label, (10, y0),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, val, 1, cv2.LINE_AA)
            y0 += 26

        # Also draw big number
        flex = int(180 - raw_l)
        cv2.putText(frame, f"L ROM: {flex}", (w-220, h//2),
                    cv2.FONT_HERSHEY_DUPLEX, 2.0, (0,220,180), 3)

    else:
        cv2.putText(frame, "No pose detected", (50,50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2)

    cv2.imshow("DEBUG — angle values", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
