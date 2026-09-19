import cv2, os, re, time, sys
import numpy as np
from rapidocr_onnxruntime import RapidOCR

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

engine = RapidOCR(max_side_len=1200)

def test_tiling(img_path, tile_dim=800, upscale_factor=1.5):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Error loading {img_path}")
        return
    h_orig, w_orig = img.shape[:2]
    # Resize to max 1600 as in preprocess
    if max(h_orig, w_orig) > 1600:
        scale = 1600.0 / max(h_orig, w_orig)
        img = cv2.resize(img, (int(w_orig * scale), int(h_orig * scale)), interpolation=cv2.INTER_AREA)
    H, W = img.shape[:2]
    print(f"\n--- Testing {os.path.basename(img_path)} ({W}x{H}) with tile_dim={tile_dim}, upscale={upscale_factor} ---", flush=True)

    # 15% overlap
    stride = int(tile_dim * 0.85)

    x_steps = []
    curr_x = 0
    while curr_x + tile_dim < W:
        x_steps.append(curr_x)
        curr_x += stride
    x_steps.append(max(0, W - tile_dim))
    x_steps = sorted(list(set(x_steps)))

    y_steps = []
    curr_y = 0
    while curr_y + tile_dim < H:
        y_steps.append(curr_y)
        curr_y += stride
    y_steps.append(max(0, H - tile_dim))
    y_steps = sorted(list(set(y_steps)))

    print(f"Grid: {len(x_steps)} cols x {len(y_steps)} rows = {len(x_steps)*len(y_steps)} tiles: X={x_steps}, Y={y_steps}", flush=True)

    t0 = time.time()
    detections = []
    tile_idx = 0

    for ty in y_steps:
        for tx in x_steps:
            tile_idx += 1
            tile = img[ty:ty+tile_dim, tx:tx+tile_dim]
            if upscale_factor != 1.0:
                tile = cv2.resize(tile, (0, 0), fx=upscale_factor, fy=upscale_factor, interpolation=cv2.INTER_CUBIC)
            
            t_start = time.time()
            res, _ = engine(tile)
            t_tile = time.time() - t_start
            print(f"  Tile #{tile_idx} ({tx},{ty}) took {t_tile:.2f}s -> {len(res) if res else 0} detections", flush=True)
            
            if res:
                for item in res:
                    bbox = item[0]
                    text = item[1].strip()
                    conf = float(item[2])
                    if not text:
                        continue
                    full_bbox = [[round((p[0]/upscale_factor) + tx, 1), round((p[1]/upscale_factor) + ty, 1)] for p in bbox]
                    detections.append({
                        "text": text,
                        "conf": conf,
                        "bbox": full_bbox,
                        "rect": {
                            "x": min(p[0] for p in full_bbox),
                            "y": min(p[1] for p in full_bbox),
                            "w": max(p[0] for p in full_bbox) - min(p[0] for p in full_bbox),
                            "h": max(p[1] for p in full_bbox) - min(p[1] for p in full_bbox)
                        }
                    })

    total_time = time.time() - t0
    print(f"All {tile_idx} tiles completed in {total_time:.2f}s, total raw detections: {len(detections)}", flush=True)

    # Deduplicate with IoU and text similarity
    deduped = []
    for d in sorted(detections, key=lambda x: x["conf"], reverse=True):
        is_dup = False
        r1 = d["rect"]
        cx1 = r1["x"] + r1["w"] / 2.0
        cy1 = r1["y"] + r1["h"] / 2.0
        clean1 = re.sub(r'[^A-Z0-9]', '', d["text"].upper())

        for kept in deduped:
            r2 = kept["rect"]
            cx2 = r2["x"] + r2["w"] / 2.0
            cy2 = r2["y"] + r2["h"] / 2.0
            clean2 = re.sub(r'[^A-Z0-9]', '', kept["text"].upper())

            dist = ((cx1 - cx2)**2 + (cy1 - cy2)**2)**0.5
            ix1 = max(r1["x"], r2["x"])
            iy1 = max(r1["y"], r2["y"])
            ix2 = min(r1["x"] + r1["w"], r2["x"] + r2["w"])
            iy2 = min(r1["y"] + r1["h"], r2["y"] + r2["h"])
            inter_area = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            area1 = r1["w"] * r1["h"]
            area2 = r2["w"] * r2["h"]
            iou = inter_area / float(area1 + area2 - inter_area) if (area1 + area2 - inter_area) > 0 else 0.0

            if (iou > 0.35) or (dist < 20 and (clean1 == clean2 or clean1 in clean2 or clean2 in clean1)):
                is_dup = True
                break

        if not is_dup:
            deduped.append(d)

    print(f"Deduplicated to {len(deduped)} distinct blocks", flush=True)
    # Check for target declarations
    print("Found key declarations:")
    for d in deduped:
        t = d["text"].upper()
        if any(k in t for k in ['MRP', 'RS', '₹', 'NET', 'QTY', '5G', '50G', '6G', 'EXP', 'USE BY', 'BATCH', 'MFG', 'HALOL', 'SHRI HARI', 'ENO']):
            print(f"  [{d['conf']:.2f}] {d['text']}", flush=True)

if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__), "..", "test_images")
    test_tiling(os.path.join(base, "dense_sachet_small_text.jpg"), tile_dim=800, upscale_factor=1.5)
    test_tiling(os.path.join(base, "curved_bottle_label.jpg"), tile_dim=800, upscale_factor=1.5)
