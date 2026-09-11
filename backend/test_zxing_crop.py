import os, sys, cv2
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)
import zxingcpp

# 1. Ketchup
k_path = os.path.join(backend_dir, "uploads", "ff132bef634f4860b952a42a2e2257a5.jpeg")
k_img = cv2.imread(k_path)
print(f"Ketchup image shape: {k_img.shape}")

# Test full image ZXing
barcodes = zxingcpp.read_barcodes(k_img)
print(f"ZXing full image ketchup barcodes: {[(b.text, b.format) for b in barcodes]}")

# 2. Schezwan Chutney Side 2
s2_path = os.path.join(backend_dir, "uploads", "42227ec47bd04596a3458c9871c509c7.jpeg")
s2_img = cv2.imread(s2_path)
print(f"Schezwan 2 image shape: {s2_img.shape}")
barcodes2 = zxingcpp.read_barcodes(s2_img)
print(f"ZXing full image schezwan 2 barcodes: {[(b.text, b.format) for b in barcodes2]}")

# Now test cropping the barcode area!
# In Ketchup, barcode is at bottom left:
# Let's crop x: 100-400, y: 900-1300
h, w = k_img.shape[:2]
# Let's find crop for Ketchup barcode
crop_k = k_img[int(h*0.65):int(h*0.85), int(w*0.1):int(w*0.4)]
b_crop_k = zxingcpp.read_barcodes(crop_k)
print(f"Crop Ketchup barcodes: {[(b.text, b.format) for b in b_crop_k]}")

# For Schezwan 2, barcode is bottom:
h2, w2 = s2_img.shape[:2]
crop_s2 = s2_img[int(h2*0.65):int(h2*0.9), int(w2*0.1):int(w2*0.6)]
b_crop_s2 = zxingcpp.read_barcodes(crop_s2)
print(f"Crop Schezwan 2 barcodes: {[(b.text, b.format) for b in b_crop_s2]}")
