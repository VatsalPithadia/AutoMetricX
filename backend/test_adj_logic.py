import os, sys, math, re
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image

def test_s2_with_validator():
    s2_path = os.path.join(backend_dir, "uploads", "42227ec47bd04596a3458c9871c509c7.jpeg")
    with open(s2_path, "rb") as f:
        s2_blocks = extract_text_from_image(f.read()).get("blocks", [])

    b17 = [b for b in s2_blocks if b.get('id') == 17][0]
    print(f"Anchor: B17 '{b17['text']}' rect={b17['rect']}")

    def price_validator(cand, t):
        # Must contain digits
        if not re.search(r'\d', t):
            return False
        # Must not be pure date
        if re.search(r'\b\d{2}[/-]\d{2}[/-]\d{2,4}\b', t):
            return False
        # Must not be statutory label like "Incl of all taxes"
        cl = re.sub(r'[^A-Z]', '', t.upper())
        if any(lbl in cl for lbl in ['INCL', 'TAXES', 'MRP', 'BATCH', 'MFG', 'EXP', 'USEBY']):
            return False
        return True

    best = None
    min_dist = float('inf')
    a_rect = b17['rect']
    a_x, a_y, a_w, a_h = a_rect['x'], a_rect['y'], a_rect['width'], a_rect['height']

    for c in s2_blocks:
        if c.get('id') == 17:
            continue
        cr = c.get('rect', {})
        if not cr:
            continue
        cx, cy, cw, ch = cr['x'], cr['y'], cr['width'], cr['height']
        txt = c.get('text', '').strip()

        if not price_validator(c, txt):
            continue

        is_right = (cx >= a_x + a_w * 0.3) and (cx - (a_x + a_w) <= 350.0) and (abs(cy - a_y) <= 45.0)
        is_below = (cy >= a_y + a_h * 0.4) and (cy - (a_y + a_h) <= 100.0) and (abs(cx - a_x) <= 200.0)

        if is_right:
            dx = max(0.0, cx - (a_x + a_w))
            dy = abs(cy - a_y)
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < min_dist:
                min_dist = dist
                best = c
        elif is_below:
            dx = abs(cx - a_x)
            dy = max(0.0, cy - (a_y + a_h))
            dist = math.sqrt(dx*dx + dy*dy) + 60.0
            if dist < min_dist:
                min_dist = dist
                best = c

    print(f"With validator, best adjacent for B17: B{best.get('id') if best else None} '{best.get('text') if best else None}' dist={min_dist}")

test_s2_with_validator()
