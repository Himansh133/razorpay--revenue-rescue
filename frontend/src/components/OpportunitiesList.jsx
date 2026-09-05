import React, { useEffect, useState, useMemo } from 'react';
import { getOpportunities, getInvoices } from '../api';
import { TOKENS } from '../tokens';
import { AlertCircle, FileText, ChevronRight, Zap, Target, Filter, ArrowUpDown } from 'lucide-react';

export default function OpportunitiesList({ onSelectInvoice }) {
  const [leaks, setLeaks] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'leaks' | 'invoices'
  const [tierFilter, setTierFilter] = useState(''); // Default: '' = All Invoices (no tier parameter)
  const [sortBy, setSortBy] = useState('score_desc');

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [oppRes, invRes] = await Promise.all([
          getOpportunities(5),
          getInvoices(tierFilter || null, 0)
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
  }, [tierFilter]);

  const sortedInvoices = useMemo(() => {
    const list = [...invoices];
    switch (sortBy) {
      case 'score_asc':
        return list.sort((a, b) => (a.recovery_score || 0) - (b.recovery_score || 0));
      case 'name_asc':
        return list.sort((a, b) => (a.customer_id || '').localeCompare(b.customer_id || ''));
      case 'name_desc':
        return list.sort((a, b) => (b.customer_id || '').localeCompare(a.customer_id || ''));
      case 'amount_desc':
        return list.sort((a, b) => (b.amount || 0) - (a.amount || 0));
      case 'amount_asc':
        return list.sort((a, b) => (a.amount || 0) - (b.amount || 0));
      case 'score_desc':
      default:
        return list.sort((a, b) => (b.recovery_score || 0) - (a.recovery_score || 0));
    }
  }, [invoices, sortBy]);

  const formatRupees = (val) => {
    if (!val && val !== 0) return '₹0';
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)}Cr`;
    if (val >= 100000) return `₹${(val / 100000).toFixed(2)}L`;
    return `₹${val.toLocaleString('en-IN')}`;
  };

  const getHeadingText = () => {
    switch (tierFilter) {
      case 'high_priority':
        return 'High Priority Overdue Invoices';
      case 'standard':
        return 'Standard Priority Overdue Invoices';
      case 'low_priority':
        return 'Low Priority Overdue Invoices';
      default:
        return 'All Recovery Opportunities';
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-neu-surface rounded w-1/4"></div>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} h-24`}></div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header & Filter Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold font-display text-neu-primary tracking-tight">
            Recovery Opportunities
          </h1>
          <p className="text-sm text-neu-secondary mt-1">
            Statistical revenue leaks & overdue invoices for recovery
          </p>
        </div>

        {/* Top Tab Selection */}
        <div className={`p-1.5 ${TOKENS.radius.button} ${TOKENS.shadows.insetSmall} bg-neu-surface flex gap-2 self-start border border-neu`}>
          <button
            onClick={() => setActiveTab('all')}
            className={`px-4 py-2 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic ${
              activeTab === 'all'
                ? `bg-neu-surface ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                : 'text-neu-secondary hover:text-neu-primary'
            } ${TOKENS.focus}`}
          >
            All ({leaks.length + sortedInvoices.length})
          </button>
          <button
            onClick={() => setActiveTab('leaks')}
            className={`px-4 py-2 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic ${
              activeTab === 'leaks'
                ? `bg-neu-surface ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                : 'text-neu-secondary hover:text-neu-primary'
            } ${TOKENS.focus}`}
          >
            Leaks ({leaks.length})
          </button>
          <button
            onClick={() => setActiveTab('invoices')}
            className={`px-4 py-2 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic ${
              activeTab === 'invoices'
                ? `bg-neu-surface ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                : 'text-neu-secondary hover:text-neu-primary'
            } ${TOKENS.focus}`}
          >
            Invoices ({sortedInvoices.length})
          </button>
        </div>
      </div>

      {/* Filter & Sort Controls Bar */}
      <div className={`p-4 ${TOKENS.radius.button} ${TOKENS.shadows.extrudedSmall} bg-neu-surface flex flex-wrap items-center justify-between gap-4 border border-neu`}>
        <div className="flex flex-wrap items-center gap-4">
          {/* Tier Filter */}
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-[#6C63FF]" />
            <label htmlFor="tier-filter-select" className="text-xs font-bold font-display text-neu-primary">
              Filter:
            </label>
            <select
              id="tier-filter-select"
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              className={`px-3 py-1.5 text-xs font-medium font-display ${TOKENS.radius.inner} bg-neu-surface text-neu-primary ${TOKENS.shadows.insetSmall} border border-neu focus:outline-none cursor-pointer`}
            >
              <option value="">All Invoices</option>
              <option value="high_priority">High Priority</option>
              <option value="standard">Standard</option>
              <option value="low_priority">Low Priority</option>
            </select>
          </div>

          {/* Sort By */}
          <div className="flex items-center gap-2">
            <ArrowUpDown size={16} className="text-[#6C63FF]" />
            <label htmlFor="sort-by-select" className="text-xs font-bold font-display text-neu-primary">
              Sort By:
            </label>
            <select
              id="sort-by-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className={`px-3 py-1.5 text-xs font-medium font-display ${TOKENS.radius.inner} bg-neu-surface text-neu-primary ${TOKENS.shadows.insetSmall} border border-neu focus:outline-none cursor-pointer`}
            >
              <option value="score_desc">Recovery Score: High → Low</option>
              <option value="score_asc">Recovery Score: Low → High</option>
              <option value="amount_desc">Invoice Amount: High → Low</option>
              <option value="amount_asc">Invoice Amount: Low → High</option>
              <option value="name_asc">Customer Name: A → Z</option>
              <option value="name_desc">Customer Name: Z → A</option>
            </select>
          </div>
        </div>

        {/* Count Indicator */}
        <div className="text-xs font-bold font-display text-neu-secondary">
          Showing <span className="text-[#6C63FF] font-extrabold">{sortedInvoices.length}</span> invoices
        </div>
      </div>

      {/* SECTION 1: Statistical Revenue Leaks (LEAK-SCAN) */}
      {(activeTab === 'all' || activeTab === 'leaks') && leaks.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-lg font-bold font-display text-neu-primary">
            <Zap size={20} className="text-[#6C63FF]" />
            <h2>Detected Revenue Leaks (LEAK-SCAN)</h2>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {leaks.map((leak, idx) => {
              const confPct = Math.round((leak.confidence || 0.85) * 100);
              return (
                <div
                  key={idx}
                  onClick={() => onSelectInvoice(sortedInvoices[0]?.invoice_id || 'INV001184')}
                  className={`p-6 ${TOKENS.radius.button} bg-neu-surface ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} hover:-translate-y-1 transition-neumorphic cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 group border border-neu`}
                >
                  <div className="flex items-start gap-4">
                    <div className={`p-3 rounded-2xl ${TOKENS.shadows.insetSmall} text-[#6C63FF] mt-1`}>
                      <AlertCircle size={22} />
                    </div>
                    <div>
                      <h3 className="text-base font-bold font-display text-neu-primary group-hover:text-[#6C63FF] transition-colors">
                        {leak.title || `Leak Segment #${idx + 1}`}
                      </h3>
                      <p className="text-xs text-neu-secondary mt-1 line-clamp-1">
                        {leak.description || 'Statistically significant drop in conversion compared to merchant baseline.'}
                      </p>
                      <div className="flex items-center gap-4 mt-3 text-xs text-neu-secondary">
                        <span>Baseline: {(leak.baseline_conversion * 100).toFixed(1)}%</span>
                        <span>Segment: {(leak.segment_conversion * 100).toFixed(1)}%</span>
                        <span className="text-red-500 font-semibold">Drop: -{(leak.drop_pct * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6 self-end md:self-center">
                    {/* Confidence Track / Pill */}
                    <div className="text-right">
                      <div className="text-xs font-semibold text-neu-secondary mb-1">Confidence</div>
                      <div className="flex items-center gap-2">
                        <div className={`w-24 h-3 rounded-full ${TOKENS.shadows.insetSmall} bg-neu-base overflow-hidden p-0.5`}>
                          <div
                            className="h-full bg-[#6C63FF] rounded-full transition-all duration-500"
                            style={{ width: `${confPct}%` }}
                          ></div>
                        </div>
                        <span className="text-xs font-bold text-neu-primary font-mono">{confPct}%</span>
                      </div>
                    </div>

                    <div className="text-right min-w-[120px]">
                      <div className="text-xs font-semibold text-neu-secondary">Impact</div>
                      <div className="text-lg font-extrabold font-display text-neu-primary">
                        {formatRupees(leak.impact_rupees)}
                      </div>
                    </div>

                    <ChevronRight size={20} className="text-neu-secondary group-hover:text-[#6C63FF] group-hover:translate-x-1 transition-all" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SECTION 2: Overdue Invoices (RECOVERY-SCORE) */}
      {(activeTab === 'all' || activeTab === 'invoices') && (
        <div className="space-y-4 pt-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-lg font-bold font-display text-neu-primary">
              <Target size={20} className="text-[#6C63FF]" />
              <h2>{getHeadingText()} (RECOVERY-SCORE)</h2>
            </div>
            <span className="text-xs font-bold text-neu-secondary">
              {sortedInvoices.length} invoices found
            </span>
          </div>

          {sortedInvoices.length === 0 ? (
            <div className={`p-8 text-center ${TOKENS.radius.button} ${TOKENS.shadows.inset} bg-neu-surface text-neu-secondary border border-neu`}>
              No overdue invoices match the selected filter criteria.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {sortedInvoices.map((inv) => {
                const scorePct = Math.round((inv.recovery_score || 0.5) * 100);

                return (
                  <div
                    key={inv.invoice_id}
                    onClick={() => onSelectInvoice(inv.invoice_id)}
                    className={`p-6 ${TOKENS.radius.button} bg-neu-surface ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} hover:-translate-y-1 transition-neumorphic cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 group border border-neu`}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`p-3 rounded-2xl ${TOKENS.shadows.insetSmall} text-[#6C63FF]`}>
                        <FileText size={22} />
                      </div>
                      <div>
                        <div className="flex items-center gap-3">
                          <h3 className="text-base font-bold font-display text-neu-primary group-hover:text-[#6C63FF] transition-colors">
                            {inv.invoice_id}
                          </h3>
                          <span className={`px-2.5 py-0.5 text-[10px] font-bold font-display uppercase ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-neu-surface text-[#6C63FF]`}>
                            {inv.tier?.replace('_', ' ')}
                          </span>
                        </div>
                        <p className="text-xs text-neu-secondary mt-1 font-medium">
                          Customer: <span className="text-neu-primary">{inv.customer_id}</span> | Overdue: <span className="text-red-500 font-semibold">{inv.days_overdue} days</span>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-6 self-end md:self-center">
                      {/* Recovery Score Track / Pill */}
                      <div className="text-right">
                        <div className="text-xs font-semibold text-neu-secondary mb-1">Recovery Score</div>
                        <div className="flex items-center gap-2">
                          <div className={`w-28 h-3 rounded-full ${TOKENS.shadows.insetSmall} bg-neu-base overflow-hidden p-0.5`}>
                            <div
                              className="h-full bg-[#6C63FF] rounded-full transition-all duration-500"
                              style={{ width: `${scorePct}%` }}
                            ></div>
                          </div>
                          <span className="text-xs font-bold text-neu-primary font-mono">{scorePct}%</span>
                        </div>
                      </div>

                      <div className="text-right min-w-[120px]">
                        <div className="text-xs font-semibold text-neu-secondary">Invoice Amount</div>
                        <div className="text-lg font-extrabold font-display text-neu-primary">
                          {formatRupees(inv.amount)}
                        </div>
                      </div>

                      <ChevronRight size={20} className="text-neu-secondary group-hover:text-[#6C63FF] group-hover:translate-x-1 transition-all" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
