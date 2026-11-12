"""Experimental amber MCP window localization; no expected values or fixed ROIs."""
import cv2
import numpy as np
from .preprocess_mcp_ocr import amber_mask


def locate_windows(image):
    # A label-anchored OCR path handles pale, narrow camera glyphs. Numeric
    # targets and previous values never participate in localization.
    from .text_windows import locate_text_windows
    return locate_text_windows(image) or _locate_color_windows(image)


def _locate_color_windows(image):
    strict = _locate_mask(amber_mask(image).astype(np.uint8), .12)
    if strict is not None:
        return strict
    # Camera white balance and blooming can desaturate amber strokes. Use a
    # second color mask with stronger column occupancy, not guessed OCR values.
    rgb = np.asarray(image.convert('RGB'), dtype=np.int16)
    r, g, b = rgb[:,:,0], rgb[:,:,1], rgb[:,:,2]
    camera_mask = ((r > 110) & (g > 65) & (r > g*1.03) & (g > b*1.15) & (r-b > 40))
    proposals = [_locate_mask(camera_mask.astype(np.uint8), fraction)
                 for fraction in (.06, .07, .08, .10, .12, .18, .22, .26, .30, .34)]
    proposals = [proposal for proposal in proposals if proposal is not None]
    if not proposals:
        return None
    first = proposals[0]
    # Compression changes stroke occupancy. Accept only geometrically agreeing
    # proposals; competing window locations remain ambiguous.
    for proposal in proposals[1:]:
        for kind in ('hdg', 'alt'):
            a, b = first[kind], proposal[kind]
            overlap = max(0,min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))
            union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
            if not union or overlap/union < .65:
                return None
    return first


def _locate_mask(mask, column_fraction):
    height, width = mask.shape
    # Build candidate text lines at several character scales; components can be
    # disconnected strokes, so grouping does not require a connected digit.
    candidates = {}
    for size in (8, 12, 18, 26, 38, 56, 80):
        if size > height / 3:
            continue
        grouped = cv2.dilate(mask, np.ones((max(1, size//6), max(3, size//2)), np.uint8))
        count, _, stats, _ = cv2.connectedComponentsWithStats(grouped)
        for x, y, w, h, area in stats[1:]:
            ys, xs = np.nonzero(mask[y:y+h, x:x+w])
            if len(xs) < 20:
                continue
            x1, y1 = int(x+xs.min()), int(y+ys.min())
            x2, y2 = int(x+xs.max()+1), int(y+ys.max()+1)
            dw, dh = x2-x1, y2-y1
            if dh < 8 or dh > height*.22 or not .8 < dw/dh < 9:
                continue
            crop = mask[y1:y2, x1:x2]
            active = crop.sum(axis=0) >= max(2, dh*column_fraction)
            edges = np.diff(np.r_[False, active, False].astype(int))
            starts, ends = np.flatnonzero(edges==1), np.flatnonzero(edges==-1)
            runs = [(a,b) for a,b in zip(starts,ends) if b-a >= 2]
            digits = len(runs)
            if digits not in (3,5):
                continue
            # Exclude dots, labels and runs with severely mismatched heights.
            if any(np.count_nonzero(crop[:,a:b].sum(axis=1)) < dh*.55 for a,b in runs):
                continue
            if any(not .08 < (b-a)/dh < 1.8 for a,b in runs):
                continue
            candidates[(x1,y1,x2,y2)] = digits
    pairs = []
    for alt, digits in candidates.items():
        if digits != 5:
            continue
        ax,ay,ar,ab = alt
        ah = ab-ay
        nearby = []
        for hdg, n in candidates.items():
            if n != 3:
                continue
            hx,hy,hr,hb = hdg
            hh = hb-hy
            gap = ax-hr
            if (0 < gap < max(ah,hh)*14 and .6 < hh/ah < 1.65
                    and abs((hy+hb-ay-ab)/2) < max(ah,hh)*.7):
                # Do not jump over another illuminated readout (IAS is left of
                # HDG). An unreadable middle window must not relabel IAS as HDG.
                middle = mask[max(hy, ay):min(hb, ab), hr:ax]
                occupied = np.count_nonzero(middle.sum(axis=0) >= 2)
                if occupied > max(ah, hh) * .45:
                    continue
                nearby.append(hdg)
        if nearby:
            # IAS is further left than HDG on the supported MCP layout.
            hdg = max(nearby, key=lambda box: box[2])
            pairs.append((hdg,alt))
    if len(pairs) != 1:
        return None
    def padded(box):
        x,y,r,b=box;h=b-y;px=max(3,round(h*.18));py=max(3,round(h*.25))
        return [max(0,x-px),max(0,y-py),min(width,r+px),min(height,b+py)]
    return dict(zip(('hdg','alt'), map(padded,pairs[0])))
