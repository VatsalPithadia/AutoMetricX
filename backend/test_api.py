import urllib.request
import json

def check(text, name):
    url = "http://127.0.0.1:8000/check-ingredients"
    payload = {"ingredients_text": text, "product_name": name}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print(f"[{name}] Verdict: {res.get('safety_verdict')}, Score: {res.get('safety_score')}, Flagged: {[f['name'] for f in res.get('flagged_ingredients', [])]}")

check("Refined Wheat Flour, Palm Oil, TBHQ (INS 319), Tartrazine (INS 102), MSG (INS 621), Salt", "Harmful Snack")
check("100% Organic Rolled Oats, Raw Honey, Roasted Almonds, Chia Seeds", "Safe Organic Oats")

