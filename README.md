# Fast Guard: Motion-to-Minimize Security Bot

작업 중인 화면을 주변 시선에서 빠르게 보호하기 위한 자동 보안 봇입니다.  
지정한 감시 영역(ROI)에서 움직임이 감지되면 즉시 `Win + M`을 실행해 모든 창을 최소화합니다.

## What It Does
- 실시간 웹캠 프레임 감시
- 사용자 지정 ROI(관심 영역) 내부만 움직임 분석
- 일정 수준 이상 움직임 발생 시 즉시 화면 최소화
- `Q` 종료, `R` 배경 리셋(환경 변화 재학습)

## Runtime Requirements
- Windows (Win 키 이벤트 사용)
- Python 3.9+
- 웹캠

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
python auto_motion_detector.py
```

## ROI(감시 영역) 수정 방법
`auto_motion_detector.py`의 `ROI_POINTS_NORM` 배열을 수정하면 됩니다.

각 점은 `[x, y]` 형식이며, **정규화 좌표**입니다.
- `x`: 왼쪽=0.0, 오른쪽=1.0
- `y`: 위쪽=0.0, 아래쪽=1.0

현재 기본값:
```python
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
```

현재 점 번호 설명:
```text
1-----------------------2
|                       |
|                       |
|         4-------------3
|         |
|         |
6---------5
```

현재 설정된 배열은 위 도식 순서대로 `1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 1`로 연결됩니다.

1. 좌상단 시작점
2. 우상단
3. 우측 중간점
4. 안쪽 꺾임점
5. 안쪽 하단점
6. 좌하단

수정 규칙:
1. 점 순서는 시계방향(또는 반시계방향)으로 유지
2. x/y 값은 0.0~1.0 범위 유지
3. 점이 교차하지 않게 다각형 유지
4. 저장 후 재실행해서 빨간 ROI 라인이 원하는 위치인지 확인

## 감지 민감도 튜닝
`auto_motion_detector.py`에서 아래 상수를 조정합니다.

- `MOTION_THRESHOLD`
  - 낮추면 민감도 증가(작은 움직임도 감지)
  - 높이면 오탐 감소
- `DIFF_THRESHOLD`
  - 낮추면 미세한 밝기 변화에도 반응
  - 높이면 조명 변화 노이즈 감소
- `COOLDOWN_SEC`
  - 감지 후 재실행 대기 시간

## Key Controls
- `Q`: 종료
- `R`: 배경 리셋

## Suggested Repository Description
아래 문구를 GitHub 저장소 설명(Description)으로 사용하세요:

`A privacy-first desktop guard bot that instantly minimizes your workspace when motion is detected in a custom camera zone.`
