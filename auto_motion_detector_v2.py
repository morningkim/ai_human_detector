import ctypes
import json
import os
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

ROI_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roi_config.json")


# ── ROI 설정 ─────────────────────────────────────────────
def setup_roi(cap, fw, fh):
    """마우스 드래그로 감시 사각형을 여러 개 그린 뒤 Enter로 확정."""
    rects_px = []

    drawing, start, cur = False, None, None

    def mouse(event, x, y, flags, param):
        nonlocal drawing, start, cur
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing, start, cur = True, (x, y), None
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            cur = [min(start[0],x), min(start[1],y), max(start[0],x), max(start[1],y)]
        elif event == cv2.EVENT_LBUTTONUP and drawing:
            r = [min(start[0],x), min(start[1],y), max(start[0],x), max(start[1],y)]
            if (r[2]-r[0]) > 10 and (r[3]-r[1]) > 10:
                rects_px.append(r)
            drawing, cur = False, None
        elif event == cv2.EVENT_RBUTTONDOWN and rects_px:
            rects_px.pop()

    cv2.namedWindow("ROI Setup", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("ROI Setup", mouse)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        overlay = frame.copy()
        for i, (x1,y1,x2,y2) in enumerate(rects_px):
            c = [(0,255,0),(255,165,0),(0,200,255),(255,0,128),(0,255,255)][i % 5]
            cv2.rectangle(overlay, (x1,y1), (x2,y2), c, -1)
            cv2.rectangle(frame, (x1,y1), (x2,y2), c, 2)
        if cur:
            cv2.rectangle(overlay, (cur[0],cur[1]), (cur[2],cur[3]), (0,255,0), -1)
        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
        cv2.putText(frame, f"Regions: {len(rects_px)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        cv2.putText(frame, "Drag:add | Right-click:undo | C:clear | Enter/Space:start | Q:quit",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.imshow("ROI Setup", frame)
        key = cv2.waitKey(30) & 0xFF
        if key in (13, 32) and rects_px:
            break
        elif key == ord("c"):
            rects_px.clear()
        elif key == ord("q"):
            cv2.destroyWindow("ROI Setup")
            return None

    cv2.destroyWindow("ROI Setup")
    rects_norm = [[x1/fw, y1/fh, x2/fw, y2/fh] for x1,y1,x2,y2 in rects_px]
    with open(ROI_SAVE_FILE, "w") as f:
        json.dump(rects_norm, f)
    polys = []
    for x1,y1,x2,y2 in rects_norm:
        polys.append(np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]], dtype=np.float32))
    return polys


# ── 메인 ──────────────────────────────────────────────────
user32 = ctypes.windll.user32


def instant_minimize() -> None:
    user32.keybd_event(0x5B, 0, 0, 0)
    user32.keybd_event(0x4D, 0, 0, 0)
    user32.keybd_event(0x4D, 0, 2, 0)
    user32.keybd_event(0x5B, 0, 2, 0)


def reset_background_state():
    """감지 기준 배경 상태 초기화."""
    return None, 0, 0, time.time()


def draw_help(frame, status_text, motion_pixels=None):
    lines = [
        status_text,
        "Keys: Q quit | P pause/resume | O reset ROI | R reset background",
    ]
    if motion_pixels is not None:
        lines.append(f"motion_pixels={motion_pixels}")

    y = 30
    for line in lines:
        cv2.putText(frame, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 255), 2)
        y += 28


cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

if not cap.isOpened():
    raise RuntimeError("카메라를 열 수 없습니다. CAMERA_INDEX를 확인하세요.")

for _ in range(WARMUP_FRAMES):
    cap.read()

ROI_POLYGONS = setup_roi(cap, FRAME_WIDTH, FRAME_HEIGHT)
if ROI_POLYGONS is None:
    cap.release()
    cv2.destroyAllWindows()
    raise SystemExit(0)

background_float = None
init_count = 0
motion_streak = 0
last_action_time = 0.0
startup_time = time.time()
paused = False

