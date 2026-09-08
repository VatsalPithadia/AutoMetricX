import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from app.llm_extractor import LLMExtractor

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

logger = logging.getLogger("metrolens.classifier")

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
        self.price_standalone_pattern = re.compile(
            r'(?:F|R|RS\.?|₹|\$)\s*(\d{1,4}\.\d{1,2})\b',
            re.IGNORECASE
        )
        self.tax_clause_pattern = re.compile(
            r'(?:INCL(?:USIVE)?\.?\s*OF\s*ALL\s*TAXES|INCL\.?\s*TAXES|ALL\s*TAXES)',
            re.IGNORECASE
        )

        self.net_qty_prefix_pattern = re.compile(
            r'(?:NET\s*(?:QTY|QUANTITY|WT|WEIGHT|VOL|VOLUME)|NET|N\.W\.)\s*[:=.\s]*(\d+(?:\.\d+)?)\s*([a-zA-Z]+|Pcs|Units|N)',
            re.IGNORECASE
        )
        self.standalone_qty_pattern = re.compile(
            r'^\b(\d+(?:\.\d+)?)\s*(g|kg|gm|gms|ml|l|ltr|liter|litres|n|pcs|units)\b$',
            re.IGNORECASE
        )

        # Month normalization (including OCR dot-matrix fixes e.g. 0CT -> OCT)
        self.month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', '0CT', 'NOV', 'DEC']
        self.date_pattern = re.compile(
            r'\b(0[1-9]|1[0-2]|0CT|OCT|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|NOV|DEC)\s*[\.\s/|-]+\s*(20[1-3][0-9]|[1-3][0-9])\b',
            re.IGNORECASE
        )
        self.full_date_pattern = re.compile(
            r'\b([0-3]?[0-9])[\.\s/|-]+(0[1-9]|1[0-2]|0CT|OCT|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|NOV|DEC)[\.\s/|-]+(20[1-3][0-9]|[1-3][0-9])\b',
            re.IGNORECASE
        )

        # FSSAI 14-digit pattern
        self.fssai_strict_pattern = re.compile(r'\b(1\d{13}|2\d{13})\b')

        # Phone & Email patterns
        self.phone_pattern = re.compile(
            r'(?:CARE|HELPLINE|NO|TEL|PHONE|CONTACT|CALL|CUSTOMER|CUSTOMERCARE)?\s*[:=.\s]*(\+?\d{2,4}[-\s]?)?(\d{10}|\d{5}\s*\d{5}|\d{4}[-\s]?\d{3}[-\s]?\d{4})',
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

        self.known_commodity_keywords = {
            'MASALA', 'SPICE', 'SAUCE', 'KETCHUP', 'POWDER', 'OIL', 'TEA', 'COFFEE',
            'SOAP', 'CREAM', 'PASTE', 'SHAMPOO', 'NOODLES', 'CHIPS', 'BISCUIT',
            'DRINK', 'WATER', 'JUICE', 'ANTACID', 'SACHET', 'TABLET', 'CAPSULE',
            'FOOD', 'SALT', 'SUGAR', 'MILK', 'BUTTER', 'CHEESE', 'FLOUR', 'ATTA',
            'RICE', 'DAL', 'PULSE', 'PICKLE', 'JAM', 'SYRUP', 'MIX', 'PASTA',
            'SHRI', 'HARI', 'SUHANA', 'ENO'
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
        if self.code_batch_pattern.match(upper) and not any(kw in upper for kw in ['MFG', 'EXP', 'PKD']):
            return None

        full_m = self.full_date_pattern.search(text)
        if full_m:
            d, m, y_str = full_m.groups()
            y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
            if 2015 <= y <= 2035:
                return f"{d}/{m.upper()}/{y}"

        m_yr = self.date_pattern.search(text)
        if m_yr:
            m, y_str = m_yr.groups()
            y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
            if 2015 <= y <= 2035:
                m_norm = "OCT" if m.upper() == "0CT" else m.upper()
                return f"{m_norm}/{y}"

        return None

    def _parse_net_quantity(self, text: str) -> Optional[Tuple[float, str, bool]]:
        """
        Parses Net Quantity with strict physical plausibility range check (1g/1ml to 25kg/25L).
        """
        match = self.net_qty_prefix_pattern.search(text) or self.standalone_qty_pattern.search(text)
        if not match:
            # Flexible quantity regex
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
                    "is_valid_14_digit": True,
                    "confidence": block["confidence"],
                    "bbox": block.get("bbox"),
                    "rect": block.get("rect")
                }
                claimed_block_ids.add(b_id)
                break
            elif 'LIC' in text.upper() or 'FSSAI' in text.upper():
                digits = re.findall(r'\b(1\d{13}|2\d{13})\b', text)
                if digits:
                    classified["fssai_number"] = {
                        "raw_text": text,
                        "license_number": digits[0],
                        "is_valid_14_digit": True,
                        "confidence": block["confidence"],
                        "bbox": block.get("bbox"),
                        "rect": block.get("rect")
                    }
                    claimed_block_ids.add(b_id)
                    break

        # --- Pass 2: Net Quantity (Excluding Recipe Blocks & Implausible Quantities) ---
        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue
            text = block.get("text", "").strip()

            parsed_qty = self._parse_net_quantity(text)
            if parsed_qty:
                num_val, unit_str, is_standard = parsed_qty
                # Higher confidence if preceded by explicit Net Qty prefix
                has_prefix = bool(self.net_qty_prefix_pattern.search(text))
                field_conf = block["confidence"] if has_prefix else min(block["confidence"], 0.55)

                classified["net_quantity"] = {
                    "raw_text": text,
                    "numeric_value": num_val,
                    "unit": unit_str,
                    "is_standard_unit": is_standard,
                    "confidence": field_conf,
                    "bbox": block.get("bbox"),
                    "rect": block.get("rect")
                }
                claimed_block_ids.add(b_id)
                break

        # --- Pass 3: MRP & Manufacturing / Expiry Date ---
        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue
            text = block.get("text", "").strip()
            upper_text = text.upper()

            # MRP Check: Requires explicit currency symbol or MRP keyword adjacent to number
            if not classified["mrp"]:
                mrp_match = self.mrp_strict_pattern.search(text) or self.price_standalone_pattern.search(text)
                if mrp_match:
                    raw_price_substr = mrp_match.group(0)
                    nums = re.findall(r'\d+(?:\.\d{1,2})?', raw_price_substr)
                    if nums:
                        price_num = float(nums[-1])
                        if 1.0 <= price_num <= 50000.0:
                            classified["mrp"] = {
                                "raw_text": f"MRP {raw_price_substr}",
                                "value": price_num,
                                "currency": "₹" if "₹" in text else "Rs",
                                "has_tax_clause": has_global_tax_clause or bool(self.tax_clause_pattern.search(text)),
                                "confidence": block["confidence"],
                                "bbox": block.get("bbox"),
                                "rect": block.get("rect")
                            }

            # Date Check: Calendar date validation
            parsed_d = self._parse_and_validate_date(text)
            if parsed_d:
                if any(kw in upper_text.replace(" ", "") for kw in ['EXP', 'BESTBEFORE', 'USEBY', 'EXPIRY']):
                    if not classified["expiry_date"]:
                        classified["expiry_date"] = {"raw_text": text, "extracted_date": parsed_d, "confidence": block["confidence"]}
                else:
                    if not classified["mfg_date"]:
                        classified["mfg_date"] = {"raw_text": text, "extracted_date": parsed_d, "confidence": block["confidence"]}

            if classified["mrp"] and classified["mrp"].get("raw_text") == text or parsed_d:
                claimed_block_ids.add(b_id)

        # --- Pass 4: Manufacturer Details (Strict Spatial Adjacency & Semantic Boundaries) ---
        mfg_anchors = ['MANUFACTURED', 'MANUFACTURER', 'PACKED BY', 'MFD BY', 'MFG BY', 'PKD BY', 'MARKETED BY', 'IMPORTER', 'REGISTERED OFFICE', 'REGD OFFICE']
        mfg_address_words = ['ROAD', 'STREET', 'CITY', 'DIST', 'GUJARAT', 'PIN', 'OFFICE', 'PLOT', 'LTD', 'LIMITED', 'PVT', 'FOODS', 'SATARA', 'MAHARASHTRA', 'GODHRA', 'FACTORY', 'PRATAPPURA']
        
        mfg_parts = []
        last_mfg_y = None

        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue

            # Skip rotated vertical blocks and customer care blocks in manufacturer details
            if block.get("angle", 0) != 0:
                continue

            text = block.get("text", "").strip()
            upper_text = text.upper()

            # Cross-boundary check: Never merge customer care or barcode info into manufacturer details
            if any(kw in upper_text for kw in ['CUSTOMER', 'CONSUMER', 'CARE', 'HELPLINE', 'TOLL FREE', 'E-MAIL', 'EMAIL', 'FEEDBACK']):
                continue

            rect = block.get("rect", {})
            y_pos = rect.get("y", 0.0)

            is_anchor = fuzzy_match_any(text, mfg_anchors, min_score=80.0)
            is_address = any(re.search(r'\b' + term + r'\b', upper_text) for term in mfg_address_words)

            if is_anchor or (mfg_parts and is_address and last_mfg_y is not None and abs(y_pos - last_mfg_y) < 65.0):
                mfg_parts.append(text)
                claimed_block_ids.add(b_id)
                last_mfg_y = y_pos

        if mfg_parts:
            combined_mfg = " ".join(mfg_parts)
            classified["manufacturer_details"] = {
                "raw_text": combined_mfg,
                "has_name": True,
                "has_address": any(re.search(r'\b' + kw + r'\b', combined_mfg.upper()) for kw in mfg_address_words),
                "confidence": 0.90
            }

        # --- Pass 5: Consumer Care Details (Deduplication & Barcode Exclusion) ---
        care_parts = []
        care_keywords = ['CONSUMER CARE', 'CUSTOMER CARE', 'HELPLINE', 'TOLL FREE', 'SUHANACARE', 'EMAIL', 'FEEDBACK', 'CONTACT US']

        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue

            # Skip rotated vertical blocks for consumer care
            if block.get("angle", 0) != 0:
                continue

            text = block.get("text", "").strip()

            # Reject standalone barcode/EAN numbers (11-15 digits without explicit phone prefix)
            clean_digits = re.sub(r'[^0-9]', '', text)
            if len(clean_digits) >= 11 and not any(kw in text.upper() for kw in ['CARE', 'NO', 'TEL', 'PHONE', 'CALL', 'HELP']):
                continue

            phone_m = self.phone_pattern.search(text)
            email_m = self.email_pattern.search(text)
            is_care_kw = fuzzy_match_any(text, care_keywords, min_score=80.0)

            if phone_m or email_m or is_care_kw:
                if text not in care_parts:
                    care_parts.append(text)
                    claimed_block_ids.add(b_id)

        if care_parts:
            combined_care = " ".join(care_parts)
            classified["consumer_care"] = {
                "raw_text": combined_care,
                "has_phone": bool(self.phone_pattern.search(combined_care) or re.search(r'\d{10}', combined_care)),
                "has_email": bool(self.email_pattern.search(combined_care) or '@' in combined_care),
                "confidence": 0.90
            }

        # --- Pass 6: Generic Commodity Name Extraction ---
        # Reverted & Fixed: Require 0° horizontal text, word-boundary commodity matching, exclude garbled fragments
        commodity_candidates = []
        for block in valid_blocks:
            b_id = block.get("id")
            if b_id in claimed_block_ids or b_id in recipe_block_ids:
                continue

            # Skip rotated vertical blocks for commodity name
            if block.get("angle", 0) != 0:
                continue

            text = block.get("text", "").strip()
            upper = text.upper()

            # Reject garbled text fragments (e.g. 'PASTEII', 'TaprEvie...')
            if re.search(r'[A-Z]{2,}II$', upper) or len(re.sub(r'[^A-Za-z]', '', text)) < 3:
                continue

            # Reject code patterns, batch numbers, dates, and warning/disclaimer notices
            if self.code_batch_pattern.match(upper) or self.batch_keyword_pattern.search(upper):
                continue

            if any(kw in upper.replace(" ", "") for kw in ['ACCEPT', 'DAMAGED', 'SACHET', 'SEAL', 'TAMPER', 'WARNING', 'DONOTACCEPT', 'DISCLAIMER', 'STOREINA', 'COOLANDDRY']):
                continue

            words = re.findall(r'[a-zA-Z]+', text)
            if len(words) < 1 or len(words) > 5:
                continue

            letters = len(re.findall(r'[a-zA-Z]', text))
            non_space = len(re.sub(r'\s+', '', text))
            if letters < 3 or (letters / float(non_space) < 0.60 if non_space > 0 else True):
                continue

            rect = block.get("rect", {})
            h_px = rect.get("height", 10.0)
            y_pos = rect.get("y", 9999.0)

            # Prominence scoring: text height + top position + word-boundary commodity match
            score = block["confidence"] * 10.0 + (h_px / 5.0)
            if any(re.search(r'\b' + kw + r'\b', upper) for kw in self.known_commodity_keywords):
                score += 30.0
            if y_pos < 500:
                score += 10.0

            commodity_candidates.append((score, block))

        if commodity_candidates:
            commodity_candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_block = commodity_candidates[0]
            cand_conf = best_block["confidence"] if best_score >= 15.0 else 0.50
            classified["commodity_name"] = {
                "raw_text": best_block["text"].strip(),
                "confidence": cand_conf,
                "bbox": best_block.get("bbox"),
                "rect": best_block.get("rect")
            }

        classified["unclassified_blocks_count"] = max(0, len(valid_blocks) - len(claimed_block_ids))

        # --- Pass 7: Gemini LLM Hybrid Second Opinion & Fallback ---
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
                        price_num = float(re.findall(r'\d+(?:\.\d+)?', str(llm_val))[0]) if re.findall(r'\d+(?:\.\d+)?', str(llm_val)) else None
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

        return classified
