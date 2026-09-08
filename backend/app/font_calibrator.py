import logging
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("metrolens.font_calibrator")

class FontCalibrator:
    """
    Physical Scale Calibration & Font Size Measurement Engine for Legal Metrology.
    
    Converts OCR bounding box pixel heights to physical letter heights in millimeters (mm):
    - Barcode Calibration: Detects EAN-13 barcodes (standard physical width = 31.35mm).
    - Resolution Scale Fallback: Uses camera resolution metadata.
    - Rule 7(3): Package Weight Tier Font Size Verification (1.0mm, 2.0mm, 4.0mm, 6.0mm).
    - Rule 9(1): MRP Visual Prominence Ratio Check (h_mrp / h_body >= 1.2x).
    """

    # Standard EAN-13 Barcode Nominal Physical Width in mm
    EAN13_STANDARD_WIDTH_MM = 31.35

    def __init__(self):
        pass

    def estimate_px_to_mm_scale(self, image: np.ndarray, metadata: Dict[str, Any], blocks: List[Dict[str, Any]]) -> Tuple[float, str]:
        """
        Estimates the pixels-per-millimeter (px/mm) scale factor.
        """
        # Method A: Try PyZbar barcode detection
        try:
            from pyzbar import pyzbar
            barcodes = pyzbar.decode(image)
            for barcode in barcodes:
                rect = barcode.rect
                if rect.width > 20 and rect.height > 10:
                    scale = float(rect.width) / self.EAN13_STANDARD_WIDTH_MM
                    logger.info(f"Calibrated physical scale via Barcode Detection: {scale:.2f} px/mm ({rect.width}px = {self.EAN13_STANDARD_WIDTH_MM}mm)")
                    return scale, "EAN-13 Barcode Detection"
        except Exception as err:
            logger.debug(f"Barcode scale calibration skipped: {err}")

        # Method B: Fallback resolution scale
        # Assuming nominal label width ~100mm for camera photos scaled to 1600px
        img_w = metadata.get("width", 1600)
        img_h = metadata.get("height", 1200)
        max_dim = max(img_w, img_h)

        # Baseline: 1600px long edge on 100mm label width = 16.0 px/mm
        scale = max_dim / 100.0
        logger.info(f"Using resolution fallback scale calibration: {scale:.2f} px/mm")
        return scale, "Resolution Scale Model (1600px = 100mm)"

    def calculate_letter_height_mm(self, height_px: float, px_to_mm_scale: float) -> float:
        """
        Converts text bounding box height (px) to uppercase letter height (mm).
        Capital letter height is ~70% of total line box height.
        """
        if px_to_mm_scale <= 0:
            return 0.0
        letter_px = height_px * 0.70
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
        image: np.ndarray,
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

        # Calculate font height in mm for each classified declaration
        fields_font_mm = {}
        for field_name in ["mrp", "net_quantity", "mfg_date", "expiry_date", "manufacturer_details", "consumer_care", "commodity_name"]:
            field_obj = classified_fields.get(field_name)
            if field_obj and isinstance(field_obj, dict):
                rect = field_obj.get("rect") or {}
                h_px = rect.get("height", 12.0)
                h_mm = self.calculate_letter_height_mm(h_px, scale_px_mm)
                field_obj["font_height_px"] = h_px
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
                h_px = b.get("height_px", 12.0)
                body_heights_mm.append(self.calculate_letter_height_mm(h_px, scale_px_mm))

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
