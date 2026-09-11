import os, sys, cv2, re
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image

def check_gs1_checksum(digits):
    if len(digits) not in [8, 12, 13, 14]:
        return False
    check_digit = digits[-1]
    core_digits = digits[:-1]
    total = sum(d * (3 if idx % 2 == 0 else 1) for idx, d in enumerate(reversed(core_digits)))
    return (10 - (total % 10)) % 10 == check_digit

def recover_ean13_from_text(raw_text):
    # Normalize OCR confusions: 'l' or '|' or 'I' to '1', 'O' to '0'
    norm = raw_text.replace('l', '1').replace('|', '1').replace('I', '1').replace('O', '0').replace('o', '0')
    digits = [int(c) for c in norm if c.isdigit()]
    if len(digits) == 13:
        if check_gs1_checksum(digits):
            return "".join(map(str, digits))
        # Try Indian prefix repair if second digit was misread as 4, 1, or 7 instead of 9 (e.g. 840 -> 890)
        if digits[0] == 8 and digits[2] == 0:
            test_digits = list(digits)
            test_digits[1] = 9
            if check_gs1_checksum(test_digits):
                return "".join(map(str, test_digits))
    return None

for fname in ['ff132bef634f4860b952a42a2e2257a5.jpeg', '42227ec47bd04596a3458c9871c509c7.jpeg']:
    p = os.path.join(backend_dir, 'uploads', fname)
    with open(p, 'rb') as f:
        blocks = extract_text_from_image(f.read()).get('blocks', [])
    print(f"\n=== Testing {fname} ===")
    for b in blocks:
        code = recover_ean13_from_text(b.get('text', ''))
        if code:
            print(f"FOUND EAN13 in Block {b.get('id')}: '{b.get('text')}' -> Code: {code}")
