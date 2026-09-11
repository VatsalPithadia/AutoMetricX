import os
import re
import json
import base64
import logging
import httpx
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("metrolens.llm_extractor")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

class LLMExtractor:
    """
    Advanced Multilingual & Multimodal Legal Metrology (LMPC) Extractor.
    
    Capabilities:
    1. Multimodal Gemini 2.5 Flash: When GEMINI_API_KEY is available and image bytes are passed,
       analyzes packaging visually with native Gujarati, Hindi, and English understanding,
       vertical/curved text resolution, and high-accuracy structured extraction.
    2. Deep Local NLP Contextual Engine: High-accuracy pattern matching and heuristic clustering
       across diverse Indian retail package formats in English, Gujarati, and Hindi:
       - Consumer Care Search: Phone, toll-free 1800, emails, grievance cell, postal addresses.
       - Manufacturer Details Search: Multi-line address clustering, GIDC/MIDC industrial plots, PIN codes.
       - FSSAI License Search: 14-digit sequences, spaced/hyphenated variations, multiple licenses.
       - Mfg & Expiry Date Search: Calendar dates, relative shelf life ('Best before X months'), batch codes.
       - MRP Context Search: Amount, currency, tax clause variations, Unit Sale Price (USP).
       - Net Quantity Context Search: Standard LMPC units, gross vs net weight.
    """

    def __init__(self, timeout_sec: float = 6.0):
        self.timeout_sec = timeout_sec

    def extract_fields_from_ocr(self, raw_ocr_text: str, image_bytes: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
        """
        Main extraction entry point.
        Executes Multimodal Gemini API if configured; otherwise runs the local multilingual NLP engine.
        """
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
        # 1. Multimodal Gemini 2.5 Flash Pass (Vision + OCR Text)
        if api_key:
            try:
                result = self._call_gemini_multimodal(api_key, raw_ocr_text, image_bytes)
                if result:
                    logger.info("Successfully extracted fields via Gemini 2.5 Flash API.")
                    return result
            except Exception as err:
                logger.warning(f"Gemini API call skipped/failed ({err}). Running local NLP extractor.")

        # 2. Local Multilingual Contextual Recovery Engine (No external dependencies)
        return self._extract_fields_locally(raw_ocr_text)

    def local_multilingual_recovery(self, raw_ocr_text: str) -> Dict[str, Any]:
        """
        Public execution entry point for local multilingual NLP contextual extraction.
        Runs offline-first without requiring external API access.
        """
        return self._extract_fields_locally(raw_ocr_text)

    def _call_gemini_multimodal(self, api_key: str, raw_ocr_text: str, image_bytes: Optional[bytes]) -> Optional[Dict[str, Any]]:
        """
        Executes Gemini 2.5 Flash multimodal vision call with packaging instructions.
        """
        prompt = """You are an expert Legal Metrology (LMPC) auditor for Indian packaged goods.
Extract mandatory product packaging declarations. The packaging may contain English, Hindi, and Gujarati text, rotated vertical text on side gussets/margins, curved text on bottles, or variable inkjet dot-matrix batch codes.

Extract the following fields accurately:
1. generic_commodity_name: string or null (e.g. "Spiced Masala Powder", "Refined Sunflower Oil", "Wheat Flour / Atta")
2. net_quantity: string or null (Total net weight/volume of the packet e.g. "250 g", "500 ml", "1 kg". Exclude serving sizes like 'per 100g' or ingredient percentages)
3. mrp: string or null (Full Maximum Retail Price declaration e.g. "Rs. 45.00 (Incl. of all taxes)")
4. unit_sale_price: string or null (e.g. "Rs. 0.18 / g", "₹ 0.50 per ml")
5. mfg_date: string or null (e.g. "15/10/2025", "OCT 2025", "15-OCT-25")
6. expiry_date: string or null (e.g. "14/10/2026", "SEP 2026", "Best before 12 months from mfg")
7. batch_number: string or null (e.g. "B.No. 2408A", "LOT-992")
8. manufacturer_details: string or null (Full name and complete multi-line address of manufacturer/packer/importer including Industrial Area / GIDC, City, State, and 6-digit PIN code)
9. consumer_care: string or null (Complete consumer care details: Toll-Free 1800 number, phone, email address, customer executive, and postal address for complaints)
10. fssai_number: string or null (14-digit FSSAI license number)
11. ingredients: string or null (Complete list of ingredients, e.g. "Wheat Flour, Palm Oil, Sugar, Salt, Artificial Flavor (INS 102), Antioxidant (INS 319)")
12. detected_languages: list of strings (e.g. ["English", "Gujarati", "Hindi"])

Return ONLY valid JSON matching this exact structure:
{
  "generic_commodity_name": string or null,
  "net_quantity": string or null,
  "mrp": string or null,
  "unit_sale_price": string or null,
  "mfg_date": string or null,
  "expiry_date": string or null,
  "batch_number": string or null,
  "manufacturer_details": string or null,
  "consumer_care": string or null,
  "fssai_number": string or null,
  "ingredients": string or null,
  "detected_languages": ["English"]
}
"""
        parts: List[Dict[str, Any]] = [{"text": prompt}]

        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode('utf-8')
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": b64_img
                }
            })

        if raw_ocr_text and len(raw_ocr_text.strip()) > 5:
            parts.append({"text": f"\n\nEXTRACTED OCR TEXT FROM LABELS:\n{raw_ocr_text.strip()}"})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}
        }

        url = f"{GEMINI_API_URL}?key={api_key}"
        with httpx.Client(timeout=self.timeout_sec) as client:
            response = client.post(url, json=payload)
            if response.status_code == 200:
                res_json = response.json()
                candidates = res_json.get("candidates", [])
                if candidates:
                    raw_json = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return json.loads(raw_json)
        return None

    def _extract_fields_locally(self, raw_ocr_text: str) -> Dict[str, Any]:
        """
        Deep Local Multilingual NLP Contextual Recovery Engine.
        Executes specialized search extractors across English, Gujarati, and Hindi.
        """
        text = raw_ocr_text or ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Translate Gujarati (૦-૯) and Devanagari (०-९) digits to standard ASCII (0-9)
        # for robust mathematical, license, and date pattern matching
        INDIAN_DIGIT_MAP = str.maketrans('૦૧૨૩૪૫૬૭૮૯०१२३४५६७८९', '01234567890123456789')
        norm_text = text.translate(INDIAN_DIGIT_MAP)
        norm_lines = [line.translate(INDIAN_DIGIT_MAP) for line in lines]

        consumer_care_info = self._search_consumer_care(norm_lines, norm_text)
        mfg_info = self._search_manufacturer_details(lines, text)
        fssai_info = self._search_fssai_license(norm_text)
        dates_info = self._search_mfg_expiry_dates(norm_text, norm_lines)
        mrp_info = self._search_mrp(norm_text)
        qty_info = self._search_net_quantity(norm_text)
        commodity_info = self._search_commodity_name(lines, text)
        ingredients_info = self._search_ingredients(lines, text)

        # Detect scripts present
        detected_langs = []
        if re.search(r'[\u0A80-\u0AFF]', text): detected_langs.append("Gujarati")
        if re.search(r'[\u0900-\u097F]', text): detected_langs.append("Hindi")
        if re.search(r'[A-Za-z]', text): detected_langs.append("English")
        if not detected_langs: detected_langs.append("English")

        return {
            "generic_commodity_name": commodity_info.get("name"),
            "net_quantity": qty_info.get("formatted"),
            "mrp": mrp_info.get("formatted"),
            "unit_sale_price": mrp_info.get("usp"),
            "mfg_date": dates_info.get("mfg_date"),
            "expiry_date": dates_info.get("expiry_date"),
            "batch_number": dates_info.get("batch_number"),
            "manufacturer_details": mfg_info.get("raw_text"),
            "consumer_care": consumer_care_info.get("formatted"),
            "fssai_number": fssai_info.get("license_number"),
            "ingredients": ingredients_info.get("raw_text"),
            "detected_languages": detected_langs,
            "deep_search_details": {
                "consumer_care": consumer_care_info,
                "manufacturer": mfg_info,
                "fssai": fssai_info,
                "dates": dates_info,
                "mrp": mrp_info,
                "net_quantity": qty_info,
                "ingredients": ingredients_info
            }
        }

    # =========================================================================
    # 1. Consumer Care Extraction Search
    # =========================================================================
    def _search_consumer_care(self, lines: List[str], text: str) -> Dict[str, Any]:
        """
        Searches for Consumer Care phone, toll-free 1800, email, executive title,
        and complaint postal address in English, Gujarati, and Hindi.
        """
        res: Dict[str, Any] = {
            "toll_free": None,
            "phone": None,
            "email": None,
            "officer_title": None,
            "postal_address": None,
            "formatted": None,
            "raw_text": None
        }

        # 1. Toll-Free & Standard Phone Search
        tf_match = re.search(r'\b(1800[-\s]?\d{3}[-\s]?\d{3,4}|1800\d{6,7}|0800[-\s]?\d{6,8})\b', text)
        if tf_match:
            res["toll_free"] = tf_match.group(1).replace(" ", "-")

        phone_match = re.search(r'(?:\+91[-\s]?|0\d{2,4}[-\s]?|\b)([6-9]\d{9}|[2-8]\d{7})\b', text)
        if phone_match and phone_match.group(1) != res["toll_free"]:
            res["phone"] = phone_match.group(0).strip()

        # 2. Email Address Search
        email_match = re.search(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', text)
        if email_match:
            res["email"] = email_match.group(1)

        # 3. Officer / Executive Title Search
        title_match = re.search(r'\b(Consumer\s*Care\s*Executive|Customer\s*Care\s*(?:Manager|Executive|Officer)|Grievance\s*Officer|Manager\s*Customer\s*Care|Customer\s*Service\s*Cell|ગ્રાહક\s*સેવા\s*(?:અધિકારી|પ્રતિનિધિ)|ઉપભોક્તા\s*સેવા)\b', text, re.IGNORECASE)
        if title_match:
            res["officer_title"] = title_match.group(1)

        # 4. Multi-Line Block Aggregation around Consumer Care Header
        care_keywords = [
            "CONSUMER CARE", "CUSTOMER CARE", "FEEDBACK", "COMPLAINT", "QUERIES",
            "REACH US", "WRITE TO", "GRIEVANCE", "HELPLINE", "TOLL FREE", "CUSTOMER SERVICE",
            "ગ્રાહક સેવા", "સંપર્ક", "ફરિયાદ", "ટોલ ફ્રી", "ઉપભોક્તા સેવા", "ગ્રાહક સહાય"
        ]
        collected_lines = []
        for i, l in enumerate(lines):
            l_upper = l.upper()
            if any(kw in l_upper for kw in care_keywords):
                # Collect this line and up to 3 following lines
                for j in range(i, min(len(lines), i + 4)):
                    nxt = lines[j]
                    if nxt and not any(stop in nxt.upper() for stop in ["NUTRITION", "INGREDIENTS", "RECIPE", "BEST BEFORE"]):
                        collected_lines.append(nxt)
                break

        parts = []
        if res["officer_title"]: parts.append(res["officer_title"])
        if res["toll_free"]: parts.append(f"Toll-Free: {res['toll_free']}")
        elif res["phone"]: parts.append(f"Phone: {res['phone']}")
        if res["email"]: parts.append(f"Email: {res['email']}")

        if parts:
            res["formatted"] = " | ".join(parts)
            res["raw_text"] = "\n".join(collected_lines) if collected_lines else res["formatted"]
        elif collected_lines:
            res["formatted"] = " ".join(collected_lines)
            res["raw_text"] = "\n".join(collected_lines)

        return res

    # =========================================================================
    # 2. Manufacturer Details Extraction Search
    # =========================================================================
    def _search_manufacturer_details(self, lines: List[str], text: str) -> Dict[str, Any]:
        """
        Searches for genuine Manufacturer / Packer entity name, clean physical address,
        and authentic 6-digit Indian PIN code in English, Gujarati, and Hindi.
        Strictly excludes allergen disclaimers, nutritional facts, social tags, and OCR noise.
        """
        res: Dict[str, Any] = {
            "company_name": None,
            "address": None,
            "pin_code": None,
            "declaration_type": "Manufactured By",
            "raw_text": None,
            "has_name": False,
            "has_address": False
        }

        mfg_headers = [
            r'MANUFACTURED\s*(?:&|AND)?\s*PACKED\s*BY',
            r'MANUFACTURED\s*BY', r'MFD\.?\s*BY', r'MFG\.?\s*BY',
            r'PACKED\s*BY', r'PKD\.?\s*BY',
            r'MARKETED\s*BY', r'MKTG?\.?\s*BY',
            r'IMPORTED\s*(?:&|AND)?\s*DISTRIBUTED\s*BY',
            r'FORMULATED\s*BY', r'REGISTERED\s*OFFICE', r'REGD\.?\s*OFFICE',
            r'WORKS\s*AT', r'UNIT\s*[I|V|X\d]+',
            r'ઉત્પાદક', r'પેક કરનાર', r'બનાવનાર', r'નિર્માતા', r'દ્વારા નિર્મિત'
        ]
        combined_header_re = re.compile(r'(' + '|'.join(mfg_headers) + r')\s*[:=.\s]*', re.IGNORECASE)

        # Filter out noisy or allergen lines
        allergen_terms = [
            "FACILITY THAT", "PROCESSES THESE", "ALLERGEN", "MAY CONTAIN",
            "DRODUCTMANUFACTURED", "PRODUCT MANUFACTURED", "FACILITYTHAT"
        ]
        stop_terms = [
            "NUTRITION", "INGREDIENTS", "NET QTY", "NET WT", "MRP RS", "BATCH NO",
            "FSSAI LIC", "LIC NO", "CUSTOMER CARE", "CONSUMER CARE", "FEEDBACK",
            "SERVING SIZE", "%RDA", "CALORIES", "ગ્રાહક સેવા", "સંપર્ક", "SCANTO",
            "WWW.", "@SUHANA", "TASTEMAKERS"
        ]

        start_idx = -1
        for idx, line in enumerate(lines):
            ln_up = line.upper()
            if any(at in ln_up for at in allergen_terms):
                continue
            if combined_header_re.search(line):
                start_idx = idx
                break

        collected = []
        if start_idx != -1:
            for i in range(start_idx, min(len(lines), start_idx + 20)):
                ln = lines[i].strip()
                ln_up = ln.upper()
                if any(at in ln_up for at in allergen_terms):
                    continue
                if i > start_idx and any(term in ln_up for term in stop_terms):
                    break
                # Skip empty or lone punctuation lines
                if len(re.sub(r'[^A-Za-z0-9]', '', ln)) > 0:
                    collected.append(ln)
        else:
            # Fallback: look for company suffix + GIDC / PIN
            for idx, line in enumerate(lines):
                ln_up = line.upper()
                if any(at in ln_up for at in allergen_terms):
                    continue
                if re.search(r'\b(PVT\.?\s*LTD|LIMITED|LTD\.?|FOODS|INDUSTRIES|PRODUCTS|DAIRY|AGRO|MASALEWALE)\b', line, re.IGNORECASE):
                    for j in range(idx, min(len(lines), idx + 5)):
                        j_ln = lines[j].strip()
                        if any(at in j_ln.upper() for at in allergen_terms) or any(st in j_ln.upper() for st in stop_terms):
                            break
                        collected.append(j_ln)
                    break

        if collected:
            # Determine genuine Company Name
            header_stripped = re.sub(combined_header_re, '', collected[0]).strip()
            header_stripped = re.sub(r'^[^\w]+|[^\w]+$', '', header_stripped)

            company_candidate = None
            company_line_idx = -1

            company_suffix_pattern = re.compile(
                r'\b[A-Za-z]*(?:PVT\.?\s*LTD|LIMITED|LTD\.?|FOODS(?:\s*LTD)?|INDUSTRIES|ENTERPRISES|PRODUCTS|DAIRY|AGRO|PHARMA|MASALEWALE|BAKERY)\b',
                re.IGNORECASE
            )

            # Check if header line itself contains the company name after the header prefix
            if header_stripped and len(header_stripped) >= 3 and not re.search(r'\b(?:ROAD|STREET|PLOT|DIST|GIDC|PIN)\b', header_stripped, re.IGNORECASE):
                company_candidate = header_stripped
                company_line_idx = 0
            else:
                # Search subsequent collected lines for company entity
                for c_idx, cl in enumerate(collected):
                    cleaned_l = re.sub(combined_header_re, '', cl).strip()
                    cleaned_l = re.sub(r'^[^\w]+|[^\w]+$', '', cleaned_l)
                    if company_suffix_pattern.search(cleaned_l) and len(cleaned_l) >= 3:
                        company_candidate = cleaned_l
                        company_line_idx = c_idx
                        break

                # If still not found, check line right after header
                if not company_candidate and len(collected) > 1:
                    first_after = re.sub(combined_header_re, '', collected[1]).strip()
                    first_after = re.sub(r'^[^\w]+|[^\w]+$', '', first_after)
                    if len(first_after) >= 3:
                        company_candidate = first_after
                        company_line_idx = 1
                elif not company_candidate and header_stripped:
                    company_candidate = header_stripped
                    company_line_idx = 0

            # Further sanitize company_candidate
            if company_candidate:
                company_candidate = re.sub(combined_header_re, '', company_candidate).strip()
                company_candidate = company_candidate.split('\n')[0].strip()
                # If excessively long, trim to entity boundary
                if len(company_candidate) > 70:
                    match_suf = company_suffix_pattern.search(company_candidate)
                    if match_suf:
                        company_candidate = company_candidate[:match_suf.end()].strip()
                    else:
                        company_candidate = company_candidate[:70].strip()

            # Separate Address lines (strictly excluding nutritional facts or metric table noise)
            nutrition_kw = {'FAT', 'SUGAR', 'PROTEIN', 'CARBOHYDRATE', 'CHOLESTEROL', 'SODIUM', 'ENERGY', 'KCAL', 'CALORIE', 'RDA', 'SERVING', 'PER', 'APPROX'}
            addr_lines = []
            for c_idx, cl in enumerate(collected):
                if c_idx == company_line_idx:
                    continue
                cleaned_l = re.sub(combined_header_re, '', cl).strip()
                cleaned_l = re.sub(r'^[^\w(]+|[^\w)]+$', '', cleaned_l)
                if not cleaned_l or cleaned_l == company_candidate or len(cleaned_l) <= 1:
                    continue
                up_l = cleaned_l.upper()
                if any(k in up_l for k in nutrition_kw):
                    continue
                if re.match(r'^[\d.\s]+(?:G|MG|KCAL|%|GM|ML)?$', up_l, re.I):
                    continue
                addr_lines.append(cleaned_l)

            # Robust Indian PIN code extraction
            search_pool = " ".join(collected) + " " + text
            # Explicit pin pattern: "Pin 412801(INDIA)", "Pin: 382330", "Pune - 411001", "Assam-785001"
            pin_explicit = re.findall(r'(?:PIN(?:\s*CODE)?[:\s.-]*|INDIA\s*[-–]\s*|(?<!\d)-)\s*([1-8]\d{5})\b', search_pool, re.IGNORECASE)
            pin_found = None
            if pin_explicit:
                for cand in pin_explicit:
                    # Validate candidate is not immediately followed by decimal (e.g. 202623.00)
                    if not re.search(r'\b' + cand + r'\.\d', search_pool):
                        pin_found = cand
                        break

            if not pin_found:
                # Look for PIN followed by (INDIA) or state/city
                pin_india = re.findall(r'\b([1-8]\d{5})\s*\((?:INDIA|IND)\)', search_pool, re.IGNORECASE)
                for cand in pin_india:
                    if not re.search(r'\b' + cand + r'\.\d', search_pool):
                        pin_found = cand
                        break

            if not pin_found:
                # Fallback: standard 6-digit Indian PIN not preceded by month/year and not followed by decimals
                for pm in re.finditer(r'(?<![A-Za-z0-9.])([1-8]\d{5})(?!\.\d)(?![0-9])', " ".join(collected)):
                    cand = pm.group(1)
                    pre_ctx = " ".join(collected)[max(0, pm.start()-10):pm.start()].upper()
                    if not any(m in pre_ctx for m in ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', '202']):
                        pin_found = cand
                        break

            res["company_name"] = company_candidate or "Declared Entity"
            res["pin_code"] = pin_found
            res["address"] = ", ".join(addr_lines) if addr_lines else (company_candidate or "Declared Entity")
            res["raw_text"] = f"{res['company_name']}, {res['address']}" if res['address'] != res['company_name'] else res['company_name']
            res["has_name"] = bool(company_candidate)
            res["has_address"] = bool(addr_lines or pin_found)

        return res

    # =========================================================================
    # 3. FSSAI License Extraction Search
    # =========================================================================
    def _search_fssai_license(self, text: str) -> Dict[str, Any]:
        """
        Extracts 14-digit FSSAI license numbers, including spaced or hyphenated sequences,
        and distinguishes between primary manufacturer vs marketer licenses.
        """
        res: Dict[str, Any] = {
            "license_number": None,
            "all_licenses": [],
            "raw_text": None,
            "is_valid_format": False
        }

        # 1. Clean out spaces/dashes between digits when near FSSAI keyword
        fssai_near = re.findall(r'(?:FSSAI|LIC|LICENCE|LICENSE|લાયસન્સ|લાઇસન્સ|લાઈસન્સ|લાયસન્સ નં\.?)\D{0,15}(\d[\d\s-]{12,18}\d)', text, re.IGNORECASE)
        found_licenses = []

        for candidate in fssai_near:
            digits = re.sub(r'\D', '', candidate)
            if len(digits) == 14 and (digits.startswith("1") or digits.startswith("2")):
                found_licenses.append(digits)

        # 2. General strict regex for 14-digit sequence starting with 1 or 2
        general_matches = re.findall(r'\b(1\d{13}|2\d{13})\b', text)
        for g in general_matches:
            if g not in found_licenses:
                found_licenses.append(g)

        if found_licenses:
            res["license_number"] = found_licenses[0]
            res["all_licenses"] = found_licenses
            res["raw_text"] = f"FSSAI Lic. No. {found_licenses[0]}"
            res["is_valid_format"] = True

        return res

    # =========================================================================
    # 4. Mfg & Expiry Date Extraction Search
    # =========================================================================
    def _search_mfg_expiry_dates(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """
        Extracts Manufacturing / Packing date, Expiry / Best Before date,
        relative shelf-life ("Best before X months"), and Batch / Lot number.
        """
        res: Dict[str, Any] = {
            "mfg_date": None,
            "expiry_date": None,
            "batch_number": None,
            "relative_shelf_life": None
        }

        # 1. Batch Number Search
        batch_m = re.search(r'\b(?:BATCH(?:\s*(?:NO\.?|NUMBER))?|LOT(?:\s*NO\.?)?|B\.?\s*NO\.?|BNO|CH\.?\s*NO\.?|B\. NO|બેચ(?:\s*નંબર)?|લોટ(?:\s*નંબર)?)[\s:.-]*([A-Za-z0-9/-]+)\b', text, re.IGNORECASE)
        if batch_m:
            b_val = batch_m.group(1).strip()
            if b_val.upper() not in ["NO", "NUMBER", "NUM", "DATE", "DT"]:
                res["batch_number"] = b_val

        # 2. Relative Shelf-Life Search (e.g. "Best before 6 months from packaging")
        rel_m = re.search(r'\b(BEST\s*BEFORE|CONSUME\s*WITHIN|USE\s*WITHIN)\s*(\d{1,2}\s*(?:MONTHS?|DAYS?|WEEKS?|YEARS?))\b', text, re.IGNORECASE)
        if rel_m:
            res["relative_shelf_life"] = f"{rel_m.group(1)} {rel_m.group(2)}"
            res["expiry_date"] = res["relative_shelf_life"]

        # 3. Explicit Mfg / Packing Date
        mfg_m = re.search(r'(?:MFG(?:\s*DATE)?|MFD(?:\s*DATE)?|PKD(?:\s*DATE)?|PACKED(?:\s*ON|\s*DATE)?|DOM|DATE\s*OF\s*(?:MFG|PACKAGING)|ઉત્પાદન\s*તારીખ|પેકિંગ\s*તારીખ|નિર્માણ\s*તિથિ)[\s:.-]*([0-3]?[0-9][/\-.][0-1]?[0-9][/\-.](?:20)?[1-3][0-9]|(?:0[1-9]|1[0-2])[/\-.](?:20)?[1-3][0-9]|\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|0CT|NOV|DEC)[\s./-]*(?:20)?[1-3][0-9]\b)', text, re.IGNORECASE)
        if mfg_m:
            res["mfg_date"] = mfg_m.group(1).strip()

        # 4. Explicit Expiry / Use By Date
        exp_m = re.search(r'(?:EXP(?:\s*DATE)?|EXPIRY(?:\s*DATE)?|USE\s*BY|BEST\s*BEFORE|BB|વાપરવાની\s*છેલ્લી\s*તારીખ|એક્સપાયરી|સમાપ્તિ\s*તિથિ|શ્રેષ્ઠ\s*ઉપયોગ|ઉપયોગ\s*તારીખ)[\s:.-]*([0-3]?[0-9][/\-.][0-1]?[0-9][/\-.](?:20)?[1-3][0-9]|(?:0[1-9]|1[0-2])[/\-.](?:20)?[1-3][0-9]|\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|0CT|NOV|DEC)[\s./-]*(?:20)?[1-3][0-9]\b)', text, re.IGNORECASE)
        if exp_m:
            res["expiry_date"] = exp_m.group(1).strip()

        # 5. Dual Date Scan fallback (e.g. "OCT 2025" and "OCT 2026")
        if not res["mfg_date"] or not res["expiry_date"]:
            all_dates = re.findall(r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|0CT|NOV|DEC)[\s./-]*(20[1-3][0-9]|[1-3][0-9])\b', text, re.IGNORECASE)
            if len(all_dates) >= 2:
                if not res["mfg_date"]: res["mfg_date"] = f"{all_dates[0][0].upper()}/{all_dates[0][1]}"
                if not res["expiry_date"]: res["expiry_date"] = f"{all_dates[1][0].upper()}/{all_dates[1][1]}"
            elif len(all_dates) == 1 and not res["mfg_date"]:
                res["mfg_date"] = f"{all_dates[0][0].upper()}/{all_dates[0][1]}"

        return res

    # =========================================================================
    # 5. MRP Context Extraction Search
    # =========================================================================
    def _search_mrp(self, text: str) -> Dict[str, Any]:
        """
        Extracts Maximum Retail Price amount, ₹/Rs currency, tax clause,
        and Unit Sale Price (USP) in English, Gujarati, and Hindi.
        """
        res: Dict[str, Any] = {
            "value": None,
            "currency": "₹",
            "has_tax_clause": False,
            "usp": None,
            "formatted": None
        }

        # Check for Tax Clause (English, Gujarati, Hindi)
        tax_patterns = [
            r'INCL(?:USIVE)?\.?\s*(?:OF\s*)?ALL\s*TAXE?S?',
            r'ALL\s*TAXE?S?',
            r'બધા\s*કર\s*સહિત', r'કર\s*સહિત', r'તમામ\s*કર\s*સહિત', r'તમામ\s*કરો\s*સહિત',
            r'સભી\s*કરોં\s*સહિત', r'સભી\s*કર\s*સહિત', r'સભી\s*ટેક્સ\s*સહિત'
        ]
        if any(re.search(tp, text, re.IGNORECASE) for tp in tax_patterns):
            res["has_tax_clause"] = True

        # Unit Sale Price (USP) Search
        usp_m = re.search(r'(?:USP|UNIT\s*SALE\s*PRICE|યુનિટ\s*દીઠ(?:\s*વેચાણ\s*કિંમત)?|પ્રતિ\s*યુનિટ)[\s:.-]*[₹Rs.રૂ\.]?\s*(\d+(?:\.\d{1,2})?)\s*(?:PER|\/|દીઠ|પ્રતિ)\s*(G|KG|GM|ML|L|N|UNIT|ગ્રામ|કિલો|મિલી|લિટર|ગ્રા|કિગ્રા)', text, re.IGNORECASE)
        if usp_m:
            res["usp"] = f"₹ {usp_m.group(1)} / {usp_m.group(2).lower()}"

        # MRP Value Search
        mrp_patterns = [
            r'(?:M\.?R\.?P\.?|MAX(?:IMUM)?\s*RETAIL\s*PRICE|મ\.ચી\.ભા|મહત્તમ\s*છૂટક\s*કિંમત|અ\.ખુ\.મૂ|એમ\.?આર\.?પી\.?|છૂટક\s*કિંમત|કિંમત|ભાવ)(?:\s*\([^\)]*\))?[\s:.-]*[₹Rs.રૂ\.]?\s*(\d{1,5}(?:\.\d{1,2})?)',
            r'(?:RS\.?|₹|રૂ\.)\s*(\d{1,5}(?:\.\d{1,2})?)\s*(?:/-|(?=.*INCL))'
        ]
        for pat in mrp_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    val = float(m.group(1))
                    if 1.0 <= val <= 99999.0:
                        res["value"] = val
                        tax_suffix = " (Incl. of all taxes)" if res["has_tax_clause"] else ""
                        res["formatted"] = f"₹ {val:.2f}{tax_suffix}"
                        break
                except Exception:
                    pass

        return res

    # =========================================================================
    # 6. Net Quantity Context Extraction Search
    # =========================================================================
    def _search_net_quantity(self, text: str) -> Dict[str, Any]:
        """
        Extracts package Net Weight / Net Volume / Net Count using standard LMPC units
        in English, Gujarati, and Hindi, rejecting per-100g serving table rows.
        """
        res: Dict[str, Any] = {
            "value": None,
            "unit": None,
            "is_standard": True,
            "formatted": None
        }

        # 1. Prefixed Net Quantity pattern
        prefix_pattern = r'(?:NET\s*(?:QTY|WT|WEIGHT|QUANTITY|VOL|CONTENTS?)|N\.W\.|TOTAL\s*NET|ચોખ્ખું\s*વજન|ચોખ્ખો\s*જથ્થો|નેટ\s*વજન|શુદ્ધ\s*માત્રા|શુદ્ધ\s*વજન)[\s:.-]*\b(\d+(?:\.\d+)?)\s*(g|kg|gm|gms|ml|l|ltr|liter|litres|pcs|units|n|ગ્રામ|કિલો|મિલી|લિટર|ગ્રા|કિગ્રા|ग्राम|किलो|मिली|लीटर)\b'
        m = re.search(prefix_pattern, text, re.IGNORECASE)
        if m:
            val_str = m.group(1)
            unit_str = m.group(2).lower()
            # Normalize unit
            unit_map = {
                "gm": "g", "gms": "g", "ગ્રામ": "g", "ગ્રા": "g", "ग्राम": "g",
                "કિલો": "kg", "કિગ્રા": "kg", "किलो": "kg",
                "ltr": "L", "liter": "L", "litres": "L", "લિટર": "L", "लीटर": "L",
                "મિલી": "ml", "मिली": "ml", "units": "Units", "pcs": "Pcs"
            }
            norm_unit = unit_map.get(unit_str, unit_str)
            res["value"] = float(val_str) if "." in val_str else int(val_str)
            res["unit"] = norm_unit
            res["formatted"] = f"{val_str} {norm_unit}"
            return res

        # 2. Standalone prominent front quantity fallback (e.g. "500 g", "1 kg")
        standalone_m = re.search(r'\b(\d{1,4})\s*(g|kg|ml|l)\b', text, re.IGNORECASE)
        if standalone_m and "PER" not in text.upper():
            v = standalone_m.group(1)
            u = standalone_m.group(2).lower()
            res["value"] = int(v)
            res["unit"] = u
            res["formatted"] = f"{v} {u}"

        return res

    # =========================================================================
    # 7. Generic Commodity Name Search
    # =========================================================================
    def _search_commodity_name(self, lines: List[str], text: str) -> Dict[str, Any]:
        """
        Identifies generic commodity name (e.g. Premium Black Tea, Besan, Whole Spices),
        excluding recipes, cooking instructions, and nutrition facts tables.
        """
        res = {"name": None}

        # 1. Explicit declaration check
        expl_m = re.search(r'(?:GENERIC\s*(?:COMMODITY)?(?:\s*NAME)?|COMMODITY|PRODUCT\s*(?:NAME)?|વસ્તુનું\s*નામ|ઉત્પાદન)[\s:.-]*([A-Za-z0-9\s.,\/-]{3,60})', text, re.IGNORECASE)
        if expl_m:
            res["name"] = expl_m.group(1).strip()
            return res

        # 2. Heuristic scan on top lines
        commodity_words = [
            "TEA", "COFFEE", "MASALA", "SPICE", "ATTA", "BESAN", "FLOUR", "RICE",
            "DAL", "OIL", "BISCUIT", "NOODLES", "CHIPS", "WAFER", "SALT", "SUGAR",
            "SAUCE", "KETCHUP", "JAM", "PICKLE", "PANEER", "MILK", "CHOCOLATE"
        ]
        for line in lines[:6]:
            l_upper = line.upper()
            if any(cw in l_upper for cw in commodity_words):
                # Clean line
                if not any(ex in l_upper for ex in ["PER 100G", "INGREDIENTS", "NET QTY", "MRP", "MFG"]):
                    res["name"] = line.strip()
                    break

        return res

    # =========================================================================
    # 8. Ingredients List Search
    # =========================================================================
    def _search_ingredients(self, lines: List[str], text: str) -> Dict[str, Any]:
        """
        Locates ingredient declaration blocks across English, Hindi, and Gujarati.
        """
        res = {"raw_text": None, "confidence": 0.0}
        stop_headers = [
            "NUTRITION", "NUTRITIONAL", "MFG", "PKD", "MFD", "MRP", "BEST BEFORE",
            "EXPIRY", "BATCH", "NET QTY", "NET WT", "FSSAI", "MARKETED BY",
            "MANUFACTURED BY", "CUSTOMER CARE", "STORAGE", "ALLERGEN ADVICE",
            "LIC NO", "UNIT SALE PRICE"
        ]

        header_patterns = [
            r"(?:INGREDIENTS\s*(?:USED)?|INGREDIENT\s*LIST|CONTAINS|COMPOSITION|सामग्री|ઘટકો)\s*[:\-–—]\s*(.+)",
            r"\bINGREDIENTS\b\s*[:\-–—]?\s*(.+)",
            r"\bCONTAINS\b\s*[:\-–—]\s*(.+)",
            r"\bMADE FROM\b\s*[:\-–—]\s*(.+)"
        ]

        for i, line in enumerate(lines):
            for pat in header_patterns:
                m = re.search(pat, line, re.IGNORECASE)
                if m:
                    extracted = m.group(1).strip()
                    # Collect following lines
                    j = i + 1
                    while j < len(lines):
                        nl = lines[j]
                        if any(nl.upper().startswith(sh) for sh in stop_headers):
                            break
                        if re.match(r"^(\d{10,14}|[A-Z0-9]{6,12})$", nl):
                            break
                        extracted += " " + nl
                        j += 1
                    res["raw_text"] = extracted.strip()
                    res["confidence"] = 0.85
                    return res

        return res
