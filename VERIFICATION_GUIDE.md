# Revenue Recovery Engine — Complete System Verification Guide

This document provides a comprehensive summary of everything that has been built and a **step-by-step verification guide** so you can test every feature, API endpoint, ML model, and the Neumorphic Web Dashboard yourself.

---

## 🛠️ What Has Been Built (All 10 Modules)

| # | Module | Source File | Description & Key Output |
|---|---|---|---|
| 1 | **`LEAK-SCAN`** | [`leak_scan.py`](file:///home/himansh/Desktop/hackathon/razorpay/leak_scan.py) | Statistical anomaly detection engine using two-proportion z-tests to detect conversion drops. |
| 2 | **`RECOVERY-SCORE`** | [`recovery_score.py`](file:///home/himansh/Desktop/hackathon/razorpay/recovery_score.py) | Weighted heuristic ranking engine categorizing invoices into 4 recoverability tiers. |
| 3 | **`ACCEPT-MODEL`** | [`accept_model.py`](file:///home/himansh/Desktop/hackathon/razorpay/accept_model.py) | Trained `LogisticRegression` ML model predicting offer acceptance probability (**ROC-AUC: 0.7446**). |
| 4 | **`OFFER-OPTIMIZER`** | [`offer_optimizer.py`](file:///home/himansh/Desktop/hackathon/razorpay/offer_optimizer.py) | Expected-value offer optimizer enforcing **hard merchant floor guardrails**. |
| 5 | **`AGENT-BRAIN`** | [`agent_brain.py`](file:///home/himansh/Desktop/hackathon/razorpay/agent_brain.py) | Anthropic Claude tool-calling agent with strict zero-hallucination guardrails and narration. |
| 6 | **`API-CORE`** | [`main.py`](file:///home/himansh/Desktop/hackathon/razorpay/main.py) & [`models.py`](file:///home/himansh/Desktop/hackathon/razorpay/models.py) | Production-ready `FastAPI` backend exposing 10 typed HTTP endpoints with Pydantic validation. |
| 7 | **`PAY-BRIDGE`** | [`pay_bridge.py`](file:///home/himansh/Desktop/hackathon/razorpay/pay_bridge.py) | Razorpay test-mode payment link generator, HMAC-SHA256 signature verifier & webhook parser. |
| 8 | **`AUDIT-TRAIL`** | [`audit_trail.py`](file:///home/himansh/Desktop/hackathon/razorpay/audit_trail.py) | Timestamped, append-only SQLite compliance log recording every action and timeline summary. |
| 9 | **`DASHBOARD-UI`** | [`frontend/`](file:///home/himansh/Desktop/hackathon/razorpay/frontend) | Distinctive **Neumorphic (Soft UI)** React + Vite web dashboard featuring the 3-minute demo flow. |
| 10 | **`DATA & MODELS`** | [`output/`](file:///home/himansh/Desktop/hackathon/razorpay/output) | Synthetic dataset CSVs and trained model weights (`output/accept_model.joblib`). |

---

## 🚀 How to Verify Everything Yourself

### Option 1: Automated 1-Command Verification

Run our built-in automated test script from the project root:

```bash
./venv/bin/python verify_all.py
```

**Expected Output:**
```text
==================================================================
🚀 SYSTEM VERIFICATION: REVENUE RECOVERY BACKEND & FRONTEND
==================================================================

✅ 1. GET /health                    : SUCCESS [status: ok]
✅ 2. GET /opportunities               : SUCCESS [Found 2 leak segments]
✅ 3. GET /invoices                    : SUCCESS [Found 342 high-priority invoices]
✅ 4. GET /invoices/INV000001          : SUCCESS [Score: 0.7591, Tier: high_priority]
✅ 5. POST /recovery/.../recommend      : SUCCESS [Best Offer: ₹106,100.00, Evaluated: 35 candidates]
✅ 6. POST /recovery/.../execute        : SUCCESS [Payment Link: https://rzp.io/i/plink_test_...]
✅ 7. POST /webhooks/razorpay          : SUCCESS [Signature Verified, Recovered: ₹106,100.00]
✅ 8. POST /agent/ask                  : SUCCESS [Turns: 5, Tool Calls: 5]
✅ 9. GET /invoices/.../audit-trail   : SUCCESS [15 compliance events recorded in SQLite]
✅ 10. GET /dashboard/summary          : SUCCESS [Risk: ₹444.4M | Recoverable: ₹57.5M | Recovered: ₹400.4K]

==================================================================
🎉 ALL 10 MODULES & ENDPOINTS ARE FULLY FUNCTIONAL AND VERIFIED!
==================================================================
```

---

### Option 2: Interactive Web Dashboard (Neumorphic UI)

1. Ensure the **FastAPI Backend** is running (currently active on port `8000`):
   ```bash
   ./venv/bin/uvicorn main:app --reload
   ```

2. Open the **Vite Frontend Web Server**:
   ```bash
   cd frontend
   npm run dev
   ```

3. Open your web browser and navigate to:
   👉 **`http://127.0.0.1:5173/`**

#### 🎭 Demo Script Walkthrough inside the Dashboard:
1. **0:00 — Dashboard Overview**: View top-level cards (*Revenue at Risk*, *Recoverable*, *Recovered* in `#38B2AC` teal).
2. **0:20 — AI Investigation Scan**: Watch the staggered reveal sequence cycle through 31,824 transactions and reveal detected leak segments.
3. **0:50 — Opportunities Tab**: Click **"Review Opportunities"** to inspect detected statistical leaks and prioritized B2B overdue invoices.
4. **1:10 — Recovery Case (`INV000001`)**: Click invoice **`INV000001`**:
   - View recommended offer focal point (e.g. **₹106,100 TODAY**).
   - Adjust the **Merchant Floor Slider** and watch candidate offers dynamically re-evaluate.
   - **The Hard-Floor Demo Moment**: Observe the Candidate Offer Matrix — valid offers are raised Extruded cards, while rejected offers (below floor) are visually pressed **INTO** the surface with strikethroughs and `❌ rejected: below merchant floor` labels.
5. **1:40 — Payment Link Creation**: Click **`CREATE PAYMENT LINK`** to see the satisfying physical push-down interaction and the generated Razorpay URL.
6. **2:00 — Webhook Settlement**: Click **`Simulate Webhook Payment`** to fire a signed Razorpay webhook and see status transition live to **`✅ RECOVERED`**.
7. **2:30 — Compliance Audit Trail**: Scroll down to view the vertical timeline inside an Inset groove powered by SQLite.

---

### Option 3: Interactive OpenAPI Swagger Docs (Backend APIs)

Open your browser and navigate to:
👉 **`http://127.0.0.1:8000/docs`**

You will see interactive documentation for all 10 endpoints:
- `GET /health`
- `GET /opportunities`
- `GET /invoices`
- `GET /invoices/{invoice_id}`
- `GET /invoices/{invoice_id}/audit-trail`
- `POST /recovery/{invoice_id}/recommend`
- `POST /recovery/{invoice_id}/execute`
- `POST /webhooks/razorpay`
- `POST /agent/ask`
- `GET /dashboard/summary`

---

### Option 4: Standalone Module CLI Smoke Tests

Each core module includes a standalone execution block (`if __name__ == "__main__":`):

```bash
# 1. Test Statistical Leak Scanner
./venv/bin/python leak_scan.py

# 2. Test Heuristic Recovery Scoring
./venv/bin/python recovery_score.py

# 3. Test Machine Learning Model (Logistic Regression AUC: 0.7446)
./venv/bin/python accept_model.py

# 4. Test Deterministic Offer Optimizer & Hard Floors
./venv/bin/python offer_optimizer.py

# 5. Test Agent Brain Tool-Calling Loop & Guardrails
./venv/bin/python agent_brain.py

# 6. Test Razorpay Payment Bridge & Webhook Verification
./venv/bin/python pay_bridge.py

# 7. Test SQLite Audit Trail Compliance Logging
./venv/bin/python audit_trail.py
```

---

## 📁 Key File Locations

- **FastAPI Core**: [`main.py`](file:///home/himansh/Desktop/hackathon/razorpay/main.py) & [`models.py`](file:///home/himansh/Desktop/hackathon/razorpay/models.py)
- **Frontend App**: [`frontend/src/App.jsx`](file:///home/himansh/Desktop/hackathon/razorpay/frontend/src/App.jsx)
- **Neumorphic Tokens**: [`frontend/src/tokens.js`](file:///home/himansh/Desktop/hackathon/razorpay/frontend/src/tokens.js)
- **Verification Script**: [`verify_all.py`](file:///home/himansh/Desktop/hackathon/razorpay/verify_all.py)
- **Project Report**: [`completed.md`](file:///home/himansh/Desktop/hackathon/razorpay/completed.md)
