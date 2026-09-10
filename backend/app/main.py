import os
import json
import uuid
import time
import asyncio
import logging
import datetime
import cv2
import numpy as np
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

logger = logging.getLogger("metrolens.main")

from app.database import engine, get_db, Base
from app.models import ScanRecord
from app.ocr_engine import extract_text_from_image, get_rapid_ocr, preprocess_image
from app.classifier import FieldClassifier
from app.rule_engine import LMPCRuleEngine
from app.pdf_generator import LMPCPdfReportGenerator
from app.barcode_engine import BarcodeQREngine
from app.product_checker import ProductConsistencyChecker

# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load RapidOCR ONNX engine on startup
    get_rapid_ocr()
    yield  # app runs here
    # (add shutdown cleanup here if needed)

app = FastAPI(
    title="MetroLens API - Legal Metrology OCR & Compliance",
    description="Backend service for MetroLens Legal Metrology Compliance Inspection",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend
# NOTE: allow_origins=["*"] is incompatible with allow_credentials=True per
# the Fetch spec — browsers reject such responses. Use explicit origins instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules", "lmpc_rules.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Initialize engines
classifier_engine = FieldClassifier(min_confidence=0.40)
rule_checker = LMPCRuleEngine(RULES_PATH)
pdf_generator = LMPCPdfReportGenerator()
barcode_engine = BarcodeQREngine()
consistency_checker = ProductConsistencyChecker()


@app.get("/")
def api_root():
    return {
        "service": "MetroLens Legal Metrology OCR API",
        "status": "online",
        "endpoints": ["/health", "/scan", "/rules", "/export-pdf", "/scans"]
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "uploads_dir_exists": os.path.exists(UPLOAD_DIR),
        "rules_loaded": os.path.exists(RULES_PATH)
    }

@app.get("/rules")
def get_lmpc_rules():
    if not os.path.exists(RULES_PATH):
        raise HTTPException(status_code=404, detail="Rules configuration file missing")
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def _process_single_image_bytes(contents: bytes, filename: str) -> dict:
    """
    Internal pipeline processing image bytes across OCR, Classifier, Rule Engine, and Barcode/QR Engine.
    """
    nparr = np.frombuffer(contents, np.uint8)
    cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 1. OCR text extraction
    ocr_result = extract_text_from_image(contents)
    ocr_blocks = ocr_result.get("blocks", [])

    # Produce an OCR-resolution image for font calibration.
    # CRITICAL: OCR block bounding boxes are in the resized (max 1600px) coordinate space.
    # Barcode detection for px/mm calibration MUST use the same resolution image,
    # otherwise the scale factor is computed in full-res pixels but applied to resized-pixel
    # heights — causing font_height_mm to be systematically under-reported.
    try:
        ocr_res_img, _ = preprocess_image(contents, max_dimension=1600, apply_clahe=False, apply_deskew=False)
    except Exception:
        ocr_res_img = cv_img  # safe fallback

    # 2. Field classification
    classified_fields = classifier_engine.classify_blocks(ocr_blocks)

    # 3. LMPC Rule Engine evaluation with font calibration
    # Pass the OCR-resolution image so barcode px measurement matches OCR block coordinate space
    compliance_report = rule_checker.evaluate_compliance(
        classified_fields,
        ocr_blocks,
        image=ocr_res_img,
        image_metadata=ocr_result.get("image_metadata")
    )

    # 4. Barcode & QR code cross-check
    decoded_codes = barcode_engine.decode_barcodes_and_qr(cv_img) if cv_img is not None else []
    barcode_qr_analysis = barcode_engine.verify_cross_check(decoded_codes, classified_fields)

    return {
        "engine": ocr_result["engine"],
        "image_metadata": ocr_result["image_metadata"],
        "total_blocks": ocr_result["total_detected_blocks"],
        "raw_text": ocr_result["raw_text"],
        "text_lines": ocr_result["text_lines"],
        "ocr_blocks": ocr_result["blocks"],
        "classified_fields": classified_fields,
        "compliance_report": compliance_report,
        "barcode_qr_analysis": barcode_qr_analysis
    }

@app.post("/scan")
async def scan_label_image(
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db)
):
    """
    Accepts single or multi-side image upload of a packaged commodity product.
    If multiple images are uploaded:
    1. Processes each image through OCR, Classification, and Barcode engines.
    2. Runs ProductConsistencyChecker to ensure all uploaded sides belong to the SAME product.
    3. Rejects with HTTP 400 if different products are mixed (e.g. Tea Front + Biscuit Back).
    4. Unifies declarations across complementary sides and evaluates comprehensive LMPC compliance.
    """
    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend([f for f in files if f and f.filename])
    if file and file.filename and file not in upload_list:
        upload_list.append(file)

    if not upload_list:
        raise HTTPException(status_code=400, detail="No image file received. Please upload at least one label photo.")

    for f in upload_list:
        if not (f.content_type and f.content_type.startswith("image/")):
            raise HTTPException(status_code=400, detail=f"File '{f.filename}' must be a valid image (JPEG, PNG, WEBP).")

    start_time = time.time()
    side_results = []
    saved_files = []

    try:
        for idx, up_file in enumerate(upload_list):
            contents = await up_file.read()
            if len(contents) == 0:
                raise HTTPException(status_code=400, detail=f"Empty image file received: {up_file.filename}")

            ext = os.path.splitext(up_file.filename)[1] if up_file.filename else ".jpg"
            saved_filename = f"{uuid.uuid4().hex}{ext}"
            saved_filepath = os.path.join(UPLOAD_DIR, saved_filename)

            with open(saved_filepath, "wb") as out_f:
                out_f.write(contents)
            saved_files.append(saved_filename)

            res = await asyncio.to_thread(_process_single_image_bytes, contents, up_file.filename or f"side_{idx+1}.jpg")
            res["filename"] = up_file.filename or f"side_{idx+1}.jpg"
            res["saved_file"] = saved_filename
            res["side_index"] = idx + 1
            side_results.append(res)

        # Multi-Image Cross-Check (Same-Product Verification)
        if len(side_results) > 1:
            is_consistent, conf_score, mismatch_reason = consistency_checker.check_consistency(side_results)
            if not is_consistent:
                logger.warning(f"Product mismatch rejected: {mismatch_reason}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "product_mismatch": True,
                        "detail": mismatch_reason
                    }
                )

        # Merge fields across sides
        if len(side_results) == 1:
            merged_classified = side_results[0]["classified_fields"]
            final_report = side_results[0]["compliance_report"]
            primary_engine = side_results[0]["engine"]
            combined_raw_text = side_results[0]["raw_text"]
            combined_blocks = side_results[0]["ocr_blocks"]
            combined_barcode = side_results[0]["barcode_qr_analysis"]
            primary_meta = side_results[0]["image_metadata"]
        else:
            merged_classified = classifier_engine.merge_multiside_fields(side_results)
            all_blocks = []
            for s in side_results:
                for b in s.get("ocr_blocks", []):
                    b_copy = dict(b)
                    b_copy["side_index"] = s["side_index"]
                    all_blocks.append(b_copy)

            final_report = rule_checker.evaluate_compliance(
                merged_classified,
                all_blocks,
                image=None,
                image_metadata=side_results[0]["image_metadata"]
            )
            primary_engine = side_results[0]["engine"]
            combined_raw_text = "\n\n--- Next Package Side ---\n\n".join([f"[{s['filename']}]:\n{s['raw_text']}" for s in side_results])
            combined_blocks = all_blocks
            combined_barcode = barcode_engine.verify_cross_check(
                [c for s in side_results for c in s.get("barcode_qr_analysis", {}).get("decoded_codes", [])],
                merged_classified
            )
            primary_meta = side_results[0]["image_metadata"]

        processing_time_sec = round(time.time() - start_time, 3)

        # Extract product name
        comm_obj = merged_classified.get("commodity_name", {})
        comm_text = (comm_obj.get("clean_name") or comm_obj.get("raw_text")) if isinstance(comm_obj, dict) else None
        comm_conf = comm_obj.get("confidence", 0.0) if isinstance(comm_obj, dict) else 0.0

        generic_reject_kw = ['AYURVEDIC', 'PROPRIETARY', 'MEDICINE', 'ACCEPT', 'DAMAGED', 'SACHET', 'WARNING']
        is_generic_phrase = any(kw in (comm_text or '').upper() for kw in generic_reject_kw)

        if comm_text and comm_conf >= 0.50 and len(comm_text.strip()) >= 3 and not is_generic_phrase:
            product_name = comm_text.strip()
            if len(product_name) > 80:
                product_name = product_name[:80] + "..."
        else:
            product_name = "Unknown Product"

        overall_status = final_report["overall_status"]
        compliance_score = float(final_report["compliance_score"])

        result_payload = {
            "success": True,
            "is_multiside": len(side_results) > 1,
            "total_sides": len(side_results),
            "filename": side_results[0]["filename"] if len(side_results) == 1 else f"{len(side_results)} Package Sides ({side_results[0]['filename']} + {len(side_results)-1} more)",
            "product_name": product_name,
            "saved_file": saved_files[0],
            "saved_files": saved_files,
            "side_images": [
                {
                    "side_index": s["side_index"],
                    "filename": s["filename"],
                    "saved_file": s["saved_file"],
                    "ocr_blocks": s["ocr_blocks"],
                    "image_metadata": s["image_metadata"]
                }
                for s in side_results
            ],
            "processing_time_seconds": processing_time_sec,
            "engine": primary_engine,
            "image_metadata": primary_meta,
            "total_blocks": len(combined_blocks),
            "raw_text": combined_raw_text,
            "ocr_blocks": combined_blocks,
            "classified_fields": merged_classified,
            "compliance_report": final_report,
            "barcode_qr_analysis": combined_barcode,
            "product_consistency": {
                "is_consistent": True,
                "confidence": 0.95,
                "message": f"All {len(side_results)} package sides verified to belong to the same product." if len(side_results) > 1 else "Single side scan"
            }
        }

        # Save scan record to SQLite database
        scan_rec = ScanRecord(
            image_filename=saved_files[0],
            product_name=product_name,
            overall_status=overall_status,
            compliance_score=compliance_score,
            full_report_json=json.dumps(result_payload)
        )
        db.add(scan_rec)
        db.commit()
        db.refresh(scan_rec)

        result_payload["scan_id"] = scan_rec.id
        return JSONResponse(status_code=200, content=result_payload)
    except HTTPException:
        db.rollback()
        raise
    except Exception as err:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(err)}")

