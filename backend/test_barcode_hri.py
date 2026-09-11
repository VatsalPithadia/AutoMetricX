import os, sys, re
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image

def check_gs1_ean13(code):
    digits = [int(c) for c in code if c.isdigit()]
    if len(digits) != 13:
        return False
    chk = (10 - sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12])) % 10) % 10
    return chk == digits[12]

for fname in ['ff132bef634f4860b952a42a2e2257a5.jpeg', '42227ec47bd04596a3458c9871c509c7.jpeg']:
    p = os.path.join(backend_dir, 'uploads', fname)
    with open(p, 'rb') as f:
        ocr = extract_text_from_image(f.read())
    print(f"=== Testing {fname} ===")
    for b in ocr.get('blocks', []):
        t = b.get('text', '')
        clean = re.sub(r'[^0-9]', '', t)
        if len(clean) >= 7:
            is_valid = check_gs1_ean13(clean)
            print(f"Block {b.get('id')}: '{t}' -> clean: {clean} (len {len(clean)}) valid_ean13={is_valid}")
