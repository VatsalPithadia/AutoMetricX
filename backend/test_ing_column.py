import os, sys, re
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image

def test_ing_extraction():
    k_path = os.path.join(backend_dir, "uploads", "ff132bef634f4860b952a42a2e2257a5.jpeg")
    with open(k_path, "rb") as f:
        k_blocks = extract_text_from_image(f.read()).get("blocks", [])

    # Find header block
    h_block = None
    for b in k_blocks:
        t = b.get("text", "").upper()
        if re.search(r'\b(?:INGREDIENTS?|COMPOSITION|CONTAINS)\b', t):
            h_block = b
            break
    print(f"Header block: B{h_block.get('id')} '{h_block.get('text')}' rect={h_block.get('rect')}")

    hr = h_block.get("rect", {})
    hx, hy, hw, hh = hr["x"], hr["y"], hr["width"], hr["height"]

    # Candidate column: blocks that lie in the same vertical column band below the header
    # and before any next statutory section (e.g. Nutritional Information)
    col_blocks = []
    # Stop keywords:
    STOP_KW = ['NUTRITION', 'NUTRITIONAL', 'PER 100', 'SERVING', 'MFG', 'MARKETED BY', 'MANUFACTURED', 'FSSAI', 'CUSTOMER CARE', 'STORAGE']

    for b in k_blocks:
        if b.get('id') == h_block.get('id'):
            continue
        br = b.get('rect', {})
        if not br:
            continue
        bx, by, bw, bh = br['x'], br['y'], br['width'], br['height']
        bt = b.get('text', '').strip()

        # Must be below header
        if by < hy - 10:
            continue

        # Column alignment: check overlap with column band
        # The ingredient box extends horizontally from hx-30 to hx + 350
        if not (hx - 40 <= bx <= hx + 350):
            continue

        # Check if this block is a stop section
        if any(sk in bt.upper() for sk in STOP_KW):
            continue

        col_blocks.append(b)

    # Sort top-to-bottom by y
    col_blocks.sort(key=lambda b: b.get('rect', {}).get('y', 0))

    # Sequential grouping: connect lines while vertical gap <= 70px
    current_y = hy + hh
    collected = []
    for b in col_blocks:
        by = b.get('rect', {}).get('y', 0)
        bh = b.get('rect', {}).get('height', 0)
        gap = by - current_y
        if gap > 70:
            # gap too big, end of ingredients section
            break
        collected.append(b)
        current_y = by + bh

    print(f"\nCollected {len(collected)} blocks:")
    for b in collected:
        print(f"  B{b.get('id')}: '{b.get('text')}'")

    full_text = " ".join(b.get('text', '') for b in collected)
    print(f"\nFull ingredients text:\n{full_text}")

test_ing_extraction()
