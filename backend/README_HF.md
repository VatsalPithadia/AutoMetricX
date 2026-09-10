---
title: AutoMetricX Backend
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# AutoMetricX Backend API

FastAPI backend for AutoMetricX - Legal Metrology OCR & Compliance Inspection.

## Endpoints
- `GET /` - API root
- `GET /health` - Health check
- `POST /scan` - Scan label image
- `GET /scans` - List past scans
- `POST /export-pdf` - Export PDF audit report
