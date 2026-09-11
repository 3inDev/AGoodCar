import cv2
import time
import socket
import math
from collections import deque, Counter
import mediapipe as mp

ESP32_IP = "192.168.4.1"
ESP32_PORT = 4210
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_cmd(cmd: str):
    if not cmd: return
    try:
        sock.sendto(cmd.encode("utf-8"), (ESP32_IP, ESP32_PORT))
    except Exception:
        pass

# MediaPipe
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    model_complexity=1,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.75,
)

# Tay
def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)

def is_finger_extended(landmarks, tip_idx, pip_idx):
    wrist = landmarks[0]
    return dist(landmarks[tip_idx], wrist) > dist(landmarks[pip_idx], wrist)

def is_thumb_extended(landmarks):
    return dist(landmarks[4], landmarks[17]) > dist(landmarks[2], landmarks[17])

def thumb_direction(landmarks):
    cmc = landmarks[1]
    tip = landmarks[4]
    dx = tip.x - cmc.x
    dy = tip.y - cmc.y 
    angle = math.degrees(math.atan2(-dy, dx))
    if 45 <= angle < 135: return "UP"
    elif -135 <= angle < -45: return "DOWN"
    elif -45 <= angle < 45: return "RIGHT"
    else: return "LEFT"

def classify_pose(landmarks):
    fingers_ext_count = sum([
        is_finger_extended(landmarks, 8, 6),   # Trỏ
        is_finger_extended(landmarks, 12, 10), # Giữa
        is_finger_extended(landmarks, 16, 14), # Áp út
        is_finger_extended(landmarks, 20, 18)  # Út
    ])
    
    thumb_ext = is_thumb_extended(landmarks)
    if fingers_ext_count == 4 and thumb_ext:
        return "OPEN"
    if fingers_ext_count <= 1:
        if thumb_ext:
            return f"THUMB_{thumb_direction(landmarks)}"
        else:
            return "FIST"
    return "UNKNOWN"

def draw_text(frame, text, y, scale=0.75, thickness=2, color=(0, 255, 0)):
    cv2.putText(frame, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

def majority_vote(cmds):
    if not cmds: return None
    cmd, count = Counter(cmds).most_common(1)[0]
    return cmd if count >= 4 else None

INIT = "INIT"
COUNTDOWN = "COUNTDOWN"
DRIVE = "DRIVE"
state = INIT
init_hold_start = None
countdown_start = None
countdown_seconds = 3
recent_cmds = deque(maxlen=7)
last_sent_cmd = "S"
last_send_time = 0.0
SEND_INTERVAL = 0.08  
send_cmd("S")

cap = cv2.VideoCapture(0)

try:
    while True:
        ok, frame = cap.read()
        if not ok: break
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)
        hand_infos = []
        if results.multi_hand_landmarks and results.multi_handedness:
            for idx, hand_lm in enumerate(results.multi_hand_landmarks):
                mp_label = results.multi_handedness[idx].classification[0].label
                real_hand = "Right" if mp_label == "Left" else "Left"
                landmarks = hand_lm.landmark
                pose = classify_pose(landmarks)
                hand_infos.append({"real_hand": real_hand,"pose": pose,"landmarks": landmarks})
                mp_draw.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)
                cx = int(landmarks[0].x * w)
                cy = int(landmarks[0].y * h)
                cv2.putText(frame, f"{real_hand}: {pose}", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        now = time.monotonic()

        primary = next((h for h in hand_infos if h["real_hand"] == "Right"), None)
        if state == INIT:
            draw_text(frame, "MODE: INIT", 35, 0.9, 2)
            draw_text(frame, "GIO 1 BAN TAY PHAI (NAM DAM)", 70, 0.7, 2)
            init_ok = (len(hand_infos) == 1 and primary is not None and primary["pose"] == "FIST")

            if init_ok:
                if init_hold_start is None: init_hold_start = now
                remain = 1.0 - (now - init_hold_start)
                draw_text(frame, f"HOLD... {max(0.0, remain):.1f}s", 110, 0.9, 2)
                if remain <= 0:
                    state = COUNTDOWN
                    countdown_start = now
                    init_hold_start = None
            else:
                init_hold_start = None
        elif state == COUNTDOWN:
            draw_text(frame, "READY", 35, 1.0, 3)
            init_ok = (len(hand_infos) == 1 and primary is not None and primary["pose"] == "FIST")
            elapsed = now - countdown_start
            left = countdown_seconds - int(elapsed)
            if not init_ok:
                state = INIT
                countdown_start = None
            elif left > 0:
                draw_text(frame, str(left), 130, 2.2, 6)
            else:
                state = DRIVE
                recent_cmds.clear()
                send_cmd("S")

        elif state == DRIVE:
            draw_text(frame, "MODE: DRIVE", 35, 0.9, 2)
            candidate = "S"
            if len(hand_infos) != 1 or primary is None:
                candidate = "S"
            else:
                pose = primary["pose"]
                if pose == "OPEN": candidate = "S"
                elif pose == "THUMB_UP": candidate = "F"
                elif pose == "THUMB_DOWN": candidate = "B"
                elif pose == "THUMB_LEFT": candidate = "L"
                elif pose == "THUMB_RIGHT": candidate = "R"
            recent_cmds.append(candidate)
            stable_cmd = majority_vote(recent_cmds) or candidate
            if now - last_send_time >= SEND_INTERVAL:
                send_cmd(stable_cmd)
                last_sent_cmd = stable_cmd
                last_send_time = now
            draw_text(frame, f"CMD SENDING: {last_sent_cmd}", 80, 0.95, 3, (0, 0, 255))
        cv2.imshow("Dieu Khien", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"): break
        elif key == ord("r"):
            state = INIT
            init_hold_start = None
            countdown_start = None
            send_cmd("S")
finally:
    send_cmd("S")
    cap.release()
    cv2.destroyAllWindows()
    hands.close()
