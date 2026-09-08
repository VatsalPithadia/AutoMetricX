import os
import glob
import json
import re
import time
from typing import Dict, Any, List

# Ensure backend module can be imported
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from app.ocr_engine import extract_text_from_image
from app.classifier import FieldClassifier
from app.rule_engine import LMPCRuleEngine

TEST_IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_images")
RULES_PATH = os.path.join(os.path.dirname(__file__), "rules", "lmpc_rules.json")

def detect_suspicious_matches(classified_fields: Dict[str, Any]) -> List[str]:
    """
    Scans classified fields for suspicious false positives.
    """
    suspicious = []
    
    # 1. Commodity Name checks
    comm = classified_fields.get("commodity_name")
    if comm:
        raw_comm = comm.get("raw_text", "") if isinstance(comm, dict) else str(comm)
        # Suspicious if purely alphanumeric code with dashes/numbers or very short
        if re.search(r'^[A-Z0-9]{2,}-[A-Z0-9\-]+$', raw_comm):
            suspicious.append(f"commodity_name matched batch/product code: '{raw_comm}'")
        elif len(re.sub(r'[^a-zA-Z]', '', raw_comm)) < 3:
            suspicious.append(f"commodity_name lacks alphabetic words: '{raw_comm}'")
            
    # 2. MRP checks
    mrp = classified_fields.get("mrp")
    if mrp:
        val = mrp.get("value") if isinstance(mrp, dict) else None
        if val is not None and (val <= 0 or val > 50000):
            suspicious.append(f"mrp value out of realistic range: {val}")
            
    # 3. Net Quantity checks
    net_qty = classified_fields.get("net_quantity")
    if net_qty:
        unit = net_qty.get("unit", "") if isinstance(net_qty, dict) else ""
        if unit and unit.lower() not in ['g', 'kg', 'gm', 'gms', 'ml', 'l', 'ltr', 'n', 'pcs', 'units']:
            suspicious.append(f"net_quantity non-standard unit: '{unit}'")
            
    # 4. Check overlapping raw texts across distinct fields
    used_texts = {}
    for field_name, field_val in classified_fields.items():
        if field_name == "unclassified_blocks_count" or not field_val:
            continue
        raw_text = field_val.get("raw_text") if isinstance(field_val, dict) else str(field_val)
        if raw_text:
            if raw_text in used_texts:
                suspicious.append(f"Field overlap: '{field_name}' and '{used_texts[raw_text]}' both claimed '{raw_text}'")
            else:
                used_texts[raw_text] = field_name
                
    return suspicious

def run_accuracy_benchmark() -> Dict[str, Any]:
    classifier = FieldClassifier(min_confidence=0.40)
    rule_engine = LMPCRuleEngine(RULES_PATH)
    
    image_paths = sorted(glob.glob(os.path.join(TEST_IMAGES_DIR, "*.[jJ][pP][gG]")) + 
                        glob.glob(os.path.join(TEST_IMAGES_DIR, "*.[pP][nN][gG]")))
    
    if not image_paths:
        print(f"No test images found in {TEST_IMAGES_DIR}")
        return {}
        
    results = []
    total_blocks_all = 0
    total_suspicious_all = 0
    
    print(f"\n==========================================================================")
    print(f"RUNNING METROLENS ACCURACY BENCHMARK ON {len(image_paths)} TEST IMAGES")
    print(f"==========================================================================\n")
    
    for img_path in image_paths:
        filename = os.path.basename(img_path)
        start_t = time.time()
        
        with open(img_path, "rb") as f:
            img_bytes = f.read()
            
        ocr_result = extract_text_from_image(img_bytes)
        blocks = ocr_result.get("blocks", [])
        classified = classifier.classify_blocks(blocks)
        compliance = rule_engine.evaluate_compliance(classified, blocks)
        
        suspicious_flags = detect_suspicious_matches(classified)
        
        # Count non-null classified declarations (out of 7 core LMPC fields)
        target_fields = ["mrp", "net_quantity", "mfg_date", "expiry_date", "manufacturer_details", "consumer_care", "commodity_name"]
        confident_declarations = sum(1 for f in target_fields if classified.get(f) is not None)
        
        # High confidence blocks count (conf >= 0.60)
        high_conf_blocks = sum(1 for b in blocks if b.get("confidence", 0) >= 0.60)
        low_conf_blocks = sum(1 for b in blocks if b.get("confidence", 0) < 0.60)
        
        elapsed = round(time.time() - start_t, 2)
        total_blocks_all += len(blocks)
        total_suspicious_all += len(suspicious_flags)
        
        item_res = {
            "filename": filename,
            "engine": ocr_result.get("engine"),
            "image_size": f"{ocr_result['image_metadata']['width']}x{ocr_result['image_metadata']['height']}",
            "original_size": f"{ocr_result['image_metadata']['original_width']}x{ocr_result['image_metadata']['original_height']}",
            "total_detected_blocks": len(blocks),
            "high_conf_blocks": high_conf_blocks,
            "low_conf_blocks": low_conf_blocks,
            "confident_declarations": confident_declarations,
            "overall_status": compliance["overall_status"],
            "compliance_score": compliance["compliance_score"],
            "suspicious_flags": suspicious_flags,
            "processing_time_sec": elapsed,
            "classified_fields": {k: (v.get("raw_text") if isinstance(v, dict) else v) for k, v in classified.items() if v}
        }
        results.append(item_res)
        
        print(f"Image: {filename}")
        print(f"  - Size: {item_res['original_size']} -> Resized: {item_res['image_size']}")
        print(f"  - Detected Regions: {len(blocks)} (High Conf >=0.6: {high_conf_blocks}, Low Conf <0.6: {low_conf_blocks})")
        print(f"  - Confident Declarations: {confident_declarations}/7")
        print(f"  - Compliance Score: {compliance['compliance_score']}% ({compliance['overall_status']})")
        if suspicious_flags:
            print(f"  - [SUSPICIOUS MATCHES] ({len(suspicious_flags)}):")
            for flag in suspicious_flags:
                print(f"      * {flag}")
        else:
            print(f"  - [OK] Suspicious Matches: None (0)")
        print(f"  - Processing Time: {elapsed}s")
        print("--------------------------------------------------------------------------")
        
    summary = {
        "timestamp": time.time(),
        "total_test_images": len(image_paths),
        "total_detected_blocks": total_blocks_all,
        "total_suspicious_matches": total_suspicious_all,
        "images": results
    }
    
    return summary

if __name__ == "__main__":
    benchmark_data = run_accuracy_benchmark()
    output_path = os.path.join(os.path.dirname(__file__), "test_benchmark_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)
    print(f"\nSaved benchmark metrics to {output_path}\n")
