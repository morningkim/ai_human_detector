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
MOTION_THRESHOLD = 500000
COOLDOWN_SEC = 2.0

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

static_back = None
last_action_time = 0.0

print("초고속 보안 감시 모드 가동 중... (Q: 종료, R: 배경 리셋)")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] 카메라 프레임 읽기 실패. 루프 종료")
        break

    h, w = frame.shape[:2]
    roi_pts = (ROI_POINTS_NORM * [w, h]).astype(np.int32)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)

    if static_back is None:
        static_back = gray
        cv2.polylines(frame, [roi_pts], True, (0, 0, 255), 3)
        cv2.imshow("Fast Guard", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        continue

    diff_frame = cv2.absdiff(static_back, gray)
    thresh_frame = cv2.threshold(diff_frame, DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)[1]

    mask = np.zeros_like(thresh_frame)
    cv2.fillPoly(mask, [roi_pts], 255)
    roi_motion = cv2.bitwise_and(thresh_frame, thresh_frame, mask=mask)

    motion_score = int(np.sum(roi_motion))
    now = time.time()
    if motion_score > MOTION_THRESHOLD and (now - last_action_time) > COOLDOWN_SEC:
        instant_minimize()
        print(f"!!! 즉각 대응 실행: {time.strftime('%H:%M:%S')} | score={motion_score} !!!")
        last_action_time = now
        static_back = gray

    cv2.polylines(frame, [roi_pts], True, (0, 0, 255), 3)
    cv2.imshow("Fast Guard", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    if key == ord("r"):
        static_back = None
        print("[INFO] 배경이 리셋되었습니다.")

cap.release()
cv2.destroyAllWindows()
