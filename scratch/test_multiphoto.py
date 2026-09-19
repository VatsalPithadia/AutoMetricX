import os, sys, json
sys.path.insert(0, 'backend')
from app.main import _process_single_image_bytes
from app.classifier import FieldClassifier
from app.rule_engine import LMPCRuleEngine
from app.barcode_engine import BarcodeQREngine as BarcodeEngine

classifier_engine = FieldClassifier(min_confidence=0.40)
rule_checker = LMPCRuleEngine('backend/rules/lmpc_rules.json')
barcode_engine = BarcodeEngine()

def test_pair(front_name, back_name):
    print(f"\n=======================================================")
    print(f"TESTING MULTI-PHOTO MERGE: {front_name} + {back_name}")
    print(f"=======================================================")
    
    front_path = os.path.join('test_images', front_name)
    back_path = os.path.join('test_images', back_name)
    
    with open(front_path, 'rb') as f:
        front_bytes = f.read()
    with open(back_path, 'rb') as f:
        back_bytes = f.read()
        
    res_front = _process_single_image_bytes(front_bytes, front_name)
    res_front["filename"] = front_name
    res_front["side_index"] = 1
    
    res_back = _process_single_image_bytes(back_bytes, back_name)
    res_back["filename"] = back_name
    res_back["side_index"] = 2
    
    print(f"Front alone: Score = {res_front['compliance_report']['compliance_score']}%, Status = {res_front['compliance_report']['overall_status']}")
    print(f"Back alone:  Score = {res_back['compliance_report']['compliance_score']}%, Status = {res_back['compliance_report']['overall_status']}")
    
    # Merge sides
    side_results = [res_front, res_back]
    merged_fields = classifier_engine.merge_multiside_fields(side_results)
    
    all_blocks = []
    for s in side_results:
        for b in s.get("ocr_blocks", []):
            b_copy = dict(b)
            b_copy["side_index"] = s["side_index"]
            all_blocks.append(b_copy)
            
    final_report = rule_checker.evaluate_compliance(
        merged_fields,
        all_blocks,
        image=None,
        image_metadata=side_results[0]["image_metadata"]
    )
    
    print(f"\nMERGED RESULT:")
    print(f"Overall Status: {final_report['overall_status']}")
    print(f"Compliance Score: {final_report['compliance_score']}%")
    print("Merged Fields:")
    for k in ['commodity_name', 'net_quantity', 'mrp', 'mfg_date', 'expiry_date', 'manufacturer_details', 'consumer_care', 'fssai_number']:
        v = merged_fields.get(k)
        val = v.get('formatted_value') or v.get('clean_name') or v.get('raw_text') if isinstance(v, dict) else v
        src = v.get('source_side', '?') if isinstance(v, dict) else ''
        print(f"  {k:22s}: {str(val)[:45]:45s} (side {src})")
        
    passed_rules = sum(1 for r in final_report.get('rules', []) if r.get('status') == 'PASS')
    total_rules = len(final_report.get('rules', []))
    print(f"Passed rules: {passed_rules} / {total_rules}")

if __name__ == '__main__':
    test_pair('biscuit_front_label.jpg', 'biscuit_back_label.jpg')
    test_pair('tea_front_label.jpg', 'tea_back_label.jpg')
