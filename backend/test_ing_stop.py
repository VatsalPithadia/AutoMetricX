import os, sys, re
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image

p = os.path.join(backend_dir, "uploads", "ff132bef634f4860b952a42a2e2257a5.jpeg")
with open(p, "rb") as f:
    ocr = extract_text_from_image(f.read())
blocks = ocr.get("blocks", [])

h_block = None
for b in blocks:
    t = b.get("text", "").upper()
    if re.search(r'\b(?:INGREDIENTS?|COMPOSITION|CONTAINS)\b', t):
        h_block = b
        break

hr = h_block.get("rect", {})
hx, hy, hw, hh = hr["x"], hr["y"], hr["width"], hr["height"]
col_min_x = hx - 40.0
col_max_x = hx + max(hw, 260.0) + 120.0
col_min_y = hy - 5.0

stop_keywords = [
    'NUTRITION', 'NUTRITIONAL', 'PER 100', 'SERVING', 'MFG', 'MARKETED BY',
    'MANUFACTURED', 'FSSAI', 'CUSTOMER CARE', 'CONSUMER CARE', 'STORAGE', 'KEEP REFRIGERATED'
]

# Find lowest y of any stop keyword block IN THE SAME COLUMN below header
stop_y = float('inf')
stop_block = None
for b in blocks:
    br = b.get("rect", {})
    if not br:
        continue
    bx = br.get("x", 0.0)
    by = br.get("y", 0.0)
    bw = br.get("width", 0.0)
    # Must overlap this column
    if (col_min_x <= bx <= col_max_x or col_min_x <= (bx + bw) <= col_max_x):
        if by > col_min_y:
            bt = b.get("text", "").upper()
            if any(sk in bt for sk in stop_keywords):
                if by < stop_y:
                    stop_y = by
                    stop_block = b

print(f"Header: '{h_block['text']}' at y={hy}")
print(f"Stop block: '{stop_block['text'] if stop_block else None}' at y={stop_y}")

column_candidates = []
for b in blocks:
    if b.get("id") == h_block.get("id"):
        continue
    br = b.get("rect", {})
    if not br:
        continue
    bx = br.get("x", 0.0)
    by = br.get("y", 0.0)
    bw = br.get("width", 0.0)
    if by <= col_min_y or by >= stop_y:
        continue
    if not (col_min_x <= bx <= col_max_x or col_min_x <= (bx + bw) <= col_max_x):
        continue
    column_candidates.append(b)

column_candidates.sort(key=lambda b: b.get("rect", {}).get("y", 0.0))

deduped = []
for cand in column_candidates:
    cy = cand.get("rect", {}).get("y", 0.0)
    cw = cand.get("rect", {}).get("width", 0.0)
    merged = False
    for idx, ex in enumerate(deduped):
        ey = ex.get("rect", {}).get("y", 0.0)
        ew = ex.get("rect", {}).get("width", 0.0)
        if abs(cy - ey) <= 15.0:
            if cw > ew:
                deduped[idx] = cand
            merged = True
            break
    if not merged:
        deduped.append(cand)

print(f"\nCaptured {len(deduped)} ingredient blocks:")
for d in deduped:
    print(f"  B{d.get('id')}: '{d.get('text')}' (y={d.get('rect', {}).get('y')})")

full_t = " ".join(d.get("text", "").strip() for d in deduped)
print(f"\nResult text:\n{full_t}")
