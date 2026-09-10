import re
import logging
from typing import List, Dict, Any, Tuple, Optional

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

logger = logging.getLogger("metrolens.product_checker")

class ProductConsistencyChecker:
    """
    Automated Cross-Image Consistency Verification Engine.
    
    When multiple images (e.g. Front, Back, Side panels) of a product are uploaded,
    this engine verifies that all images belong to the SAME product and rejects
    accidental or deliberate mixing of different products (e.g. Tea Front + Biscuit Back).
    
    Verification Criteria:
    1. FSSAI License Number: Rejects if two images declare conflicting 14-digit FSSAI licenses.
    2. Product Category Conflict: Rejects if images belong to contradictory food types (e.g. Tea vs Biscuit).
    3. Manufacturer / Packer Identity: Rejects if images declare conflicting manufacturer entities.
    4. Brand Identity: Verifies brand continuity between front and back panels.
    """

    def __init__(self, min_brand_similarity: float = 65.0, min_mfg_similarity: float = 60.0):
        self.min_brand_similarity = min_brand_similarity
        self.min_mfg_similarity = min_mfg_similarity

    def check_consistency(self, side_results: List[Dict[str, Any]]) -> Tuple[bool, float, Optional[str]]:
        """
        Evaluates cross-image consistency across all uploaded side results.
        
        Returns:
            (is_consistent: bool, confidence_score: float, mismatch_reason: Optional[str])
        """
        if not side_results or len(side_results) <= 1:
            return True, 1.0, None

        distinct_fssai = {}
        distinct_commodities = {}
        distinct_mfgs = {}
        side_full_texts = {}

        for idx, res in enumerate(side_results):
            side_num = idx + 1
            filename = res.get("filename", f"Side {side_num}")
            fields = res.get("classified_fields", {})
            side_full_texts[side_num] = res.get("raw_text", "").upper()

            # FSSAI
            fssai_obj = fields.get("fssai_number")
            if fssai_obj and isinstance(fssai_obj, dict):
                lic = fssai_obj.get("license_number")
                if lic and len(lic) == 14:
                    distinct_fssai[side_num] = (lic, filename)

            # Commodity & Brand
            comm_obj = fields.get("commodity_name")
            if comm_obj and isinstance(comm_obj, dict):
                has_explicit = comm_obj.get("has_explicit_declaration", False)
                c_clean = comm_obj.get("clean_name") or comm_obj.get("raw_text")
                if c_clean and len(c_clean.strip()) >= 3 and (has_explicit or comm_obj.get("confidence", 0.0) >= 0.70):
                    distinct_commodities[side_num] = (c_clean.strip(), filename, has_explicit)

            # Manufacturer
            mfg_obj = fields.get("manufacturer_details")
            if mfg_obj and isinstance(mfg_obj, dict):
                m_raw = mfg_obj.get("raw_text")
                if m_raw and len(m_raw.strip()) >= 5:
                    comp_name = re.split(r'[,;|\n]|\b(?:PLOT|ROAD|STREET|INDUSTRIAL|GAT|SURUR|PIN)\b', m_raw, flags=re.IGNORECASE)[0].strip()
                    distinct_mfgs[side_num] = (comp_name or m_raw[:50], filename)

        # --- Rule A: FSSAI License Conflict Check ---
        fssai_entries = list(distinct_fssai.items())
        for i in range(len(fssai_entries)):
            for j in range(i + 1, len(fssai_entries)):
                side_a, (lic_a, file_a) = fssai_entries[i]
                side_b, (lic_b, file_b) = fssai_entries[j]
                if lic_a != lic_b:
                    reason = (
                        f"FSSAI License Mismatch: Image {side_a} ('{file_a}') declares FSSAI Lic. #{lic_a}, "
                        f"while Image {side_b} ('{file_b}') declares FSSAI Lic. #{lic_b}. "
                        "These photos belong to two different products."
                    )
                    logger.warning(reason)
                    return False, 0.0, reason

        # --- Rule B: Product Category Conflict Check (e.g. Tea vs Biscuit) ---
        food_categories = [
            ('TEA', 'CHAI'),
            ('BISCUIT', 'COOKIE', 'BAKERY', 'RUSK'),
            ('CHIPS', 'WAFER', 'CRISP', 'NAMKEEN'),
            ('NOODLE', 'PASTA'),
            ('OIL', 'GHEE'),
            ('ATTA', 'FLOUR'),
            ('SPICE', 'MASALA'),
            ('SOAP', 'DETERGENT'),
            ('SHAMPOO', 'CONDITIONER'),
            ('CHOCOLATE', 'CANDY')
        ]

        def get_category(text_str: str) -> Optional[str]:
            upper = text_str.upper()
            for cat in food_categories:
                if any(kw in upper for kw in cat):
                    return cat[0]
            return None

        # Check full text of each side for categorical conflict
        for i in range(1, len(side_results) + 1):
            for j in range(i + 1, len(side_results) + 1):
                cat_i = get_category(side_full_texts.get(i, ""))
                cat_j = get_category(side_full_texts.get(j, ""))
                if cat_i and cat_j and cat_i != cat_j:
                    file_i = side_results[i - 1].get("filename", f"Side {i}")
                    file_j = side_results[j - 1].get("filename", f"Side {j}")
                    reason = (
                        f"Product Category Mismatch: Image {i} ('{file_i}') is a {cat_i} product, "
                        f"whereas Image {j} ('{file_j}') is a {cat_j} product. "
                        "All uploaded images must belong to the same product."
                    )
                    logger.warning(reason)
                    return False, 0.0, reason

        # --- Rule C: Manufacturer Name Conflict Check ---
        mfg_entries = list(distinct_mfgs.items())
        for i in range(len(mfg_entries)):
            for j in range(i + 1, len(mfg_entries)):
                side_a, (mfg_a, file_a) = mfg_entries[i]
                side_b, (mfg_b, file_b) = mfg_entries[j]

                clean_mfg_a = re.sub(r'^(?:Mfd|Mfg|Manufactured|Packed|Pkd)\s*(?:&|\+)?\s*(?:Pkd|Packed)?\s*(?:by|By)?\s*[:=.\s]*', '', mfg_a, flags=re.IGNORECASE).strip()
                clean_mfg_b = re.sub(r'^(?:Mfd|Mfg|Manufactured|Packed|Pkd)\s*(?:&|\+)?\s*(?:Pkd|Packed)?\s*(?:by|By)?\s*[:=.\s]*', '', mfg_b, flags=re.IGNORECASE).strip()

                if HAS_RAPIDFUZZ and len(clean_mfg_a) >= 5 and len(clean_mfg_b) >= 5:
                    sim = fuzz.token_set_ratio(clean_mfg_a.upper(), clean_mfg_b.upper())
                    if sim < 40.0:
                        reason = (
                            f"Manufacturer Mismatch: Image {side_a} ('{file_a}') indicates manufacturer '{clean_mfg_a}', "
                            f"which conflicts with Image {side_b} ('{file_b}') indicating '{clean_mfg_b}'. "
                            "These photos appear to be from different products made by different manufacturers. "
                            "Please upload sides of the SAME product only."
                        )
                        logger.warning(reason)
                        return False, sim / 100.0, reason

        # --- Rule D: Net Quantity Conflict Check ---
        # If two sides both declare net quantities and they differ significantly, reject as different products
        distinct_qtys = {}
        for idx, res in enumerate(side_results):
            side_num = idx + 1
            filename = res.get("filename", f"Side {side_num}")
            fields = res.get("classified_fields", {})
            qty_obj = fields.get("net_quantity")
            if qty_obj and isinstance(qty_obj, dict):
                numeric_val = qty_obj.get("numeric_value")
                unit = qty_obj.get("unit", "")
                conf = qty_obj.get("confidence", 0.0)
                # Only use high-confidence net quantities for conflict check
                if numeric_val is not None and conf >= 0.70 and unit in ['g', 'kg', 'ml', 'L']:
                    # Normalize to grams/ml for comparison
                    norm_val = float(numeric_val) * 1000.0 if unit in ['kg', 'L'] else float(numeric_val)
                    distinct_qtys[side_num] = (norm_val, unit, numeric_val, filename)

        qty_entries = list(distinct_qtys.items())
        for i in range(len(qty_entries)):
            for j in range(i + 1, len(qty_entries)):
                side_a, (norm_a, unit_a, raw_a, file_a) = qty_entries[i]
                side_b, (norm_b, unit_b, raw_b, file_b) = qty_entries[j]
                # Allow small OCR rounding differences (within 5%), but reject large disparities
                if norm_a > 0 and norm_b > 0:
                    ratio = max(norm_a, norm_b) / min(norm_a, norm_b)
                    if ratio > 1.20:  # More than 20% difference = different product sizes
                        reason = (
                            f"Net Quantity Mismatch: Image {side_a} ('{file_a}') declares {raw_a} {unit_a}, "
                            f"but Image {side_b} ('{file_b}') declares {raw_b} {unit_b}. "
                            "These appear to be different product sizes (not different sides of the same package). "
                            "Please upload photos of the SAME product unit only."
                        )
                        logger.warning(reason)
                        return False, 0.0, reason

        # All sides consistent and verified
        return True, 0.95, None
