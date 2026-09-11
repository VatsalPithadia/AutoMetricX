import os
import sys

from app.ingredient_checker import IngredientSafetyEngine
from app.pdf_generator import LMPCPdfReportGenerator

def test_safety_engine():
    engine = IngredientSafetyEngine()

    # Test 1: Harmful ingredients (TBHQ, Palm oil, Tartrazine, MSG, Hydrogenated Fat)
    harmful_text = "Ingredients: Refined Wheat Flour, Partially Hydrogenated Vegetable Oil, Palm Oil, TBHQ (INS 319), Tartrazine (INS 102), Monosodium Glutamate (INS 621), Salt, Spices"
    res1 = engine.evaluate_ingredients(harmful_text, commodity_name="Crunchy Spicy Chips")
    assert res1["has_ingredients"] is True
    assert res1["is_harmful"] is True
    assert res1["safety_verdict"] == "HARMFUL"
    assert res1["safety_score"] < 50
    flagged_names = [f["name"] for f in res1["flagged_ingredients"]]
    assert any("TBHQ" in n for n in flagged_names)
    assert any("Tartrazine" in n for n in flagged_names)
    assert any("Trans" in n or "Hydrogenated" in n for n in flagged_names)
    print("Test 1 (Harmful Snack): PASSED -> Score:", res1["safety_score"], "Verdict:", res1["safety_verdict"])

    # Test 2: Clean/Safe ingredients (Assam Royal Tea)
    safe_text = "Ingredients: 100% Pure Orthodox Whole Leaf Assam Black Tea"
    res2 = engine.evaluate_ingredients(safe_text, commodity_name="Assam Royal Tea")
    assert res2["has_ingredients"] is True
    assert res2["is_harmful"] is False
    assert res2["safety_verdict"] == "SAFE"
    assert res2["safety_score"] == 100
    assert len(res2["flagged_ingredients"]) == 0
    print("Test 2 (Clean Tea): PASSED -> Score:", res2["safety_score"], "Verdict:", res2["safety_verdict"])

    # Test 3: Moderate caution (Single additive, e.g. Sodium Benzoate in fruit jam)
    caution_text = "Ingredients: Mixed Fruit Pulp, Sugar, Pectin, Acidity Regulator (INS 330), Preservative (INS 211)"
    res3 = engine.evaluate_ingredients(caution_text, commodity_name="Mixed Fruit Jam")
    assert res3["has_ingredients"] is True
    assert res3["safety_verdict"] == "CAUTION"
    assert any("Sodium Benzoate" in f["name"] for f in res3["flagged_ingredients"])
    print("Test 3 (Moderate Caution): PASSED -> Score:", res3["safety_score"], "Verdict:", res3["safety_verdict"])

    # Test 4: PDF Generation with Ingredient Safety section
    pdf_gen = LMPCPdfReportGenerator()
    audit_data = {
        "filename": "crunchy_chips.jpg",
        "product_name": "Crunchy Spicy Chips",
        "total_blocks": 12,
        "processing_time_seconds": 0.45,
        "engine": "RapidOCR",
        "compliance_report": {
            "overall_status": "COMPLIANT",
            "compliance_score": 90,
            "declarations": [],
            "passed_rules_count": 8,
            "total_rules_checked": 8
        },
        "ingredient_safety": res1
    }
    pdf_bytes = pdf_gen.generate_pdf_bytes(audit_data)
    assert len(pdf_bytes) > 1000
    print("Test 4 (PDF Export with Ingredient Safety): PASSED -> Generated", len(pdf_bytes), "bytes")

    print("\nAll Ingredient Safety tests passed successfully!")

if __name__ == "__main__":
    test_safety_engine()
