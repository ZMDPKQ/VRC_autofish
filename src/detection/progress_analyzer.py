# detection/progress_analyzer.py
import cv2
import numpy as np
import config

def analyze_progress(roi_img, progress_box):
    x1, y1, x2, y2 = map(int, progress_box)
    h, w = roi_img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    progress_roi = roi_img[y1:y2, x1:x2]
    hsv = cv2.cvtColor(progress_roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, config.PROGRESS_GREEN_LOWER, config.PROGRESS_GREEN_UPPER)
    green = cv2.countNonZero(mask)
    total = mask.size
    return green / total if total > 0 else 0.0