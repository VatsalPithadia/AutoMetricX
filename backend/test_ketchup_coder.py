import os, sys
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image

p = os.path.join(backend_dir, "uploads", "ff132bef634f4860b952a42a2e2257a5.jpeg")
with open(p, "rb") as f:
    ocr = extract_text_from_image(f.read())
blocks = ocr.get("blocks", [])

print("=== KETCHUP MRP & CODER STRIP BLOCKS ===")
for b in blocks:
    r = b.get("rect", {})
    txt = b.get("text", "")
    if any(k in txt.upper() for k in ["MRP", "140", "PACKAGING", "USE BY", "LOT NO", "UNIT SALE"]):
        print(f"B{b.get('id')}: '{txt}' rect={r}")
