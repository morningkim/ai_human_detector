import cv2
import numpy as np
import ctypes
import time

# 윈도우 키 입력을 위한 시스템 상수 및 함수
user32 = ctypes.windll.user32
def instant_minimize():
    # Win + M 신호를 시스템 레벨에서 즉시 발생 (토글 현상 없음, 매우 빠름)
    user32.keybd_event(0x5B, 0, 0, 0) # Left Windows key down
    user32.keybd_event(0x4D, 0, 0, 0) # M key down
    user32.keybd_event(0x4D, 0, 2, 0) # M key up
    user32.keybd_event(0x5B, 0, 2, 0) # Left Windows key up

# 박사님의 파티션 밀착 ROI 좌표
ROI_POINTS_NORM = np.array([
    [0.25, 0.08], [0.85, 0.08], [0.85, 0.44], 
    [0.38, 0.44], [0.38, 0.7], [0.25, 0.7]
], dtype=np.float32)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# 카메라 안정화 (버퍼 비우기)
for _ in range(5): cap.read()

static_back = None
last_action_time = 0

print("초고속 보안 감시 모드 가동 중... (Q: 종료)")

while True:
    ret, frame = cap.read()
    if not ret: break

    h, w = frame.shape[:2]
    roi_pts = (ROI_POINTS_NORM * [w, h]).astype(np.int32)
    
    # 전처리 속도 최적화 (가우시안 블러 크기 축소 21->11)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (11, 11), 0)

    if static_back is None:
        static_back = gray
        continue

    # 배경 차분 및 이진화 (속도 위주 설정)
    diff_frame = cv2.absdiff(static_back, gray)
    thresh_frame = cv2.threshold(diff_frame, 35, 255, cv2.THRESH_BINARY)[1]

    # ROI 영역 추출
    mask = np.zeros_like(thresh_frame)
    cv2.fillPoly(mask, [roi_pts], 255)
    roi_motion = cv2.bitwise_and(thresh_frame, thresh_frame, mask=mask)

    # 움직임 감지 (컨투어 연산을 생략하고 픽셀 합계로 속도 극대화)
    motion_score = np.sum(roi_motion)
    
    now = time.time()
    # 일정량 이상의 픽셀 변화가 생기면 즉시 실행 (기준값 500,000은 환경에 따라 조절)
    if motion_score > 500000 and (now - last_action_time) > 2:
        instant_minimize() # 가장 빠른 최소화 명령
        print(f"!!! 즉각 대응 실행: {time.strftime('%H:%M:%S')} !!!")
        last_action_time = now
        static_back = gray # 현재 프레임을 새 배경으로

    # 모니터링 출력
    cv2.polylines(frame, [roi_pts], True, (0, 0, 255), 3)
    cv2.imshow("Fast Guard", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'): break
    if key == ord('r'): static_back = None

cap.release()
cv2.destroyAllWindows()