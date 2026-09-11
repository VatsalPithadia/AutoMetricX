import os, sys
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image

# 1. Ketchup
k_path = os.path.join(backend_dir, "uploads", "ff132bef634f4860b952a42a2e2257a5.jpeg")
with open(k_path, "rb") as f:
    k_blocks = extract_text_from_image(f.read()).get("blocks", [])

print("=== KETCHUP BLOCKS IN INGREDIENTS BOX (x: 150-550, y: 550-800) ===")
ing_zone = [b for b in k_blocks if 150 <= b.get("rect", {}).get("x", 0) <= 550 and 550 <= b.get("rect", {}).get("y", 0) <= 800]
ing_zone.sort(key=lambda b: b.get("rect", {}).get("y", 0))
for b in ing_zone:
    print(f"B{b.get('id')}: '{b.get('text')}' rect={b.get('rect')}")

# 2. Schezwan Chutney Side 1
s1_path = os.path.join(backend_dir, "uploads", "6a56920af0334a3d8eb833300b4c6518.jpeg")
with open(s1_path, "rb") as f:
    s1_blocks = extract_text_from_image(f.read()).get("blocks", [])

print("\n=== SCHEZWAN CHUTNEY SIDE 1 INGREDIENTS BLOCKS (y: 500-800) ===")
s1_ing = [b for b in s1_blocks if 500 <= b.get("rect", {}).get("y", 0) <= 800]
s1_ing.sort(key=lambda b: b.get("rect", {}).get("y", 0))
for b in s1_ing:
    print(f"B{b.get('id')}: '{b.get('text')}' rect={b.get('rect')}")
