import React, { useEffect, useState } from 'react';
import {
  getInvoiceDetail,
  recommendRecoveryOffer,
  executeRecoveryOffer,
  executeCustomerOutreach,
  getInvoiceAuditTrail,
  triggerMockWebhook
} from '../api';
import { TOKENS } from '../tokens';
import OfferTable from '../components/OfferTable';
import Timeline from '../components/Timeline';
import GeminiAgentPanel from '../components/GeminiAgentPanel';
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  Send,
  Zap,
  Lock,
  ListOrdered,
  AlertTriangle,
  Mail,
  MessageSquare,
  ShieldCheck
} from 'lucide-react';

export default function RecoveryCase({ invoiceId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [merchantFloor, setMerchantFloor] = useState(0);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);
  const [executionError, setExecutionError] = useState(null);

  // Customer Outreach State
  const [outreachSending, setOutreachSending] = useState(false);
  const [outreachResult, setOutreachResult] = useState(null);
  const [outreachError, setOutreachError] = useState(null);
  const [selectedChannels, setSelectedChannels] = useState(['email', 'sms']);

  const [auditTrail, setAuditTrail] = useState(null);
  const [webhookSimulating, setWebhookSimulating] = useState(false);

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

  async function fetchRecommendation(invId, floorVal) {
    try {
      const rec = await recommendRecoveryOffer(invId, floorVal);
      setRecommendation(rec);
    } catch (err) {
      console.error("Error fetching offer recommendation:", err);
    }
  }

  async function fetchAuditTrail(invId) {
    try {
      const trailData = await getInvoiceAuditTrail(invId);
      setAuditTrail(trailData);
    } catch (err) {
      console.error("Error fetching audit trail:", err);
    }
  }

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
      } catch (e) {}
    }, 3000);
    return () => clearInterval(interval);
  }, [invoiceId]);

  const handleFloorChange = (e) => {
    setMerchantFloor(Number(e.target.value));
  };

  const handleFloorCommit = () => {
    if (detail?.invoice_id) {
      fetchRecommendation(detail.invoice_id, merchantFloor);
    }
  };

  const handleExecute = async () => {
    if (!recommendation?.best_offer) return;
    setExecutionError(null);
    setExecutionResult(null);
    try {
      setExecuting(true);
      const offerAmt = recommendation.best_offer.offer_amount;
      const res = await executeRecoveryOffer(invoiceId, offerAmt);
      if (res.status === 'success' && res.payment_link_url) {
        setExecutionResult(res);
      } else {
        setExecutionError(res.detail || res.error || 'Failed to create payment link');
      }
      await fetchAuditTrail(invoiceId);
    } catch (err) {
      console.error("Execution error:", err);
      setExecutionError(err.message || 'Razorpay API Connection Error');
    } finally {
      setExecuting(false);
    }
  };

  const handleSendOutreach = async (overrideChannels = null) => {
    const channelsToUse = overrideChannels || selectedChannels;
    if (!channelsToUse || channelsToUse.length === 0) return;
    setOutreachError(null);
    setOutreachResult(null);
    try {
      setOutreachSending(true);
      const offerAmt = recommendation?.best_offer?.offer_amount;
      const res = await executeCustomerOutreach(invoiceId, channelsToUse, offerAmt, merchantFloor);
      setOutreachResult(res);
      if (res.payment_link_url) {
        setExecutionResult({
          payment_link_id: res.payment_link_id,
          payment_link_url: res.payment_link_url
        });
      }
      await fetchAuditTrail(invoiceId);
    } catch (err) {
      console.error("Outreach error:", err);
      setOutreachError(err.message || 'Customer Outreach Service Error');
    } finally {
      setOutreachSending(false);
    }
  };

  const toggleChannel = (channel) => {
    setSelectedChannels(prev => {
      if (prev.includes(channel)) {
        if (prev.length === 1) return prev; // Keep at least one selected
        return prev.filter(c => c !== channel);
      } else {
        return [...prev, channel];
      }
    });
  };

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
        <div className="h-8 bg-neu-surface rounded w-1/4"></div>
        <div className={`p-10 ${TOKENS.radius.container} ${TOKENS.shadows.inset} h-96`}></div>
      </div>
    );
  }

  if (!loading && !detail) {
    return (
      <div className="space-y-6">
        <button
          onClick={onBack}
          className={`px-5 py-2.5 ${TOKENS.radius.button} bg-neu-surface ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} text-neu-primary font-semibold text-sm font-display flex items-center gap-2 transition-neumorphic ${TOKENS.focus}`}
        >
          <ArrowLeft size={18} /> Back to Opportunities
        </button>
        <div className={`p-10 ${TOKENS.radius.container} ${TOKENS.shadows.inset} text-center space-y-4`}>
          <div className="text-lg font-bold text-red-500 font-display">
            Unable to load recovery case details for invoice {invoiceId || 'N/A'}
          </div>
          <p className="text-xs text-neu-secondary">
            Please verify that the backend service is online and the invoice exists.
          </p>
        </div>
      </div>
    );
  }

  const isRecovered = detail?.status === 'recovered';
  const bestOffer = recommendation?.best_offer;
  const allCandidates = recommendation?.all_candidates || [];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className={`px-5 py-2.5 ${TOKENS.radius.button} bg-neu-surface ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} text-neu-primary font-semibold text-sm font-display flex items-center gap-2 transition-neumorphic ${TOKENS.focus}`}
        >
          <ArrowLeft size={18} /> Back to Opportunities
        </button>

        <div className="flex items-center gap-3">
          {isRecovered ? (
            <div className={`px-4 py-2 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-neu-surface text-[#38B2AC] font-bold text-xs font-display flex items-center gap-2`}>
              <CheckCircle2 size={16} /> ₹{detail?.actual_recovered?.toLocaleString('en-IN') || bestOffer?.offer_amount?.toLocaleString('en-IN') || '0'} RECOVERED
            </div>
          ) : (
            <div className={`px-4 py-2 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-neu-surface text-[#6C63FF] font-bold text-xs font-display flex items-center gap-2 animate-pulse`}>
              <Clock size={16} /> AWAITING PAYMENT
            </div>
          )}
        </div>
      </div>

      <div className={`p-8 md:p-10 ${TOKENS.radius.container} bg-neu-surface ${TOKENS.shadows.extruded} space-y-10 border border-neu transition-neumorphic`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-neu pb-8">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-extrabold font-display text-neu-primary tracking-tight">
                {detail?.customer_profile?.customer_id || detail?.customer_id || 'Customer'}
              </h1>
              <span className={`px-3 py-1 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} text-xs font-bold font-display text-[#6C63FF]`}>
                Invoice: {detail?.invoice_id}
              </span>
            </div>
            <p className="text-xs text-neu-secondary mt-1 font-medium">
              Risk Tier: <strong className="uppercase text-neu-primary">{detail?.recovery_score_breakdown?.tier || 'standard'}</strong>
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4 text-center">
            <div className={`p-4 ${TOKENS.radius.inner} ${TOKENS.shadows.insetSmall}`}>
              <div className="text-[10px] uppercase font-bold text-neu-secondary font-display">Invoice</div>
              <div className="text-base font-extrabold text-neu-primary font-display mt-0.5">{formatRupees(detail?.amount || 0)}</div>
            </div>
            <div className={`p-4 ${TOKENS.radius.inner} ${TOKENS.shadows.insetSmall}`}>
              <div className="text-[10px] uppercase font-bold text-neu-secondary font-display">Overdue</div>
              <div className="text-base font-extrabold text-red-500 font-display mt-0.5">{detail?.days_overdue || 0} Days</div>
            </div>
            <div className={`p-4 ${TOKENS.radius.inner} ${TOKENS.shadows.insetSmall}`}>
              <div className="text-[10px] uppercase font-bold text-neu-secondary font-display">Customer LTV</div>
              <div className="text-base font-extrabold text-neu-primary font-display mt-0.5">{formatRupees(detail?.customer_profile?.ltv || 250000)}</div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} space-y-4`}>
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-neu-secondary font-display flex items-center gap-2">
                <Lock size={16} className="text-[#6C63FF]" /> Merchant Floor Guardrail
              </label>
              <span className="text-sm font-extrabold font-mono text-[#6C63FF]">
                {formatRupees(merchantFloor)}
              </span>
            </div>
            <input
              type="range"
              min={detail?.amount ? Math.round(detail.amount * 0.5) : 0}
              max={detail?.amount || 100000}
              step={1000}
              value={merchantFloor || 0}
              onChange={handleFloorChange}
              onMouseUp={handleFloorCommit}
              onTouchEnd={handleFloorCommit}
              className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-neu-base accent-[#6C63FF]"
            />
          </div>

          <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.extrudedSmall} bg-neu-surface flex flex-col justify-between`}>
            <div className="flex justify-between items-start">
              <span className="text-xs font-bold uppercase tracking-wider text-neu-secondary font-display">
                ML Predicted Acceptance
              </span>
              <span className={`px-2.5 py-1 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} text-xs font-bold text-[#38B2AC] font-mono`}>
                {bestOffer ? `${Math.round(bestOffer.acceptance_probability * 100)}%` : '0%'}
              </span>
            </div>
            <div className="mt-4">
              <div className="text-xs font-medium text-neu-secondary">Expected Value Yield</div>
              <div className="text-3xl font-extrabold font-display text-neu-primary mt-1">
                {bestOffer ? formatRupees(bestOffer.expected_value) : '₹0'}
              </div>
            </div>
          </div>
        </div>

        <div className={`p-10 ${TOKENS.radius.container} ${TOKENS.shadows.insetDeep} text-center space-y-4 bg-neu-surface`}>
          <span className="text-xs font-bold uppercase tracking-widest text-neu-secondary font-display block">
            AI-Optimized Recovery Offer
          </span>
          <div className="text-5xl md:text-7xl font-extrabold font-display text-[#6C63FF] tracking-tight">
            {bestOffer ? formatRupees(bestOffer.offer_amount) : 'NO VALID OFFER'}
          </div>
          <p className="text-sm font-semibold text-neu-secondary">
            {bestOffer ? `${bestOffer.discount_pct}% Discount | ${bestOffer.days_to_payment}-Day Payment Terms` : 'All candidate offers fall below merchant floor.'}
          </p>

          {/* Autonomous Outreach Action Area */}
          <div className="pt-4 space-y-6">
            <div className="flex justify-center items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-neu-secondary font-display">Outreach Channels:</span>
              <button
                type="button"
                onClick={() => toggleChannel('email')}
                className={`px-3 py-1.5 ${TOKENS.radius.button} text-xs font-bold font-display flex items-center gap-1.5 transition-neumorphic ${
                  selectedChannels.includes('email')
                    ? `bg-[#6C63FF] text-white ${TOKENS.shadows.extrudedSmall}`
                    : `bg-neu-surface text-neu-secondary ${TOKENS.shadows.insetSmall}`
                }`}
              >
                <Mail size={14} /> Resend Email
              </button>
              <button
                type="button"
                onClick={() => toggleChannel('sms')}
                className={`px-3 py-1.5 ${TOKENS.radius.button} text-xs font-bold font-display flex items-center gap-1.5 transition-neumorphic ${
                  selectedChannels.includes('sms')
                    ? `bg-[#6C63FF] text-white ${TOKENS.shadows.extrudedSmall}`
                    : `bg-neu-surface text-neu-secondary ${TOKENS.shadows.insetSmall}`
                }`}
              >
                <MessageSquare size={14} /> Twilio SMS
              </button>
            </div>

            <div className="flex flex-col sm:flex-row justify-center items-center gap-4">
              <button
                onClick={() => handleSendOutreach()}
                disabled={outreachSending || !bestOffer}
                className={`w-full sm:w-auto px-8 py-4 ${TOKENS.radius.button} bg-[#6C63FF] text-white font-bold text-base font-display ${TOKENS.shadows.extruded} hover:bg-[#8B84FF] transition-neumorphic hover:-translate-y-1 active:translate-y-0.5 flex items-center justify-center gap-3 disabled:opacity-50 ${TOKENS.focus}`}
              >
                <Send size={20} /> {outreachSending ? 'DISPATCHING...' : 'DISPATCH OUTREACH (EMAIL + SMS)'}
              </button>

              <button
                onClick={handleExecute}
                disabled={executing || !bestOffer}
                className={`w-full sm:w-auto px-6 py-4 ${TOKENS.radius.button} bg-neu-surface text-neu-primary font-bold text-sm font-display ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} flex items-center justify-center gap-2 disabled:opacity-50 ${TOKENS.focus}`}
              >
                <ShieldCheck size={18} /> {executing ? 'CREATING LINK...' : 'CREATE LINK ONLY'}
              </button>

              <button
                onClick={handleSimulateWebhook}
                disabled={webhookSimulating}
                className={`w-full sm:w-auto px-6 py-4 ${TOKENS.radius.button} bg-neu-surface text-[#38B2AC] font-bold text-sm font-display ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} flex items-center justify-center gap-2 ${TOKENS.focus}`}
              >
                <Zap size={18} /> {webhookSimulating ? 'Processing...' : 'Development Simulation'}
              </button>
            </div>
          </div>

          {/* Outreach Status Diagnostics */}
          {outreachResult && (
            <div className={`mt-6 p-4 ${TOKENS.radius.button} ${TOKENS.shadows.inset} bg-neu-surface text-left space-y-3 animate-fadeIn`}>
              <div className="text-xs font-bold text-[#6C63FF] font-display flex items-center gap-2">
                <CheckCircle2 size={16} /> Autonomous Outreach Execution Summary:
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {Object.entries(outreachResult.channels || {}).map(([ch, details]) => (
                  <div key={ch} className={`p-3 ${TOKENS.radius.inner} ${TOKENS.shadows.insetSmall} space-y-1`}>
                    <div className="flex justify-between items-center">
                      <span className="uppercase font-bold text-neu-primary flex items-center gap-1">
                        {ch === 'email' ? <Mail size={12} /> : <MessageSquare size={12} />} {ch}
                      </span>
                      <span className={`px-2 py-0.5 ${TOKENS.radius.pill} text-[10px] font-bold uppercase ${
                        details.status === 'sent' ? 'bg-emerald-500/10 text-emerald-500' :
                        details.status === 'already_sent' ? 'bg-blue-500/10 text-blue-500' :
                        details.status === 'unavailable' ? 'bg-amber-500/10 text-amber-500' : 'bg-red-500/10 text-red-500'
                      }`}>
                        {details.status}
                      </span>
                    </div>
                    {details.recipient && (
                      <div className="text-[11px] text-neu-secondary truncate">To: {details.recipient}</div>
                    )}
                    {details.error && (
                      <div className="text-[10px] text-amber-400 truncate">{details.error}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {outreachError && (
            <div className={`mt-6 p-4 ${TOKENS.radius.button} ${TOKENS.shadows.inset} bg-red-950/20 text-left space-y-2 animate-fadeIn border border-red-500/30`}>
              <div className="text-xs font-bold text-red-500 font-display flex items-center gap-2">
                <AlertTriangle size={16} /> Outreach Delivery Error:
              </div>
              <div className="font-mono text-xs text-red-400">
                {outreachError}
              </div>
            </div>
          )}

          {executionResult && executionResult.payment_link_url && (
            <div className={`mt-6 p-4 ${TOKENS.radius.button} ${TOKENS.shadows.inset} bg-neu-surface text-left space-y-2 animate-fadeIn`}>
              <div className="text-xs font-bold text-[#6C63FF] font-display flex items-center gap-2">
                <CheckCircle2 size={16} /> Razorpay Test Payment Link Active:
              </div>
              <div className="flex items-center justify-between gap-4 font-mono text-xs text-neu-primary">
                <span className="truncate">{executionResult.payment_link_url}</span>
                <a href={executionResult.payment_link_url} target="_blank" rel="noreferrer" className="text-[#6C63FF] hover:underline font-bold flex items-center gap-1 shrink-0">
                  Open Link <ExternalLink size={14} />
                </a>
              </div>
            </div>
          )}

          {executionError && (
            <div className={`mt-6 p-4 ${TOKENS.radius.button} ${TOKENS.shadows.inset} bg-red-950/20 text-left space-y-2 animate-fadeIn border border-red-500/30`}>
              <div className="text-xs font-bold text-red-500 font-display flex items-center gap-2">
                <AlertTriangle size={16} /> Razorpay Payment Link Error:
              </div>
              <div className="font-mono text-xs text-red-400">
                {executionError}
              </div>
            </div>
          )}
        </div>

        {/* Gemini Revenue Rescue Agent Panel */}
        <GeminiAgentPanel
          invoiceId={detail?.invoice_id}
          customerName={detail?.customer_profile?.customer_id}
          onRefresh={() => fetchAuditTrail(invoiceId)}
        />

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-base font-bold font-display text-neu-primary">
              <ListOrdered size={20} className="text-[#6C63FF]" />
              <h3>Candidate Offer Matrix & Floor Filter</h3>
            </div>
          </div>
          <OfferTable candidates={allCandidates} formatRupees={formatRupees} />
        </div>

        <div className="space-y-4 pt-4 border-t border-neu">
          <h3 className="text-base font-bold font-display text-neu-primary">
            Compliance Audit Trail (SQLite)
          </h3>
          <Timeline auditTrail={auditTrail} />
        </div>
      </div>
    </div>
  );
}
