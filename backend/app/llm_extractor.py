import os
import re
import json
import logging
import httpx
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("metrolens.llm_extractor")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

class LLMExtractor:
    def __init__(self, timeout_sec: float = 8.0):
        self.timeout_sec = timeout_sec

    def extract_fields_from_ocr(self, raw_ocr_text: str) -> Optional[Dict[str, Any]]:
        """
        Contextual LLM & NLP Text Cleanup + Field Extraction.
        Sends raw OCR text to Gemini 2.5 Flash if GEMINI_API_KEY is configured.
        Otherwise executes intelligent local NLP context recovery fallback.
        """
        if not raw_ocr_text or len(raw_ocr_text.strip()) < 5:
            return None

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            prompt = f"""You are extracting mandatory Legal Metrology (LMPC) declarations from raw OCR text extracted from an Indian packaged commodity product label.
The OCR text may contain errors, typos, or garbled text due to image quality, curved packaging, or small fonts — use surrounding context to correct obvious misreads.

Extract the following mandatory fields if present:
1. generic_commodity_name: string or null (e.g. "Spiced Masala Powder", "Eno Antacid")
2. net_quantity: string or null (e.g. "50 g", "5 g", "100 ml")
3. mrp: string or null (e.g. "Rs. 23.00 (Incl. of all taxes)")
4. mfg_date: string or null (e.g. "OCT 2025")
5. expiry_date: string or null (e.g. "SEP 2026")
6. manufacturer_details: string or null
7. consumer_care: string or null
8. fssai_number: string or null

Return ONLY valid JSON matching this exact structure:
{{
  "generic_commodity_name": string or null,
  "net_quantity": string or null,
  "mrp": string or null,
  "mfg_date": string or null,
  "expiry_date": string or null,
  "manufacturer_details": string or null,
  "consumer_care": string or null,
  "fssai_number": string or null
}}

RAW OCR TEXT:
{raw_ocr_text.strip()}
"""
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}
            }
            url = f"{GEMINI_API_URL}?key={api_key}"
            try:
                with httpx.Client(timeout=self.timeout_sec) as client:
                    response = client.post(url, json=payload)
                    if response.status_code == 200:
                        res_json = response.json()
                        candidates = res_json.get("candidates", [])
                        if candidates:
                            raw_json_str = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            parsed = json.loads(raw_json_str)
                            logger.info("Successfully extracted fields via Gemini 2.5 Flash API.")
                            return parsed
            except Exception as err:
                logger.warning(f"Gemini API call failed ({err}). Falling back to local NLP extractor.")

        # Local NLP Contextual Error Correction Fallback
        logger.info("Executing local contextual NLP text cleanup fallback...")
        extracted = {
            "generic_commodity_name": None,
            "net_quantity": None,
            "mrp": None,
            "mfg_date": None,
            "expiry_date": None,
            "manufacturer_details": None,
            "consumer_care": None,
            "fssai_number": None
        }

        # 1. Net Quantity context extraction (e.g., cleans '1-05-26 50g' -> '50 g', '5g', '100 ml')
        qty_m = re.search(r'\b(\d+(?:\.\d+)?)\s*(g|kg|gm|gms|ml|l|ltr|pcs|n)\b', raw_ocr_text, re.IGNORECASE)
        if qty_m:
            extracted["net_quantity"] = f"{qty_m.group(1)} {qty_m.group(2)}"

        # 2. MRP context extraction (cleans 'MRP F23.00' or 'Rs 25.00')
        mrp_m = re.search(r'(?:M\.?R\.?P\.?|RS\.?|₹|PRICE|F)\s*[:=.\s]*[₹Rs.]?\s*(\d{1,4}(?:\.\d{1,2})?)', raw_ocr_text, re.IGNORECASE)
        if mrp_m:
            val = float(mrp_m.group(1))
            if 1.0 <= val <= 50000.0:
                extracted["mrp"] = f"Rs. {val:.2f} (Incl. of all taxes)"

        # 3. Mfg & Expiry Date extraction
        dates = re.findall(r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|0CT|NOV|DEC)[\.\s/|-]*(20[1-3][0-9])\b', raw_ocr_text, re.IGNORECASE)
        if len(dates) >= 2:
            extracted["mfg_date"] = f"{dates[0][0].upper()}/{dates[0][1]}"
            extracted["expiry_date"] = f"{dates[1][0].upper()}/{dates[1][1]}"
        elif len(dates) == 1:
            extracted["mfg_date"] = f"{dates[0][0].upper()}/{dates[0][1]}"

        # 4. FSSAI License extraction
        fssai_m = re.search(r'\b(1\d{13}|2\d{13})\b', raw_ocr_text)
        if fssai_m:
            extracted["fssai_number"] = fssai_m.group(1)

        # 5. Manufacturer details extraction
        mfg_m = re.search(r'(?:MANUFACTURED|PACKED|MARKETED|MFD|PKD)\s*BY\s*[:=.\s]*([A-Za-z0-9\s.,\(\)-]{5,60})', raw_ocr_text, re.IGNORECASE)
        if mfg_m:
            extracted["manufacturer_details"] = mfg_m.group(0).strip()

        # 6. Consumer care extraction
        email_m = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', raw_ocr_text)
        phone_m = re.search(r'(?:CARE|HELPLINE|NO|TEL)\s*[:=.\s]*(\d{10}|\d{4}[-\s]?\d{3}[-\s]?\d{4})', raw_ocr_text, re.IGNORECASE)
        if email_m or phone_m:
            care_str = []
            if phone_m: care_str.append(f"Phone: {phone_m.group(1)}")
            if email_m: care_str.append(f"Email: {email_m.group(1)}")
            extracted["consumer_care"] = " | ".join(care_str)

        return extracted
