import React, { useEffect, useState } from 'react';
import { getOpportunities, getInvoices } from '../api';
import { TOKENS } from '../tokens';
import { AlertCircle, FileText, ChevronRight, Zap, Target } from 'lucide-react';

export default function OpportunitiesList({ onSelectInvoice }) {
  const [leaks, setLeaks] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'leaks' | 'invoices'

  useEffect(() => {
    async function loadData() {
      try {
        const [oppRes, invRes] = await Promise.all([
          getOpportunities(5),
          getInvoices('high_priority', 1000)
        ]);
        setLeaks(oppRes.opportunities || []);
        setInvoices(invRes.invoices || []);
      } catch (err) {
        console.error("Opportunities fetch error:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const formatRupees = (val) => {
    if (!val && val !== 0) return '₹0';
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)}Cr`;
    if (val >= 100000) return `₹${(val / 100000).toFixed(2)}L`;
    return `₹${val.toLocaleString('en-IN')}`;
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-[#C5CEDC] rounded w-1/4"></div>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} h-24`}></div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Header & Filter Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold font-display text-[#3D4852] tracking-tight">
            Recovery Opportunities
          </h1>
          <p className="text-sm text-[#6B7280] mt-1">
            Statistical revenue leaks & prioritized overdue invoices
          </p>
        </div>

        {/* Tab Selection */}
        <div className={`p-1.5 ${TOKENS.radius.button} ${TOKENS.shadows.insetSmall} bg-[#E0E5EC] flex gap-2 self-start`}>
          <button
            onClick={() => setActiveTab('all')}
            className={`px-4 py-2 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic ${
              activeTab === 'all'
                ? `bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                : 'text-[#6B7280] hover:text-[#3D4852]'
            } ${TOKENS.focus}`}
          >
            All ({leaks.length + invoices.length})
          </button>
          <button
            onClick={() => setActiveTab('leaks')}
            className={`px-4 py-2 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic ${
              activeTab === 'leaks'
                ? `bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                : 'text-[#6B7280] hover:text-[#3D4852]'
            } ${TOKENS.focus}`}
          >
            Leaks ({leaks.length})
          </button>
          <button
            onClick={() => setActiveTab('invoices')}
            className={`px-4 py-2 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic ${
              activeTab === 'invoices'
                ? `bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                : 'text-[#6B7280] hover:text-[#3D4852]'
            } ${TOKENS.focus}`}
          >
            Invoices ({invoices.length})
          </button>
        </div>
      </div>

      {/* SECTION 1: Statistical Revenue Leaks (LEAK-SCAN) */}
      {(activeTab === 'all' || activeTab === 'leaks') && leaks.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-lg font-bold font-display text-[#3D4852]">
            <Zap size={20} className="text-[#6C63FF]" />
            <h2>Detected Revenue Leaks (LEAK-SCAN)</h2>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {leaks.map((leak, idx) => {
              const confPct = Math.round((leak.confidence || 0.85) * 100);
              return (
                <div
                  key={idx}
                  onClick={() => onSelectInvoice(invoices[0]?.invoice_id || 'INV000001')}
                  className={`p-6 ${TOKENS.radius.button} bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} hover:-translate-y-1 transition-neumorphic cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 group`}
                >
                  <div className="flex items-start gap-4">
                    <div className={`p-3 rounded-2xl ${TOKENS.shadows.insetSmall} text-[#6C63FF] mt-1`}>
                      <AlertCircle size={22} />
                    </div>
                    <div>
                      <h3 className="text-base font-bold font-display text-[#3D4852] group-hover:text-[#6C63FF] transition-colors">
                        {leak.title || `Leak Segment #${idx + 1}`}
                      </h3>
                      <p className="text-xs text-[#6B7280] mt-1 line-clamp-1">
                        {leak.description || 'Statistically significant drop in conversion compared to merchant baseline.'}
                      </p>
                      <div className="flex items-center gap-4 mt-3 text-xs text-[#6B7280]">
                        <span>Baseline: {(leak.baseline_conversion * 100).toFixed(1)}%</span>
                        <span>Segment: {(leak.segment_conversion * 100).toFixed(1)}%</span>
                        <span className="text-red-500 font-semibold">Drop: -{(leak.drop_pct * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6 self-end md:self-center">
                    {/* Confidence Track / Pill */}
                    <div className="text-right">
                      <div className="text-xs font-semibold text-[#6B7280] mb-1">Confidence</div>
                      <div className="flex items-center gap-2">
                        <div className={`w-24 h-3 rounded-full ${TOKENS.shadows.insetSmall} bg-[#E0E5EC] overflow-hidden p-0.5`}>
                          <div
                            className="h-full bg-[#6C63FF] rounded-full transition-all duration-500"
                            style={{ width: `${confPct}%` }}
                          ></div>
                        </div>
                        <span className="text-xs font-bold text-[#3D4852] font-mono">{confPct}%</span>
                      </div>
                    </div>

                    <div className="text-right min-w-[120px]">
                      <div className="text-xs font-semibold text-[#6B7280]">Impact</div>
                      <div className="text-lg font-extrabold font-display text-[#3D4852]">
                        {formatRupees(leak.impact_rupees)}
                      </div>
                    </div>

                    <ChevronRight size={20} className="text-[#6B7280] group-hover:text-[#6C63FF] group-hover:translate-x-1 transition-all" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SECTION 2: Prioritized Overdue Invoices (RECOVERY-SCORE) */}
      {(activeTab === 'all' || activeTab === 'invoices') && invoices.length > 0 && (
        <div className="space-y-4 pt-4">
          <div className="flex items-center gap-2 text-lg font-bold font-display text-[#3D4852]">
            <Target size={20} className="text-[#6C63FF]" />
            <h2>High Priority Overdue Invoices (RECOVERY-SCORE)</h2>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {invoices.map((inv) => {
              const scorePct = Math.round((inv.recovery_score || 0.5) * 100);

              return (
                <div
                  key={inv.invoice_id}
                  onClick={() => onSelectInvoice(inv.invoice_id)}
                  className={`p-6 ${TOKENS.radius.button} bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} hover:-translate-y-1 transition-neumorphic cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 group`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`p-3 rounded-2xl ${TOKENS.shadows.insetSmall} text-[#6C63FF]`}>
                      <FileText size={22} />
                    </div>
                    <div>
                      <div className="flex items-center gap-3">
                        <h3 className="text-base font-bold font-display text-[#3D4852] group-hover:text-[#6C63FF] transition-colors">
                          {inv.invoice_id}
                        </h3>
                        <span className={`px-2.5 py-0.5 text-[10px] font-bold font-display uppercase ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-[#E0E5EC] text-[#6C63FF]`}>
                          {inv.tier?.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-xs text-[#6B7280] mt-1 font-medium">
                        Customer: <span className="text-[#3D4852]">{inv.customer_id}</span> | Overdue: <span className="text-red-500 font-semibold">{inv.days_overdue} days</span>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-6 self-end md:self-center">
                    {/* Recovery Score Track / Pill */}
                    <div className="text-right">
                      <div className="text-xs font-semibold text-[#6B7280] mb-1">Recovery Score</div>
                      <div className="flex items-center gap-2">
                        <div className={`w-28 h-3 rounded-full ${TOKENS.shadows.insetSmall} bg-[#E0E5EC] overflow-hidden p-0.5`}>
                          <div
                            className="h-full bg-[#6C63FF] rounded-full transition-all duration-500"
                            style={{ width: `${scorePct}%` }}
                          ></div>
                        </div>
                        <span className="text-xs font-bold text-[#3D4852] font-mono">{scorePct}%</span>
                      </div>
                    </div>

                    <div className="text-right min-w-[120px]">
                      <div className="text-xs font-semibold text-[#6B7280]">Invoice Amount</div>
                      <div className="text-lg font-extrabold font-display text-[#3D4852]">
                        {formatRupees(inv.amount)}
                      </div>
                    </div>

                    <ChevronRight size={20} className="text-[#6B7280] group-hover:text-[#6C63FF] group-hover:translate-x-1 transition-all" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
