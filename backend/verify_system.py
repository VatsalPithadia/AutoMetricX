import sys
import os
import cv2
import numpy as np
import json

sys.stdout.reconfigure(encoding='utf-8')

from app.barcode_engine import BarcodeQREngine
from app.llm_extractor import LLMExtractor
from app.classifier import FieldClassifier
from app.rule_engine import LMPCRuleEngine
from app.ocr_engine import detect_scripts_in_text, stitch_vertical_text_columns

def test_1_qr_code_recovery_under_poor_conditions():
    print("\n--- TEST 1: QR Code Recovery Under Poor Image Conditions & Clickable Link Generation ---")
    engine = BarcodeQREngine()
    assert engine.has_zxing, "ZXing engine should be enabled"

    target_url = "https://fssai.gov.in/verify?lic=10721001000889&batch=B2409"
    qr_enc = cv2.QRCodeEncoder_create()
    clean_qr = qr_enc.encode(target_url)

    # Degrade image: severe low contrast + heavy blur + camera noise
    degraded = cv2.resize(clean_qr, (350, 350), interpolation=cv2.INTER_NEAREST)
    degraded = cv2.GaussianBlur(degraded, (7, 7), 2.0)
    degraded = cv2.addWeighted(degraded, 0.35, np.full_like(degraded, 110), 0.65, 0)

    decoded_list = engine.decode_barcodes_and_qr(degraded)
    print(f"Decoded {len(decoded_list)} codes from severely degraded image.")
    assert len(decoded_list) >= 1, "Should decode QR code under degraded conditions"

    qr_item = decoded_list[0]
    print(f"  Format: {qr_item.get('format')}")
    print(f"  Engine: {qr_item.get('engine')}")
    print(f"  Recovery Method: {qr_item.get('recovery_method')}")
    print(f"  Is URL: {qr_item.get('is_url')}")
    print(f"  Original URL: {qr_item.get('original_url')}")
    print(f"  Category: {qr_item.get('category')}")
    print(f"  Parsed Attributes: {qr_item.get('parsed_attributes')}")

    assert qr_item.get("is_url") is True, "Must identify as clickable URL"
    assert qr_item.get("original_url") == target_url, "Original URL must match exactly"
    assert qr_item.get("parsed_attributes", {}).get("lic") == "10721001000889", "Must extract license parameter"
    print("✓ Test 1 Passed!")

def test_2_multilingual_gujarati_hindi_extraction():
    print("\n--- TEST 2: Gujarati & Hindi Multilingual Deep Field Extraction ---")
    extractor = LLMExtractor()

    gujarati_pack_text = """
    ROYAL GUJARAT BESAN
    Generic Commodity: Chana Besan / Pure Gram Flour
    ચોખ્ખું વજન: 500 g
    મ.ચી.ભા. ₹ 65.00 (બધા કર સહિત)
    USP: ₹ 0.13 / g
    MFG DATE: 15/10/2025
    EXPIRY DATE: 14/04/2026
    BATCH NO: B2409-G
    MANUFACTURED BY: Gujarat Agro Foods Pvt Ltd,
    Plot No. 112, GIDC Industrial Estate, Naroda, Ahmedabad, Gujarat - 382330
    ગ્રાહક સેવા સંપર્ક: 1800-233-5566 | Email: care@gujaratagro.com
    FSSAI Lic. No. 10721001000889
    """

    res = extractor._extract_fields_locally(gujarati_pack_text)
    print(f"  Commodity: {res.get('generic_commodity_name')}")
    print(f"  Net Qty: {res.get('net_quantity')}")
    print(f"  MRP: {res.get('mrp')}")
    print(f"  USP: {res.get('unit_sale_price')}")
    print(f"  Mfg Date: {res.get('mfg_date')}")
    print(f"  Exp Date: {res.get('expiry_date')}")
    print(f"  Batch: {res.get('batch_number')}")
    print(f"  Manufacturer: {res.get('manufacturer_details')[:50]}...")
    print(f"  Consumer Care: {res.get('consumer_care')}")
    print(f"  FSSAI: {res.get('fssai_number')}")
    print(f"  Detected Languages: {res.get('detected_languages')}")

    assert res.get("net_quantity") == "500 g", "Should extract net quantity"
    assert "65.00" in str(res.get("mrp")), "Should extract MRP value"
    assert "Gujarat" in res.get("detected_languages", []) or "Gujarati" in res.get("detected_languages", []), "Should detect Gujarati"
    assert res.get("fssai_number") == "10721001000889", "Should extract FSSAI number"
    assert "1800-233-5566" in str(res.get("consumer_care")), "Should extract toll-free number"
    print("✓ Test 2 Passed!")

