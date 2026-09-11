import os, sys, re
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image
from app.classifier import find_adjacent_value_block

p = os.path.join(backend_dir, "uploads", "ff132bef634f4860b952a42a2e2257a5.jpeg")
with open(p, "rb") as f:
    ocr = extract_text_from_image(f.read())
blocks = ocr.get("blocks", [])

b48 = [b for b in blocks if b.get('id') == 48][0]

nutrient_kw = [
    'SERVING SIZE', 'PER 100', 'PER SERVE', 'NUTRITION FACTS', 'NUTRITIONAL',
    'DAILY VALUE', '% RDA', 'CARBOHYDRATE', 'SUGAR', 'ADDED SUGAR', 'PROTEIN',
    'TOTAL FAT', 'FAT', 'SODIUM', 'CHOLESTEROL', 'ENERGY', 'KCAL', 'DIETARY FIBER'
]
nutr_blocks = [b for b in blocks if any(k in b.get('text', '').upper() for k in nutrient_kw)]
min_nx = min(b.get("rect", {}).get("x", 0.0) for b in nutr_blocks) - 20.0
max_nx = max(b.get("rect", {}).get("x", 0.0) + b.get("rect", {}).get("width", 0.0) for b in nutr_blocks) + 180.0
min_ny = min(b.get("rect", {}).get("y", 0.0) for b in nutr_blocks) - 25.0
max_ny = max(b.get("rect", {}).get("y", 0.0) + b.get("rect", {}).get("height", 0.0) for b in nutr_blocks) + 30.0
nutrition_table_boxes = [(min_nx, min_ny, max_nx, max_ny)]

def price_validator(cand, t):
    # Reject if in nutrition table
    cr = cand.get("rect", {})
    cx = cr.get("x", 0.0) + cr.get("width", 0.0) / 2.0
    cy = cr.get("y", 0.0) + cr.get("height", 0.0) / 2.0
    if any(nx0 <= cx <= nx1 and ny0 <= cy <= ny1 for (nx0, ny0, nx1, ny1) in nutrition_table_boxes):
        return False
    if not re.search(r'\d', t):
        return False
    if re.search(r'\b\d{2}[/-]\d{2}[/-]\d{2,4}\b', t):
        return False
    if any(lbl in re.sub(r'[^A-Z]', '', t.upper()) for lbl in ['INCL', 'TAXES', 'MRP', 'BATCH', 'MFG', 'EXP', 'USEBY', 'DATEOF']):
        return False
    prices = [float(x) for x in re.findall(r'\d+(?:\.\d{1,2})?', t)]
    if not any(1.0 <= p <= 50000.0 for p in prices):
        return False
    return True

adj = find_adjacent_value_block(
    b48,
    blocks,
    max_horizontal_px=380.0,
    max_vertical_px=100.0,
    value_validator=price_validator
)
print(f"Adjacent to B48 (MRP): B{adj.get('id') if adj else None} '{adj.get('text') if adj else None}'")
