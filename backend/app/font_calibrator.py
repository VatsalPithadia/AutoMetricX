import logging
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("metrolens.font_calibrator")

class FontCalibrator:
    """
    Physical Scale Calibration & Font Size Measurement Engine for Legal Metrology.
    
    Converts OCR bounding box pixel heights to physical letter heights in millimeters (mm):
    - Barcode Calibration: Detects EAN-13 barcodes (standard physical width = 37.29mm SC2 nominal).
    - Resolution Scale Fallback: Uses camera resolution metadata.
    - Rule 7(3): Package Weight Tier Font Size Verification (1.0mm, 2.0mm, 4.0mm, 6.0mm).
    - Rule 9(1): MRP Visual Prominence Ratio Check (h_mrp / h_body >= 1.2x).
    """

    # Standard EAN-13 Barcode Nominal Physical Width in mm
    # SC2 magnification factor (1.0x) is the most common real-world consumer goods barcode size.
    # SC0 minimum = 26.73mm, SC2 nominal = 37.29mm, SC6 maximum = 52.50mm.
    EAN13_STANDARD_WIDTH_MM = 37.29

    def __init__(self):
        pass

    def estimate_px_to_mm_scale(self, image: Optional[np.ndarray], metadata: Dict[str, Any], blocks: List[Dict[str, Any]]) -> Tuple[float, str]:
        """
        Estimates the pixels-per-millimeter (px/mm) scale factor across diverse packaging conditions:
        - OpenCV BarcodeDetector & PyZbar 1D barcode detection (EAN-13 standard physical width = 37.29mm SC2)
        - OCR Barcode Number digit span detection (~30mm)
        - Text-Span ROI Scale Model (Label Surface Width ~90mm)
        - Canvas Resolution Fallback
        """
        # Method A1: OpenCV BarcodeDetector (robust on curved, foil, and rotated packages)
        if image is not None:
            try:
                import cv2
                detector = cv2.barcode.BarcodeDetector()
                ok, info, _ = detector.detectAndDecode(image)
                if ok and len(info) > 0:
                    res, pts = detector.detect(image)
                    if res and pts is not None and len(pts) > 0:
                        p = pts[0]
                        w1 = float(np.linalg.norm(p[1] - p[2]))
                        w2 = float(np.linalg.norm(p[0] - p[3]))
                        barcode_w_px = max(w1, w2)
                        if barcode_w_px > 30:
                            scale = barcode_w_px / self.EAN13_STANDARD_WIDTH_MM
                            logger.info(f"Calibrated physical scale via OpenCV BarcodeDetector: {scale:.2f} px/mm ({barcode_w_px:.1f}px = {self.EAN13_STANDARD_WIDTH_MM}mm EAN-13 SC2)")
                            return float(np.clip(scale, 5.0, 35.0)), f"Barcode Detection ({int(barcode_w_px)}px = EAN-13 SC2 {self.EAN13_STANDARD_WIDTH_MM}mm)"
            except Exception as err:
                logger.debug(f"OpenCV barcode detector skipped: {err}")

        # Method A2: PyZbar Barcode Detection
        if image is not None:
            try:
                from pyzbar import pyzbar
                barcodes = pyzbar.decode(image)
                for barcode in barcodes:
                    rect = barcode.rect
                    if rect.width > 20 and rect.height > 10:
                        scale = float(rect.width) / self.EAN13_STANDARD_WIDTH_MM
                        logger.info(f"Calibrated physical scale via PyZbar Barcode: {scale:.2f} px/mm")
                        return float(np.clip(scale, 5.0, 35.0)), "EAN-13 Barcode Detection (PyZbar)"
            except Exception as err:
                logger.debug(f"PyZbar barcode scale calibration skipped: {err}")

        # Method A3: OCR Barcode digits detection (e.g. 12-13 digits printed below bars ~ 30mm)
        if blocks:
            for b in blocks:
                t = b.get("text", "").strip()
                import re
                digits_only = re.sub(r'[^0-9]', '', t)
                if len(digits_only) in (12, 13) and b.get("width_px", 0) > 80:
                    scale = float(b["width_px"]) / 30.0
                    logger.info(f"Calibrated physical scale via OCR Barcode Digits: {scale:.2f} px/mm")
                    return float(np.clip(scale, 5.0, 35.0)), f"OCR Barcode Digits ({int(b['width_px'])}px = 30mm)"

        # Method B: Text-Span ROI Scale Model (Label Surface Width ~ 90mm)
        if blocks:
            all_xs = []
            all_ys = []
            for b in blocks:
                r = b.get("rect", {})
                if r.get("width", 0) > 0 and r.get("height", 0) > 0:
                    all_xs.extend([r["x"], r["x"] + r["width"]])
                    all_ys.extend([r["y"], r["y"] + r["height"]])
            
            if all_xs and all_ys:
                span_w = max(all_xs) - min(all_xs)
                span_h = max(all_ys) - min(all_ys)
                label_span_px = max(span_w, span_h)
                
                if label_span_px > 150:
                    scale = label_span_px / 90.0
                    logger.info(f"Calibrated physical scale via Text-Span ROI: {scale:.2f} px/mm ({label_span_px:.0f}px span = 90mm)")
                    return float(np.clip(scale, 5.0, 35.0)), f"Label Text-Span ROI ({int(label_span_px)}px = 90mm)"

        # Method C: Canvas Resolution Fallback
        img_w = metadata.get("width", 1600)
        img_h = metadata.get("height", 1200)
        max_dim = max(img_w, img_h)
        scale = max_dim / 100.0
        logger.info(f"Using resolution fallback scale calibration: {scale:.2f} px/mm")
        return float(np.clip(scale, 5.0, 35.0)), "Resolution Scale Model (1600px = 100mm)"

    def calculate_letter_height_mm(
        self,
        field_obj: Dict[str, Any],
        px_to_mm_scale: float,
        default_line_h_px: Optional[float] = None
    ) -> float:
        """
        Converts text bounding box dimensions to physical uppercase letter height (mm).
        Automatically handles multi-line declarations, constituent matched blocks, and vertical text.
        """
        if px_to_mm_scale <= 0 or not field_obj or not isinstance(field_obj, dict):
            return 0.0

        font_h_px = None

        # Method 1: Direct representative line font height stored on field
        if field_obj.get("font_height_px") and float(field_obj["font_height_px"]) > 0:
            font_h_px = float(field_obj["font_height_px"])

        # Method 2: Median across constituent line heights
        elif field_obj.get("line_heights_px") and len(field_obj["line_heights_px"]) > 0:
            font_h_px = float(np.median(field_obj["line_heights_px"]))

        # Method 3: Median across constituent matched blocks
        elif field_obj.get("matched_blocks") and len(field_obj["matched_blocks"]) > 0:
            heights = [float(b["rect"]["height"]) for b in field_obj["matched_blocks"] if b.get("rect") and b["rect"].get("height", 0) > 0]
            if heights:
                font_h_px = float(np.median(heights))

        # Method 4: Single block rect
        if font_h_px is None:
            rect = field_obj.get("rect") or {}
            w_px = float(rect.get("width", 0.0))
            h_px = float(rect.get("height", 0.0))
            text = field_obj.get("raw_text", "")

            if h_px > 0:
                is_vertical = field_obj.get("is_vertical", False) or (field_obj.get("angle", 0) in (90, 270)) or (h_px / max(1.0, w_px) > 2.2)
                if is_vertical:
                    font_h_px = w_px
                else:
                    num_lines = max(1, len(text.splitlines()))
                    font_h_px = h_px / float(num_lines)
            elif default_line_h_px and default_line_h_px > 0:
                font_h_px = default_line_h_px
            else:
                # Dynamic fallback: 1.5mm equivalent in pixels
                font_h_px = max(20.0, px_to_mm_scale * 1.5)

        # Standard typography: Cap height (uppercase letter height) ~ 0.72 of line bounding box
        letter_px = font_h_px * 0.72
        height_mm = letter_px / px_to_mm_scale
        return round(float(height_mm), 2)

    def determine_rule_7_3_min_height_mm(self, net_qty_field: Optional[Dict[str, Any]]) -> Tuple[float, str]:
        """
        Determines Legal Metrology Rule 7(3) minimum letter height requirement based on package size:
        - <= 50g / 50ml: 1.0mm
        - > 50g to 200g / ml: 2.0mm
        - > 200g to 500g / ml: 4.0mm
        - > 500g / ml: 6.0mm
        """
        if not net_qty_field or not isinstance(net_qty_field, dict):
            return 1.0, "Default (Tier <= 50g)"

        val = net_qty_field.get("numeric_value", 50.0)
        try:
            val = float(val)
        except (ValueError, TypeError):
            val = 50.0

        unit = str(net_qty_field.get("unit", "g")).lower()

        # Convert to grams or ml
        if unit == 'kg' or unit == 'l':
            qty_g = val * 1000.0
        else:
            qty_g = val

        if qty_g <= 50.0:
            return 1.0, "Tier <= 50g/ml (Min 1.0mm)"
        elif qty_g <= 200.0:
            return 2.0, "Tier 50g-200g/ml (Min 2.0mm)"
        elif qty_g <= 500.0:
            return 4.0, "Tier 200g-500g/ml (Min 4.0mm)"
        else:
            return 6.0, "Tier > 500g/ml (Min 6.0mm)"

    def analyze_legibility_and_prominence(
        self,
        image: Optional[np.ndarray],
        metadata: Dict[str, Any],
        classified_fields: Dict[str, Any],
        blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Executes complete Phase 3 legibility analysis:
        1. Scale calibration (px/mm)
        2. Letter height calculation (mm) for all declarations
        3. Rule 7(3) letter height tier check
        4. Rule 9(1) MRP prominence ratio check
        """
        scale_px_mm, scale_source = self.estimate_px_to_mm_scale(image, metadata, blocks)

        # Compute median body line height across all OCR blocks as reliable universal fallback
        all_block_heights = [
            float(b["rect"]["height"]) for b in blocks 
            if b.get("rect") and b["rect"].get("height", 0) > 8.0 and b.get("confidence", 0) >= 0.40
        ]
        median_body_line_h = float(np.median(all_block_heights)) if all_block_heights else 25.0

        # Calculate font height in mm for each classified declaration
        fields_font_mm: Dict[str, Optional[float]] = {}
        for field_name in ["mrp", "net_quantity", "mfg_date", "expiry_date", "manufacturer_details", "consumer_care", "commodity_name"]:
            field_obj = classified_fields.get(field_name)
            if field_obj and isinstance(field_obj, dict):
                h_mm = self.calculate_letter_height_mm(field_obj, scale_px_mm, default_line_h_px=median_body_line_h)
                field_obj["font_height_mm"] = h_mm
                fields_font_mm[field_name] = h_mm
            else:
                fields_font_mm[field_name] = None

        # Rule 7(3) Letter Height Verification
        min_required_mm, tier_label = self.determine_rule_7_3_min_height_mm(classified_fields.get("net_quantity"))
        
        rule_7_3_results = []
        compliant_fields_count = 0
        total_checked_fields = 0

        for field_name, h_mm in fields_font_mm.items():
            if h_mm is not None:
                total_checked_fields += 1
                is_pass = h_mm >= min_required_mm
                if is_pass:
                    compliant_fields_count += 1
                rule_7_3_results.append({
                    "field": field_name,
                    "font_height_mm": h_mm,
                    "min_required_mm": min_required_mm,
                    "status": "PASS" if is_pass else "WARNING",
                    "explanation": f"Letter height {h_mm}mm {'meets' if is_pass else 'is below'} required {min_required_mm}mm minimum."
                })

        # Rule 9(1) MRP Visual Prominence Ratio
        mrp_obj = classified_fields.get("mrp")
        mrp_h_mm = fields_font_mm.get("mrp")
        
        body_heights_mm = []
        for b in blocks:
            if b.get("confidence", 0) >= 0.50:
                body_heights_mm.append(self.calculate_letter_height_mm(b, scale_px_mm))

        avg_body_mm = round(float(np.mean(body_heights_mm)), 2) if body_heights_mm else 1.0
        prominence_ratio = round(mrp_h_mm / avg_body_mm, 2) if mrp_h_mm and avg_body_mm > 0 else 1.0

        is_mrp_prominent = prominence_ratio >= 1.2
        rule_9_1_report = {
            "mrp_font_height_mm": mrp_h_mm,
            "avg_body_font_height_mm": avg_body_mm,
            "prominence_ratio": prominence_ratio,
            "min_required_ratio": 1.2,
            "status": "PASS" if is_mrp_prominent else "WARNING",
            "explanation": f"MRP font size ({mrp_h_mm or 0}mm) is {prominence_ratio}x body text ({avg_body_mm}mm). {'Compliant with Rule 9(1)' if is_mrp_prominent else 'MRP should be larger than surrounding text'}"
        }

        return {
            "scale_px_mm": round(scale_px_mm, 2),
            "scale_calibration_source": scale_source,
            "rule_7_3_tier": tier_label,
            "min_required_letter_height_mm": min_required_mm,
            "field_font_heights_mm": fields_font_mm,
            "rule_7_3_field_evaluations": rule_7_3_results,
            "rule_9_1_mrp_prominence": rule_9_1_report
        }
