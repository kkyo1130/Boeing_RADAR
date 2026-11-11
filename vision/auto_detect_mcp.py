"""Heuristic automatic MCP readout localization for webcam frames.

Find horizontally ordered bright digit groups (HDG, ALT).
This is a candidate detector, NOT a trained object detector. Inspect its boxes
on real camera footage before treating readings as reliable.
"""
import cv2
import numpy as np


def detect_readouts(frame):
    """Return {'hdg': (x,y,w,h), 'alt': (...)} or {} if ambiguous."""
    height, width = frame.shape[:2]
    if height < 80 or width < 120:
        return {}
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # White readouts in the photographed browser/tablet may be almost achromatic.
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    bright = cv2.inRange(hsv, (0, 0, 140), (179, 125, 255))
    bright = cv2.bitwise_and(bright, cv2.inRange(gray, 150, 255))
    # Merge characters into a display candidate without merging nearby readouts.
    # Fixed small kernel avoids merging neighboring MCP windows in HD webcam frames.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 3))
    merged = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (width*.025 <= w <= width*.23 and height*.012 <= h <= height*.11):
            continue
        if not (1.2 <= w / max(h, 1) <= 8.5):
            continue
        patch = bright[y:y+h, x:x+w]
        density = cv2.countNonZero(patch) / (w*h)
        if density < .08 or density > .85:
            continue
        candidates.append((x, y, w, h))
    # Prefer the HDG/ALT pair: unlike IAS, the left readout can be partially
    # occluded or split by glare. ALT has five digits and is wider than HDG.
    matches = []
    for hdg in candidates:
        for alt in candidates:
            if alt[0] <= hdg[0] + hdg[2]:
                continue
            if not (1.12 <= alt[2] / max(1, hdg[2]) <= 2.7):
                continue
            if not (.55 <= alt[3] / max(1, hdg[3]) <= 1.6):
                continue
            cy1, cy2 = hdg[1]+hdg[3]/2, alt[1]+alt[3]/2
            if abs(cy1-cy2) > max(hdg[3], alt[3])*.45:
                continue
            gap = alt[0]-(hdg[0]+hdg[2])
            if gap > width*.12:
                continue
            # MCP digits are large and bright. Reject tiny instrument legends.
            if min(hdg[3], alt[3]) < height*.025:
                continue
            if not (height*.16 < cy1 < height*.82):
                continue
            # Prefer a large, aligned pair over tiny text elsewhere.
            score = (hdg[3]+alt[3]) / height - abs(cy1-cy2)/height - gap/(width*3)
            matches.append((score, hdg, alt))
    if not matches:
        return {}
    matches.sort(key=lambda item: item[0], reverse=True)
    _, hdg, alt = matches[0]
    def padded(r):
        x,y,w,h = r
        px, py = max(2,int(w*.08)), max(2,int(h*.25))
        x1,y1 = max(0,x-px), max(0,y-py)
        x2,y2 = min(width,x+w+px), min(height,y+h+py)
        return (x1,y1,x2-x1,y2-y1)
    return {"hdg": padded(hdg), "alt": padded(alt)}
