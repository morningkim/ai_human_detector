# Fast Guard: Motion-to-Minimize Security Bot

Fast Guard is a privacy-focused desktop bot.  
When motion is detected inside your custom ROI (region of interest), it instantly sends `Win + M` to minimize all windows.

## Features
- Real-time webcam monitoring
- Motion analysis only inside your custom ROI
- Instant desktop minimization on motion threshold
- `Q` to quit, `R` to reset background model

## Requirements
- Windows (uses Windows key events)
- Python 3.9+
- Webcam

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
python auto_motion_detector.py
```

## How To Edit ROI
Edit `ROI_POINTS_NORM` in `auto_motion_detector.py`.

Each point is `[x, y]` in normalized coordinates:
- `x`: left=0.0, right=1.0
- `y`: top=0.0, bottom=1.0

Current default:
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

Current vertex map:
```text
1-----------------------2
|                       |
|                       |
|         4-------------3
|         |
|         |
6---------5
```

The array is connected in this order: `1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 1`.

1. Top-left start point
2. Top-right point
3. Mid-right point
4. Inner corner point
5. Lower inner point
6. Bottom-left point

Editing rules:
1. Keep vertex order clockwise or counterclockwise
2. Keep x/y within 0.0~1.0
3. Do not let polygon edges cross
4. Re-run and verify the red ROI line location

## Sensitivity Tuning
Tune these constants in `auto_motion_detector.py`:

- `MOTION_PIXELS_THRESHOLD`
  - Lower value: more sensitive
  - Higher value: fewer false alarms
- `DIFF_THRESHOLD`
  - Lower value: reacts to smaller brightness changes
  - Higher value: less noise from lighting shifts
- `COOLDOWN_SEC`
  - Wait time between trigger actions

## Key Controls
- `Q`: Quit
- `R`: Reset background model

## Suggested Repository Description
`A privacy-first desktop guard bot that instantly minimizes your workspace when motion is detected in a custom camera zone.`
