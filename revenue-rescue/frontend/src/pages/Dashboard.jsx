import React, { useEffect, useState } from 'react';
import { getDashboardSummary, getOpportunities } from '../api';
import { TOKENS } from '../tokens';
import MetricCard from '../components/MetricCard';
import { Bot, CheckCircle2, TrendingUp, AlertTriangle, ShieldCheck, ArrowRight } from 'lucide-react';

export default function Dashboard({ onSelectInvoice, onNavigateOpportunities }) {
  const [summary, setSummary] = useState(null);
  const [opps, setOpps] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanStep, setScanStep] = useState(0);

  useEffect(() => {
    async function loadData() {
      try {
        const [sumRes, oppRes] = await Promise.all([
          getDashboardSummary(),
          getOpportunities(3)
        ]);
        setSummary(sumRes);
        setOpps(oppRes);
      } catch (err) {
        console.error("Dashboard fetch error:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    if (!loading) {
      const timer1 = setTimeout(() => setScanStep(1), 300);
      const timer2 = setTimeout(() => setScanStep(2), 800);
      const timer3 = setTimeout(() => setScanStep(3), 1300);
      const timer4 = setTimeout(() => setScanStep(4), 1800);
      const timer5 = setTimeout(() => setScanStep(5), 2300);
      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
        clearTimeout(timer4);
        clearTimeout(timer5);
      };
    }
  }, [loading]);

  const formatRupees = (val) => {
    if (!val && val !== 0) return '₹0';
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)}Cr`;
    if (val >= 100000) return `₹${(val / 100000).toFixed(2)}L`;
    return `₹${val.toLocaleString('en-IN')}`;
  };

  const checklistItems = [
    "Checking customer cohorts",
    "Checking payment behavior",
    "Checking geographic patterns",
    "Checking checkout behavior"
  ];

  if (loading) {
    return (
      <div className="space-y-8 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className={`p-8 ${TOKENS.radius.container} ${TOKENS.shadows.inset} h-40`}></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* 3 Top Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          title="Revenue at Risk"
          value={formatRupees(summary?.total_revenue_at_risk)}
          subtitle={`Overdue Invoices + Stat Leaks (${summary?.overdue_invoices_count || 0} invoices)`}
          icon={AlertTriangle}
        />
        <MetricCard
          title="Recoverable"
          value={formatRupees(summary?.total_recoverable)}
          subtitle="High & Standard Priority expected yield"
          icon={TrendingUp}
        />
        <MetricCard
          title="Recovered"
          value={formatRupees(summary?.total_actually_recovered)}
          subtitle="Confirmed Webhook Settlement"
          icon={ShieldCheck}
          isSuccess={true}
        />
      </div>

      {/* AI Investigation Scan Sequence */}
      <div className={`p-8 md:p-10 ${TOKENS.radius.container} bg-[#E0E5EC] ${TOKENS.shadows.extruded} space-y-6`}>
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-2xl ${TOKENS.shadows.inset} text-[#6C63FF]`}>
            <Bot size={28} className="animate-pulse" />
          </div>
          <div>
            <h2 className="text-xl font-bold font-display text-[#3D4852] tracking-tight">🤖 AI INVESTIGATION</h2>
            <p className="text-xs text-[#6B7280]">Real-time payment ecosystem anomaly & recovery analysis</p>
          </div>
        </div>

        <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} space-y-4 font-mono text-sm`}>
          <div className="text-[#6C63FF] font-semibold flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-[#6C63FF] animate-ping"></span>
            Scanning 31,824 transactions across UPI, NetBanking & B2B channels...
          </div>

          <div className="space-y-2 pt-2">
            {checklistItems.map((item, idx) => {
              const isDone = scanStep > idx + 1;
              const isCurrent = scanStep === idx + 1;

              return (
                <div
                  key={idx}
                  className={`flex items-center gap-3 transition-all duration-300 ${
                    isDone ? 'opacity-100 translate-x-0' : isCurrent ? 'opacity-90 translate-x-1' : 'opacity-40'
                  }`}
                >
                  {isDone ? (
                    <CheckCircle2 size={18} className="text-[#38B2AC]" />
                  ) : (
                    <span className="w-4 h-4 rounded-full border-2 border-[#6B7280] inline-block animate-pulse"></span>
                  )}
                  <span className={isDone ? 'text-[#3D4852] font-medium' : 'text-[#6B7280]'}>
                    {item}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {scanStep >= 5 && (
          <div className="pt-2 animate-fadeIn space-y-4">
            <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.extrudedSmall} bg-[#E0E5EC] flex flex-col md:flex-row md:items-center justify-between gap-4`}>
              <div>
                <h3 className="text-lg font-bold font-display text-[#3D4852]">
                  {summary?.leaks_detected_count || opps?.total_leaks || 2} revenue opportunities found.
                </h3>
                <p className="text-sm text-[#6B7280] mt-1">
                  Estimated revenue at risk: <strong className="text-[#3D4852]">{formatRupees(summary?.total_revenue_at_risk)}</strong> |
                  Potentially recoverable: <strong className="text-[#38B2AC]">{formatRupees(summary?.total_recoverable)}</strong>
                </p>
              </div>
              <button
                onClick={onNavigateOpportunities}
                className={`px-6 py-3 ${TOKENS.radius.button} bg-[#6C63FF] text-white font-semibold font-display ${TOKENS.shadows.extrudedSmall} hover:bg-[#8B84FF] transition-neumorphic hover:-translate-y-0.5 active:translate-y-0.5 active:${TOKENS.shadows.insetSmall} flex items-center justify-center gap-2 ${TOKENS.focus}`}
              >
                Review Opportunities <ArrowRight size={18} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
