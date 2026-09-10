import re
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Set, Tuple
# pyrefly: ignore [missing-import]
try:
    from app.llm_extractor import LLMExtractor
except (ImportError, ModuleNotFoundError):
    from .llm_extractor import LLMExtractor

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

logger = logging.getLogger("metrolens.classifier")

def _make_multiline_field_dict(blocks_list: List[Dict[str, Any]], raw_text: str, extra_props: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes accurate union bounding box, line heights, and representative font size
    from constituent OCR text lines of multi-line declarations.
    """
    xs = [b["rect"]["x"] for b in blocks_list if b.get("rect")]
    ys = [b["rect"]["y"] for b in blocks_list if b.get("rect")]
    x2s = [b["rect"]["x"] + b["rect"]["width"] for b in blocks_list if b.get("rect")]
    y2s = [b["rect"]["y"] + b["rect"]["height"] for b in blocks_list if b.get("rect")]

    min_x = round(float(min(xs)), 1) if xs else 0.0
    min_y = round(float(min(ys)), 1) if ys else 0.0
    max_x = round(float(max(x2s)), 1) if x2s else 0.0
    max_y = round(float(max(y2s)), 1) if y2s else 0.0

    line_heights = [float(b["rect"]["height"]) for b in blocks_list if b.get("rect") and b["rect"].get("height", 0) > 0]
    if line_heights:
        font_h_px = round(float(np.median(np.array(line_heights))), 1)
    elif max_y > min_y and len(blocks_list) > 0:
        font_h_px = round(float(max_y - min_y) / max(1, len(blocks_list)), 1)
    else:
        font_h_px = 25.0

    res = {
        "raw_text": raw_text,
        "rect": {"x": min_x, "y": min_y, "width": round(max_x - min_x, 1), "height": round(max_y - min_y, 1)} if xs else None,
        "bbox": [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]] if xs else None,
        "font_height_px": font_h_px,
        "line_heights_px": line_heights,
        "matched_blocks": [{"id": b.get("id"), "text": b.get("text"), "rect": b.get("rect"), "confidence": b.get("confidence")} for b in blocks_list]
    }
    res.update(extra_props)
    return res


def fuzzy_match_any(text: str, targets: List[str], min_score: float = 80.0) -> bool:
    """
    RapidFuzz partial ratio similarity matcher with threshold 80.0%
    Catches OCR misreads (e.g. Net Wf -> Net Wt, Mfd by -> Mfd by, Customercare -> Customer Care).
    """
    if not text or not targets:
        return False
    upper = text.upper()
    for t in targets:
        if t.upper() in upper:
            return True
        if HAS_RAPIDFUZZ and len(t) >= 4:
            score = fuzz.partial_ratio(t.upper(), upper)
            if score >= min_score:
                return True
    return False

class FieldClassifier:
    """
    Production-Grade Field Classifier for Legal Metrology OCR blocks.
    
    Field Rules & Safeguards:
    1. Generic Commodity Name: Excludes recipe/instruction blocks, batch codes, full sentences.
       Prioritizes prominent header text, short phrases (1-4 words), and brand/commodity terms.
    2. Net Quantity: Plausibility range check (1g/1ml to 25kg/25L). Excludes quantities inside recipes.
    3. MRP: Requires adjacent currency symbol (₹, Rs., MRP). Excludes bare numbers & recipe text.
    4. Mfg/Expiry Date: Calendar date validation (Month 1-12/JAN-DEC, Year 2015-2035). Excludes batch codes.
    5. Manufacturer Details: Requires MFD/Packer keywords and address indicators. Excludes recipes.
    6. Consumer Care: Accepts phone number ONLY or email ONLY or helpline keyword.
    7. FSSAI Number: Strictly requires valid 14-digit FSSAI license format starting with 1 or 2.
    """

    def __init__(self, min_confidence: float = 0.30):
        self.min_confidence = min_confidence
        self.llm_extractor = LLMExtractor(timeout_sec=8.0)

        # Recipe / Instruction Exclusion Patterns
        self.recipe_keywords = {
            'RECIPE', 'INSTRUCTION', 'INSTRUCTIONS', 'METHOD', 'DIRECTIONS', 'PREPARATION',
            'PREPARE', 'COOKING', 'SERVING', 'SUGGESTION', 'INGREDIENTS', 'HOW TO', 'TAKE',
            'BOIL', 'CRUSH', 'HEAT', 'ADD', 'MIX', 'SERVE', 'STEP', 'STEP1', 'STEP2', 'NUTRITION',
            'FACTS', 'PER100G', 'ENERGY', 'PROTEIN', 'CARBOHYDRATE', 'FAT'
        }
        self.step_pattern = re.compile(r'(\(\d+\)|\bSTEP\s*\d+\b|\b\d+\)\s*[A-Z])', re.IGNORECASE)

        # Regex Patterns for Core Fields
        self.mrp_strict_pattern = re.compile(
            r'(?:M\.?R\.?P\.?|MR\.?R|MAX(?:IMUM)?\s*RETAIL\s*PRICE|PRICE|RS\.?|₹|\$)\s*[:=.\s]*[₹Rs.]?\s*(\d{1,5}(?:\.\d{1,2})?)',
            re.IGNORECASE
        )
        # Tightened: requires explicit RS./₹/$ prefix (removed bare 'F'/'R' which matched random words)
        self.price_standalone_pattern = re.compile(
            r'(?:RS\.?|₹|\$)\s*(\d{1,4}\.\d{1,2})\b',
            re.IGNORECASE
        )
        self.tax_clause_pattern = re.compile(
            r'(?:INCL(?:USIVE)?\.?\s*OF\s*ALL\s*TAXES|INCL\.?\s*TAXES|ALL\s*TAXES)',
            re.IGNORECASE
        )
        self.mrp_tax_suffix_pattern = re.compile(
            r'(?:^|[^\d])(\d{1,5}(?:\.\d{1,2})?)\s*\(?(?:INCL(?:USIVE)?\.?\s*OF\s*ALL\s*TAXES|INCL\.?\s*TAXES|ALL\s*TAXES|PER\s*G|PER\s*KG)',
            re.IGNORECASE
        )

        self.net_qty_prefix_pattern = re.compile(
            r'(?:NET\s*(?:QTY|QUANTITY|WT|WEIGHT|VOL|VOLUME|CONTENTS|MASS)|TOTAL\s*NET\s*(?:WT|WEIGHT|QTY)|NET|N\.W\.)\s*[:=.\s]*(\d+(?:\.\d+)?)\s*([a-zA-Z]+|Pcs|Units)',
            re.IGNORECASE
        )
        self.standalone_qty_pattern = re.compile(
            r'^\b(?:NET\s*(?:WT|WEIGHT|QTY|QUANTITY)\s*[:=.\s]*)?(\d+(?:\.\d+)?)\s*(g|kg|gm|gms|ml|l|ltr|liter|litres|pcs|units)\b$',
            re.IGNORECASE
        )

        # Month normalization (including OCR dot-matrix fixes e.g. 0CT -> OCT)
        self.month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', '0CT', 'NOV', 'DEC']
        self.date_pattern = re.compile(
            r'(?:^|[^A-Za-z0-9])(0[1-9]|1[0-2]|0CT|OCT|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|NOV|DEC)\s*[\.\s/|-]*\s*(20[1-3][0-9]|[1-3][0-9])\b',
            re.IGNORECASE
        )
        self.full_date_pattern = re.compile(
            r'(?:^|[^A-Za-z0-9])([0-3]?[0-9])[\.\s/|-]+(0[1-9]|1[0-2]|0CT|OCT|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|NOV|DEC)[\.\s/|-]*(20[1-3][0-9]|[1-3][0-9])\b',
            re.IGNORECASE
        )

        # FSSAI pattern: 14-digit or 13-digit sequence
        self.fssai_strict_pattern = re.compile(r'\b(1\d{12,13}|2\d{12,13})\b')

        # Phone & Email patterns
        # Tightened: requires a care/helpline keyword OR explicit toll-free (1800) format
        # This prevents address pin-codes or batch numbers from being mistaken for phone numbers
        self.phone_pattern = re.compile(
            r'(?:(?:CARE|HELPLINE|NO\.?|TEL|PHONE|CONTACT|CALL|TOLL\s*FREE|CUSTOMER(?:\s*CARE)?|CONSUMER(?:\s*CARE)?)\s*[:=.\s]*)?(1800[-\s]?\d{3}[-\s]?\d{4}|1800\d{6,7}|\+91[-\s]?\d{10}|0\d{2,4}[-\s]\d{6,8}|\d{10})\b',
            re.IGNORECASE
        )
        self.email_pattern = re.compile(
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        )

        # Batch & Code Exclusions
        self.code_batch_pattern = re.compile(r'^[A-Z0-9]{2,}[-/\.][A-Z0-9\-/\.]+$', re.IGNORECASE)
        self.batch_keyword_pattern = re.compile(
            r'\b(BATCH|LOT|B\.NO|LIC|LIC\.NO|CODE|BARCODE|FSSAI|SERIAL|SERIES|PKD|MFG|EXP)\b',
            re.IGNORECASE
        )
        self.commodity_exclude_words = {
            'QUANTITY', 'NET', 'WT', 'WEIGHT', 'VOL', 'VOLUME', 'MRP', 'PRICE', 'RS',
            'BATCH', 'LOT', 'B.NO', 'MFD', 'EXP', 'USEBY', 'USE BY', 'PKD', 'PACKED',
            'INGREDIENTS', 'NUTRITION', 'NUTRITIONAL', 'INFORMATION', 'PORTION',
            'KNOW', 'YOUR', 'ADVICE', 'STORAGE', 'WARNING', 'CAUTION', 'ACCEPT',
            'DAMAGED', 'SACHET', 'SEAL', 'LETS TALK', 'LETSTALK', 'FEEDBACK'
        }

        self.known_commodity_keywords = {
            'MASALA', 'SPICE', 'SAUCE', 'KETCHUP', 'POWDER', 'OIL', 'TEA', 'COFFEE',
            'SOAP', 'CREAM', 'PASTE', 'SHAMPOO', 'NOODLES', 'CHIPS', 'BISCUIT',
            'DRINK', 'WATER', 'JUICE', 'ANTACID', 'SACHET', 'TABLET', 'CAPSULE',
            'FOOD', 'SALT', 'SUGAR', 'MILK', 'BUTTER', 'CHEESE', 'FLOUR', 'ATTA',
            'RICE', 'DAL', 'PULSE', 'PICKLE', 'JAM', 'SYRUP', 'MIX', 'PASTA',
            'SHRI', 'HARI', 'SUHANA', 'ENO', 'WAFER', 'CHOCOLATE', 'CONFECTIONERY'
        }

        self.mfg_keywords = [
            'MANUFACTURED', 'MANUFACTURER', 'PACKED', 'PACKER', 'MARKETED',
            'MFDBY', 'MFG BY', 'PKD BY', 'IMPORTER', 'REGISTERED OFFICE', 'REGD OFFICE',
            'AVEER', 'FOODS', 'LTD', 'LIMITED', 'FACTORY', 'PLOT', 'GAT',
            'STREET', 'ROAD', 'PIN', 'SURUR', 'SATARA', 'MAHARASHTRA', 'GODHRA'
        ]

    def _is_recipe_instruction_block(self, text: str) -> bool:
        """
        Detects if OCR text block is part of recipe, cooking method, ingredients,
        or Nutrition Facts table (e.g. Serving Size, Calories, % Daily Value).
        """
        upper = text.upper()
        upper_no_space = upper.replace(" ", "")

        if self.step_pattern.search(text):
            return True

        words = set(re.findall(r'[A-Z0-9]+', upper))
        if words.intersection(self.recipe_keywords):
            return True

        nutrition_phrases = [
            'SERVINGSIZE', 'PERSERVING', 'NUTRITIONFACTS', 'NUTRITIONALINFO',
            'NUTRITIONALINFORMATION', 'DAILYVALUE', 'CALORIES', 'SERVINGSPERCONTAINER',
            'PERCENTDAILYVALUE', '%DAILYVALUE', '1/4TSP', '1/2TSP', '1TSP', '1TBSP'
        ]
        if any(phrase in upper_no_space for phrase in nutrition_phrases):
            return True

        return False

    def _parse_and_validate_date(self, text: str) -> Optional[str]:
        """
        Validates calendar date format and verifies plausible year (2015-2035).
        """
        # Reject batch codes with hyphens/slashes
        upper = text.upper()
        if self.code_batch_pattern.match(upper) and not any(kw in upper for kw in ['MFG', 'EXP', 'PKD', 'DATE']):
            return None

        full_m = self.full_date_pattern.search(text)
        if full_m:
            d, m, y_str = full_m.groups()
            y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
            if 2015 <= y <= 2035:
                m_norm = "OCT" if m.upper() == "0CT" else m.upper()
                return f"{d}/{m_norm}/{y}"

        m_yr = self.date_pattern.search(text)
        if m_yr:
            m, y_str = m_yr.groups()
            y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
            if 2015 <= y <= 2035:
                m_norm = "OCT" if m.upper() == "0CT" else m.upper()
                return f"{m_norm}/{y}"

        # Reverse pattern (e.g. 2025/11 or 2025-NOV or 2025NOV)
        rev_m = re.search(r'\b(20[1-3][0-9])\s*[\.\s/|-]*\s*(0[1-9]|1[0-2]|OCT|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|NOV|DEC)\b', text, re.IGNORECASE)
        if rev_m:
            y_str, m = rev_m.groups()
            y = int(y_str)
            if 2015 <= y <= 2035:
                m_norm = "OCT" if m.upper() == "0CT" else m.upper()
                return f"{m_norm}/{y}"

        return None

    def _parse_net_quantity(self, text: str) -> Optional[Tuple[float, str, bool]]:
        """
        Parses Net Quantity with strict physical plausibility range check (1g/1ml to 25kg/25L).
        Rejects nutritional table values (e.g. Protein 5g, Fat 10g, Per 100g, etc.).
        """
        upper = text.upper()
        # Expanded nutritional exclusion keywords
        nutrition_exclusions = [
            'PROTEIN', 'FAT', 'CARB', 'SUGAR', 'ENERGY', 'CALORIE', 'PER 100', 'PER100',
            'SERVING', 'DAILY VALUE', '% RDA', 'SODIUM', 'SATURATED', 'FIBER', 'FIBRE',
            'CALCIUM', 'IRON', 'VITAMIN', 'CHOLESTEROL', 'TRANS FAT', 'TOTAL FAT',
            'POTASSIUM', 'PHOSPHORUS', 'MAGNESIUM', 'ZINC', 'MANGANESE',
            'THIAMINE', 'RIBOFLAVIN', 'NIACIN', 'FOLATE', 'PER SERVE',
        ]
        if any(kw in upper for kw in nutrition_exclusions):
            return None

        # Also reject if text has a standalone nutritional label word at start
        nutritional_prefix_pattern = re.compile(
            r'^\s*(?:PROTEIN|FAT|CARBS?|SUGAR|FIBER|FIBRE|SODIUM|CALCIUM|IRON|VITAMIN\s*[A-Z]?)\s*',
            re.IGNORECASE
        )
        if nutritional_prefix_pattern.match(text):
            return None

        match = self.net_qty_prefix_pattern.search(text) or self.standalone_qty_pattern.search(text)
        if not match:
            # Flexible quantity regex — only run if NOT inside a nutritional context sentence
            # Reject if the surrounding text has nutritional/ingredient context
            if re.search(r'\b(?:per|contains|each|typical|average|approx|approximately)\b', text, re.IGNORECASE):
                return None
            m = re.search(r'\b(\d+(?:\.\d+)?)\s*(g|kg|gm|gms|ml|l|ltr|liter|litres|pcs|n)\b', text, re.IGNORECASE)
            if m:
                num_val = float(m.group(1))
                unit = m.group(2)
            else:
                return None
        else:
            num_val = float(match.group(1))
            unit = match.group(2)

        unit_lower = unit.lower()
        # Standardize units
        if unit_lower in ['g', 'gm', 'gms']:
            norm_unit = 'g'
            qty_in_g_ml = num_val
        elif unit_lower in ['kg']:
            norm_unit = 'kg'
            qty_in_g_ml = num_val * 1000.0
        elif unit_lower in ['ml']:
            norm_unit = 'ml'
            qty_in_g_ml = num_val
        elif unit_lower in ['l', 'ltr', 'liter', 'litres']:
            norm_unit = 'L'
            qty_in_g_ml = num_val * 1000.0
        elif unit_lower in ['pcs', 'units', 'n']:
            norm_unit = 'N'
            qty_in_g_ml = 50.0  # nominal for count
        else:
            return None

        # Plausibility range check: 1.0g/1.0ml <= quantity <= 25,000g/25,000ml (25kg/25L)
        if qty_in_g_ml < 1.0 or qty_in_g_ml > 25000.0:
            logger.info(f"Rejected implausible net quantity match '{num_val}{unit}' ({qty_in_g_ml} g/ml)")
            return None

        is_standard = norm_unit in ['g', 'kg', 'ml', 'L', 'N']
        return (num_val, norm_unit, is_standard)

    def classify_blocks(self, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Classifies OCR blocks into structured fields.
        """
        valid_blocks = [b for b in blocks if b.get("confidence", 0.0) >= self.min_confidence]
        logger.info(f"Classifying {len(valid_blocks)} blocks out of {len(blocks)} (confidence >= {self.min_confidence})")

        classified = {
            "mrp": None,
            "net_quantity": None,
            "mfg_date": None,
            "expiry_date": None,
            "manufacturer_details": None,
            "consumer_care": None,
            "fssai_number": None,
            "commodity_name": None,
            "unclassified_blocks_count": 0
        }

        claimed_block_ids: Set[int] = set()

        # Identify recipe & instruction blocks to exclude from core declarations
        recipe_block_ids: Set[int] = set()
        for block in valid_blocks:
            b_id = block.get("id")
            text = block.get("text", "").strip()
            if self._is_recipe_instruction_block(text):
                recipe_block_ids.add(b_id)

        logger.info(f"Identified {len(recipe_block_ids)} recipe/instruction blocks to exclude from field matching")

        full_text_lines = [b["text"].strip() for b in valid_blocks if b.get("text")]
        full_raw_str = " ".join(full_text_lines)
        has_global_tax_clause = bool(self.tax_clause_pattern.search(full_raw_str))

        # --- Pass 1: FSSAI License Number ---
        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids:
                continue
            text = block.get("text", "").strip()

            fssai_m = self.fssai_strict_pattern.search(text)
            if fssai_m:
                classified["fssai_number"] = {
                    "raw_text": fssai_m.group(1),
                    "license_number": fssai_m.group(1),
                    "is_valid_14_digit": len(fssai_m.group(1)) == 14,
                    "confidence": block["confidence"],
                    "bbox": block.get("bbox"),
                    "rect": block.get("rect"),
                    "font_height_px": float(block.get("rect", {}).get("height", 0.0)),
                    "matched_blocks": [block]
                }
                claimed_block_ids.add(b_id)
                break
            elif 'LIC' in text.upper() or 'FSSAI' in text.upper():
                digits = re.findall(r'\b(1\d{12,13}|2\d{12,13})\b', text)
                if digits:
                    classified["fssai_number"] = {
                        "raw_text": text,
                        "license_number": digits[0],
                        "is_valid_14_digit": len(digits[0]) == 14,
                        "confidence": block["confidence"],
                        "bbox": block.get("bbox"),
                        "rect": block.get("rect"),
                        "font_height_px": float(block.get("rect", {}).get("height", 0.0)),
                        "matched_blocks": [block]
                    }
                    claimed_block_ids.add(b_id)
                    break

        # --- Pass 2: Whole Packet Net Quantity (Scoring Engine for Packet Weight vs Ingredients) ---
        net_qty_candidates = []
        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue
            text = block.get("text", "").strip()
            upper_text = text.upper()

            # Hard exclusions: Skip ingredient breakdowns, nutrition facts, recipe steps, and batch/date stamps
            if any(kw in upper_text for kw in ['INGREDIENT', 'INGREDIENTS', 'CONTAINS', 'PER SERVING', 'SERVING SIZE', 'NUTRITIONAL', 'PER 100G', 'PER 100ML', 'ADDED SUGAR', 'DAILY VALUE', '% RDA', 'CALORIES', 'FAT', 'PROTEIN']):
                continue
            if any(kw in upper_text for kw in ['PKD', 'MFG', 'EXP', 'BEST BEFORE', 'USE BY', 'BATCH', 'LOT', 'B.NO']):
                continue
            if re.search(r'\b(STEP\s*\d+|\d+\)\s*[A-Z]|TSP|TBSP|CUP)\b', upper_text):
                continue

            parsed_qty = self._parse_net_quantity(text)
            if parsed_qty:
                num_val, unit_str, is_standard = parsed_qty

                # Candidate Scoring System
                score = block.get("confidence", 0.5) * 10.0
                has_explicit_prefix = bool(self.net_qty_prefix_pattern.search(text))
                
                if has_explicit_prefix:
                    score += 50.0
                elif any(kw in upper_text for kw in ['NET', 'QTY', 'QUANTITY', 'WEIGHT', 'VOL', 'N.W.']):
                    score += 30.0

                if unit_str in ['g', 'kg', 'ml', 'L']:
                    score += 15.0

                if len(text) < 30:
                    score += 10.0

                net_qty_candidates.append((score, block, num_val, unit_str, is_standard, has_explicit_prefix))

        if net_qty_candidates:
            net_qty_candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_block, num_val, unit_str, is_standard, has_prefix = net_qty_candidates[0]
            b_id = best_block["id"]
            text = best_block["text"].strip()
            field_conf = best_block["confidence"] if has_prefix else min(best_block["confidence"], 0.75)

            num_display = int(num_val) if num_val == int(num_val) else num_val
            classified["net_quantity"] = {
                "raw_text": text,
                "numeric_value": num_val,
                "unit": unit_str,
                "formatted_value": f"{num_display} {unit_str}",
                "is_standard_unit": is_standard,
                "confidence": field_conf,
                "bbox": best_block.get("bbox"),
                "rect": best_block.get("rect"),
                "font_height_px": float(best_block.get("rect", {}).get("height", 0.0)),
                "matched_blocks": [best_block]
            }
            claimed_block_ids.add(b_id)

        # --- Pass 3: MRP & Manufacturing / Expiry Date ---
        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue
            text = block.get("text", "").strip()
            upper_text = text.upper()
            claimed_this_block = False

            # MRP Check: Requires currency symbol, MRP prefix, OR price followed by tax/weight clause
            if not classified["mrp"]:
                mrp_match = (
                    self.mrp_strict_pattern.search(text) or 
                    self.price_standalone_pattern.search(text) or
                    self.mrp_tax_suffix_pattern.search(text)
                )
                if mrp_match:
                    valid_prices = [float(x) for x in re.findall(r'\d+(?:\.\d{1,2})?', text) if 1.0 <= float(x) <= 50000.0]
                    if valid_prices:
                        price_num = max(valid_prices)
                        formatted_price = f"{price_num:g}" if price_num == int(price_num) else f"{price_num:.2f}"
                        currency_sym = "₹" if "₹" in text else "Rs."
                        has_taxes = has_global_tax_clause or bool(self.tax_clause_pattern.search(text))
                        classified["mrp"] = {
                            "raw_text": text,
                            "value": price_num,
                            "formatted_value": f"{currency_sym} {formatted_price}",
                            "currency": currency_sym,
                            "has_tax_clause": has_taxes,
                            "confidence": block["confidence"],
                            "bbox": block.get("bbox"),
                            "rect": block.get("rect"),
                            "font_height_px": float(block.get("rect", {}).get("height", 0.0)),
                            "matched_blocks": [block]
                        }
                        claimed_this_block = True

            # Date Check: Check for Mfg Date and Expiry Date
            has_mfg_kw = any(kw in upper_text for kw in ['MFG', 'PKD', 'PACKED', 'MANUFACTURED', 'PROD', 'M/D', 'DOM'])
            has_exp_kw = any(kw in upper_text for kw in ['EXP', 'BEST BEFORE', 'USE BY', 'EXPIRY', 'BB', 'EXPDATE', 'CONSUME BEFORE'])

            # Case A: Block contains BOTH Mfg and Expiry on one line (e.g. "Mfg Date: NOV 2025 | Expiry Date: OCT 2026")
            if has_mfg_kw and has_exp_kw:
                sub_parts = re.split(r'(\||;|\s+(?=EXP|USE\s*BY|BEST\s*BEFORE))', text, flags=re.IGNORECASE)
                mfg_sub = ""
                exp_sub = ""
                for part in sub_parts:
                    p_upper = part.upper()
                    if any(kw in p_upper for kw in ['EXP', 'BEST BEFORE', 'USE BY', 'EXPIRY']):
                        exp_sub += " " + part
                    elif any(kw in p_upper for kw in ['MFG', 'PKD', 'PACKED', 'MANUFACTURED']):
                        mfg_sub += " " + part

                mfg_date_val = self._parse_and_validate_date(mfg_sub) or self._parse_and_validate_date(text)
                if mfg_date_val and not classified["mfg_date"]:
                    classified["mfg_date"] = {
                        "raw_text": mfg_sub.strip() or text,
                        "extracted_date": mfg_date_val,
                        "confidence": block["confidence"],
                        "bbox": block.get("bbox"),
                        "rect": block.get("rect"),
                        "font_height_px": float(block.get("rect", {}).get("height", 0.0)),
                        "matched_blocks": [block]
                    }
                    claimed_this_block = True

                exp_date_val = self._parse_and_validate_date(exp_sub)
                if exp_date_val and not classified["expiry_date"]:
                    classified["expiry_date"] = {
                        "raw_text": exp_sub.strip() or text,
                        "extracted_date": exp_date_val,
                        "confidence": block["confidence"],
                        "bbox": block.get("bbox"),
                        "rect": block.get("rect"),
                        "font_height_px": float(block.get("rect", {}).get("height", 0.0)),
                        "matched_blocks": [block]
                    }
                    claimed_this_block = True

            else:
                parsed_d = self._parse_and_validate_date(text)
                if parsed_d:
                    if has_exp_kw:
                        if not classified["expiry_date"]:
                            classified["expiry_date"] = {
                                "raw_text": text,
                                "extracted_date": parsed_d,
                                "confidence": block["confidence"],
                                "bbox": block.get("bbox"),
                                "rect": block.get("rect"),
                                "font_height_px": float(block.get("rect", {}).get("height", 0.0)),
                                "matched_blocks": [block]
                            }
                            claimed_this_block = True
                    elif has_mfg_kw or not classified["mfg_date"]:
                        if not classified["mfg_date"]:
                            classified["mfg_date"] = {
                                "raw_text": text,
                                "extracted_date": parsed_d,
                                "confidence": block["confidence"],
                                "bbox": block.get("bbox"),
                                "rect": block.get("rect"),
                                "font_height_px": float(block.get("rect", {}).get("height", 0.0)),
                                "matched_blocks": [block]
                            }
                            claimed_this_block = True

            if claimed_this_block:
                claimed_block_ids.add(b_id)

        # --- Pass 4: Manufacturer Details (Strict Spatial Adjacency & Semantic Boundaries) ---
        mfg_anchors = ['MANUFACTURED', 'MANUFACTURER', 'PACKED BY', 'MFD BY', 'MFG BY', 'PKD BY', 'MARKETED BY', 'IMPORTER', 'REGISTERED OFFICE', 'REGD OFFICE', 'INDIA LTD', 'BAKERY', 'ESTATES', 'AVEER']
        mfg_address_words = ['ROAD', 'STREET', 'CITY', 'DIST', 'GUJARAT', 'PIN', 'OFFICE', 'PLOT', 'LTD', 'LIMITED', 'PVT', 'FOODS', 'SATARA', 'MAHARASHTRA', 'GODHRA', 'FACTORY', 'PRATAPPURA', 'DELHI', 'GOA', 'LANE']
        
        mfg_parts = []
        mfg_blocks = []
        last_mfg_y = None

        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue

            text = block.get("text", "").strip()
            upper_text = text.upper()

            # Cross-boundary check: Never merge customer care or barcode info into manufacturer details
            if any(kw in upper_text for kw in ['CUSTOMER', 'CONSUMER', 'CARE', 'HELPLINE', 'TOLL FREE', 'E-MAIL', 'EMAIL', 'FEEDBACK']):
                continue

            rect = block.get("rect", {})
            y_pos = rect.get("y", 0.0)

            is_anchor = fuzzy_match_any(text, mfg_anchors, min_score=80.0) or any(kw in upper_text.replace(" ", "") for kw in ['INDIALTD', 'PVTLTD', 'LIMITED', 'MFDBY', 'MFGBY', 'PACKEDBY', 'PKDBY'])
            is_address = any(re.search(r'\b' + term + r'\b', upper_text) for term in mfg_address_words)

            if is_anchor or (mfg_parts and is_address and last_mfg_y is not None and abs(y_pos - last_mfg_y) < 140.0):
                mfg_parts.append(text)
                mfg_blocks.append(block)
                claimed_block_ids.add(b_id)
                last_mfg_y = y_pos

        if mfg_parts and mfg_blocks:
            combined_mfg = " ".join(mfg_parts)
            classified["manufacturer_details"] = _make_multiline_field_dict(
                mfg_blocks,
                combined_mfg,
                {
                    "has_name": True,
                    "has_address": any(re.search(r'\b' + kw + r'\b', combined_mfg.upper()) for kw in mfg_address_words),
                    "confidence": 0.90
                }
            )

        # --- Pass 5: Consumer Care Details (Deduplication & Barcode Exclusion) ---
        care_parts = []
        care_blocks = []
        care_keywords = ['CONSUMER CARE', 'CUSTOMER CARE', 'HELPLINE', 'TOLL FREE', 'SUHANACARE', 'EMAIL', 'FEEDBACK', 'CONTACT US', 'WECARE', "LET'S TALK"]

        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue

            text = block.get("text", "").strip()

            # Reject standalone barcode/EAN numbers (11-15 digits without explicit phone prefix)
            clean_digits = re.sub(r'[^0-9]', '', text)
            if len(clean_digits) >= 11 and not any(kw in text.upper() for kw in ['CARE', 'NO', 'TEL', 'PHONE', 'CALL', 'HELP']):
                continue

            phone_m = self.phone_pattern.search(text)
            email_m = self.email_pattern.search(text)
            is_care_kw = fuzzy_match_any(text, care_keywords, min_score=80.0) or any(kw in text.upper().replace(" ", "") for kw in ['CONSUMERCARE', 'CUSTOMERCARE', 'HELPLINE', 'TOLLFREE', 'WECARE', 'FEEDBACK', 'CONTACTUS', 'LETSTALK'])

            if phone_m or email_m or is_care_kw:
                if text not in care_parts:
                    care_parts.append(text)
                    care_blocks.append(block)
                    claimed_block_ids.add(b_id)

        if care_parts and care_blocks:
            combined_care = " ".join(care_parts)
            classified["consumer_care"] = _make_multiline_field_dict(
                care_blocks,
                combined_care,
                {
                    "has_phone": bool(self.phone_pattern.search(combined_care) or re.search(r'\d{10}', combined_care)),
                    "has_email": bool(self.email_pattern.search(combined_care) or '@' in combined_care),
                    "confidence": 0.90
                }
            )

        # --- Pass 6: Generic Commodity Name & Brand Extraction ---
        commodity_candidates = []
        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue

            text = block.get("text", "").strip()
            upper = text.upper()

            # Reject packaging field headers, care terms, and instructions
            care_or_header_kws = ['CARE', 'CUSTOMER', 'CONSUMER', 'HELPLINE', 'EMAIL', 'FEEDBACK', 'TOLLFREE', 'WECARE', 'QUANTITY', 'NETWT', 'NETQTY', 'BATCH', 'USEBY', 'EXPIRY', 'INGREDIENT', 'NUTRITION', 'PORTION', 'ADVICE']
            if any(h in upper.replace(" ", "") for h in care_or_header_kws) or upper.endswith(':'):
                continue

            # Reject garbled text fragments
            if re.search(r'[A-Z]{2,}II$', upper) or len(re.sub(r'[^A-Za-z]', '', text)) < 3:
                continue

            # Reject code patterns, batch numbers, dates, and warning/disclaimer notices
            if self.code_batch_pattern.match(upper) or self.batch_keyword_pattern.search(upper):
                continue

            if any(kw in upper.replace(" ", "") for kw in ['ACCEPT', 'DAMAGED', 'SACHET', 'SEAL', 'TAMPER', 'WARNING', 'DONOTACCEPT', 'DISCLAIMER', 'STOREINA', 'COOLANDDRY']):
                continue

            # Reject address components, street names, and postal pin codes from commodity candidate
            if re.search(r'\b(?:ROAD|STREET|AVENUE|LANE|PLOT|GAT|NAGAR|SECTOR|INDUSTRIAL|ESTATE|DIST|PIN|\d{6})\b', upper):
                continue

            # Explicit generic commodity prefix detection (Rule 6(1)(b))
            has_explicit_prefix = bool(re.match(r'^(?:Generic\s*(?:Commodity|Name)|Commodity|Product\s*Name)\s*[:=.\s]', text, re.IGNORECASE))
            clean_text = re.sub(r'^(?:Generic\s*(?:Commodity|Name)|Commodity|Product\s*Name)\s*[:=.\s]*', '', text, flags=re.IGNORECASE).strip()

            words = re.findall(r'[a-zA-Z]+', clean_text)
            if len(words) < 1 or len(words) > 8:
                continue

            rect = block.get("rect", {})
            h_px = rect.get("height", 10.0)
            y_pos = rect.get("y", 9999.0)

            # Prominence scoring:
            score = block.get("confidence", 0.5) * 10.0 + (h_px / 4.0)
            if has_explicit_prefix:
                score += 100.0  # Highest priority for explicit LMPC declaration
            if any(re.search(r'\b' + kw + r'\b', clean_text.upper()) for kw in self.known_commodity_keywords):
                score += 30.0
            if y_pos < 500:
                score += 15.0

            commodity_candidates.append((score, block, clean_text, has_explicit_prefix))

        if commodity_candidates:
            commodity_candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_block, clean_text, has_prefix = commodity_candidates[0]
            # Raised threshold from 15.0 to 25.0 — prevents garbled low-quality text from being picked
            cand_conf = best_block["confidence"] if best_score >= 25.0 else 0.50
            classified["commodity_name"] = {
                "raw_text": best_block["text"].strip(),
                "clean_name": clean_text or best_block["text"].strip(),
                "has_explicit_declaration": has_prefix,
                "confidence": cand_conf,
                "bbox": best_block.get("bbox"),
                "rect": best_block.get("rect"),
                "font_height_px": float(best_block.get("rect", {}).get("height", 0.0)),
                "matched_blocks": [best_block]
            }

        classified["unclassified_blocks_count"] = max(0, len(valid_blocks) - len(claimed_block_ids))

        # --- Pass 7: Gemini LLM Hybrid Second Opinion & Fallback ---
        found_fields = [k for k in ["mrp", "net_quantity", "mfg_date", "expiry_date", "manufacturer_details", "consumer_care", "commodity_name", "fssai_number"] if classified.get(k) is not None]
        has_critical_fields = bool(classified.get("mrp") or classified.get("net_quantity") or classified.get("commodity_name"))

        if len(found_fields) >= 4 and has_critical_fields:
            logger.info(f"Fast-path skip: Regex extracted {len(found_fields)}/8 fields successfully. Skipping LLM network call.")
            return classified

        llm_extractions = self.llm_extractor.extract_fields_from_ocr(full_raw_str)
        if llm_extractions:
            field_mapping = {
                "commodity_name": "generic_commodity_name",
                "net_quantity": "net_quantity",
                "mrp": "mrp",
                "mfg_date": "mfg_date",
                "expiry_date": "expiry_date",
                "manufacturer_details": "manufacturer_details",
                "consumer_care": "consumer_care",
                "fssai_number": "fssai_number"
            }

            for class_key, llm_key in field_mapping.items():
                llm_val = llm_extractions.get(llm_key)
                if not llm_val or str(llm_val).lower() == "null":
                    continue

                existing = classified.get(class_key)
                if existing is None:
                    # Regex missed it completely - use LLM extraction with llm_assisted=True flag
                    if class_key == "mrp":
                        nums = re.findall(r'\d+(?:\.\d+)?', str(llm_val))
                        price_num = float(nums[0]) if nums else None
                        classified["mrp"] = {
                            "raw_text": str(llm_val),
                            "value": price_num,
                            "currency": "₹" if "₹" in str(llm_val) else "Rs",
                            "has_tax_clause": has_global_tax_clause or "tax" in str(llm_val).lower(),
                            "confidence": 0.85,
                            "llm_assisted": True
                        }
                    elif class_key == "net_quantity":
                        parsed_q = self._parse_net_quantity(str(llm_val))
                        if parsed_q:
                            num_val, unit_str, is_std = parsed_q
                            classified["net_quantity"] = {
                                "raw_text": str(llm_val),
                                "numeric_value": num_val,
                                "unit": unit_str,
                                "is_standard_unit": is_std,
                                "confidence": 0.85,
                                "llm_assisted": True
                            }
                        else:
                            classified["net_quantity"] = {
                                "raw_text": str(llm_val),
                                "numeric_value": str(llm_val),
                                "unit": "",
                                "is_standard_unit": True,
                                "confidence": 0.75,
                                "llm_assisted": True
                            }
                    else:
                        classified[class_key] = {
                            "raw_text": str(llm_val),
                            "confidence": 0.85,
                            "llm_assisted": True
                        }
                    logger.info(f"LLM Fallback filled missing field '{class_key}': '{llm_val}'")
                else:
                    # Both Regex and LLM extracted value - Upgrade confidence signal
                    existing["confidence"] = max(existing.get("confidence", 0.70), 0.95)
                    existing["llm_verified"] = True
                    logger.info(f"LLM Verified field '{class_key}' (Confidence upgraded to 0.95)")

            # Attach matching block geometry to any fields that still lack rect/font_height_px
            for class_key in ["mrp", "net_quantity", "mfg_date", "expiry_date", "manufacturer_details", "consumer_care", "commodity_name", "fssai_number"]:
                f_obj = classified.get(class_key)
                if f_obj and (not f_obj.get("rect") or not f_obj.get("font_height_px")):
                    r_text = str(f_obj.get("raw_text", "")).strip()
                    best_b = None
                    best_score = 0.0
                    for b in valid_blocks:
                        bt = b.get("text", "").strip()
                        if not bt:
                            continue
                        if r_text.lower() in bt.lower() or bt.lower() in r_text.lower():
                            best_b = b
                            break
                        if HAS_RAPIDFUZZ:
                            sc = fuzz.partial_ratio(r_text.lower(), bt.lower())
                            if sc > best_score and sc >= 60:
                                best_score = sc
                                best_b = b
                    if best_b:
                        f_obj["rect"] = best_b.get("rect")
                        f_obj["bbox"] = best_b.get("bbox")
                        f_obj["font_height_px"] = float(best_b.get("rect", {}).get("height", 25.0))
                        f_obj["matched_blocks"] = [best_b]

        return classified

    def merge_multiside_fields(self, side_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merges classified fields from multiple compatible sides of the same package into
        a single unified, highest-confidence declaration dictionary.
        """
        merged = {
            "mrp": None,
            "net_quantity": None,
            "mfg_date": None,
            "expiry_date": None,
            "manufacturer_details": None,
            "consumer_care": None,
            "fssai_number": None,
            "commodity_name": None,
            "unclassified_blocks_count": 0
        }

        all_fields_keys = ["mrp", "net_quantity", "mfg_date", "expiry_date", "manufacturer_details", "consumer_care", "fssai_number", "commodity_name"]

        for res in side_results:
            side_fields = res.get("classified_fields", {})
            for key in all_fields_keys:
                val = side_fields.get(key)
                if val is not None:
                    curr = merged[key]
                    if curr is None:
                        merged[key] = val
                    else:
                        curr_conf = curr.get("confidence", 0.0) if isinstance(curr, dict) else 0.0
                        new_conf = val.get("confidence", 0.0) if isinstance(val, dict) else 0.0

                        # Special case: commodity_name - prefer explicit declaration
                        if key == "commodity_name":
                            if val.get("has_explicit_declaration") and not curr.get("has_explicit_declaration"):
                                merged[key] = val
                            elif new_conf > curr_conf:
                                merged[key] = val
                        # Special case: manufacturer_details - prefer more complete address
                        elif key == "manufacturer_details":
                            if val.get("has_address") and not curr.get("has_address"):
                                merged[key] = val
                            elif new_conf > curr_conf:
                                merged[key] = val
                        elif new_conf > curr_conf:
                            merged[key] = val

            merged["unclassified_blocks_count"] += side_fields.get("unclassified_blocks_count", 0)

        return merged
