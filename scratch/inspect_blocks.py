import cv2, os, sys
sys.path.insert(0, 'backend')
from app.ocr_engine import extract_text_from_image

for name in ['dense_sachet_small_text.jpg', 'curved_bottle_label.jpg']:
    p = os.path.join('test_images', name)
    with open(p, 'rb') as f:
        data = f.read()
    res = extract_text_from_image(data)
    print(f'=== ALL BLOCKS FOR {name} ({len(res["blocks"])} blocks) ===')
    for b in res['blocks']:
        t = b['text']
        r = b['rect']
        print(f"  [{b['confidence']:.2f}] y={r['y']:.0f}-{r['y']+r['height']:.0f} x={r['x']:.0f}: '{t}'")