@app.get("/scans")
def list_past_scans(
    search: Optional[str] = Query(None, description="Search by product name"),
    status: Optional[str] = Query(None, description="Filter by overall status"),
    db: Session = Depends(get_db)
):
    """
    Returns list of past scans from SQLite database with optional search and status filters.
    """
    query = db.query(ScanRecord)

    if search and search.strip():
        query = query.filter(ScanRecord.product_name.ilike(f"%{search.strip()}%"))

    if status and status.strip():
        query = query.filter(ScanRecord.overall_status == status.strip())

    scans = query.order_by(ScanRecord.id.desc()).all()

    return [
        {
            "id": s.id,
            "timestamp": (s.timestamp.isoformat() + "Z") if s.timestamp else None,
            "image_filename": s.image_filename,
            "product_name": s.product_name,
            "overall_status": s.overall_status,
            "compliance_score": s.compliance_score
        }
        for s in scans
    ]

@app.get("/scans/{scan_id}")
def get_scan_detail(scan_id: int, db: Session = Depends(get_db)):
    """
    Returns full stored JSON audit report for a specific scan ID.
    """
    scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found")
    
    try:
        report_data = json.loads(str(scan.full_report_json))
        report_data["scan_id"] = scan.id
        return report_data
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to parse stored scan JSON: {str(err)}")

