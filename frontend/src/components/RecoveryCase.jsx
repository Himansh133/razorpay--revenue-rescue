import React, { useEffect, useState } from 'react';
import {
  getInvoiceDetail,
  recommendRecoveryOffer,
  executeRecoveryOffer,
  getInvoiceAuditTrail,
  triggerMockWebhook
} from '../api';
import { TOKENS } from '../tokens';
import {
  ArrowLeft,
  DollarSign,
  ShieldAlert,
  CheckCircle2,
  Clock,
  ExternalLink,
  Sliders,
  Send,
  Zap,
  Lock,
  ListOrdered
} from 'lucide-react';

export default function RecoveryCase({ invoiceId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [merchantFloor, setMerchantFloor] = useState(0);
  const [loading, setLoading] = useState(true);
  const [recommending, setRecommending] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);
  const [auditTrail, setAuditTrail] = useState(null);
  const [webhookSimulating, setWebhookSimulating] = useState(false);

  // 1. Initial Load of Invoice Detail
  useEffect(() => {
    async function loadInvoice() {
      try {
        setLoading(true);
        const data = await getInvoiceDetail(invoiceId);
        setDetail(data);
        const initialFloor = Math.round(data.amount * 0.94);
        setMerchantFloor(initialFloor);
        await fetchRecommendation(data.invoice_id, initialFloor);
        await fetchAuditTrail(data.invoice_id);
      } catch (err) {
        console.error("Error loading recovery case:", err);
      } finally {
        setLoading(false);
      }
    }
    loadInvoice();
  }, [invoiceId]);

  // 2. Fetch Recommendation from OFFER-OPTIMIZER
  async function fetchRecommendation(invId, floorVal) {
    try {
      setRecommending(true);
      const rec = await recommendRecoveryOffer(invId, floorVal);
      setRecommendation(rec);
    } catch (err) {
      console.error("Error fetching offer recommendation:", err);
    } finally {
      setRecommending(false);
    }
  }

  // 3. Fetch Audit Trail
  async function fetchAuditTrail(invId) {
    try {
      const trailData = await getInvoiceAuditTrail(invId);
      setAuditTrail(trailData);
    } catch (err) {
      console.error("Error fetching audit trail:", err);
    }
  }

  // 4. Polling for Live Payment Webhook Status Update
  useEffect(() => {
    if (!invoiceId) return;

    const interval = setInterval(async () => {
      try {
        const freshDetail = await getInvoiceDetail(invoiceId);
        setDetail(prev => {
          if (prev && freshDetail.status !== prev.status) {
            fetchAuditTrail(invoiceId);
          }
          return freshDetail;
        });
      } catch (e) {
        // Silent poll error catch
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [invoiceId]);

  // Handle Floor Slider/Input Change
  const handleFloorChange = (e) => {
    const val = Number(e.target.value);
    setMerchantFloor(val);
  };

  const handleFloorCommit = () => {
    if (detail?.invoice_id) {
      fetchRecommendation(detail.invoice_id, merchantFloor);
    }
  };

  // Handle Execute Recovery Payment Link Creation
  const handleExecute = async () => {
    if (!recommendation?.best_offer) return;
    try {
      setExecuting(true);
      const offerAmt = recommendation.best_offer.offer_amount;
      const res = await executeRecoveryOffer(invoiceId, offerAmt);
      setExecutionResult(res);
      await fetchAuditTrail(invoiceId);
    } catch (err) {
      console.error("Execution error:", err);
    } finally {
      setExecuting(false);
    }
  };

  // Handle Stage Webhook Simulation
  const handleSimulateWebhook = async () => {
    const offerAmt = recommendation?.best_offer?.offer_amount || detail?.amount || 1000;
    try {
      setWebhookSimulating(true);
      await triggerMockWebhook(invoiceId, offerAmt);
      const updated = await getInvoiceDetail(invoiceId);
      setDetail(updated);
      await fetchAuditTrail(invoiceId);
    } catch (err) {
      console.error("Webhook simulation error:", err);
    } finally {
      setWebhookSimulating(false);
    }
  };

  const formatRupees = (val) => {
    if (!val && val !== 0) return '₹0';
    return `₹${val.toLocaleString('en-IN')}`;
  };

  if (loading) {
    return (
      <div className="space-y-8 animate-pulse">
        <div className="h-8 bg-[#C5CEDC] rounded w-1/4"></div>
        <div className={`p-10 ${TOKENS.radius.container} ${TOKENS.shadows.inset} h-96`}></div>
      </div>
    );
  }

  const isRecovered = detail?.status === 'recovered';
  const bestOffer = recommendation?.best_offer;
  const allCandidates = recommendation?.all_candidates || [];

  return (
    <div className="space-y-8">
      {/* Back Button & Top Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className={`px-5 py-2.5 ${TOKENS.radius.button} bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} hover:-translate-y-0.5 text-[#3D4852] font-semibold text-sm font-display flex items-center gap-2 transition-neumorphic ${TOKENS.focus}`}
        >
          <ArrowLeft size={18} /> Back to Opportunities
        </button>

        <div className="flex items-center gap-3">
          {isRecovered ? (
            <div className={`px-4 py-2 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-[#E0E5EC] text-[#38B2AC] font-bold text-xs font-display flex items-center gap-2`}>
              <CheckCircle2 size={16} /> ₹{detail?.actual_recovered?.toLocaleString('en-IN') || bestOffer?.offer_amount?.toLocaleString('en-IN')} RECOVERED
            </div>
          ) : (
            <div className={`px-4 py-2 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-[#E0E5EC] text-[#6C63FF] font-bold text-xs font-display flex items-center gap-2 animate-pulse`}>
              <Clock size={16} /> AWAITING PAYMENT
            </div>
          )}
        </div>
      </div>

      {/* Main Extruded Container */}
      <div className={`p-8 md:p-10 ${TOKENS.radius.container} bg-[#E0E5EC] ${TOKENS.shadows.extruded} space-y-10`}>
        {/* Customer Header Info */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-[#C5CEDC]/40 pb-8">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-extrabold font-display text-[#3D4852] tracking-tight">
                {detail?.customer_profile?.customer_id || detail?.customer_id || 'CUSTOMER'}
              </h1>
              <span className={`px-3 py-1 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} text-xs font-bold font-display text-[#6C63FF]`}>
                Invoice: {detail?.invoice_id}
              </span>
            </div>
            <p className="text-xs text-[#6B7280] mt-1 font-medium">
              Segment: {detail?.customer_profile?.segment || 'B2B Merchant'} | Risk Tier: <strong className="uppercase text-[#3D4852]">{detail?.recovery_score_breakdown?.tier}</strong>
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4 text-center">
            <div className={`p-4 ${TOKENS.radius.inner} ${TOKENS.shadows.insetSmall}`}>
              <div className="text-[10px] uppercase font-bold text-[#6B7280] font-display">Invoice</div>
              <div className="text-base font-extrabold text-[#3D4852] font-display mt-0.5">{formatRupees(detail?.amount)}</div>
            </div>

            <div className={`p-4 ${TOKENS.radius.inner} ${TOKENS.shadows.insetSmall}`}>
              <div className="text-[10px] uppercase font-bold text-[#6B7280] font-display">Overdue</div>
              <div className="text-base font-extrabold text-red-500 font-display mt-0.5">{detail?.days_overdue} Days</div>
            </div>

            <div className={`p-4 ${TOKENS.radius.inner} ${TOKENS.shadows.insetSmall}`}>
              <div className="text-[10px] uppercase font-bold text-[#6B7280] font-display">Customer LTV</div>
              <div className="text-base font-extrabold text-[#3D4852] font-display mt-0.5">{formatRupees(detail?.customer_profile?.ltv || 250000)}</div>
            </div>
          </div>
        </div>

        {/* MERCHANT FLOOR CONTROLLER & EXPECTED VALUE */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Merchant Floor Slider (Styled as an Inset Well) */}
          <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} space-y-4`}>
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-[#6B7280] font-display flex items-center gap-2">
                <Lock size={16} className="text-[#6C63FF]" /> Merchant Floor Guardrail
              </label>
              <span className="text-sm font-extrabold font-mono text-[#6C63FF]">
                {formatRupees(merchantFloor)}
              </span>
            </div>

            <input
              type="range"
              min={Math.round(detail?.amount * 0.5)}
              max={detail?.amount}
              step={1000}
              value={merchantFloor}
              onChange={handleFloorChange}
              onMouseUp={handleFloorCommit}
              onTouchEnd={handleFloorCommit}
              className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-[#C5CEDC] accent-[#6C63FF]"
            />

            <div className="flex justify-between text-[10px] text-[#6B7280] font-semibold">
              <span>50% ({formatRupees(Math.round(detail?.amount * 0.5))})</span>
              <span>100% ({formatRupees(detail?.amount)})</span>
            </div>
          </div>

          {/* Expected Value & Probability Metric */}
          <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.extrudedSmall} bg-[#E0E5EC] flex flex-col justify-between`}>
            <div className="flex justify-between items-start">
              <span className="text-xs font-bold uppercase tracking-wider text-[#6B7280] font-display">
                ML Predicted Acceptance
              </span>
              <span className={`px-2.5 py-1 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} text-xs font-bold text-[#38B2AC] font-mono`}>
                {bestOffer ? `${Math.round(bestOffer.acceptance_probability * 100)}%` : '0%'}
              </span>
            </div>

            <div className="mt-4">
              <div className="text-xs font-medium text-[#6B7280]">Expected Value Yield</div>
              <div className="text-3xl font-extrabold font-display text-[#3D4852] mt-1">
                {bestOffer ? formatRupees(bestOffer.expected_value) : '₹0'}
              </div>
            </div>
          </div>
        </div>

        {/* FOCAL POINT: RECOMMENDED OFFER */}
        <div className={`p-10 ${TOKENS.radius.container} ${TOKENS.shadows.insetDeep} text-center space-y-4 bg-[#E0E5EC]`}>
          <span className="text-xs font-bold uppercase tracking-widest text-[#6B7280] font-display inline-block">
            AI Recommended Offer
          </span>

          <div className="text-5xl md:text-7xl font-extrabold font-display text-[#6C63FF] tracking-tight">
            {bestOffer ? formatRupees(bestOffer.offer_amount) : 'NO VALID OFFER'}
          </div>

          <p className="text-sm font-semibold text-[#6B7280]">
            {bestOffer ? `${bestOffer.discount_pct}% Discount | ${bestOffer.days_to_payment}-Day Payment Terms` : 'All candidate offers fall below merchant floor.'}
          </p>

          {/* Action Button: Create Payment Link */}
          <div className="pt-4 flex flex-col sm:flex-row justify-center items-center gap-4">
            <button
              onClick={handleExecute}
              disabled={executing || !bestOffer}
              className={`w-full sm:w-auto px-10 py-4 ${TOKENS.radius.button} bg-[#6C63FF] text-white font-bold text-base font-display ${TOKENS.shadows.extruded} hover:bg-[#8B84FF] transition-neumorphic hover:-translate-y-1 active:translate-y-0.5 active:${TOKENS.shadows.insetSmall} flex items-center justify-center gap-3 disabled:opacity-50 ${TOKENS.focus}`}
            >
              {executing ? (
                <>Generating Razorpay Link...</>
              ) : (
                <>
                  <Send size={20} /> CREATE PAYMENT LINK
                </>
              )}
            </button>

            {/* Stage Demo Convenience Button */}
            <button
              onClick={handleSimulateWebhook}
              disabled={webhookSimulating}
              className={`w-full sm:w-auto px-6 py-4 ${TOKENS.radius.button} bg-[#E0E5EC] text-[#38B2AC] font-bold text-sm font-display ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} hover:-translate-y-0.5 transition-neumorphic active:translate-y-0.5 active:${TOKENS.shadows.insetSmall} flex items-center justify-center gap-2 ${TOKENS.focus}`}
            >
              <Zap size={18} /> {webhookSimulating ? 'Processing...' : 'Simulate Webhook Payment'}
            </button>
          </div>

          {/* Generated Payment Link URL Display Well */}
          {executionResult && (
            <div className={`mt-6 p-4 ${TOKENS.radius.button} ${TOKENS.shadows.inset} bg-[#E0E5EC] text-left space-y-2 animate-fadeIn`}>
              <div className="text-xs font-bold text-[#6C63FF] font-display flex items-center gap-2">
                <CheckCircle2 size={16} /> Razorpay Payment Link Generated:
              </div>
              <div className="flex items-center justify-between gap-4 font-mono text-xs text-[#3D4852]">
                <span className="truncate">{executionResult.payment_link_url}</span>
                <a
                  href={executionResult.payment_link_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[#6C63FF] hover:underline font-bold flex items-center gap-1 shrink-0"
                >
                  Open <ExternalLink size={14} />
                </a>
              </div>
            </div>
          )}
        </div>

        {/* THE HARD-FLOOR DEMO MOMENT: CANDIDATE OFFER LADDER */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-base font-bold font-display text-[#3D4852]">
              <ListOrdered size={20} className="text-[#6C63FF]" />
              <h3>Candidate Offer Matrix & Floor Filter</h3>
            </div>
            <span className="text-xs text-[#6B7280] font-medium">
              {allCandidates.length} Candidates Evaluated
            </span>
          </div>

          <div className="space-y-3 max-h-80 overflow-y-auto pr-2 custom-scrollbar">
            {allCandidates.map((cand, idx) => {
              const isValid = cand.is_valid;

              return (
                <div
                  key={idx}
                  className={`p-4 ${TOKENS.radius.button} transition-all duration-300 flex items-center justify-between text-xs font-mono ${
                    isValid
                      ? `bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} text-[#3D4852]`
                      : `bg-[#E0E5EC] ${TOKENS.shadows.inset} opacity-50 text-[#6B7280]`
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <span className={isValid ? 'font-bold text-[#6C63FF]' : 'line-through'}>
                      {formatRupees(cand.offer_amount)}
                    </span>
                    <span className="text-[11px]">
                      {cand.discount_pct}% discount | {cand.days_to_payment}d terms
                    </span>
                  </div>

                  <div className="flex items-center gap-4">
                    <span>EV: {formatRupees(cand.expected_value)}</span>
                    <span>Prob: {Math.round(cand.acceptance_probability * 100)}%</span>
                    {isValid ? (
                      <span className="text-[#38B2AC] font-bold uppercase text-[10px]">Valid</span>
                    ) : (
                      <span className="text-red-500 font-bold text-[10px] flex items-center gap-1">
                        ❌ rejected: below floor
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* AUDIT TRAIL TIMELINE GROOVE */}
        <div className="space-y-4 pt-4 border-t border-[#C5CEDC]/40">
          <h3 className="text-base font-bold font-display text-[#3D4852]">
            Compliance Audit Trail (SQLite)
          </h3>

          <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} space-y-4`}>
            {auditTrail?.events?.length > 0 ? (
              <div className="relative pl-6 border-l-2 border-[#6C63FF]/30 space-y-6">
                {auditTrail.events.map((evt, idx) => (
                  <div key={idx} className="relative group">
                    {/* Timeline Dot */}
                    <div className={`absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} flex items-center justify-center`}>
                      <div className="w-2 h-2 rounded-full bg-[#38B2AC]"></div>
                    </div>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs">
                      <span className="font-bold text-[#3D4852] font-display">
                        {evt.summary}
                      </span>
                      <span className="text-[10px] font-mono text-[#6B7280]">
                        {evt.timestamp?.substring(11, 16) || '14:00'} ({evt.actor})
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-[#6B7280] font-mono">
                {auditTrail?.timeline_summary || 'No audit trail entries recorded yet.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
