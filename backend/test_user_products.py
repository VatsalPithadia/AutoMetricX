import os, sys, json
backend_dir = r"v:\Desktop\AutoMatriX\AutoMetricX\backend"
sys.path.insert(0, backend_dir)

from app.main import _process_single_image_bytes
from app.classifier import FieldClassifier

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def test_ketchup():
    print("=" * 60)
    print("TESTING 1: KETCHUP IMAGE EXTRACTION")
    print("=" * 60)
    p = os.path.join(backend_dir, "uploads", "ff132bef634f4860b952a42a2e2257a5.jpeg")
    with open(p, "rb") as f:
        bytes_data = f.read()
    
    res = _process_single_image_bytes(bytes_data, "ketchup.jpeg")
    fields = res["classified_fields"]
    barcodes = res["barcode_qr_analysis"]

    print("\n[EXTRACTED DECLARATION VALUES - KETCHUP]")
    print(f"COMMODITY NAME:   {fields.get('commodity_name', {}).get('clean_name') if isinstance(fields.get('commodity_name'), dict) else fields.get('commodity_name')}")
    print(f"NET QUANTITY:     {fields.get('net_quantity', {}).get('formatted_value') if isinstance(fields.get('net_quantity'), dict) else fields.get('net_quantity')}")
    print(f"MRP:              {fields.get('mrp', {}).get('formatted_value') if isinstance(fields.get('mrp'), dict) else fields.get('mrp')}")
    print(f"MFG DATE:         {fields.get('mfg_date', {}).get('extracted_date') if isinstance(fields.get('mfg_date'), dict) else fields.get('mfg_date')}")
    print(f"EXPIRY DATE:      {fields.get('expiry_date', {}).get('extracted_date') if isinstance(fields.get('expiry_date'), dict) else fields.get('expiry_date')}")
    print(f"BATCH NO:         {fields.get('batch_number', {}).get('raw_text') if isinstance(fields.get('batch_number'), dict) else fields.get('batch_number')}")
    print(f"FSSAI LICENSE:    {fields.get('fssai_number', {}).get('license_number') if isinstance(fields.get('fssai_number'), dict) else fields.get('fssai_number')}")
    print(f"INGREDIENTS LIST: {fields.get('ingredients', {}).get('raw_text') if isinstance(fields.get('ingredients'), dict) else fields.get('ingredients')}")
    print(f"BARCODES DETECTED: {barcodes.get('gtin_barcodes')} (Total: {barcodes.get('total_decoded_codes')})")
    for b in barcodes.get("decoded_codes", []):
        print(f"   -> {b.get('type')} ({b.get('engine')}): {b.get('data')}")

def test_schezwan_side2():
    print("\n" + "=" * 60)
    print("TESTING 2: SCHEZWAN CHUTNEY SIDE 2 (PRICE / MRP & BARCODE)")
    print("=" * 60)
    p = os.path.join(backend_dir, "uploads", "42227ec47bd04596a3458c9871c509c7.jpeg")
    with open(p, "rb") as f:
        bytes_data = f.read()
    
    res = _process_single_image_bytes(bytes_data, "schezwan_side2.jpeg")
    fields = res["classified_fields"]
    barcodes = res["barcode_qr_analysis"]

    print("\n[EXTRACTED DECLARATION VALUES - SCHEZWAN SIDE 2]")
    print(f"COMMODITY NAME:   {fields.get('commodity_name', {}).get('clean_name') if isinstance(fields.get('commodity_name'), dict) else fields.get('commodity_name')}")
    print(f"NET QUANTITY:     {fields.get('net_quantity', {}).get('formatted_value') if isinstance(fields.get('net_quantity'), dict) else fields.get('net_quantity')}")
    print(f"MRP:              {fields.get('mrp', {}).get('formatted_value') if isinstance(fields.get('mrp'), dict) else fields.get('mrp')}")
    print(f"MFG DATE:         {fields.get('mfg_date', {}).get('extracted_date') if isinstance(fields.get('mfg_date'), dict) else fields.get('mfg_date')}")
    print(f"EXPIRY DATE:      {fields.get('expiry_date', {}).get('extracted_date') if isinstance(fields.get('expiry_date'), dict) else fields.get('expiry_date')}")
    print(f"BATCH NO:         {fields.get('batch_number', {}).get('raw_text') if isinstance(fields.get('batch_number'), dict) else fields.get('batch_number')}")
    print(f"BARCODES DETECTED: {barcodes.get('gtin_barcodes')} (Total: {barcodes.get('total_decoded_codes')})")
    for b in barcodes.get("decoded_codes", []):
        print(f"   -> {b.get('type')} ({b.get('engine')}): {b.get('data')}")

def test_schezwan_side1():
    print("\n" + "=" * 60)
    print("TESTING 3: SCHEZWAN CHUTNEY SIDE 1 (INGREDIENTS LIST & WEIGHT)")
    print("=" * 60)
    p = os.path.join(backend_dir, "uploads", "6a56920af0334a3d8eb833300b4c6518.jpeg")
    with open(p, "rb") as f:
        bytes_data = f.read()
    
    res = _process_single_image_bytes(bytes_data, "schezwan_side1.jpeg")
    fields = res["classified_fields"]

    print("\n[EXTRACTED DECLARATION VALUES - SCHEZWAN SIDE 1]")
    print(f"COMMODITY NAME:   {fields.get('commodity_name', {}).get('clean_name') if isinstance(fields.get('commodity_name'), dict) else fields.get('commodity_name')}")
    print(f"NET QUANTITY:     {fields.get('net_quantity', {}).get('formatted_value') if isinstance(fields.get('net_quantity'), dict) else fields.get('net_quantity')}")
    print(f"INGREDIENTS LIST: {fields.get('ingredients', {}).get('raw_text') if isinstance(fields.get('ingredients'), dict) else fields.get('ingredients')}")

if __name__ == "__main__":
    test_ketchup()
    test_schezwan_side2()
    test_schezwan_side1()
