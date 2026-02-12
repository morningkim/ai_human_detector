import ctypes
import time

import cv2
import numpy as np


CAMERA_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
WARMUP_FRAMES = 5
BLUR_KERNEL = (11, 11)
DIFF_THRESHOLD = 35
MOTION_PIXELS_THRESHOLD = 2200
COOLDOWN_SEC = 2.0
STARTUP_GRACE_SEC = 3.0
BACKGROUND_INIT_FRAMES = 20
BACKGROUND_ALPHA = 0.02
MOTION_CONFIRM_FRAMES = 3

# ROI normalized coordinates (x, y), 0.0 ~ 1.0
# Vertex numbering for editing:
# 1: [0.25, 0.08]  top-left
# 2: [0.85, 0.08]  top-right
# 3: [0.85, 0.44]  mid-right
# 4: [0.38, 0.44]  inner bend
# 5: [0.38, 0.70]  bottom-inner
# 6: [0.25, 0.70]  bottom-left
ROI_POINTS_NORM = np.array(
    [
        [0.25, 0.08],  # 1
        [0.85, 0.08],  # 2
        [0.85, 0.44],  # 3
        [0.38, 0.44],  # 4
        [0.38, 0.70],  # 5
        [0.25, 0.70],  # 6
    ],
    dtype=np.float32,
)


user32 = ctypes.windll.user32


def instant_minimize() -> None:
    # Win + M minimizes all windows without Win+D toggle behavior.
    user32.keybd_event(0x5B, 0, 0, 0)  # Left Windows key down
    user32.keybd_event(0x4D, 0, 0, 0)  # M key down
    user32.keybd_event(0x4D, 0, 2, 0)  # M key up
    user32.keybd_event(0x5B, 0, 2, 0)  # Left Windows key up


cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

if not cap.isOpened():
    raise RuntimeError("카메라를 열 수 없습니다. CAMERA_INDEX를 확인하세요.")

for _ in range(WARMUP_FRAMES):
    cap.read()

background_float = None
init_count = 0
motion_streak = 0
last_action_time = 0.0
startup_time = time.time()

print("초고속 보안 감시 모드 가동 중... (Q: 종료, R: 배경 리셋)")
print("[INFO] 카메라/노출 안정화 중...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] 카메라 프레임 읽기 실패. 루프 종료")
        break

    h, w = frame.shape[:2]
    roi_pts = (ROI_POINTS_NORM * [w, h]).astype(np.int32)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)

    if background_float is None:
        background_float = gray.astype(np.float32)
        init_count = 1
        cv2.polylines(frame, [roi_pts], True, (0, 0, 255), 3)
        cv2.putText(frame, "Stabilizing background...", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.imshow("Fast Guard", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        continue

    if init_count < BACKGROUND_INIT_FRAMES:
        # Average multiple startup frames to avoid immediate false trigger.
        alpha = 1.0 / (init_count + 1)
        cv2.accumulateWeighted(gray, background_float, alpha)
        init_count += 1
        cv2.polylines(frame, [roi_pts], True, (0, 0, 255), 3)
        cv2.putText(frame, f"Stabilizing... {init_count}/{BACKGROUND_INIT_FRAMES}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.imshow("Fast Guard", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        continue

    static_back = cv2.convertScaleAbs(background_float)
    diff_frame = cv2.absdiff(static_back, gray)
    thresh_frame = cv2.threshold(diff_frame, DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)[1]

    mask = np.zeros_like(thresh_frame)
    cv2.fillPoly(mask, [roi_pts], 255)
    roi_motion = cv2.bitwise_and(thresh_frame, thresh_frame, mask=mask)

    motion_pixels = int(cv2.countNonZero(roi_motion))
    now = time.time()
    in_grace_period = (now - startup_time) < STARTUP_GRACE_SEC

    if in_grace_period:
        motion_streak = 0
    elif motion_pixels > MOTION_PIXELS_THRESHOLD:
        motion_streak += 1
    else:
        motion_streak = 0

    if motion_streak >= MOTION_CONFIRM_FRAMES and (now - last_action_time) > COOLDOWN_SEC:
        instant_minimize()
        print(f"!!! 즉각 대응 실행: {time.strftime('%H:%M:%S')} | pixels={motion_pixels} !!!")
        last_action_time = now
        motion_streak = 0
        background_float = gray.astype(np.float32)
        init_count = 1

    # Keep adapting background slowly for lighting drift.
    cv2.accumulateWeighted(gray, background_float, BACKGROUND_ALPHA)

    cv2.polylines(frame, [roi_pts], True, (0, 0, 255), 3)
    cv2.putText(frame, f"motion_pixels={motion_pixels}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow("Fast Guard", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    if key == ord("r"):
        background_float = None
        init_count = 0
        motion_streak = 0
        startup_time = time.time()
        print("[INFO] 배경이 리셋되었습니다.")

cap.release()
cv2.destroyAllWindows()
