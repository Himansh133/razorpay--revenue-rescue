# Revenue Rescue — Automated Financial Recovery Engine

A modular, explainable, and audit-traceable revenue recovery backend & Neumorphic web application designed for Indian payment contexts (UPI, NetBanking, B2B invoices).

---

## 📁 Repository Directory Architecture

```text
revenue-rescue/
│
├── backend/
│   ├── main.py                 # FastAPI entry point & app initialization
│   ├── config.py               # Environment configuration
│   │
│   ├── api/
│   │   ├── opportunities.py    # Revenue leak endpoints (LEAK-SCAN)
│   │   ├── recovery.py         # Recovery scoring & offer optimizer endpoints
│   │   └── webhooks.py         # Razorpay webhook signature verifier & parser
│   │
│   ├── agents/
│   │   ├── detective.py        # AI statistical anomaly scan agent
│   │   └── negotiator.py       # AI recovery decision narrator & tool loop
│   │
│   ├── services/
│   │   ├── analytics.py        # Z-test revenue leak calculations
│   │   ├── scoring.py          # Weighted heuristic invoice recovery score
│   │   ├── optimizer.py        # Candidate offer generator & floor filter
│   │   └── razorpay.py         # Razorpay payment link & webhook logic
│   │
│   ├── ml/
│   │   ├── train.py            # Train Logistic Regression model
│   │   └── model.pkl           # Saved scikit-learn model weights
│   │
│   ├── models/
│   │   └── schemas.py          # Pydantic data validation schemas
│   │
│   └── db/
│       ├── database.py         # SQLite connection & compliance log engine
│       └── models.py           # Audit event data models
│
├── data/
│   ├── customers.csv
│   ├── transactions.csv
│   ├── invoices.csv
│   └── negotiations.csv
│
├── scripts/
│   └── generate_data.py        # Synthetic dataset generator
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Opportunities.jsx
│   │   │   └── RecoveryCase.jsx
│   │   │
│   │   ├── components/
│   │   │   ├── MetricCard.jsx
│   │   │   ├── OpportunityCard.jsx
│   │   │   ├── OfferTable.jsx
│   │   │   └── Timeline.jsx
│   │   │
│   │   └── api.js
│   │
│   └── package.json
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Start the FastAPI Backend
```bash
PYTHONPATH=backend uvicorn backend.main:app --reload --port 8000
```
- OpenAPI Swagger Docs: `http://127.0.0.1:8000/docs`

### 2. Start the Neumorphic Web Dashboard
```bash
cd frontend
npm install
npm run dev
```
- Web Application: `http://127.0.0.1:5173/`

### 3. Run Automated System Verification
```bash
PYTHONPATH=. python verify_all.py
```
