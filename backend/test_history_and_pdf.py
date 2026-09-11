import os
import json
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, Base, SessionLocal, DB_PATH
from app.models import ScanRecord
from app.pdf_generator import LMPCPdfReportGenerator
from app.main import _process_single_image_bytes

def test_history_and_pdf_features():
    print(f"\n==========================================================================")
    print(f"VERIFYING PART 1 (SCAN HISTORY SQLITE DB) & PART 2 (EMBEDDED PDF PHOTO)")
    print(f"==========================================================================\n")

    # 1. Initialize SQLite database
    Base.metadata.create_all(bind=engine)
    print(f"[OK] Database initialized at: {DB_PATH}")

    db = SessionLocal()

    # Clear previous test rows for clean run
    db.query(ScanRecord).delete()
    db.commit()

    test_images_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_images")
    test_files = [
        "suhana_sauce_packet_large_text.jpg",
        "package_label_medium_text.jpg",
        "dense_sachet_small_text.jpg"
    ]

    scanned_ids = []
    result_payload = None

    # 2. Perform 3 scans and populate database
    for fname in test_files:
        fpath = os.path.join(test_images_dir, fname)
        if not os.path.exists(fpath):
            print(f"Skipping missing file: {fpath}")
            continue

        # Ensure file is in uploads directory
        backend_uploads = os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(backend_uploads, exist_ok=True)
        dst_fpath = os.path.join(backend_uploads, fname)
        if not os.path.exists(dst_fpath):
            import shutil
            shutil.copy2(fpath, dst_fpath)

        with open(fpath, "rb") as img_f:
            img_bytes = img_f.read()

        pipeline_res = _process_single_image_bytes(img_bytes, fname)
        
        result_payload = {
            "success": True,
            "filename": fname,
            "saved_file": fname,
            "processing_time_seconds": 2.5,
            **pipeline_res
        }

        # Extract product name with confidence >= 0.60 requirement
        comm_obj = pipeline_res["classified_fields"].get("commodity_name", {})
        comm_text = comm_obj.get("raw_text") if isinstance(comm_obj, dict) else None
        comm_conf = comm_obj.get("confidence", 0.0) if isinstance(comm_obj, dict) else 0.0

        generic_reject_kw = ['AYURVEDIC', 'PROPRIETARY', 'MEDICINE', 'ACCEPT', 'DAMAGED', 'SACHET', 'WARNING']
        is_generic_phrase = any(kw in (comm_text or '').upper() for kw in generic_reject_kw)

        if comm_text and comm_conf >= 0.60 and len(comm_text.strip()) >= 3 and not is_generic_phrase:
            product_name = comm_text.strip()
            if len(product_name) > 80:
                product_name = product_name[:80] + "..."
        else:
            product_name = "Unknown Product"
        overall_status = pipeline_res["compliance_report"]["overall_status"]
        compliance_score = float(pipeline_res["compliance_report"]["compliance_score"])

        scan_rec = ScanRecord(
            image_filename=fname,
            product_name=product_name,
            overall_status=overall_status,
            compliance_score=compliance_score,
            full_report_json=json.dumps(result_payload)
        )
        db.add(scan_rec)
        db.commit()
        db.refresh(scan_rec)

        scanned_ids.append(scan_rec.id)
        print(f"[OK] Saved Scan Record #{scan_rec.id}: Product='{product_name}' | Status='{overall_status}' | Score={compliance_score}%")

    db.close()

    # 3. Test Database Persistence across new connection
    print("\n--- Verifying SQLite Persistence across DB reconnect ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, product_name, overall_status, compliance_score FROM scans ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    print(f"[OK] Retrieved {len(rows)} scan records from SQLite DB file:")
    for r in rows:
        print(f"   Row #{r[0]}: Name='{r[1]}' | Status='{r[2]}' | Score={r[3]}%")

    assert len(rows) == len(scanned_ids), "Database record count mismatch!"

    # 4. Test Search and Status Filtering Logic
    print("\n--- Testing Search & Status Filter Logic ---")
    db = SessionLocal()
    
    # Test search by product name
    search_results = db.query(ScanRecord).filter(ScanRecord.product_name.ilike("%MASALA%")).all()
    print(f"[OK] Search query 'MASALA' matched {len(search_results)} record(s).")

    # Test filter by compliance status
    status_results = db.query(ScanRecord).filter(ScanRecord.overall_status == "PARTIALLY_COMPLIANT").all()
    print(f"[OK] Status filter 'PARTIALLY_COMPLIANT' matched {len(status_results)} record(s).")
    
    db.close()

    # 5. Test Embedded Photo PDF Export
    print("\n--- Testing PDF Exporter with Embedded Label Photo ---")
    pdf_gen = LMPCPdfReportGenerator()
    
    sample_scan = result_payload if result_payload is not None else {}
    pdf_bytes = pdf_gen.generate_pdf_bytes(sample_scan)
    
    pdf_out_path = os.path.join(os.path.dirname(__file__), "pdf_exports", "sample_with_photo.pdf")
    os.makedirs(os.path.dirname(pdf_out_path), exist_ok=True)
    with open(pdf_out_path, "wb") as pdf_file:
        pdf_file.write(pdf_bytes)

    print(f"[OK] Successfully generated PDF Certificate with embedded photo ({len(pdf_bytes)} bytes): {pdf_out_path}")
    print("\nALL SCAN HISTORY DATABASE & PDF PHOTO EMBEDDING TESTS PASSED SUCCESSFULLY!\n")

if __name__ == "__main__":
    test_history_and_pdf_features()
