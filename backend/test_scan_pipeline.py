import os
from app.main import _process_single_image_bytes

def test_full_pipeline():
    img_path = os.path.join(os.path.dirname(__file__), "..", "test_images", "snack_chips_label.jpg")
    assert os.path.exists(img_path), f"Image not found at {img_path}"

    with open(img_path, "rb") as f:
        contents = f.read()

    res = _process_single_image_bytes(contents, "snack_chips_label.jpg")
    print("Raw text extracted lines:", len(res["text_lines"]))
    print("Ingredient safety result:")
    ing = res.get("ingredient_safety", {})
    print("  Has ingredients:", ing.get("has_ingredients"))
    print("  Verdict:", ing.get("safety_verdict"))
    print("  Score:", ing.get("safety_score"))
    print("  Is harmful:", ing.get("is_harmful"))
    print("  Flagged ingredients count:", len(ing.get("flagged_ingredients", [])))
    for f in ing.get("flagged_ingredients", []):
        print(f"    - {f['name']} ({f['severity']}): {f['ins_code']} - {f['hazard_type']}")

    assert ing.get("has_ingredients") is True
    assert ing.get("is_harmful") is True
    assert ing.get("safety_verdict") == "HARMFUL"
    print("\nEnd-to-end scan pipeline test PASSED!")

if __name__ == "__main__":
    test_full_pipeline()
