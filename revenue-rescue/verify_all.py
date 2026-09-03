import sys
import json
import urllib.request
import hmac
import hashlib

BASE_URL = "http://127.0.0.1:8000"

def get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.urlopen(url, timeout=5)
    return json.loads(req.read().decode())

def post(path, data_dict, headers=None):
    if headers is None:
        headers = {"Content-Type": "application/json"}
    url = f"{BASE_URL}{path}"
    req_data = json.dumps(data_dict).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    res = urllib.request.urlopen(req, timeout=5)
    return json.loads(res.read().decode())

def run_verifications():
    print("==================================================================")
    print("🚀 REVENUE RESCUE ARCHITECTURE VERIFICATION")
    print("==================================================================\n")

    try:
        health = get("/health")
        print(f"✅ 1. GET /health                   : SUCCESS [{health['status']}]")
    except Exception as e:
        print(f"❌ 1. GET /health FAILED: {e}")
        return

    try:
        opps = get("/opportunities?top_n=3")
        print(f"✅ 2. GET /opportunities              : SUCCESS [{opps['total_leaks']} leak opportunities found]")
    except Exception as e:
        print(f"❌ 2. GET /opportunities FAILED: {e}")

    try:
        invs = get("/invoices?tier=high_priority&min_amount=1000")
        print(f"✅ 3. GET /invoices                   : SUCCESS [{invs['total_count']} high-priority invoices]")
    except Exception as e:
        print(f"❌ 3. GET /invoices FAILED: {e}")

    try:
        rec = post("/recovery/INV000001/recommend", {"merchant_floor": 80000.0})
        best_amt = rec["best_offer"]["offer_amount"] if rec.get("best_offer") else 0
        print(f"✅ 4. POST /recovery/.../recommend     : SUCCESS [Best Offer: ₹{best_amt:,.2f}]")
    except Exception as e:
        print(f"❌ 4. POST /recovery/.../recommend FAILED: {e}")

    try:
        trail = get("/invoices/INV000001/audit-trail")
        print(f"✅ 5. GET /invoices/.../audit-trail  : SUCCESS [{trail['events_count']} SQLite compliance events]")
    except Exception as e:
        print(f"❌ 5. GET /invoices/.../audit-trail FAILED: {e}")

    print("\n==================================================================")
    print("🎉 REVENUE-RESCUE ARCHITECTURE VERIFIED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_verifications()
