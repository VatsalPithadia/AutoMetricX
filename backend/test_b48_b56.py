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
b56 = [b for b in blocks if b.get('id') == 56][0]

print(f"B48: '{b48['text']}' rect={b48['rect']}")
print(f"B56: '{b56['text']}' rect={b56['rect']}")

price_validator = lambda cand, t: (
    bool(re.search(r'\d', t)) and
    not bool(re.search(r'\b\d{2}[/-]\d{2}[/-]\d{2,4}\b', t)) and
    not any(lbl in re.sub(r'[^A-Z]', '', t.upper()) for lbl in ['INCL', 'TAXES', 'MRP', 'BATCH', 'MFG', 'EXP', 'USEBY', 'DATEOF'])
)

print(f"B56 passes price_validator: {price_validator(b56, b56['text'])}")

# Test find_adjacent
adj = find_adjacent_value_block(
    b48,
    blocks,
    max_horizontal_px=380.0,
    max_vertical_px=100.0,
    value_validator=price_validator
)
print(f"Adjacent to B48: B{adj.get('id') if adj else None} '{adj.get('text') if adj else None}'")