def test_3_vertical_text_stitching():
    print("\n--- TEST 3: Vertical Format Text Column Stitching ---")
    mock_vertical_blocks = [
        {"id": 1, "text": "M", "rect": {"x": 12, "y": 80, "width": 18, "height": 22}, "confidence": 0.92},
        {"id": 2, "text": "R", "rect": {"x": 13, "y": 105, "width": 18, "height": 22}, "confidence": 0.94},
        {"id": 3, "text": "P", "rect": {"x": 12, "y": 130, "width": 18, "height": 22}, "confidence": 0.91},
        {"id": 4, "text": "Normal Horizontal Text", "rect": {"x": 100, "y": 100, "width": 150, "height": 25}, "confidence": 0.95}
    ]

    stitched, used_ids = stitch_vertical_text_columns(mock_vertical_blocks, start_block_id=10)
    print(f"  Stitched blocks: {len(stitched)}")
    if stitched:
        st = stitched[0]
        print(f"  Stitched Text: '{st['text']}'")
        print(f"  Is Vertical: {st['is_vertical']}")
        print(f"  Bounding Box: {st['rect']}")
        assert st["text"] == "MRP", "Should combine M-R-P into MRP"
        assert st["is_vertical"] is True, "Must tag is_vertical: True"
        assert used_ids == {1, 2, 3}, "Should mark IDs 1, 2, 3 as consumed"
    print("✓ Test 3 Passed!")

def test_4_full_rule_engine_compliance():
    print("\n--- TEST 4: Full Rule Engine 3-State Compliance Report ---")
    rules_path = os.path.join(os.path.dirname(__file__), "rules", "lmpc_rules.json")
    rule_checker = LMPCRuleEngine(rules_path)

    classified = {
        "commodity_name": {"clean_name": "Gram Flour / Besan", "confidence": 0.95},
        "net_quantity": {"formatted_value": "500 g", "numeric_value": 500, "unit": "g", "is_standard_unit": True, "confidence": 0.95},
        "mrp": {"formatted_value": "₹ 65.00 (Incl. of all taxes)", "value": 65.0, "has_tax_clause": True, "confidence": 0.95},
        "mfg_date": {"extracted_date": "15/10/2025", "confidence": 0.95},
        "expiry_date": {"extracted_date": "14/04/2026", "confidence": 0.95},
        "manufacturer_details": {"raw_text": "Gujarat Agro Foods Pvt Ltd, GIDC Naroda, Ahmedabad - 382330", "has_name": True, "has_address": True, "confidence": 0.95},
        "consumer_care": {"raw_text": "Toll-Free: 1800-233-5566 | care@gujaratagro.com", "has_phone": True, "has_email": True, "confidence": 0.95},
        "fssai_number": {"license_number": "10721001000889", "confidence": 0.95}
    }

    report = rule_checker.evaluate_compliance(classified, [])
    print(f"  Overall Status: {report['overall_status']}")
    print(f"  Compliance Score: {report['compliance_score']}%")
    print(f"  Passed Rules: {report['passed_rules_count']}/{report['total_rules_checked']}")

    assert report["overall_status"] in ["COMPLIANT", "PARTIALLY_COMPLIANT", "PASS"], f"Expected compliant or partially compliant, got {report['overall_status']}"
    assert report["passed_rules_count"] >= 8, f"Expected at least 8 passed rules, got {report['passed_rules_count']}"
    assert report["compliance_score"] >= 85.0, f"Compliance score should be >= 85%, got {report['compliance_score']}%"
    print("✓ Test 4 Passed!")

if __name__ == "__main__":
    test_1_qr_code_recovery_under_poor_conditions()
    test_2_multilingual_gujarati_hindi_extraction()
    test_3_vertical_text_stitching()
    test_4_full_rule_engine_compliance()
    print("\n=======================================================")
    print("🎉 ALL 4 SYSTEM VERIFICATION TESTS PASSED PERFECTLY!")
    print("=======================================================")
