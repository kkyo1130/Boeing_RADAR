"""Heuristic automatic MCP readout localization for webcam frames.

Find three horizontally ordered bright digit groups (IAS, HDG, ALT).
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
    scale = max(1., width / 960.)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(5, int(13*scale)), max(2, int(3*scale))))
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
    # Three displays are roughly level, adjacent, and appear in IAS/HDG/ALT order.
    matches = []
    for a in candidates:
        for b in candidates:
            if b[0] <= a[0] + a[2]:
                continue
            for c in candidates:
                if c[0] <= b[0] + b[2]:
                    continue
                heights = [a[3], b[3], c[3]]
                if max(heights) / max(1, min(heights)) > 2.0:
                    continue
                centers = [z[1] + z[3]/2 for z in (a,b,c)]
                if max(centers) - min(centers) > max(heights)*1.1:
                    continue
                gaps = [b[0]-(a[0]+a[2]), c[0]-(b[0]+b[2])]
                if min(gaps) < 0 or max(gaps) > width*.14:
                    continue
                # Altitude is five digits, typically wider than the heading.
                if c[2] < b[2]*1.05:
                    continue
                # Prefer aligned, compact triples of similar text height.
                score = (max(centers)-min(centers))/max(heights) + sum(gaps)/width
                matches.append((score, (a,b,c)))
    if not matches:
        return {}
    matches.sort(key=lambda v: v[0])
    if len(matches) > 1 and abs(matches[1][0]-matches[0][0]) < .015:
        # Multiple near-equal triples: don't pretend localization is certain.
        return {}
    _, (_, hdg, alt) = matches[0]
    def padded(r):
        x,y,w,h = r
        px, py = max(2,int(w*.08)), max(2,int(h*.25))
        x1,y1 = max(0,x-px), max(0,y-py)
        x2,y2 = min(width,x+w+px), min(height,y+h+py)
        return (x1,y1,x2-x1,y2-y1)
    return {"hdg": padded(hdg), "alt": padded(alt)}
