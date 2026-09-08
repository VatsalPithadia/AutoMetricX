import os
import json
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.pdf_generator import LMPCPdfReportGenerator

def test_pdf_export():
    benchmark_file = os.path.join(os.path.dirname(__file__), "test_benchmark_results.json")
    if not os.path.exists(benchmark_file):
        print(f"Benchmark result file missing: {benchmark_file}")
        return

    with open(benchmark_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    generator = LMPCPdfReportGenerator()
    images = data.get("images", [])
    
    output_dir = os.path.join(os.path.dirname(__file__), "pdf_exports")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n==========================================================================")
    print(f"TESTING PHASE 4 PDF AUDIT CERTIFICATE GENERATOR ON {len(images)} TEST RESULTS")
    print(f"==========================================================================\n")

    for item in images:
        filename = item.get("filename", "report.jpg")
        # Build mock scan result payload
        payload = {
            "filename": filename,
            "engine": item.get("engine", "RapidOCR ONNX"),
            "processing_time_seconds": item.get("processing_time_sec", 10.0),
            "total_blocks": item.get("total_detected_blocks", 50),
            "compliance_report": {
                "overall_status": item.get("overall_status", "PARTIALLY_COMPLIANT"),
                "compliance_score": item.get("compliance_score", 75.0),
                "passed_rules_count": 5,
                "total_rules_checked": 8,
                "font_legibility_analysis": {
                    "scale_px_mm": 16.0,
                    "scale_calibration_source": "Resolution Scale Model (1600px = 100mm)",
                    "rule_7_3_tier": "Tier <= 50g/ml (Min 1.0mm)",
                    "min_required_letter_height_mm": 1.0,
                    "rule_7_3_field_evaluations": [
                        {"field": "mrp", "font_height_mm": 2.4, "status": "PASS"},
                        {"field": "net_quantity", "font_height_mm": 1.8, "status": "PASS"},
                        {"field": "mfg_date", "font_height_mm": 1.2, "status": "PASS"},
                        {"field": "commodity_name", "font_height_mm": 3.5, "status": "PASS"}
                    ],
                    "rule_9_1_mrp_prominence": {
                        "mrp_font_height_mm": 2.4,
                        "avg_body_font_height_mm": 1.5,
                        "prominence_ratio": 1.6,
                        "status": "PASS",
                        "explanation": "MRP font size (2.4mm) is 1.6x body text (1.5mm). Compliant with Rule 9(1)"
                    }
                },
                "declarations": [
                    {
                        "rule_id": "LMPC-R6-1a", "clause": "Rule 6(1)(a)", "name": "Manufacturer / Packer Details",
                        "status": "PASS", "found_value": "Shri Hari Foods Ltd, Godhra Road", "explanation": "Manufacturer name and address clearly printed."
                    },
                    {
                        "rule_id": "LMPC-R6-1b", "clause": "Rule 6(1)(b)", "name": "Generic Commodity Name",
                        "status": "PASS", "found_value": "SHRI HARI MASALA", "explanation": "Generic commodity name declared."
                    },
                    {
                        "rule_id": "LMPC-R6-1c", "clause": "Rule 6(1)(c)", "name": "Net Quantity & Standard Unit",
                        "status": "PASS", "found_value": "50 g", "explanation": "Net quantity declared in compliant standard unit."
                    },
                    {
                        "rule_id": "LMPC-R6-1e", "clause": "Rule 6(1)(e)", "name": "Maximum Retail Price (MRP)",
                        "status": "PASS", "found_value": "Rs. 25.00 (Incl. of all taxes)", "explanation": "MRP printed with mandatory tax clause."
                    }
                ]
            }
        }

        pdf_bytes = generator.generate_pdf_bytes(payload)
        pdf_path = os.path.join(output_dir, f"audit_certificate_{filename.replace('.jpg', '')}.pdf")
        with open(pdf_path, "wb") as pf:
            pf.write(pdf_bytes)

        print(f"Generated PDF Certificate ({len(pdf_bytes)} bytes): {pdf_path}")

    print("\nPhase 4 PDF Export Verification PASSED successfully!\n")

if __name__ == "__main__":
    test_pdf_export()
