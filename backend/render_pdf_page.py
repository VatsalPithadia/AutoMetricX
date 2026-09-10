# pyrefly: ignore [missing-import]
import pymupdf as fitz  # PyMuPDF (fitz alias for compatibility)
import os

# Paths relative to this script's directory (works on any machine)
_script_dir = os.path.dirname(os.path.abspath(__file__))
pdf_exports_dir = os.path.join(_script_dir, "pdf_exports")
os.makedirs(pdf_exports_dir, exist_ok=True)

pdf_path = os.path.join(pdf_exports_dir, "sample_with_photo.pdf")
out_png_path = os.path.join(pdf_exports_dir, "sample_pdf_page1.png")
artifact_png_path = out_png_path  # Save in same pdf_exports folder

if os.path.exists(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    pix.save(out_png_path)
    pix.save(artifact_png_path)
    print(f"[OK] Rendered PDF Page 1 to PNG ({pix.width}x{pix.height} px): {out_png_path}")
    print(f"[OK] Saved copy to artifact directory: {artifact_png_path}")
else:
    print(f"PDF file missing: {pdf_path}")
