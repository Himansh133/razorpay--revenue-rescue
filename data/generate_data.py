"""
Synthetic data generator for Revenue Rescue.

Generates 4 linked tables with DELIBERATELY PLANTED patterns so the
detection/ML layers have real signal to find, and so we can honestly
explain ground truth when asked "how do you know this is real."

Planted patterns (write these down — you'll need them for the pitch):
  1. Android + UPI + evening (8-11 PM) checkout has a much higher
     failure/abandonment rate than baseline -> the "leak" LeakHunter
     should discover.
  2. A cohort of high-LTV customers has gone dormant (no txn in 90+ days)
     -> second discoverable leak.
  3. B2B invoice negotiation outcomes follow a real (logistic) relationship:
     bigger discount + faster payment + better customer history => higher
     acceptance probability. This is what the acceptance-probability model
     is trained on.
  4. A "Group D" segment of customers with repeated broken promises and
     poor payment history exists on purpose, so the recovery-score /
     "don't chase this" logic has something real to catch.

Run: python generate_data.py
Outputs CSVs into ./output/
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

SEED = 42
rng = np.random.default_rng(SEED)

OUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT_DIR, exist_ok=True)

NOW = datetime(2026, 9, 1)

CITIES = ["Delhi", "Mumbai", "Bangalore", "Pune", "Hyderabad", "Chennai",
          "Ahmedabad", "Jaipur", "Lucknow", "Kolkata", "Indore", "Nagpur"]
TIER2_CITIES = {"Jaipur", "Lucknow", "Indore", "Nagpur"}

PAYMENT_METHODS = ["UPI", "Card", "NetBanking", "Wallet"]
DEVICES = ["Android", "iOS", "Desktop"]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Ananya",
               "Diya", "Saanvi", "Myra", "Kiara", "Rohan", "Sanya",
               "Arjun", "Neha", "Priya", "Rahul", "Simran", "Karan",
               "Meera", "Aman"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Reddy", "Iyer", "Nair",
              "Patel", "Singh", "Mehta", "Rao", "Kapoor", "Malhotra",
              "Joshi", "Chawla", "Bose"]
COMPANY_SUFFIXES = ["Traders", "Enterprises", "Textiles", "Logistics",
                     "Solutions", "Industries", "Retail", "Distributors",
                     "Foods", "Tech", "Apparel", "Exports"]


def rand_name():
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def rand_company():
    return f"{rng.choice(LAST_NAMES)} {rng.choice(COMPANY_SUFFIXES)} Pvt Ltd"


# ---------------------------------------------------------------------------
# 1. CUSTOMERS (10,000)
# ---------------------------------------------------------------------------
N_CUSTOMERS = 10_000

print("Generating customers...")

customer_ids = [f"CUST{i:06d}" for i in range(1, N_CUSTOMERS + 1)]

# Segment assignment (drives behavior downstream):
#   - 8% "dormant_high_ltv": high LTV, but planted to go quiet for 90+ days
#   - 12% "group_d_broken_promise": poor payment history, low response
#   - 15% "b2b": has a company name, eligible for B2B invoices
#   - rest: normal retail customers
segment_roll = rng.random(N_CUSTOMERS)
segment = np.where(
    segment_roll < 0.08, "dormant_high_ltv",
    np.where(segment_roll < 0.20, "group_d_broken_promise",
             np.where(segment_roll < 0.35, "b2b", "normal"))
)

ltv = np.zeros(N_CUSTOMERS)
ltv[segment == "dormant_high_ltv"] = rng.gamma(shape=6, scale=45_000, size=(segment == "dormant_high_ltv").sum()) + 150_000
ltv[segment == "group_d_broken_promise"] = rng.gamma(shape=3, scale=8_000, size=(segment == "group_d_broken_promise").sum()) + 5_000
ltv[segment == "b2b"] = rng.gamma(shape=5, scale=60_000, size=(segment == "b2b").sum()) + 80_000
ltv[segment == "normal"] = rng.gamma(shape=3, scale=6_000, size=(segment == "normal").sum()) + 3_000
ltv = np.round(ltv, -2)

orders = rng.poisson(lam=np.clip(ltv / 8000, 1, 60), size=N_CUSTOMERS) + 1

# Payment success rate: worse for group_d, better for b2b/dormant (they were good payers before going quiet)
base_success_rate = np.where(
    segment == "group_d_broken_promise", rng.uniform(0.35, 0.60, N_CUSTOMERS),
    np.where(segment == "b2b", rng.uniform(0.80, 0.97, N_CUSTOMERS),
             np.where(segment == "dormant_high_ltv", rng.uniform(0.85, 0.98, N_CUSTOMERS),
                      rng.uniform(0.70, 0.95, N_CUSTOMERS)))
)
successful_payments = np.round(orders * base_success_rate).astype(int)
failed_payments = orders - successful_payments
failed_payments = np.clip(failed_payments, 0, None)

# avg_delay in days (payment vs due date) — group_d pays very late, b2b moderate
avg_delay = np.where(
    segment == "group_d_broken_promise", rng.gamma(3, 6, N_CUSTOMERS) + 10,
    np.where(segment == "b2b", rng.gamma(2, 3, N_CUSTOMERS) + 2,
             rng.gamma(1.5, 2, N_CUSTOMERS))
)
avg_delay = np.round(avg_delay, 1)

promises_made = np.where(
    segment == "group_d_broken_promise", rng.integers(3, 12, N_CUSTOMERS),
    np.where(segment == "b2b", rng.integers(1, 6, N_CUSTOMERS),
             rng.integers(0, 3, N_CUSTOMERS))
)
promise_keep_rate = np.where(
    segment == "group_d_broken_promise", rng.uniform(0.10, 0.35, N_CUSTOMERS),
    rng.uniform(0.70, 0.98, N_CUSTOMERS)
)
promises_kept = np.round(promises_made * promise_keep_rate).astype(int)

customers = pd.DataFrame({
    "customer_id": customer_ids,
    "name": [rand_name() for _ in range(N_CUSTOMERS)],
    "company": [rand_company() if seg in ("b2b",) else "" for seg in segment],
    "segment": segment,  # not shown to the model — ground truth for you to validate against
    "ltv": ltv,
    "orders": orders,
    "successful_payments": successful_payments,
    "failed_payments": failed_payments,
    "avg_delay_days": avg_delay,
    "promises_made": promises_made,
    "promises_kept": promises_kept,
    "city": rng.choice(CITIES, N_CUSTOMERS),
    "preferred_device": rng.choice(DEVICES, N_CUSTOMERS, p=[0.55, 0.30, 0.15]),
})

# ---------------------------------------------------------------------------
# 2. TRANSACTIONS (30,000) — with the planted Android+UPI+evening leak
# ---------------------------------------------------------------------------
N_TXN = 30_000
print("Generating transactions...")

txn_customer_idx = rng.integers(0, N_CUSTOMERS, N_TXN)
txn_customer_ids = customers["customer_id"].values[txn_customer_idx]
txn_cities = customers["city"].values[txn_customer_idx]
txn_segment = customers["segment"].values[txn_customer_idx]

# Dormant customers: their transactions are pushed to be >90 days old on purpose
days_ago = rng.exponential(scale=25, size=N_TXN)
is_dormant_cust = txn_segment == "dormant_high_ltv"
# For dormant customers, cap most of their txns to be old, simulate few then silence
days_ago[is_dormant_cust] = rng.uniform(95, 240, is_dormant_cust.sum())

timestamps = [NOW - timedelta(days=float(d), hours=float(rng.uniform(0, 24))) for d in days_ago]
hours = np.array([t.hour for t in timestamps])

devices = rng.choice(DEVICES, N_TXN, p=[0.55, 0.30, 0.15])
payment_methods = rng.choice(PAYMENT_METHODS, N_TXN, p=[0.55, 0.25, 0.12, 0.08])

amount = np.round(rng.gamma(shape=2.2, scale=650, size=N_TXN) + 150, -1)

# --- Baseline success probability ---
success_prob = np.full(N_TXN, 0.78)

# Group D customers fail more often regardless of channel
success_prob = np.where(txn_segment == "group_d_broken_promise", success_prob - 0.20, success_prob)

# PLANTED LEAK: Android + UPI + evening (20:00-23:00) has ~31% relative drop
evening_mask = (hours >= 20) & (hours <= 23)
leak_mask = (devices == "Android") & (payment_methods == "UPI") & evening_mask
success_prob = np.where(leak_mask, success_prob * 0.69, success_prob)

# small extra friction for tier-2 cities during the same window (compounds the leak, matches the "root cause" narrative)
tier2_mask = np.isin(txn_cities, list(TIER2_CITIES))
success_prob = np.where(leak_mask & tier2_mask, success_prob * 0.92, success_prob)

success_prob = np.clip(success_prob, 0.05, 0.99)
outcome_roll = rng.random(N_TXN)
status = np.where(outcome_roll < success_prob, "success",
                   np.where(outcome_roll < success_prob + (1 - success_prob) * 0.55, "failed", "abandoned"))

transactions = pd.DataFrame({
    "transaction_id": [f"TXN{i:07d}" for i in range(1, N_TXN + 1)],
    "customer_id": txn_customer_ids,
    "amount": amount,
    "timestamp": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
    "payment_method": payment_methods,
    "status": status,
    "device": devices,
    "city": txn_cities,
})

# ---------------------------------------------------------------------------
# 3. INVOICES (2,000) — B2B overdue receivables
# ---------------------------------------------------------------------------
N_INVOICES = 2_000
print("Generating invoices...")

# Draw invoice customers weighted toward b2b and group_d segments (that's who gets invoiced/chased)
b2b_pool = customers[customers["segment"].isin(["b2b", "group_d_broken_promise", "dormant_high_ltv"])]
if len(b2b_pool) < N_INVOICES:
    # top up with normal customers if pool too small
    b2b_pool = pd.concat([b2b_pool, customers[customers["segment"] == "normal"].sample(
        N_INVOICES - len(b2b_pool), random_state=1)])

inv_customers = b2b_pool.sample(N_INVOICES, replace=len(b2b_pool) < N_INVOICES, random_state=2).reset_index(drop=True)

issue_days_ago = rng.uniform(20, 200, N_INVOICES)
issue_dates = [NOW - timedelta(days=float(d)) for d in issue_days_ago]
payment_terms = rng.choice([15, 30, 45, 60], N_INVOICES, p=[0.2, 0.45, 0.2, 0.15])
due_dates = [issue_dates[i] + timedelta(days=int(payment_terms[i])) for i in range(N_INVOICES)]

days_overdue = np.array([(NOW - d).days for d in due_dates])
days_overdue = np.clip(days_overdue, -10, None)  # a few not-yet-due, most overdue

inv_amount = np.round(rng.gamma(shape=2.5, scale=inv_customers["ltv"].values / 12 + 8000, size=N_INVOICES), -2)
inv_amount = np.clip(inv_amount, 5_000, 500_000)

# status: paid / overdue / written_off, influenced by segment
status_roll = rng.random(N_INVOICES)
seg = inv_customers["segment"].values
inv_status = np.select(
    [
        (seg == "group_d_broken_promise") & (status_roll < 0.55),
        (seg != "group_d_broken_promise") & (days_overdue < 0),
        status_roll < 0.35,
    ],
    ["written_off", "not_yet_due", "paid"],
    default="overdue"
)

invoices = pd.DataFrame({
    "invoice_id": [f"INV{i:06d}" for i in range(1, N_INVOICES + 1)],
    "customer_id": inv_customers["customer_id"].values,
    "amount": inv_amount,
    "issue_date": [d.strftime("%Y-%m-%d") for d in issue_dates],
    "due_date": [d.strftime("%Y-%m-%d") for d in due_dates],
    "days_overdue": days_overdue,
    "status": inv_status,
})

# ---------------------------------------------------------------------------
# 4. NEGOTIATION OUTCOMES (2,000) — training data for the acceptance model
# ---------------------------------------------------------------------------
N_NEG = 2_000
print("Generating negotiation outcomes...")

neg_customers = customers.sample(N_NEG, replace=True, random_state=3).reset_index(drop=True)

invoice_amount = np.round(rng.gamma(shape=2.3, scale=neg_customers["ltv"].values / 14 + 6000, size=N_NEG), -2)
invoice_amount = np.clip(invoice_amount, 5_000, 400_000)

offer_discount_pct = rng.choice([0, 2, 5, 8, 12, 18, 25], N_NEG,
                                 p=[0.15, 0.15, 0.20, 0.20, 0.15, 0.10, 0.05])
offer_amount = np.round(invoice_amount * (1 - offer_discount_pct / 100), -2)

days_to_payment = rng.choice([0, 7, 15, 30, 45], N_NEG, p=[0.30, 0.20, 0.20, 0.20, 0.10])

payment_success_rate = neg_customers["successful_payments"] / neg_customers["orders"].clip(lower=1)
promise_fulfillment = np.where(
    neg_customers["promises_made"] > 0,
    neg_customers["promises_kept"] / neg_customers["promises_made"].clip(lower=1),
    0.8  # no promise history -> neutral prior
)

# customer_score: 0-1 composite used as a FEATURE (not the label)
customer_score = (
    0.35 * payment_success_rate
    + 0.25 * promise_fulfillment
    + 0.20 * np.clip(neg_customers["ltv"] / neg_customers["ltv"].max(), 0, 1)
    + 0.20 * (1 - np.clip(neg_customers["avg_delay_days"] / 60, 0, 1))
)
customer_score = np.clip(customer_score, 0, 1)

# --- Ground-truth logistic relationship for acceptance ---
# Higher discount, faster payment, and better customer_score all push acceptance up.
# This is the real relationship a LogisticRegression should recover from the data.
z = (
    -1.4
    + 3.6 * (offer_discount_pct / 25)      # bigger discount -> more likely to accept
    + 1.8 * (1 - days_to_payment / 45)     # sooner ask -> counterintuitively this represents "flexibility offered", tune sign below
    + 2.5 * customer_score                 # better customer -> more likely to honor/accept a fair deal
    - 0.9 * (invoice_amount / 400_000)     # bigger invoices are harder to get accepted
)
# NOTE: days_to_payment here represents how much TIME the offer gives the customer to pay;
# more time modestly increases acceptance (easier for them), so flip the sign to be intuitive:
z = (
    -1.4
    + 3.6 * (offer_discount_pct / 25)
    + 1.2 * (days_to_payment / 45)
    + 2.5 * customer_score
    - 0.9 * (invoice_amount / 400_000)
)
prob_accept = 1 / (1 + np.exp(-z))
prob_accept = np.clip(prob_accept, 0.02, 0.98)
accepted = (rng.random(N_NEG) < prob_accept).astype(int)

negotiations = pd.DataFrame({
    "negotiation_id": [f"NEG{i:06d}" for i in range(1, N_NEG + 1)],
    "customer_id": neg_customers["customer_id"].values,
    "invoice_amount": invoice_amount,
    "offer_amount": offer_amount,
    "offer_discount_pct": offer_discount_pct,
    "days_to_payment": days_to_payment,
    "customer_score": np.round(customer_score, 3),
    "true_accept_probability": np.round(prob_accept, 3),  # ground truth, for your own validation only
    "accepted": accepted,
})

# ---------------------------------------------------------------------------
# Save everything
# ---------------------------------------------------------------------------
customers.to_csv(os.path.join(OUT_DIR, "customers.csv"), index=False)
transactions.to_csv(os.path.join(OUT_DIR, "transactions.csv"), index=False)
invoices.to_csv(os.path.join(OUT_DIR, "invoices.csv"), index=False)
negotiations.to_csv(os.path.join(OUT_DIR, "negotiations.csv"), index=False)

print("\nSaved to", OUT_DIR)
print(f"  customers.csv     {len(customers):>7,} rows")
print(f"  transactions.csv  {len(transactions):>7,} rows")
print(f"  invoices.csv      {len(invoices):>7,} rows")
print(f"  negotiations.csv  {len(negotiations):>7,} rows")

# ---------------------------------------------------------------------------
# Sanity checks — verify the planted patterns actually show up in the data
# ---------------------------------------------------------------------------
print("\n--- Sanity checks (verify planted patterns are detectable) ---")

overall_success = (transactions["status"] == "success").mean()
leak_txns = transactions[
    (transactions["device"] == "Android") &
    (transactions["payment_method"] == "UPI") &
    (pd.to_datetime(transactions["timestamp"]).dt.hour >= 20) &
    (pd.to_datetime(transactions["timestamp"]).dt.hour <= 23)
]
leak_success = (leak_txns["status"] == "success").mean()
print(f"Overall txn success rate:              {overall_success:.1%}")
print(f"Android+UPI+evening(20-23h) success:    {leak_success:.1%}  (n={len(leak_txns)})  <- planted leak")

dormant = customers[customers["segment"] == "dormant_high_ltv"]
print(f"\nDormant high-LTV customers:             {len(dormant)}  avg LTV ₹{dormant['ltv'].mean():,.0f}")

overdue = invoices[invoices["status"] == "overdue"]
print(f"\nOverdue invoices:                       {len(overdue)}  total ₹{overdue['amount'].sum():,.0f}")

print(f"\nNegotiation acceptance rate overall:    {negotiations['accepted'].mean():.1%}")
low_disc = negotiations[negotiations["offer_discount_pct"] <= 2]
high_disc = negotiations[negotiations["offer_discount_pct"] >= 18]
print(f"  accept rate at <=2% discount:          {low_disc['accepted'].mean():.1%}")
print(f"  accept rate at >=18% discount:         {high_disc['accepted'].mean():.1%}")
print("  (should be clearly higher at higher discount -- confirms learnable signal)")
