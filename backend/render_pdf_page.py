import fitz  # PyMuPDF
import os

pdf_path = r"c:\Users\swapn\OneDrive\Documents\Metrology\backend\pdf_exports\sample_with_photo.pdf"
out_png_path = r"c:\Users\swapn\OneDrive\Documents\Metrology\backend\pdf_exports\sample_pdf_page1.png"
artifact_dir = r"C:\Users\swapn\.gemini\antigravity-ide\brain\8d54f7e0-8e2b-47d0-ae6c-914b32542f74"
artifact_png_path = os.path.join(artifact_dir, "sample_pdf_page1.png")

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
