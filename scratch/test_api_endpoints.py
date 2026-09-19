import requests
import json
import os

API_BASE = "http://localhost:8000"

# 1. Test /health or root
try:
    r = requests.get(f"{API_BASE}/health", timeout=5)
    print(f"Health check: {r.status_code} -> {r.json()}")
except Exception as e:
    print(f"Server not running or health check failed: {e}")

# 2. Test /check-ingredients
try:
    payload = {
        "ingredients_text": "Refined Wheat Flour, Palm Oil, Sugar, TBHQ (INS 319), Tartrazine (INS 102), Salt",
        "commodity_name": "Test Biscuits"
    }
    r = requests.post(f"{API_BASE}/check-ingredients", json=payload, timeout=5)
    print(f"\n/check-ingredients: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print("Feature Title:", data.get("feature_title"))
        print("Safety Verdict:", data.get("safety_verdict"))
        print("Safety Score:", data.get("safety_score"))
        print("Flagged Count:", data.get("harmful_count"))
        print("Summary:", data.get("summary"))
        print("Disclaimer:", data.get("disclaimer")[:80] + "...")
except Exception as e:
    print(f"Ingredients test error: {e}")
