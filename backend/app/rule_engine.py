import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("metrolens.rule_engine")

class LMPCRuleEngine:
    """
    Legal Metrology (Packaged Commodities) Rules, 2011 Compliance Checking Engine.
    
    Supports 3-State Compliance Reporting:
    - PASS / COMPLIANT: Declaration detected with high confidence (>= 0.60)
    - LOW_CONFIDENCE: Candidate detected, but uncertain / low confidence (< 0.60)
    - FAIL / MISSING: Declaration missing or unreadable
    """

    def __init__(self, rules_json_path: str):
        self.rules_data = {}
        self.rules_list = []
        self._load_rules(rules_json_path)

    def _load_rules(self, rules_json_path: str):
        if not os.path.exists(rules_json_path):
            logger.error(f"LMPC Rules file not found at: {rules_json_path}")
            return
        try:
            with open(rules_json_path, 'r', encoding='utf-8') as f:
                self.rules_data = json.load(f)
                self.rules_list = self.rules_data.get("rules", [])
            logger.info(f"Loaded {len(self.rules_list)} LMPC rules from rules JSON.")
        except Exception as err:
            logger.error(f"Error loading LMPC rules JSON: {err}")

    def evaluate_compliance(
        self,
        classified_fields: Dict[str, Any],
        ocr_blocks: List[Dict[str, Any]],
        image: Optional[Any] = None,
        image_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs comprehensive LMPC compliance verification.
        Returns detailed compliance report with 3-state evaluation per declaration.
        """
        evaluations = []
        total_passed = 0
        total_low_conf = 0
        total_failed = 0
        total_checked = 0

        # --- Rule 1: Rule 6(1)(a) Manufacturer/Packer Name & Address ---
        mfg_field = classified_fields.get("manufacturer_details")
        total_checked += 1
        if mfg_field and mfg_field.get("has_name"):
            conf = mfg_field.get("confidence", 0.90)
            found_val = mfg_field["raw_text"]
            if conf >= 0.60:
                status = "PASS"
                explanation = "Manufacturer name & address details are clearly declared on the package."
                severity = "NONE"
                total_passed += 1
            else:
                status = "LOW_CONFIDENCE"
                explanation = f"Manufacturer details candidate found ('{found_val[:40]}...'), but detection confidence is low ({int(conf*100)}%). Verification recommended."
                severity = "LOW"
                total_low_conf += 1
        else:
            status = "FAIL"
            found_val = None
            explanation = "Mandatory declaration of Manufacturer / Packer name & complete address is missing."
            severity = "CRITICAL"
            total_failed += 1

        evaluations.append({
            "rule_id": "LMPC-R6-1a",
            "clause": "Rule 6(1)(a)",
            "name": "Manufacturer / Packer Details",
            "declaration": "manufacturer_name_address",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # --- Rule 2: Rule 6(1)(b) Commodity Generic Name ---
        comm_field = classified_fields.get("commodity_name")
        total_checked += 1
        if comm_field and isinstance(comm_field, dict) and (comm_field.get("clean_name") or comm_field.get("raw_text")):
            conf = comm_field.get("confidence", 0.50)
            found_val = comm_field.get("clean_name") or comm_field["raw_text"]
            if conf >= 0.60:
                status = "PASS"
                explanation = f"Generic commodity name / product identity ('{found_val}') is clearly declared."
                severity = "NONE"
                total_passed += 1
            else:
                status = "LOW_CONFIDENCE"
                explanation = f"Commodity name candidate found ('{found_val}'), but confidence is low ({int(conf*100)}%)."
                severity = "MEDIUM"
                total_low_conf += 1
        else:
            status = "FAIL"
            found_val = None
            explanation = "Generic commodity name / product identity could not be confidently identified."
            severity = "HIGH"
            total_failed += 1

        evaluations.append({
            "rule_id": "LMPC-R6-1b",
            "clause": "Rule 6(1)(b)",
            "name": "Generic Commodity Name",
            "declaration": "commodity_name",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # --- Rule 3: Rule 6(1)(c) Net Quantity & Standard Unit ---
        net_qty = classified_fields.get("net_quantity")
        total_checked += 1
        if net_qty:
            conf = net_qty.get("confidence", 0.80)
            num_val = net_qty.get("numeric_value", "")
            unit_val = net_qty.get("unit", "")
            found_val = net_qty.get("formatted_value") or net_qty.get("raw_text") or f"{num_val} {unit_val}".strip()
            if net_qty.get("is_standard_unit", True) and conf >= 0.60:
                status = "PASS"
                explanation = f"Net Quantity ('{found_val}') declared using compliant standard unit '{net_qty['unit']}'."
                severity = "NONE"
                total_passed += 1
            else:
                status = "LOW_CONFIDENCE"
                explanation = f"Net Quantity candidate found ('{found_val}'), but unit notation or detection confidence ({int(conf*100)}%) requires review."
                severity = "MEDIUM"
                total_low_conf += 1
        else:
            status = "FAIL"
            found_val = None
            explanation = "Mandatory Net Quantity declaration (weight/volume/count) is missing."
            severity = "CRITICAL"
            total_failed += 1

        evaluations.append({
            "rule_id": "LMPC-R6-1c",
            "clause": "Rule 6(1)(c)",
            "name": "Net Quantity & Standard Unit",
            "declaration": "net_quantity",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # --- Rule 4: Rule 6(1)(d) Month & Year of Manufacture/Packing ---
        mfg_date = classified_fields.get("mfg_date")
        total_checked += 1
        if mfg_date:
            conf = mfg_date.get("confidence", 0.80)
            found_val = mfg_date.get("raw_text") or mfg_date.get("extracted_date")
            if conf >= 0.60:
                status = "PASS"
                explanation = f"Manufacturing / Packing date declaration detected ('{found_val}')."
                severity = "NONE"
                total_passed += 1
            else:
                status = "LOW_CONFIDENCE"
                explanation = f"Date stamp candidate detected ('{found_val}'), but confidence is low ({int(conf*100)}%)."
                severity = "LOW"
                total_low_conf += 1
        else:
            exp_date = classified_fields.get("expiry_date")
            if exp_date:
                status = "LOW_CONFIDENCE"
                found_val = f"Expiry only: {exp_date.get('raw_text')}"
                explanation = "Expiry date is present, but Month & Year of Manufacture/Packing is missing or separate."
                severity = "MEDIUM"
                total_low_conf += 1
            else:
                status = "FAIL"
                found_val = None
                explanation = "Mandatory Month & Year of Manufacture/Packing declaration is missing."
                severity = "HIGH"
                total_failed += 1

        evaluations.append({
            "rule_id": "LMPC-R6-1d",
            "clause": "Rule 6(1)(d)",
            "name": "Month & Year of Manufacture / Packing",
            "declaration": "mfg_date",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # --- Rule 5: Rule 6(1)(e) Maximum Retail Price (MRP) & Tax Clause ---
        mrp_data = classified_fields.get("mrp")
        total_checked += 1
        if mrp_data:
            conf = mrp_data.get("confidence", 0.80)
            found_val = mrp_data.get("raw_text") or mrp_data.get("formatted_value")
            if mrp_data.get("has_tax_clause") and conf >= 0.60:
                status = "PASS"
                explanation = f"Retail Sale Price (MRP) printed with mandatory 'inclusive of all taxes' clause ('{found_val}')."
                severity = "NONE"
                total_passed += 1
            else:
                status = "LOW_CONFIDENCE"
                found_val = mrp_data.get("raw_text") or mrp_data.get("formatted_value")
                explanation = f"MRP candidate found ('{found_val}'), but mandatory 'inclusive of all taxes' wording or detection confidence requires review."
                severity = "MEDIUM"
                total_low_conf += 1
        else:
            status = "FAIL"
            found_val = None
            explanation = "Mandatory Maximum Retail Price (MRP) declaration is missing."
            severity = "CRITICAL"
            total_failed += 1

        evaluations.append({
            "rule_id": "LMPC-R6-1e",
            "clause": "Rule 6(1)(e)",
            "name": "Maximum Retail Price (MRP)",
            "declaration": "mrp",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # --- Rule 6: Rule 6(1)(f) Consumer Care Contact Details ---
        care_data = classified_fields.get("consumer_care")
        total_checked += 1
        if care_data and (care_data.get("has_phone") or care_data.get("has_email")):
            conf = care_data.get("confidence", 0.90)
            found_val = care_data["raw_text"]
            if conf >= 0.60:
                status = "PASS"
                explanation = "Consumer Care helpline contact details (phone/email) are clearly printed."
                severity = "NONE"
                total_passed += 1
            else:
                status = "LOW_CONFIDENCE"
                explanation = f"Consumer Care contact candidate found ('{found_val[:40]}...'), but confidence is low ({int(conf*100)}%)."
                severity = "LOW"
                total_low_conf += 1
        else:
            status = "FAIL"
            found_val = None
            explanation = "Mandatory Consumer Care contact details (telephone/email) are missing."
            severity = "HIGH"
            total_failed += 1

        evaluations.append({
            "rule_id": "LMPC-R6-1f",
            "clause": "Rule 6(1)(f)",
            "name": "Consumer Care Details",
            "declaration": "consumer_care",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # --- Rule 7: Rule 7(3) Minimum Font Height Legibility (Physical mm) ---
        from app.font_calibrator import FontCalibrator
        calibrator = FontCalibrator()
        
        # Default metadata fallback
        meta = image_metadata or {"width": 1200, "height": 900}
        
        legibility_analysis = calibrator.analyze_legibility_and_prominence(
            image, meta, classified_fields, ocr_blocks
        )
        
        total_checked += 1
        min_req_mm = legibility_analysis["min_required_letter_height_mm"]
        tier_label = legibility_analysis["rule_7_3_tier"]
        
        # Check if declared field font heights meet min_req_mm
        non_compliant_font_fields = [
            f"{f} ({h_mm}mm < {min_req_mm}mm)"
            for f, h_mm in legibility_analysis["field_font_heights_mm"].items()
            if h_mm is not None and h_mm < min_req_mm
        ]

        if not non_compliant_font_fields:
            status = "PASS"
            found_val = f"Compliant ({tier_label})"
            explanation = f"All printed declaration letter heights meet the {min_req_mm}mm minimum requirement ({tier_label})."
            severity = "NONE"
            total_passed += 1
        else:
            status = "LOW_CONFIDENCE"
            found_val = f"Below Threshold ({tier_label})"
            explanation = f"Some declarations have letter height below the {min_req_mm}mm threshold: {', '.join(non_compliant_font_fields)}."
            severity = "MEDIUM"
            total_low_conf += 1

        evaluations.append({
            "rule_id": "LMPC-R7-3",
            "clause": "Rule 7(3)",
            "name": "Font Height & Legibility Standards",
            "declaration": "font_legibility",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # --- Rule 8: Rule 9(1) Manner & Prominence of MRP ---
        total_checked += 1
        rule_9_1 = legibility_analysis["rule_9_1_mrp_prominence"]
        mrp_status = rule_9_1["status"]
        mrp_prom_ratio = rule_9_1["prominence_ratio"]
        
        if mrp_status == "PASS":
            status = "PASS"
            found_val = f"{mrp_prom_ratio}x Prominence Ratio"
            explanation = rule_9_1["explanation"]
            severity = "NONE"
            total_passed += 1
        else:
            status = "LOW_CONFIDENCE"
            found_val = f"{mrp_prom_ratio}x Prominence Ratio"
            explanation = rule_9_1["explanation"]
            severity = "LOW"
            total_low_conf += 1

        evaluations.append({
            "rule_id": "LMPC-R9-1",
            "clause": "Rule 9(1)",
            "name": "Manner & Prominence of MRP",
            "declaration": "mrp_prominence",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # --- Rule 9 (Informational): FSSAI License / Registration Number ---
        # FSSAI license is mandatory only for food businesses under the Food Safety & Standards Act.
        # It is NOT a universal LMPC (Legal Metrology) declaration required on every packaged commodity.
        # Absence does NOT count as a FAIL or penalise the compliance score.
        fssai_field = classified_fields.get("fssai_number")
        total_checked += 1
        if fssai_field and fssai_field.get("license_number"):
            lic_num = fssai_field["license_number"]
            is_valid_14 = fssai_field.get("is_valid_14_digit", False)
            conf = fssai_field.get("confidence", 0.80)
            status = "PASS"
            found_val = lic_num
            if is_valid_14 and conf >= 0.60:
                explanation = f"FSSAI License No. ({lic_num}) detected and appears valid (14-digit format)."
            else:
                explanation = f"FSSAI-format number ({lic_num}) detected — verify full 14-digit validity against FSSAI portal."
            severity = "NONE"
            total_passed += 1
        else:
            # Not found — treat as Not Applicable, not as FAIL.
            # This does NOT decrement the compliance score.
            status = "NOT_APPLICABLE"
            found_val = None
            explanation = "FSSAI License / Registration Number not detected. This is only required for food businesses — not applicable to all packaged commodities under LMPC."
            severity = "NONE"
            # Count as a half-pass so the denominator doesn't unfairly penalise non-food products
            total_low_conf += 1

        evaluations.append({
            "rule_id": "LMPC-R6-FSSAI",
            "clause": "FSSAI / FSS Act (Informational)",
            "name": "FSSAI License / Registration No.",
            "declaration": "fssai_number",
            "status": status,
            "severity": severity,
            "found_value": found_val,
            "explanation": explanation
        })

        # Weighted Score & Overall Status Calculation
        score = round(((total_passed + 0.5 * total_low_conf) / total_checked) * 100.0, 1)
        if total_failed == 0 and total_low_conf == 0:
            overall_status = "COMPLIANT"
        elif total_failed <= 2:
            overall_status = "PARTIALLY_COMPLIANT"
        else:
            overall_status = "NON_COMPLIANT"

        return {
            "overall_status": overall_status,
            "compliance_score": score,
            "passed_rules_count": total_passed,
            "low_confidence_rules_count": total_low_conf,
            "failed_rules_count": total_failed,
            "total_rules_checked": total_checked,
            "act_name": self.rules_data.get("act", "Legal Metrology (Packaged Commodities) Rules, 2011"),
            "font_legibility_analysis": legibility_analysis,
            "declarations": evaluations
        }
