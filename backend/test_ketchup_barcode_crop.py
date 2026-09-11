import os, sys, cv2
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
from app.ocr_engine import extract_text_from_image
import zxingcpp

k_path = os.path.join(backend_dir, "uploads", "ff132bef634f4860b952a42a2e2257a5.jpeg")
k_img = cv2.imread(k_path)
with open(k_path, "rb") as f:
    k_blocks = extract_text_from_image(f.read()).get("blocks", [])

for b in k_blocks:
    if "015525" in b.get("text", "") or "03363" in b.get("text", ""):
        print(f"Barcode text block {b.get('id')}: '{b.get('text')}' rect={b.get('rect')}")
        r = b.get("rect")
        # Crop above this text block (where the barcode stripes are!)
        # Barcode stripes typically extend above the number by 1.0 to 3.0 times the height of the text block,
        # and roughly same width
        bx = int(r["x"])
        by = int(r["y"])
        bw = int(r["width"])
        bh = int(r["height"])
        
        # Crop barcode bars:
        crop_y1 = max(0, by - int(bh * 4.5))
        crop_y2 = min(k_img.shape[0], by + int(bh * 1.5))
        crop_x1 = max(0, bx - int(bw * 0.2))
        crop_x2 = min(k_img.shape[1], bx + int(bw * 1.2))
        
        crop = k_img[crop_y1:crop_y2, crop_x1:crop_x2]
        print(f"Cropped shape: {crop.shape}")
        b_res = zxingcpp.read_barcodes(crop)
        print(f"ZXing on cropped bars: {[(x.text, x.format) for x in b_res]}")
        # Try with variants
        for angle in [0, 90, 180, 270]:
            rot = crop if angle == 0 else cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE if angle==90 else (cv2.ROTATE_180 if angle==180 else cv2.ROTATE_90_COUNTERCLOCKWISE))
            res = zxingcpp.read_barcodes(rot)
            if res:
                print(f"Angle {angle} found: {[(x.text, x.format) for x in res]}")
