import cv2
import numpy as np
from app.ocr_engine import extract_text_from_image

def test_phase1_ocr():
    # Create test label image in memory
    img = np.ones((300, 500, 3), dtype=np.uint8) * 255
    cv2.putText(img, "NET QUANTITY: 500g", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, "MRP Rs. 150.00 INCL TAXES", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    cv2.putText(img, "MFD BY: TEST FOODS PVT LTD", (30, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    _, encoded = cv2.imencode(".png", img)
    img_bytes = encoded.tobytes()

    print("Running extract_text_from_image...")
    result = extract_text_from_image(img_bytes)

    print("Engine Used:", result["engine"])
    print("Total Blocks:", result["total_detected_blocks"])
    print("Extracted Text:")
    print(result["raw_text"])

    assert result["total_detected_blocks"] > 0, "No text blocks detected!"
    print("\nPhase 1 OCR Verification PASSED successfully!")

if __name__ == "__main__":
    test_phase1_ocr()
