import logging
import cv2
import numpy as np
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("metrolens.barcode_engine")

class BarcodeQREngine:
    """
    1D Barcode & 2D QR Code Decoding & Compliance Cross-Check Engine.
    
    Features:
    - Decodes EAN-13, EAN-8, UPC-A, Code-128, and QR codes using PyZbar and OpenCV.
    - Extracts FSSAI 14-digit license numbers and GS1 GTIN product codes.
    - Cross-verifies barcode/QR data against OCR-extracted label text to detect mismatch fraud.
    """

    def __init__(self):
        pass

    def decode_barcodes_and_qr(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Decodes all 1D barcodes and 2D QR codes in the image.
        """
        results = []
        try:
            from pyzbar import pyzbar
            decoded = pyzbar.decode(image)
            for item in decoded:
                b_type = item.type
                data_str = item.data.decode('utf-8', errors='ignore').strip()
                rect = item.rect
                
                results.append({
                    "type": b_type,
                    "data": data_str,
                    "rect": {"x": float(rect.left), "y": float(rect.top), "width": float(rect.width), "height": float(rect.height)}
                })
        except Exception as err:
            logger.warning(f"PyZbar decoding exception: {err}")

        # OpenCV BarcodeDetector fallback if PyZbar missed 1D barcode
        if not any(r["type"] in ["EAN13", "EAN8", "UPCA", "CODE128"] for r in results):
            try:
                bc_detector = cv2.barcode.BarcodeDetector()
                ok, info, _ = bc_detector.detectAndDecode(image)
                if ok and len(info) > 0 and info.strip():
                    results.append({
                        "type": "EAN13",
                        "data": info.strip(),
                        "rect": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0}
                    })
                    logger.info(f"Decoded 1D barcode via OpenCV BarcodeDetector: {info.strip()}")
            except Exception as err:
                logger.debug(f"OpenCV barcode detector fallback skipped: {err}")

        # OpenCV QRCodeDetector fallback if PyZbar missed QR code
        if not any(r["type"] == "QRCODE" for r in results):
            try:
                qr_detector = cv2.QRCodeDetector()
                data_str, bbox, _ = qr_detector.detectAndDecode(image)
                if data_str and data_str.strip():
                    results.append({
                        "type": "QRCODE",
                        "data": data_str.strip(),
                        "rect": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0}
                    })
            except Exception as err:
                logger.debug(f"OpenCV QR detection skipped: {err}")

        return results

    def verify_cross_check(self, decoded_codes: List[Dict[str, Any]], classified_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cross-verifies barcode/QR decoded data against OCR classified fields:
        - FSSAI License Number verification
        - GTIN / Barcode presence
        """
        ocr_fssai = classified_fields.get("fssai_number", {})
        ocr_fssai_num = ocr_fssai.get("license_number") if isinstance(ocr_fssai, dict) else None

        fssai_matches = []
        gtin_codes = []
        qr_urls = []

        for code in decoded_codes:
            data = code.get("data", "")
            b_type = code.get("type", "")

            # Check for 14-digit FSSAI number inside barcode/QR data
            fssai_found = re.findall(r'\b(1\d{13}|2\d{13})\b', data)
            if fssai_found:
                fssai_matches.extend(fssai_found)

            # Check GTIN / EAN barcode
            if b_type in ["EAN13", "EAN8", "UPCA", "CODE128"]:
                gtin_codes.append(data)

            # Check QR URLs
            if "http://" in data or "https://" in data or "gs1" in data.lower():
                qr_urls.append(data)

        # Cross-check verification status
        if ocr_fssai_num and fssai_matches:
            if ocr_fssai_num in fssai_matches:
                fssai_verification = {
                    "status": "MATCHED",
                    "explanation": f"Decoded QR/Barcode FSSAI number ('{fssai_matches[0]}') matches OCR label text."
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
                "explanation": f"FSSAI license number ('{fssai_matches[0]}') verified from QR code."
            }
        else:
            fssai_verification = {
                "status": "NOT_FOUND",
                "explanation": "No barcode/QR FSSAI code detected."
            }

        return {
            "total_decoded_codes": len(decoded_codes),
            "decoded_codes": decoded_codes,
            "gtin_barcodes": list(set(gtin_codes)),
            "qr_urls": list(set(qr_urls)),
            "fssai_cross_check": fssai_verification
        }
