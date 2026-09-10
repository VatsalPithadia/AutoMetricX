import cv2
import numpy as np
import os
from PIL import Image, ImageDraw, ImageFont

def get_font(size: int, bold: bool = False):
    font_candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "arial.ttf"
    ]
    for fp in font_candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()

def create_synthetic_labels():
    test_dir = os.path.join(os.path.dirname(__file__), "test_images")
    os.makedirs(test_dir, exist_ok=True)

    title_font = get_font(52, bold=True)
    header_font = get_font(38, bold=True)
    body_font = get_font(34, bold=False)

    # =========================================================================
    # 1. Full Tea Label
    # =========================================================================
    img1 = Image.new('RGB', (1200, 1600), color=(24, 38, 28))
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([(40, 40), (1160, 1560)], outline=(212, 175, 55), width=4)
    draw1.rectangle([(50, 50), (1150, 1550)], outline=(60, 90, 70), width=2)

    y = 120
    draw1.text((100, y), "ASSAM ROYAL TEA", font=title_font, fill=(255, 215, 0))
    y += 110
    draw1.text((100, y), "Generic Commodity: Premium Black Tea", font=header_font, fill=(255, 255, 255))
    y += 100
    draw1.text((100, y), "Net Quantity: 250 g", font=header_font, fill=(255, 255, 255))
    y += 100
    draw1.text((100, y), "MRP Rs. 185.00 (Incl. of all taxes)", font=header_font, fill=(255, 255, 255))
    y += 100
    draw1.text((100, y), "Mfg Date: NOV 2025", font=body_font, fill=(240, 240, 240))
    y += 70
    draw1.text((100, y), "Expiry Date: OCT 2026", font=body_font, fill=(240, 240, 240))
    y += 90
    draw1.text((100, y), "Mfd & Pkd By: Royal Tea Estates Pvt Ltd,", font=body_font, fill=(210, 210, 210))
    y += 60
    draw1.text((100, y), "Tea Garden Road, Jorhat, Assam - 785001", font=body_font, fill=(210, 210, 210))
    y += 90
    draw1.text((100, y), "Customer Care: 1800-123-4567 | email: care@royaltea.com", font=body_font, fill=(210, 210, 210))
    y += 90
    draw1.text((100, y), "FSSAI Lic. No. 10321012000456", font=body_font, fill=(255, 215, 0))

    img1_cv = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(test_dir, "tea_pouch_label.jpg"), img1_cv)

    # =========================================================================
    # 2. Tea Pouch - FRONT SIDE ONLY (Brand, Commodity, Net Quantity)
    # =========================================================================
    img_tf = Image.new('RGB', (1200, 1400), color=(24, 38, 28))
    draw_tf = ImageDraw.Draw(img_tf)
    draw_tf.rectangle([(40, 40), (1160, 1360)], outline=(212, 175, 55), width=4)

    y = 200
    draw_tf.text((150, y), "ASSAM ROYAL TEA", font=get_font(60, bold=True), fill=(255, 215, 0))
    y += 180
    draw_tf.text((150, y), "Generic Commodity: Premium Black Tea", font=get_font(42, bold=True), fill=(255, 255, 255))
    y += 150
    draw_tf.text((150, y), "Net Quantity: 250 g", font=get_font(46, bold=True), fill=(255, 255, 255))
    y += 160
    draw_tf.text((150, y), "100% Pure Orthodox Whole Leaf", font=get_font(34, bold=False), fill=(180, 210, 180))

    cv2.imwrite(os.path.join(test_dir, "tea_front_label.jpg"), cv2.cvtColor(np.array(img_tf), cv2.COLOR_RGB2BGR))

    # =========================================================================
    # 3. Tea Pouch - BACK SIDE ONLY (MRP, Dates, Mfd By, Customer Care, FSSAI)
    # =========================================================================
    img_tb = Image.new('RGB', (1200, 1500), color=(30, 42, 32))
    draw_tb = ImageDraw.Draw(img_tb)
    draw_tb.rectangle([(40, 40), (1160, 1460)], outline=(60, 90, 70), width=2)

    y = 120
    draw_tb.text((100, y), "ASSAM ROYAL TEA - MANDATORY DECLARATIONS", font=header_font, fill=(255, 215, 0))
    y += 110
    draw_tb.text((100, y), "MRP Rs. 185.00 (Incl. of all taxes)", font=header_font, fill=(255, 255, 255))
    y += 90
    draw_tb.text((100, y), "Mfg Date: NOV 2025", font=body_font, fill=(240, 240, 240))
    y += 70
    draw_tb.text((100, y), "Expiry Date: OCT 2026", font=body_font, fill=(240, 240, 240))
    y += 90
    draw_tb.text((100, y), "Mfd & Pkd By: Royal Tea Estates Pvt Ltd,", font=body_font, fill=(210, 210, 210))
    y += 60
    draw_tb.text((100, y), "Tea Garden Road, Jorhat, Assam - 785001", font=body_font, fill=(210, 210, 210))
    y += 90
    draw_tb.text((100, y), "Customer Care: 1800-123-4567 | email: care@royaltea.com", font=body_font, fill=(210, 210, 210))
    y += 90
    draw_tb.text((100, y), "FSSAI Lic. No. 10321012000456", font=body_font, fill=(255, 215, 0))

    cv2.imwrite(os.path.join(test_dir, "tea_back_label.jpg"), cv2.cvtColor(np.array(img_tb), cv2.COLOR_RGB2BGR))

    # =========================================================================
    # 4. Full Biscuit Label
    # =========================================================================
    img2 = Image.new('RGB', (1600, 1200), color=(250, 250, 246))
    draw2 = ImageDraw.Draw(img2)
    draw2.rectangle([(40, 40), (1560, 1160)], outline=(180, 40, 40), width=4)

    y = 100
    draw2.text((120, y), "CRUNCHY NUT BISCUITS", font=title_font, fill=(180, 30, 30))
    y += 100
    draw2.text((120, y), "Generic Name: Biscuits with Almonds", font=header_font, fill=(30, 30, 30))
    y += 90
    draw2.text((120, y), "Net Wt: 120 g", font=header_font, fill=(30, 30, 30))
    y += 90
    draw2.text((120, y), "MRP Rs. 30.00 (Incl. of all taxes)", font=header_font, fill=(180, 30, 30))
    y += 90
    draw2.text((120, y), "PKD: DEC 2025", font=body_font, fill=(40, 40, 40))
    y += 60
    draw2.text((120, y), "EXP: JUN 2026", font=body_font, fill=(40, 40, 40))
    y += 80
    draw2.text((120, y), "Manufactured by: Golden Bakery Pvt Ltd, Industrial Area, Thane - 400604", font=body_font, fill=(50, 50, 50))
    y += 70
    draw2.text((120, y), "For Feedback Contact: 022-25801234 | care@goldenbakery.in", font=body_font, fill=(50, 50, 50))
    y += 70
    draw2.text((120, y), "FSSAI Lic. No. 11518014000890", font=body_font, fill=(30, 100, 50))

    img2_cv = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(test_dir, "biscuit_wrapper_label.jpg"), img2_cv)

    # =========================================================================
    # 5. Biscuit - FRONT SIDE ONLY (Brand, Generic Name, Net Wt)
    # =========================================================================
    img_bf = Image.new('RGB', (1500, 1000), color=(250, 250, 246))
    draw_bf = ImageDraw.Draw(img_bf)
    draw_bf.rectangle([(40, 40), (1460, 960)], outline=(180, 40, 40), width=4)

    y = 160
    draw_bf.text((120, y), "CRUNCHY NUT BISCUITS", font=get_font(58, bold=True), fill=(180, 30, 30))
    y += 160
    draw_bf.text((120, y), "Generic Name: Biscuits with Almonds", font=get_font(42, bold=True), fill=(40, 40, 40))
    y += 140
    draw_bf.text((120, y), "Net Wt: 120 g", font=get_font(46, bold=True), fill=(40, 40, 40))

    cv2.imwrite(os.path.join(test_dir, "biscuit_front_label.jpg"), cv2.cvtColor(np.array(img_bf), cv2.COLOR_RGB2BGR))

    # =========================================================================
    # 6. Biscuit - BACK SIDE ONLY (MRP, Dates, Mfd By, Care, FSSAI)
    # =========================================================================
    img_bb = Image.new('RGB', (1500, 1100), color=(245, 245, 240))
    draw_bb = ImageDraw.Draw(img_bb)
    draw_bb.rectangle([(40, 40), (1460, 1060)], outline=(180, 40, 40), width=2)

    y = 100
    draw_bb.text((100, y), "CRUNCHY NUT BISCUITS - PACKET BACK PANEL", font=header_font, fill=(180, 30, 30))
    y += 100
    draw_bb.text((100, y), "MRP Rs. 30.00 (Incl. of all taxes)", font=header_font, fill=(180, 30, 30))
    y += 90
    draw_bb.text((100, y), "PKD: DEC 2025", font=body_font, fill=(40, 40, 40))
    y += 60
    draw_bb.text((100, y), "EXP: JUN 2026", font=body_font, fill=(40, 40, 40))
    y += 80
    draw_bb.text((100, y), "Manufactured by: Golden Bakery Pvt Ltd, Industrial Area, Thane - 400604", font=body_font, fill=(50, 50, 50))
    y += 70
    draw_bb.text((100, y), "For Feedback Contact: 022-25801234 | care@goldenbakery.in", font=body_font, fill=(50, 50, 50))
    y += 70
    draw_bb.text((100, y), "FSSAI Lic. No. 11518014000890", font=body_font, fill=(30, 100, 50))

    cv2.imwrite(os.path.join(test_dir, "biscuit_back_label.jpg"), cv2.cvtColor(np.array(img_bb), cv2.COLOR_RGB2BGR))

    print("Created high-precision single-side & multi-side synthetic test images in test_images/ successfully.")

if __name__ == "__main__":
    create_synthetic_labels()
