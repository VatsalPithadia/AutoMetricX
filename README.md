# MetroLens (AutoMetriX) - Legal Metrology AI Audit Platform

**Smart India Hackathon 2026 Prototype**
- **Problem Statement ID**: SIH26034
- **Team**: SixSyntax
- **Phase**: 1 (FastAPI OCR Backend + React Vite Drag & Drop Frontend)

---

## Architecture Overview (Phase 1)

MetroLens provides automated Legal Metrology (LMPC) compliance verification for packaged commodity labels. In Phase 1, the platform consists of:

1. **FastAPI Backend (Python)**:
   - `GET /health`: Health check and status monitoring.
   - `POST /scan`: Receives uploaded label photos, executes OpenCV contrast enhancement/glare reduction, runs OCR (PaddleOCR / EasyOCR engine), and extracts raw text lines with bounding box coordinates `[x, y, width, height]` and confidence scores.
   - `GET /rules`: Serves structured versioned LMPC rule definitions (`rules/lmpc_rules.json`).

2. **React Web Frontend (Vite + Tailwind CSS)**:
   - **Upload Screen**: Interactive drag-and-drop zone, phone camera photo selector, image thumbnail preview, and a 1-click **Demo Sample Label Generator** for instant pitch testing.
   - **Processing Screen**: Visual scanning radar animation while backend executes OCR.
   - **OCR Result Screen**: Live image view with bounding box overlays, extracted raw text container with 1-click clipboard copy, detected text regions table, and collapsible raw JSON inspector.

---

## Local Setup & Quickstart Guide

Follow these steps to run the complete MetroLens system on your machine.

### 1. Start the FastAPI Backend (Port 8000)

#### Step 1A: Create & Activate Virtual Environment (`venv`)

It is strongly recommended to use a Python virtual environment to manage dependencies.

**1. Create the virtual environment** (if not already created):
```bash
# Run from the project root directory
python -m venv .venv
```

**2. Activate the virtual environment**:

- **Windows (PowerShell)**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
  *(If execution policy prevents running scripts, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` first)*

- **Windows (Command Prompt / CMD)**:
  ```cmd
  .venv\Scripts\activate.bat
  ```

- **macOS / Linux (Bash / Zsh)**:
  ```bash
  source .venv/bin/activate
  ```

*Once activated, you should see `(.venv)` prefixed to your terminal command prompt.*

#### Step 1B: Install Dependencies & Launch Backend Server

With the `(.venv)` environment active, navigate to the `backend` directory, install requirements, and launch Uvicorn:

```bash
cd backend
# pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Verify backend health in your browser or terminal:
- **Health Check**: `http://localhost:8000/health`
- **Interactive Swagger API Docs**: `http://localhost:8000/docs`

---

### 2. Start the React Frontend (Port 5173)

Open a second terminal window and run:

```bash
cd frontend
# npm install
npm run dev
```

Open your browser at `http://localhost:5173`.

---

## How to Test Phase 1 Features

1. Open `http://localhost:5173` in your browser.
2. Observe the header badge showing **"Backend Connected (Port 8000)"**.
3. Upload a label photo by either:
   - Dragging & dropping a photo of any packaged commodity label (e.g. snack box, bottle label).
   - Clicking **"Try Demo Sample Label"** to automatically generate a sample packaged label image.
4. Click **"Scan Label with MetroLens OCR"**.
5. View the returned OCR result:
   - **Visual Bounding Boxes**: Hover/click green rectangular bounding box overlays drawn over detected text regions.
   - **Raw Extracted Text**: Copy the full text lines with 1-click.
   - **Text Blocks Table**: Review extracted strings, confidence %, and pixel dimensions.
   - **API Payload**: Expand the JSON inspector to view raw API response data.

---

## Structured LMPC Rules Database (`backend/rules/lmpc_rules.json`)

The legal rules for Legal Metrology (Packaged Commodities) Rules, 2011 are structured in JSON format:
- **Rule 6(1)(a-f)**: Mandatory declaration checks (Manufacturer Name/Address, Net Quantity, Month & Year of Mfg/Import, MRP, Consumer Care).
- **Rule 7(3)**: Font size height thresholds (1.0mm minimum normal print, 2.0mm embossed/molded).
- **Rule 9(1)**: Manner and prominence of MRP.

---

*Team SixSyntax | SIH 2026 | PS ID: SIH26034*
