import cv2
import numpy as np
import os
import re
import logging
from typing import List, Dict, Any, Tuple, Set

# Fix Windows Paddle / oneDNN static executor issues
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logger = logging.getLogger("metrolens.ocr")
logging.basicConfig(level=logging.INFO)

# Global instances for cached lazy loading
_RAPID_OCR = None
_PADDLE_OCR = None
_EASY_OCR = None

def order_points(pts: np.ndarray) -> np.ndarray:
    """
    Orders 4 points of a quadrilateral: top-left, top-right, bottom-right, bottom-left.
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def detect_and_warp_perspective(img: np.ndarray) -> np.ndarray:
    """
    Detects rectangular label boundary using OpenCV contour detection and applies
    4-point perspective warp (cv2.getPerspectiveTransform + cv2.warpPerspective)
    to deskew angled labels before OCR runs.
    Falls back safely to original image if no quad contour >= 15% image area is found.
    """
    try:
        h, w = img.shape[:2]
        img_area = h * w
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 200)

        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)

            if len(approx) == 4 and cv2.isContourConvex(approx):
                c_area = cv2.contourArea(approx)
                if c_area >= 0.15 * img_area:
                    pts = approx.reshape(4, 2)
                    rect = order_points(pts)
                    (tl, tr, br, bl) = rect

                    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
                    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
                    maxWidth = max(int(widthA), int(widthB))

                    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
                    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
                    maxHeight = max(int(heightA), int(heightB))

                    if maxWidth > 100 and maxHeight > 100:
                        dst = np.array([
                            [0, 0],
                            [maxWidth - 1, 0],
                            [maxWidth - 1, maxHeight - 1],
                            [0, maxHeight - 1]
                        ], dtype="float32")

                        M = cv2.getPerspectiveTransform(rect, dst)
                        warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
                        logger.info(f"Successfully applied perspective deskew transform ({maxWidth}x{maxHeight})")
                        return warped
    except Exception as e:
        logger.warning(f"Perspective transform deskew skipped: {e}")

    return img

def preprocess_image(image_bytes: bytes, max_dimension: int = 1600, apply_clahe: bool = True, apply_deskew: bool = True, apply_denoise: bool = False) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Decodes raw image bytes, resizes to max_dimension (1600px), applies optional perspective deskewing,
    and performs contrast enhancement (CLAHE) & optional non-local means denoising.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        raise ValueError("Could not decode image files. Ensure a valid PNG/JPEG photo is uploaded.")
        
    orig_h, orig_w, channels = img.shape

    # 1. Smart resize to max_dimension (1600px) FIRST to optimize speed of subsequent CV operations & OCR
    curr_h, curr_w = img.shape[:2]
    if max(curr_h, curr_w) > max_dimension:
        scale = max_dimension / float(max(curr_h, curr_w))
        new_w, new_h = int(curr_w * scale), int(curr_h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        logger.info(f"Resized input image from {curr_w}x{curr_h} to {new_w}x{new_h} for high-speed OCR")
    else:
        new_w, new_h = curr_w, curr_h

    # 2. Perspective deskewing step on resized image
    if apply_deskew:
        img = detect_and_warp_perspective(img)

    # 3. Non-local means denoising for camera sensor noise
    if apply_denoise:
        try:
            img = cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 21)
            logger.info("Applied fastNlMeansDenoisingColored for sensor noise reduction")
        except Exception as e:
            logger.warning(f"Denoising skipped: {e}")

    # 4. CLAHE contrast enhancement for text legibility
    if apply_clahe:
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_gray = clahe.apply(gray)
            img = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)
            logger.info("Applied CLAHE contrast enhancement for OCR text detection")
        except Exception as e:
            logger.warning(f"CLAHE preprocessing skipped: {e}")

    metadata = {
        "width": new_w,
        "height": new_h,
        "original_width": orig_w,
        "original_height": orig_h,
        "channels": channels
    }
    
    return img, metadata

def get_rapid_ocr():
    global _RAPID_OCR
    if _RAPID_OCR is not None:
        return _RAPID_OCR
    try:
        from rapidocr_onnxruntime import RapidOCR
        logger.info("Initializing RapidOCR ONNX engine with tuned parameters (max_side_len=1600)...")
        _RAPID_OCR = RapidOCR(unclip_ratio=2.0, box_thresh=0.35, text_score=0.35, max_side_len=1600)
        return _RAPID_OCR
    except Exception as e:
        logger.warning(f"RapidOCR init failed: {e}")
        return None

def get_easy_ocr():
    global _EASY_OCR
    if _EASY_OCR is not None:
        return _EASY_OCR
    try:
        import easyocr
        logger.info("Initializing EasyOCR reader for English...")
        _EASY_OCR = easyocr.Reader(['en'], gpu=False, verbose=False)
        return _EASY_OCR
    except Exception as e:
        logger.warning(f"EasyOCR init failed: {e}")
        return None


def detect_scripts_in_text(text: str) -> List[str]:
    """
    Detects presence of Gujarati, Hindi/Devanagari, and Latin/English scripts.
    """
    scripts = []
    if re.search(r'[\u0A80-\u0AFF]', text):
        scripts.append("gu")
    if re.search(r'[\u0900-\u097F]', text):
        scripts.append("hi")
    if re.search(r'[A-Za-z]', text):
        scripts.append("en")
    return scripts or ["en"]

def stitch_vertical_text_columns(blocks: List[Dict[str, Any]], start_block_id: int) -> Tuple[List[Dict[str, Any]], Set[int]]:
    """
    Detects character-by-character stacked vertical text columns
    (e.g., M-R-P, B-A-T-C-H, dates printed vertically top-to-bottom).
    Combines them into coherent, single-line text blocks with is_vertical: True.
    """
    singles = [b for b in blocks if len(b.get("text", "").strip()) <= 3 and b.get("rect")]
    # Sort strictly by Y coordinate first to maintain top-to-bottom sequence
    singles.sort(key=lambda b: (b["rect"]["y"], b["rect"]["x"]))

    columns: List[List[Dict[str, Any]]] = []
    for b in singles:
        b_cx = b["rect"]["x"] + b["rect"]["width"] / 2.0
        placed = False
        for col in columns:
            last_item = col[-1]
            last_cx = last_item["rect"]["x"] + last_item["rect"]["width"] / 2.0
            y_gap = b["rect"]["y"] - (last_item["rect"]["y"] + last_item["rect"]["height"])
            # Within 20px horizontally and -5 to 45px vertical gap
            if abs(b_cx - last_cx) <= 20 and -5 <= y_gap <= 45:
                col.append(b)
                placed = True
                break
        if not placed:
            columns.append([b])

    stitched_blocks = []
    used_ids = set()
    current_id = start_block_id

    for col in columns:
        if len(col) >= 3:
            combined_text = "".join(b["text"].strip() for b in col)
            min_x = min(b["rect"]["x"] for b in col)
            max_x = max(b["rect"]["x"] + b["rect"]["width"] for b in col)
            min_y = min(b["rect"]["y"] for b in col)
            max_y = max(b["rect"]["y"] + b["rect"]["height"] for b in col)
            w_px = round(max_x - min_x, 1)
            h_px = round(max_y - min_y, 1)
            avg_conf = sum(b.get("confidence", 0.8) for b in col) / len(col)

            stitched_blocks.append({
                "id": current_id,
                "text": combined_text,
                "confidence": round(avg_conf, 4),
                "bbox": [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]],
                "rect": {"x": min_x, "y": min_y, "width": w_px, "height": h_px},
                "height_px": h_px,
                "width_px": w_px,
                "angle": 90,
                "is_vertical": True,
                "is_stitched_vertical": True,
                "constituent_ids": [b.get("id") for b in col]
            })
            current_id += 1
            for b in col:
                used_ids.add(b.get("id"))

    return stitched_blocks, used_ids

def transform_rotated_point(pt: List[float], angle: int, W_orig: int, H_orig: int) -> List[float]:
    """
    Transforms coordinates from rotated image frame back to original 0° image frame.
    - 90° CW: x = y', y = H_orig - x'
    - 180°: x = W_orig - x', y = H_orig - y'
    - 270° CW (90° CCW): x = W_orig - y', y = x'
    """
    x_rot, y_rot = pt[0], pt[1]
    if angle == 90:
        return [round(float(y_rot), 1), round(float(H_orig - x_rot), 1)]
    elif angle == 180:
        return [round(float(W_orig - x_rot), 1), round(float(H_orig - y_rot), 1)]
    elif angle == 270:
        return [round(float(W_orig - y_rot), 1), round(float(x_rot), 1)]
    return [round(float(x_rot), 1), round(float(y_rot), 1)]

def extract_text_from_image(image_bytes: bytes, enable_multi_angle: bool = True) -> Dict[str, Any]:
    """
    High-Speed & High-Recall Multi-Angle OCR Execution Function.
    Runs RapidOCR (PaddleOCR ONNX Runtime) at 1600px resolution with CLAHE contrast enhancement:
    - Primary 0° pass for fast extraction
    - Robust 90° & 270° rotation passes for vertical/rotated text on side margins, seams, and stamps
    - Vertical stacked character stitcher
    - Multilingual script analysis (English, Gujarati, Hindi)
    """
    img, meta = preprocess_image(image_bytes, max_dimension=1600, apply_clahe=True)
    H_orig, W_orig = meta["height"], meta["width"]
    
    blocks: List[Dict[str, Any]] = []
    ocr_engine_used = "Unknown"
    
    rapid_engine = get_rapid_ocr()
    if rapid_engine is not None:
        try:
            logger.info("Executing RapidOCR ONNX 0° primary pass...")
            result, elapse = rapid_engine(img)
            ocr_engine_used = "RapidOCR (PaddleOCR ONNX)"
            
            block_id = 1
            existing_texts = set()

            if result:
                for item in result:
                    bbox = item[0]
                    text = item[1] if len(item) < 3 else item[1]
                    conf = item[2] if len(item) >= 3 else item[1][1]
                        
                    text_str = str(text).strip()
                    if not text_str:
                        continue
                        
                    xs = [float(p[0]) for p in bbox]
                    ys = [float(p[1]) for p in bbox]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    w_px = round(max_x - min_x, 2)
                    h_px = round(max_y - min_y, 2)
                    
                    is_vert = (h_px / max(1.0, w_px)) > 1.8
                    blocks.append({
                        "id": block_id,
                        "text": text_str,
                        "confidence": round(float(conf), 4),
                        "bbox": [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in bbox],
                        "rect": {"x": round(float(min_x), 1), "y": round(float(min_y), 1), "width": w_px, "height": h_px},
                        "height_px": h_px,
                        "width_px": w_px,
                        "angle": 0,
                        "is_vertical": is_vert
                    })
                    existing_texts.add(text_str.upper())
                    block_id += 1

            # Multi-Angle Rotation Pass (90° CW & 270° CCW):
            # Critical for vertical text printed on packaging seams, gussets, side margins, and vertical format dates/MRP.
            # Runs whenever:
            # 1. Any vertical text blocks were suspected/detected in 0° pass (is_vertical is True)
            # 2. Or enable_multi_angle is True and any key declaration is missing or unverified
            # 3. Or total detected blocks < 8
            has_vertical_blocks = any(b.get("is_vertical", False) for b in blocks)
            all_text_concat = " ".join([b["text"].upper() for b in blocks])
            has_mrp = any(kw in all_text_concat for kw in ["MRP", "RS", "₹", "PRICE", "MAX", "મ.ચી.ભા", "અ.ખુ.મૂ"])
            has_qty = any(kw in all_text_concat for kw in ["NET", "QTY", "WEIGHT", "WT", "VOL", "50G", "100G", "250G", "1KG", "500G", "G", "KG", "ML", "L", "વજન", "માત્રા"])
            has_mfg = any(kw in all_text_concat for kw in ["MFG", "PKD", "EXP", "DATE", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "તારીખ", "તિથિ"])
            has_mfg_addr = any(kw in all_text_concat for kw in ["MFD BY", "MFG BY", "PACKED BY", "PKD BY", "MANUFACTURED", "ઉત્પાદક", "નિર્માતા"])
            has_care = any(kw in all_text_concat for kw in ["CARE", "CONSUMER", "CUSTOMER", "HELPLINE", "1800", "ગ્રાહક", "સેવા"])

            needs_rotation_pass = enable_multi_angle and (
                has_vertical_blocks or
                not (has_mrp and has_qty and has_mfg and has_mfg_addr and has_care) or
                len(blocks) < 8
            )

            if needs_rotation_pass:
                logger.info("Executing comprehensive 90° and 270° multi-angle rotation passes for vertical/rotated text...")
                angles_to_check = [
                    (90, cv2.ROTATE_90_CLOCKWISE),
                    (270, cv2.ROTATE_90_COUNTERCLOCKWISE)
                ]
                for angle_deg, rot_code in angles_to_check:
                    rot_img = cv2.rotate(img, rot_code)
                    rot_res, _ = rapid_engine(rot_img)
                    if rot_res:
                        logger.info(f"RapidOCR {angle_deg}° rotation pass found {len(rot_res)} items...")
                        for item in rot_res:
                            bbox_rot = item[0]
                            text_rot = item[1] if len(item) < 3 else item[1]
                            conf_rot = item[2] if len(item) >= 3 else item[1][1]

                            t_str = str(text_rot).strip()
                            if not t_str or t_str.upper() in existing_texts:
                                continue

                            # Transform bbox back to 0° frame
                            bbox_orig = [transform_rotated_point([float(p[0]), float(p[1])], angle_deg, W_orig, H_orig) for p in bbox_rot]
                            xs = [float(p[0]) for p in bbox_orig]
                            ys = [float(p[1]) for p in bbox_orig]
                            min_x, max_x = min(xs), max(xs)
                            min_y, max_y = min(ys), max(ys)
                            w_px = round(max_x - min_x, 2)
                            h_px = round(float(max_y - min_y), 2)
                            is_vert = True

                            blocks.append({
                                "id": block_id,
                                "text": t_str,
                                "confidence": round(float(conf_rot), 4),
                                "bbox": bbox_orig,
                                "rect": {"x": round(float(min_x), 1), "y": round(float(min_y), 1), "width": w_px, "height": h_px},
                                "height_px": h_px,
                                "width_px": w_px,
                                "angle": angle_deg,
                                "is_vertical": is_vert
                            })
                            existing_texts.add(t_str.upper())
                            block_id += 1
            else:
                logger.info(f"0° primary pass extracted {len(blocks)} blocks with complete LMPC declarations.")

            # 1b. Targeted Bottom Strip Pass (Inkjet Variable Coder Strip: Batch, Dates, MRP, USP)
            # In Indian packaged commodities, variable batch data (batch no, packed date, expiry/use-by,
            # MRP and unit sale price) is stamped on the bottom 25% using continuous inkjet/dot-matrix.
            # Using raw image resolution with single CLAHE pass guarantees clean dot-matrix segmentation.
            if rapid_engine is not None:
                try:
                    raw_nparr = np.frombuffer(image_bytes, np.uint8)
                    raw_img = cv2.imdecode(raw_nparr, cv2.IMREAD_COLOR)
                    if raw_img is not None:
                        H_raw, W_raw = raw_img.shape[:2]
                        y_start_raw = int(0.74 * H_raw)
                        strip_raw = raw_img[y_start_raw:, :]
                        if strip_raw.size > 0:
                            strip_2x = cv2.resize(strip_raw, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                            gray_s = cv2.cvtColor(strip_2x, cv2.COLOR_BGR2GRAY)
                            clahe_s = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                            strip_enh = cv2.cvtColor(clahe_s.apply(gray_s), cv2.COLOR_GRAY2BGR)
                            res_strip, _ = rapid_engine(strip_enh)
                            if res_strip:
                                scale_x = W_orig / float(W_raw)
                                scale_y = H_orig / float(H_raw)
                                logger.info(f"Bottom strip pass extracted {len(res_strip)} variable coder items from raw strip")
                                for item in res_strip:
                                    bbox_s = item[0]
                                    text_s = str(item[1]).strip() if len(item) < 3 else str(item[1]).strip()
                                    conf_s = float(item[2]) if len(item) >= 3 else float(item[1][1])
                                    if not text_s:
                                        continue
                                    orig_bbox = [[round((float(p[0])/2.0) * scale_x, 1), round((float(p[1])/2.0 + y_start_raw) * scale_y, 1)] for p in bbox_s]
                                    xs = [p[0] for p in orig_bbox]
                                    ys = [p[1] for p in orig_bbox]
                                    min_x, max_x = min(xs), max(xs)
                                    min_y, max_y = min(ys), max(ys)
                                    w_px = round(max_x - min_x, 2)
                                    h_px = round(max_y - min_y, 2)
                                    
                                    clean_ts = re.sub(r'[^A-Z0-9]', '', text_s.upper())
                                    is_dup = False
                                    for ex in blocks:
                                        ex_rect = ex.get("rect", {})
                                        ex_cx = ex_rect.get("x", 0) + ex_rect.get("width", 0) / 2.0
                                        ex_cy = ex_rect.get("y", 0) + ex_rect.get("height", 0) / 2.0
                                        dist = ((ex_cx - (min_x + w_px/2.0))**2 + (ex_cy - (min_y + h_px/2.0))**2)**0.5
                                        ex_clean = re.sub(r'[^A-Z0-9]', '', ex.get("text", "").upper())
                                        if dist < 20 and clean_ts == ex_clean:
                                            is_dup = True
                                            break
                                    if not is_dup:
                                        blocks.append({
                                            "id": block_id,
                                            "text": text_s,
                                            "confidence": round(float(conf_s), 4),
                                            "bbox": orig_bbox,
                                            "rect": {"x": round(float(min_x), 1), "y": round(float(min_y), 1), "width": w_px, "height": h_px},
                                            "height_px": h_px,
                                            "width_px": w_px,
                                            "angle": 0,
                                            "is_vertical": False
                                        })
                                        block_id += 1
                except Exception as strip_err:
                    logger.warning(f"Targeted bottom strip pass skipped: {strip_err}")

            # 1c. Targeted Barcode Neighbor Pass (Consumer Care Helpline & Contacts)
            # In Indian retail packaging, consumer care details (1800 toll-free, emails, complaints)
            # are standardly placed directly above or adjacent to the barcode.
            if rapid_engine is not None:
                try:
                    bc_det = cv2.barcode.BarcodeDetector()
                    ok_bc, _, bc_pts = bc_det.detectAndDecode(img)
                    if ok_bc and bc_pts is not None and len(bc_pts) > 0:
                        pts_arr = bc_pts[0]
                        b_xs = [float(p[0]) for p in pts_arr]
                        b_ys = [float(p[1]) for p in pts_arr]
                        bx_min, bx_max = min(b_xs), max(b_xs)
                        by_min, by_max = min(b_ys), max(b_ys)
                        if by_min > 60:
                            c_y1 = max(0, int(by_min - 130))
                            c_y2 = int(by_min)
                            c_x1 = max(0, int(bx_min - 120))
                            c_x2 = min(W_orig, int(bx_max + 120))
                            crop_care = img[c_y1:c_y2, c_x1:c_x2]
                            if crop_care.size > 0:
                                crop_care_2x = cv2.resize(crop_care, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                                gray_c = cv2.cvtColor(crop_care_2x, cv2.COLOR_BGR2GRAY)
                                clahe_c = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                                care_enh = cv2.cvtColor(clahe_c.apply(gray_c), cv2.COLOR_GRAY2BGR)
                                res_care, _ = rapid_engine(care_enh)
                                if res_care:
                                    logger.info(f"Targeted barcode neighbor pass extracted {len(res_care)} blocks")
                                    for item in res_care:
                                        bbox_c = item[0]
                                        text_c = str(item[1]).strip() if len(item) < 3 else str(item[1]).strip()
                                        conf_c = float(item[2]) if len(item) >= 3 else float(item[1][1])
                                        if not text_c:
                                            continue
                                        orig_bbox = [[round(float(p[0])/2.0 + c_x1, 1), round(float(p[1])/2.0 + c_y1, 1)] for p in bbox_c]
                                        xs = [p[0] for p in orig_bbox]
                                        ys = [p[1] for p in orig_bbox]
                                        min_x, max_x = min(xs), max(xs)
                                        min_y, max_y = min(ys), max(ys)
                                        w_px = round(max_x - min_x, 2)
                                        h_px = round(max_y - min_y, 2)
                                        clean_tc = re.sub(r'[^A-Z0-9]', '', text_c.upper())
                                        is_dup = False
                                        for ex in blocks:
                                            ex_rect = ex.get("rect", {})
                                            ex_cx = ex_rect.get("x", 0) + ex_rect.get("width", 0) / 2.0
                                            ex_cy = ex_rect.get("y", 0) + ex_rect.get("height", 0) / 2.0
                                            dist = ((ex_cx - (min_x + w_px/2.0))**2 + (ex_cy - (min_y + h_px/2.0))**2)**0.5
                                            ex_clean = re.sub(r'[^A-Z0-9]', '', ex.get("text", "").upper())
                                            if dist < 20 and clean_tc == ex_clean:
                                                is_dup = True
                                                break
                                        if not is_dup:
                                            blocks.append({
                                                "id": block_id,
                                                "text": text_c,
                                                "confidence": round(float(conf_c), 4),
                                                "bbox": orig_bbox,
                                                "rect": {"x": round(float(min_x), 1), "y": round(float(min_y), 1), "width": w_px, "height": h_px},
                                                "height_px": h_px,
                                                "width_px": w_px,
                                                "angle": 0,
                                                "is_vertical": False
                                            })
                                            block_id += 1
                except Exception as bc_err:
                    logger.warning(f"Targeted barcode neighbor pass skipped: {bc_err}")
        except Exception as err:
            logger.error(f"RapidOCR error: {err}. Trying EasyOCR fallback...")
            blocks = []

    # 2. Fallback to EasyOCR if RapidOCR failed
    if not blocks:
        easy_engine = get_easy_ocr()
        if easy_engine is not None:
            try:
                logger.info("Executing EasyOCR fallback...")
                results = easy_engine.readtext(img)
                ocr_engine_used = "EasyOCR"
                block_id = 1
                for bbox, text, conf in results:
                    text_str = str(text).strip()
                    if not text_str:
                        continue
                    xs = [p[0] for p in bbox]
                    ys = [p[1] for p in bbox]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    w_px = round(float(max_x - min_x), 2)
                    h_px = round(float(max_y - min_y), 2)
                    blocks.append({
                        "id": block_id,
                        "text": text_str,
                        "confidence": round(float(conf), 4),
                        "bbox": [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in bbox],
                        "rect": {"x": round(float(min_x), 1), "y": round(float(min_y), 1), "width": w_px, "height": h_px},
                        "height_px": h_px,
                        "width_px": w_px
                    })
                    block_id += 1
            except Exception as err:
                logger.error(f"EasyOCR error: {err}")
                blocks = []

    # 3. Fallback mock / CV bounding box detector if no blocks detected
    if not blocks:
        ocr_engine_used = "OpenCV-Contour-Fallback"
        logger.info("Using OpenCV heuristic fallback for text block detection...")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        block_id = 1
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > 15 and h > 8 and w < meta["width"] * 0.9:
                blocks.append({
                    "id": block_id,
                    "text": f"Unrecognized Region #{block_id}",
                    "confidence": 0.50,
                    "bbox": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                    "rect": {"x": float(x), "y": float(y), "width": float(w), "height": float(h)},
                    "height_px": float(h),
                    "width_px": float(w)
                })
                block_id += 1
                if block_id > 20:
                    break

    # 4. Vertical Stacked Character Column Stitcher
    # Aggregates vertically aligned single-character blocks into readable text declarations
    if blocks:
        try:
            stitched, used_ids = stitch_vertical_text_columns(blocks, start_block_id=len(blocks) + 1)
            if stitched:
                logger.info(f"Stitched {len(stitched)} vertical text column blocks (used {len(used_ids)} single characters)")
                # Retain original blocks that weren't consumed, plus stitched blocks
                blocks = [b for b in blocks if b.get("id") not in used_ids] + stitched
                # Re-index block ids cleanly
                for idx, b in enumerate(blocks, 1):
                    b["id"] = idx
        except Exception as v_err:
            logger.warning(f"Vertical column stitcher skipped: {v_err}")

    # 5. Multilingual Script Annotation (Gujarati, Hindi, English)
    detected_scripts_all = set()
    for b in blocks:
        s_list = detect_scripts_in_text(b.get("text", ""))
        b["scripts"] = s_list
        b["lang"] = s_list[0]
        for s in s_list:
            detected_scripts_all.add(s)

    raw_extracted_text = "\n".join([b["text"] for b in blocks if b["text"]])
    
    return {
        "engine": ocr_engine_used,
        "image_metadata": meta,
        "total_detected_blocks": len(blocks),
        "raw_text": raw_extracted_text,
        "text_lines": [b["text"] for b in blocks],
        "blocks": blocks,
        "detected_languages": sorted(list(detected_scripts_all)) or ["en"],
        "has_vertical_text": any(b.get("is_vertical") for b in blocks)
    }


