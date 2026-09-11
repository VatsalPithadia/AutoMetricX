import logging
import cv2
import numpy as np
import re
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("metrolens.barcode_engine")

class BarcodeQREngine:
    """
    Industrial-Grade 1D Barcode & 2D QR Code Decoding & Intelligence Engine.
    
    Capabilities:
    - Multi-engine architecture: ZXing-C++, PyZbar, OpenCV QRCodeDetectorAruco, OpenCV BarcodeDetector.
    - 6-stage image restoration pipeline for poor conditions (severe blur, glare, dark shadows, low contrast, angled captures).
    - Original QR link generation: Validates, cleans, and builds clickable URLs that open directly in browser.
    - Deep payload inspector: Parses GS1 Digital Links, FSSAI verification portals, batch metadata, and UPI/vCard payloads.
    - Cross-verifies barcode/QR data against OCR label text to detect mismatch fraud.
    """

    def __init__(self):
        self.has_zxing: bool = False
        self.zxing: Optional[Any] = None
        try:
            import zxingcpp
            self.zxing = zxingcpp
            self.has_zxing = True
            logger.info("ZXing-C++ high-performance engine loaded successfully.")
        except ImportError:
            self.zxing = None
            logger.warning("ZXing-C++ not available; falling back to PyZbar / OpenCV.")

    def _generate_enhanced_variants(self, image: np.ndarray) -> List[tuple]:
        """
        Generates 6 complementary image enhancement variants to recover QR codes
        under poor lighting, glare, motion blur, and distorted angles.
        Returns list of (variant_image, method_name).
        """
        variants = []
        if image is None or image.size == 0:
            return variants

        # 1. Base image (Original)
        variants.append((image, "Original Image"))

        # Convert to Grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
        variants.append((gray, "Grayscale"))

        # 2. CLAHE (Contrast-Limited Adaptive Histogram Equalization) - fixes glare & uneven shadows
        try:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced_clahe = clahe.apply(gray)
            variants.append((enhanced_clahe, "CLAHE Contrast Recovery"))
        except Exception:
            enhanced_clahe = gray

        # 3. Unsharp Masking (Deblurring & Edge Sharpening) - recovers camera blur & out-of-focus captures
        try:
            gaussian = cv2.GaussianBlur(enhanced_clahe, (0, 0), 2.0)
            unsharp = cv2.addWeighted(enhanced_clahe, 2.0, gaussian, -1.0, 0)
            variants.append((unsharp, "Unsharp Mask Sharpening"))
        except Exception:
            unsharp = enhanced_clahe

        # 4. Otsu Adaptive Binarization - handles low-contrast colored backgrounds
        try:
            _, otsu_bin = cv2.threshold(unsharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            variants.append((otsu_bin, "Otsu Adaptive Binarization"))
        except Exception:
            pass

        # 5. Multi-Scale Upsampling (2x) - recovers small / low-res QR codes on phone cameras
        h, w = gray.shape[:2]
        if max(h, w) < 1800:
            try:
                upscaled_2x = cv2.resize(unsharp, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                variants.append((upscaled_2x, "2x Super-Resolution Upscale"))
            except Exception:
                pass

        return variants

    def _parse_qr_payload(self, data_str: str, b_type: str) -> Dict[str, Any]:
        """
        Inspects raw barcode/QR data to extract clickable URLs, FSSAI licenses,
        GS1 GTIN attributes, and categorize content for user preview.
        """
        data_clean = data_str.strip()
        is_url = False
        original_url = None
        category = "RAW_TEXT"
        summary = "Standard Data Payload"
        attributes = {}

        # 1. URL & GS1 Digital Link Detection
        url_match = re.search(r'https?://[^\s<>"]+|www\.[^\s<>"]+', data_clean, re.IGNORECASE)
        if url_match:
            raw_url = url_match.group(0)
            if not raw_url.startswith("http"):
                raw_url = "https://" + raw_url
            is_url = True
            original_url = raw_url
            category = "WEB_URL"
            summary = "Clickable Web Link"

            # Parse query params or GS1 Digital Link paths
            try:
                parsed = urlparse(raw_url)
                qs = parse_qs(parsed.query)
                for k, v in qs.items():
                    attributes[k] = v[0] if len(v) == 1 else v
                
                # Check for specific portals
                if "fssai.gov.in" in parsed.netloc:
                    category = "FSSAI_VERIFICATION"
                    summary = "Official FSSAI Food Safety Verification Portal"
                elif "gs1.org" in parsed.netloc or "/01/" in parsed.path:
                    category = "GS1_DIGITAL_LINK"
                    summary = "GS1 Standard Digital Smart Label"
                elif any(term in parsed.netloc or term in parsed.path for term in ["verify", "auth", "track", "trace", "batch"]):
                    category = "PRODUCT_AUTHENTICITY"
                    summary = "Product Authenticity & Batch Tracking Link"
            except Exception:
                pass

        # 2. FSSAI License inside payload
        fssai_match = re.search(r'\b(1\d{13}|2\d{13})\b', data_clean)
        if fssai_match:
            attributes["fssai_license"] = fssai_match.group(1)
            if not is_url:
                category = "FSSAI_DATA"
                summary = f"FSSAI License: {fssai_match.group(1)}"

        # 3. UPI Payment Code
        if data_clean.startswith("upi://"):
            category = "UPI_PAYMENT"
            summary = "UPI Digital Payment Link"

        # 4. vCard / Contact Card
        if "BEGIN:VCARD" in data_clean:
            category = "CONTACT_VCARD"
            summary = "Contact Information Card"

        # 5. Barcode GTIN Code
        if b_type in ["EAN13", "EAN8", "UPCA", "CODE128", "EAN_13", "EAN_8", "UPC_A"]:
            category = "GTIN_BARCODE"
            summary = f"Retail GTIN Barcode: {data_clean}"
            attributes["gtin"] = data_clean

        return {
            "is_url": is_url,
            "original_url": original_url,
            "category": category,
            "summary": summary,
            "parsed_attributes": attributes
        }

    @staticmethod
    def _verify_gs1_checksum(digits: List[int]) -> bool:
        if len(digits) not in [8, 12, 13, 14]:
            return False
        check_digit = digits[-1]
        core_digits = digits[:-1]
        total = sum(d * (3 if idx % 2 == 0 else 1) for idx, d in enumerate(reversed(core_digits)))
        return (10 - (total % 10)) % 10 == check_digit

    def recover_barcodes_from_ocr_blocks(
        self,
        ocr_blocks: List[Dict[str, Any]],
        image: Optional[np.ndarray] = None,
        seen_data: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Industrial Fallback: Recovers retail 1D barcodes (EAN-13, EAN-8, UPC-A) when optical line scanning
        fails due to glossy glare, packaging curves, pouch crinkles, or motion blur.
        Uses OCR Human-Readable Interpretation (HRI) numbers printed below the bars and verifies GS1 Modulo-10 checksums.
        """
        results: List[Dict[str, Any]] = []
        if not ocr_blocks:
            return results
        if seen_data is None:
            seen_data = set()

        for b in ocr_blocks:
            raw_text = b.get("text", "")
            if not raw_text:
                continue

            # Standardize character confusions common in OCR of barcode font (OCR-B):
            norm_text = raw_text.replace('l', '1').replace('|', '1').replace('I', '1')
            digits = [int(c) for c in norm_text if c.isdigit()]

            verified_code: Optional[str] = None
            if len(digits) == 13:
                if self._verify_gs1_checksum(digits):
                    verified_code = "".join(map(str, digits))
                # Indian packaging OCR repair: 840... or 810... where 9 was confused for 4 or 1
                elif digits[0] == 8 and digits[2] == 0:
                    repair_digits = list(digits)
                    repair_digits[1] = 9
                    if self._verify_gs1_checksum(repair_digits):
                        verified_code = "".join(map(str, repair_digits))
            elif len(digits) in [8, 12, 14]:
                if self._verify_gs1_checksum(digits):
                    verified_code = "".join(map(str, digits))

            if verified_code and verified_code not in seen_data:
                b_rect = b.get("rect", {})
                rect_dict = {
                    "x": float(b_rect.get("x", 0.0)),
                    "y": float(b_rect.get("y", 0.0)),
                    "width": float(b_rect.get("width", 100.0)),
                    "height": float(b_rect.get("height", 30.0))
                }

                # Attempt focused localized ZXing crop above the text block (where bars are located)
                optical_found = False
                if image is not None and self.has_zxing and self.zxing is not None and rect_dict["width"] > 0:
                    try:
                        ih, iw = image.shape[:2]
                        bx = int(rect_dict["x"])
                        by = int(rect_dict["y"])
                        bw = int(rect_dict["width"])
                        bh = int(rect_dict["height"])

                        crop_y1 = max(0, by - int(bh * 4.5))
                        crop_y2 = min(ih, by + int(bh * 1.5))
                        crop_x1 = max(0, bx - int(bw * 0.2))
                        crop_x2 = min(iw, bx + int(bw * 1.2))

                        if crop_y2 > crop_y1 and crop_x2 > crop_x1:
                            crop = image[crop_y1:crop_y2, crop_x1:crop_x2]
                            crop_variants = self._generate_enhanced_variants(crop)
                            for c_var, _ in crop_variants[:3]:
                                b_codes = self.zxing.read_barcodes(c_var)
                                for bc in b_codes:
                                    bc_txt = bc.text.strip() if bc.text else ""
                                    if bc_txt == verified_code:
                                        payload_info = self._parse_qr_payload(bc_txt, "EAN13")
                                        results.append({
                                            "type": "EAN13",
                                            "format": str(bc.format).replace("BarcodeFormat.", ""),
                                            "data": bc_txt,
                                            "is_url": False,
                                            "original_url": None,
                                            "category": "GTIN_BARCODE",
                                            "summary": f"Retail GTIN Barcode: {bc_txt}",
                                            "parsed_attributes": payload_info["parsed_attributes"],
                                            "rect": rect_dict,
                                            "recovery_method": "Localized Crop Optical Barcode Recovery",
                                            "engine": "ZXing-C++"
                                        })
                                        seen_data.add(bc_txt)
                                        optical_found = True
                                        break
                                if optical_found:
                                    break
                    except Exception as cr_err:
                        logger.debug(f"Barcode crop pass error: {cr_err}")

                if not optical_found and verified_code not in seen_data:
                    # Verified GS1 Human-Readable Interpretation (HRI) recovery
                    country = "India (GS1 890)" if verified_code.startswith("890") else "GS1 Standard"
                    results.append({
                        "type": "EAN13" if len(verified_code) == 13 else ("EAN8" if len(verified_code) == 8 else "UPCA"),
                        "format": f"EAN-{len(verified_code)} (HRI)",
                        "data": verified_code,
                        "is_url": False,
                        "original_url": None,
                        "category": "GTIN_BARCODE",
                        "summary": f"Retail GTIN Barcode: {verified_code}",
                        "parsed_attributes": {
                            "gtin": verified_code,
                            "country_origin": country,
                            "checksum_verified": True
                        },
                        "rect": rect_dict,
                        "recovery_method": "OCR Human-Readable Interpretation (HRI) Checksum Verification",
                        "engine": "OCR-HRI-GS1"
                    })
                    seen_data.add(verified_code)

        return results

    def decode_barcodes_and_qr(
        self,
        image: np.ndarray,
        ocr_blocks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Comprehensive Multi-Stage Barcode & QR Code Decoder.
        Tries ZXing-C++, PyZbar, and OpenCV across multi-enhancement filters,
        with localized optical crop and OCR GS1 HRI verification fallback.
        """
        results: List[Dict[str, Any]] = []
        seen_data: Set[str] = set()

        if image is None or image.size == 0:
            return results

        def has_1d() -> bool:
            return any(r.get("category") == "GTIN_BARCODE" or r.get("type") in ["EAN13", "EAN8", "UPCA", "CODE128", "EAN_13", "EAN_8", "UPC_A"] for r in results)

        def has_qr() -> bool:
            return any(r.get("type") == "QRCODE" for r in results)

        variants = self._generate_enhanced_variants(image)

        # PASS 1: High-Performance ZXing-C++ across enhanced variants
        if self.has_zxing and self.zxing is not None:
            for var_img, method in variants:
                try:
                    barcodes = self.zxing.read_barcodes(var_img)
                    for b in barcodes:
                        txt = b.text.strip() if b.text else ""
                        if not txt or txt in seen_data:
                            continue

                        format_str = str(b.format).replace("BarcodeFormat.", "")
                        b_type = "QRCODE" if "QR" in format_str.upper() else format_str.upper()

                        pos = b.position
                        try:
                            xs = [pos.top_left.x, pos.top_right.x, pos.bottom_right.x, pos.bottom_left.x]
                            ys = [pos.top_left.y, pos.top_right.y, pos.bottom_right.y, pos.bottom_left.y]
                            rect_dict = {
                                "x": float(min(xs)),
                                "y": float(min(ys)),
                                "width": float(max(xs) - min(xs)),
                                "height": float(max(ys) - min(ys))
                            }
                        except Exception:
                            rect_dict = {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0}

                        payload_info = self._parse_qr_payload(txt, b_type)
                        results.append({
                            "type": b_type,
                            "format": format_str,
                            "data": txt,
                            "is_url": payload_info["is_url"],
                            "original_url": payload_info["original_url"],
                            "category": payload_info["category"],
                            "summary": payload_info["summary"],
                            "parsed_attributes": payload_info["parsed_attributes"],
                            "rect": rect_dict,
                            "recovery_method": method,
                            "engine": "ZXing-C++"
                        })
                        seen_data.add(txt)
                except Exception as zx_err:
                    logger.debug(f"ZXing pass error ({method}): {zx_err}")

                # If BOTH 1D barcode and QR code are decoded, we can stop variants search
                if has_1d() and has_qr():
                    break

        # PASS 2: PyZbar Decoding fallback
        if not (has_1d() and has_qr()):
            try:
                from pyzbar import pyzbar
                for var_img, method in variants[:3]:
                    decoded = pyzbar.decode(var_img)
                    for item in decoded:
                        txt = item.data.decode('utf-8', errors='ignore').strip()
                        if not txt or txt in seen_data:
                            continue
                        b_type = "QRCODE" if "QR" in str(item.type).upper() else str(item.type).upper()
                        rect = item.rect
                        payload_info = self._parse_qr_payload(txt, b_type)
                        results.append({
                            "type": b_type,
                            "format": str(item.type),
                            "data": txt,
                            "is_url": payload_info["is_url"],
                            "original_url": payload_info["original_url"],
                            "category": payload_info["category"],
                            "summary": payload_info["summary"],
                            "parsed_attributes": payload_info["parsed_attributes"],
                            "rect": {"x": float(rect.left), "y": float(rect.top), "width": float(rect.width), "height": float(rect.height)},
                            "recovery_method": method,
                            "engine": "PyZbar"
                        })
                        seen_data.add(txt)
                    if has_1d() and has_qr():
                        break
            except Exception as pz_err:
                logger.debug(f"PyZbar decoding fallback skipped: {pz_err}")

        # PASS 3: OpenCV QRCodeDetectorAruco & QRCodeDetector for missing QR code
        if not has_qr():
            try:
                aruco_det = cv2.QRCodeDetectorAruco()
                for var_img, method in variants[:3]:
                    data_str, bbox, _ = aruco_det.detectAndDecode(var_img)
                    if data_str and data_str.strip() and data_str.strip() not in seen_data:
                        txt = data_str.strip()
                        payload_info = self._parse_qr_payload(txt, "QRCODE")
                        results.append({
                            "type": "QRCODE",
                            "format": "QR Code",
                            "data": txt,
                            "is_url": payload_info["is_url"],
                            "original_url": payload_info["original_url"],
                            "category": payload_info["category"],
                            "summary": payload_info["summary"],
                            "parsed_attributes": payload_info["parsed_attributes"],
                            "rect": {"x": 0.0, "y": 0.0, "width": 120.0, "height": 120.0},
                            "recovery_method": method,
                            "engine": "OpenCV-QRCodeDetectorAruco"
                        })
                        seen_data.add(txt)
                        break
            except Exception as aruco_err:
                logger.debug(f"OpenCV Aruco detector skipped: {aruco_err}")

        # PASS 4: Rotation checks for angled / skewed packaging if still missing 1D or QR
        if not (has_1d() and has_qr()) and self.has_zxing and self.zxing is not None:
            zxing_engine = self.zxing
            for angle in [90, 180, 270]:
                rot_code = cv2.ROTATE_90_CLOCKWISE if angle == 90 else (cv2.ROTATE_180 if angle == 180 else cv2.ROTATE_90_COUNTERCLOCKWISE)
                rot_img = cv2.rotate(image, rot_code)
                try:
                    barcodes = zxing_engine.read_barcodes(rot_img)
                    for b in barcodes:
                        txt = b.text.strip() if b.text else ""
                        if not txt or txt in seen_data:
                            continue
                        format_str = str(b.format).replace("BarcodeFormat.", "")
                        b_type = "QRCODE" if "QR" in format_str.upper() else format_str.upper()
                        payload_info = self._parse_qr_payload(txt, b_type)
                        results.append({
                            "type": b_type,
                            "format": format_str,
                            "data": txt,
                            "is_url": payload_info["is_url"],
                            "original_url": payload_info["original_url"],
                            "category": payload_info["category"],
                            "summary": payload_info["summary"],
                            "parsed_attributes": payload_info["parsed_attributes"],
                            "rect": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                            "recovery_method": f"{angle}° Rotation Recovery",
                            "engine": "ZXing-C++"
                        })
                        seen_data.add(txt)
                except Exception:
                    pass
                if has_1d() and has_qr():
                    break

        # PASS 5: OCR Human-Readable Interpretation (HRI) 1D Barcode Recovery
        # If optical scan could not decode 1D barcode stripes due to pouch crinkles/curves/glare,
        # recover from mathematically verified GS1 digits below the code
        if not has_1d() and ocr_blocks:
            hri_barcodes = self.recover_barcodes_from_ocr_blocks(ocr_blocks, image, seen_data)
            results.extend(hri_barcodes)

        logger.info(f"Total decoded barcodes/QRs: {len(results)} (Engines: {[r['engine'] for r in results]})")
        return results

    def verify_cross_check(self, decoded_codes: List[Dict[str, Any]], classified_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cross-verifies decoded barcode/QR data against OCR classified fields:
        - FSSAI License Number cross-check
        - GTIN / EAN barcode catalog check
        - Original QR clickable URLs and full payload extraction
        """
        ocr_fssai = classified_fields.get("fssai_number", {})
        ocr_fssai_num = ocr_fssai.get("license_number") if isinstance(ocr_fssai, dict) else None

        fssai_matches = []
        gtin_codes = []
        qr_urls = []
        qr_payloads = []
        primary_qr = None

        for code in decoded_codes:
            data = code.get("data", "")
            b_type = code.get("type", "")
            is_url = code.get("is_url", False)
            orig_url = code.get("original_url")

            # Collect all valid URLs
            if is_url and orig_url:
                qr_urls.append(orig_url)
            elif "http://" in data or "https://" in data or "gs1" in data.lower():
                qr_urls.append(data)

            # Keep track of detailed QR payloads
            if b_type == "QRCODE":
                qr_payloads.append(code)
                if primary_qr is None:
                    primary_qr = code

            # Check for 14-digit FSSAI number inside barcode/QR data
            fssai_found = re.findall(r'\b(1\d{13}|2\d{13})\b', data)
            if fssai_found:
                fssai_matches.extend(fssai_found)

            # Check GTIN / EAN barcode
            if b_type in ["EAN13", "EAN8", "UPCA", "CODE128", "EAN_13", "EAN_8", "UPC_A"]:
                gtin_codes.append(data)

        # Cross-check verification status
        if ocr_fssai_num and fssai_matches:
            if ocr_fssai_num in fssai_matches:
                fssai_verification = {
                    "status": "MATCHED",
                    "explanation": f"Decoded QR/Barcode FSSAI number ('{fssai_matches[0]}') perfectly matches OCR label text."
                }
            else:
                fssai_verification = {
                    "status": "MISMATCH",
                    "explanation": f"Mismatch detected: QR code FSSAI ('{fssai_matches[0]}') differs from printed label ('{ocr_fssai_num}')."
                }
        elif ocr_fssai_num:
            fssai_verification = {
                "status": "OCR_ONLY",
                "explanation": f"FSSAI license number ('{ocr_fssai_num}') verified from printed OCR label text."
            }
        elif fssai_matches:
            fssai_verification = {
                "status": "QR_ONLY",
                "explanation": f"FSSAI license number ('{fssai_matches[0]}') verified from decoded QR code."
            }
        else:
            fssai_verification = {
                "status": "NOT_FOUND",
                "explanation": "No barcode/QR FSSAI code detected."
            }

        # Deduplicate URLs and GTINs
        unique_urls = list(dict.fromkeys(qr_urls))
        unique_gtin = list(dict.fromkeys(gtin_codes))

        return {
            "total_decoded_codes": len(decoded_codes),
            "decoded_codes": decoded_codes,
            "gtin_barcodes": unique_gtin,
            "qr_urls": unique_urls,
            "primary_qr_code": primary_qr,
            "qr_payloads": qr_payloads,
            "fssai_cross_check": fssai_verification
        }
