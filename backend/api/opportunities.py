from fastapi import APIRouter, HTTPException, Query
from backend.models.schemas import OpportunitiesResponse, OpportunityItem
from backend.services.analytics import scan_all_leaks

router = APIRouter(prefix="", tags=["LEAK-SCAN"])

# Data reference injected from main app state
data_store = {}

@router.get("/opportunities", response_model=OpportunitiesResponse)
def get_revenue_opportunities(top_n: int = Query(5, ge=1, le=50)):
    """
    Scans transaction data for statistical conversion anomalies (LEAK-SCAN).
    """
    df_tx = data_store.get("transactions_df")
    if df_tx is None or df_tx.empty:
        raise HTTPException(status_code=500, detail="Transaction data not loaded")

    leaks = scan_all_leaks(df_tx)
    top_leaks = leaks[:top_n]

    opp_items = []
    for idx, leak in enumerate(top_leaks):
        opp_items.append(OpportunityItem(
            opportunity_id=f"opp_leak_{idx + 1:03d}",
            type="statistical_leak",
            title=leak["title"],
            description=f"Statistically significant conversion drop of -{leak['drop_pct']*100:.1f}% vs baseline across {leak['dimension']}.",
            impact_rupees=leak["impact_rupees"],
            confidence=leak["confidence"],
            segment_details=leak["segment"]
        ))

    return OpportunitiesResponse(
        status="success",
        total_leaks=len(leaks),
        opportunities=opp_items
    )
