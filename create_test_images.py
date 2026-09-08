import cv2
import numpy as np
import os
from PIL import Image, ImageDraw, ImageFont

def create_synthetic_labels():
    test_dir = os.path.join(os.path.dirname(__file__), "test_images")
    os.makedirs(test_dir, exist_ok=True)

    # 1. Tea Pouch Label (Medium/Small text on dark background)
    img1 = Image.new('RGB', (1200, 1600), color=(30, 45, 30))
    draw1 = ImageDraw.Draw(img1)
    
    # Simple draw text
    draw1.text((100, 100), "ASSAM ROYAL TEA", fill=(255, 215, 0))
    draw1.text((100, 250), "Generic Commodity: Premium Black Tea", fill=(255, 255, 255))
    draw1.text((100, 400), "Net Quantity: 250 g", fill=(255, 255, 255))
    draw1.text((100, 550), "MRP Rs. 185.00 (Incl. of all taxes)", fill=(255, 255, 255))
    draw1.text((100, 700), "Mfg Date: NOV 2025 | Expiry Date: OCT 2026", fill=(255, 255, 255))
    draw1.text((100, 850), "Mfd & Pkd By: Royal Tea Estates, Jorhat, Assam - 785001", fill=(200, 200, 200))
    draw1.text((100, 1000), "Customer Care: 1800-123-4567 | email: care@royaltea.com", fill=(200, 200, 200))
    draw1.text((100, 1150), "FSSAI Lic No: 10321012000456", fill=(200, 200, 200))

    img1_cv = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(test_dir, "tea_pouch_label.jpg"), img1_cv)

    # 2. Biscuit Wrapper Label (Dense small text with mild tilt)
    img2 = Image.new('RGB', (1600, 1200), color=(240, 240, 235))
    draw2 = ImageDraw.Draw(img2)

    draw2.text((150, 100), "CRUNCHY NUT BISCUITS", fill=(180, 40, 40))
    draw2.text((150, 220), "Generic Name: Biscuits with Almonds", fill=(40, 40, 40))
    draw2.text((150, 340), "Net Wt: 120g", fill=(40, 40, 40))
    draw2.text((150, 460), "MRP Rs. 30.00 INCL ALL TAXES", fill=(40, 40, 40))
    draw2.text((150, 580), "PKD: DEC 2025  EXP: JUN 2026", fill=(40, 40, 40))
    draw2.text((150, 700), "Manufactured by: Golden Bakery Pvt Ltd, Industrial Area, Thane - 400604", fill=(60, 60, 60))
    draw2.text((150, 820), "For Feedback Contact: 022-25801234 care@goldenbakery.in", fill=(60, 60, 60))
    draw2.text((150, 940), "FSSAI Lic. No. 11518014000890", fill=(60, 60, 60))

    img2_cv = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(test_dir, "biscuit_wrapper_label.jpg"), img2_cv)

    print("Created synthetic test images in test_images/ successfully.")

if __name__ == "__main__":
    create_synthetic_labels()