print("초고속 보안 감시 모드 가동 중...")
print("[단축키] Q: 종료 | R: 배경 리셋 | P: 일시정지/재개 | O: 영역 재설정")
print("[INFO] 카메라/노출 안정화 중...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] 카메라 프레임 읽기 실패. 루프 종료")
        break

    h, w = frame.shape[:2]
    roi_pts_list = [(p * [w, h]).astype(np.int32) for p in ROI_POLYGONS]

    if paused:
        for pts in roi_pts_list:
            cv2.polylines(frame, [pts], True, (0, 0, 255), 3)
        draw_help(frame, "PAUSED")
        cv2.imshow("Fast Guard", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("p"):
            paused = False
            startup_time = time.time()
            print("[INFO] 감시 재개")
        if key == ord("r"):
            background_float, init_count, motion_streak, startup_time = reset_background_state()
            print("[INFO] 배경이 리셋되었습니다.")
        if key == ord("o"):
            new_polygons = setup_roi(cap, FRAME_WIDTH, FRAME_HEIGHT)
            if new_polygons is not None:
                ROI_POLYGONS = new_polygons
                background_float, init_count, motion_streak, startup_time = reset_background_state()
                print("[INFO] 영역 재설정 완료")
            else:
                print("[INFO] 영역 재설정 취소 (기존 영역 유지)")
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)

    if background_float is None:
        background_float = gray.astype(np.float32)
        init_count = 1
        for pts in roi_pts_list:
            cv2.polylines(frame, [pts], True, (0, 0, 255), 3)
        draw_help(frame, "Stabilizing background...")
        cv2.imshow("Fast Guard", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("p"):
            paused = True
            print("[INFO] 감시 일시정지")
        if key == ord("o"):
            new_polygons = setup_roi(cap, FRAME_WIDTH, FRAME_HEIGHT)
            if new_polygons is not None:
                ROI_POLYGONS = new_polygons
                background_float, init_count, motion_streak, startup_time = reset_background_state()
                print("[INFO] 영역 재설정 완료")
            else:
                print("[INFO] 영역 재설정 취소 (기존 영역 유지)")
        continue

    if init_count < BACKGROUND_INIT_FRAMES:
        alpha = 1.0 / (init_count + 1)
        cv2.accumulateWeighted(gray, background_float, alpha)
        init_count += 1
        for pts in roi_pts_list:
            cv2.polylines(frame, [pts], True, (0, 0, 255), 3)
        draw_help(frame, f"Stabilizing... {init_count}/{BACKGROUND_INIT_FRAMES}")
        cv2.imshow("Fast Guard", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("p"):
            paused = True
            print("[INFO] 감시 일시정지")
        if key == ord("o"):
            new_polygons = setup_roi(cap, FRAME_WIDTH, FRAME_HEIGHT)
            if new_polygons is not None:
                ROI_POLYGONS = new_polygons
                background_float, init_count, motion_streak, startup_time = reset_background_state()
                print("[INFO] 영역 재설정 완료")
            else:
                print("[INFO] 영역 재설정 취소 (기존 영역 유지)")
        continue

    static_back = cv2.convertScaleAbs(background_float)
    diff_frame = cv2.absdiff(static_back, gray)
    thresh_frame = cv2.threshold(diff_frame, DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)[1]

    mask = np.zeros_like(thresh_frame)
    for pts in roi_pts_list:
        cv2.fillPoly(mask, [pts], 255)
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

    cv2.accumulateWeighted(gray, background_float, BACKGROUND_ALPHA)

    for pts in roi_pts_list:
        cv2.polylines(frame, [pts], True, (0, 0, 255), 3)
    draw_help(frame, "RUNNING", motion_pixels)
    cv2.imshow("Fast Guard", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    if key == ord("r"):
        background_float, init_count, motion_streak, startup_time = reset_background_state()
        print("[INFO] 배경이 리셋되었습니다.")
    if key == ord("p"):
        paused = True
        print("[INFO] 감시 일시정지")
    if key == ord("o"):
        new_polygons = setup_roi(cap, FRAME_WIDTH, FRAME_HEIGHT)
        if new_polygons is not None:
            ROI_POLYGONS = new_polygons
            background_float, init_count, motion_streak, startup_time = reset_background_state()
            print("[INFO] 영역 재설정 완료")
        else:
            print("[INFO] 영역 재설정 취소 (기존 영역 유지)")

cap.release()
cv2.destroyAllWindows()