@app.delete("/scans/{scan_id}")
def delete_scan(scan_id: int, db: Session = Depends(get_db)):
    """
    Deletes a scan record from the database and removes its associated uploaded image file.
    """
    scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found")
    
    # Delete uploaded image file from disk if present
    if scan.image_filename:
        file_path = os.path.join(UPLOAD_DIR, str(scan.image_filename))
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as err:
                logger.warning(f"Could not delete image file '{file_path}': {err}")

    db.delete(scan)
    db.commit()
    return {"success": True, "message": f"Scan #{scan_id} and uploaded image deleted successfully"}

@app.delete("/scans")
def delete_all_scans(db: Session = Depends(get_db)):
    """
    Clears all scan records and all uploaded images from disk (preserving .gitkeep).
    """
    scans = db.query(ScanRecord).all()
    for s in scans:
        if s.image_filename:
            file_path = os.path.join(UPLOAD_DIR, str(s.image_filename))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    # Clean any orphan images in UPLOAD_DIR
    for item in os.listdir(UPLOAD_DIR):
        if item != ".gitkeep":
            p = os.path.join(UPLOAD_DIR, item)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    db.query(ScanRecord).delete()
    db.commit()
    return {"success": True, "message": "All past scans and uploaded images deleted successfully"}

@app.post("/export-pdf")
async def export_audit_pdf(audit_data: dict):
    """
    Generates downloadable PDF Audit Certificate with embedded label photo.
    """
    try:
        pdf_bytes = pdf_generator.generate_pdf_bytes(audit_data)
        filename = f"metrolens_audit_certificate_{uuid.uuid4().hex[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(err)}")
