import os
import json
import uuid
import time
import asyncio
import cv2
import numpy as np
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.database import engine, get_db, Base
from app.models import ScanRecord
from app.ocr_engine import extract_text_from_image, get_rapid_ocr
from app.classifier import FieldClassifier
from app.rule_engine import LMPCRuleEngine
from app.pdf_generator import LMPCPdfReportGenerator
from app.barcode_engine import BarcodeQREngine

# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MetroLens API - Legal Metrology OCR & Compliance",
    description="Backend service for MetroLens Legal Metrology Compliance Inspection",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules", "lmpc_rules.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize engines
classifier_engine = FieldClassifier(min_confidence=0.40)
rule_checker = LMPCRuleEngine(RULES_PATH)
pdf_generator = LMPCPdfReportGenerator()
barcode_engine = BarcodeQREngine()

@app.on_event("startup")
async def startup_event():
    # Pre-load RapidOCR ONNX engine on startup
    get_rapid_ocr()

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

    # 2. Field classification
    classified_fields = classifier_engine.classify_blocks(ocr_blocks)

    # 3. LMPC Rule Engine evaluation with font calibration
    compliance_report = rule_checker.evaluate_compliance(classified_fields, ocr_blocks)

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
async def scan_label_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Accepts image upload, runs audit pipeline, and saves scan record into SQLite database.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")
    
    start_time = time.time()
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty image file received.")
        
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    saved_filename = f"{uuid.uuid4().hex}{ext}"
    saved_filepath = os.path.join(UPLOAD_DIR, saved_filename)
    
    with open(saved_filepath, "wb") as f:
        f.write(contents)
        
    try:
        pipeline_res = await asyncio.to_thread(_process_single_image_bytes, contents, file.filename or "label.jpg")
        processing_time_sec = round(time.time() - start_time, 3)
        
        result_payload = {
            "success": True,
            "filename": file.filename,
            "saved_file": saved_filename,
            "processing_time_seconds": processing_time_sec,
            **pipeline_res
        }

        # Extract product name for easy identification (require confidence >= 0.60 & clean product name)
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

        # Save scan record to SQLite database
        scan_rec = ScanRecord(
            image_filename=saved_filename,
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
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
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
        report_data = json.loads(scan.full_report_json)
        report_data["scan_id"] = scan.id
        return report_data
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to parse stored scan JSON: {str(err)}")

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
