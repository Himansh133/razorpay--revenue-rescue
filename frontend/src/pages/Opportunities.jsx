import React, { useEffect, useState } from 'react';
import { getOpportunities, getInvoices } from '../api';
import { TOKENS } from '../tokens';
import OpportunityCard from '../components/OpportunityCard';
import { Zap, Target } from 'lucide-react';

export default function Opportunities({ onSelectInvoice }) {
  const [leaks, setLeaks] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');

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
        {[1, 2, 3].map((i) => (
          <div key={i} className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} h-24`}></div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold font-display text-[#3D4852] tracking-tight">
            Recovery Opportunities
          </h1>
          <p className="text-sm text-[#6B7280] mt-1">
            Statistical revenue leaks & prioritized overdue invoices
          </p>
        </div>

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

      {(activeTab === 'all' || activeTab === 'leaks') && leaks.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-lg font-bold font-display text-[#3D4852]">
            <Zap size={20} className="text-[#6C63FF]" />
            <h2>Detected Revenue Leaks (LEAK-SCAN)</h2>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {leaks.map((leak, idx) => (
              <OpportunityCard
                key={idx}
                title={leak.title || `Leak Segment #${idx + 1}`}
                subtitle={leak.description || 'Statistically significant drop in conversion compared to merchant baseline.'}
                impact={formatRupees(leak.impact_rupees)}
                metricLabel="Confidence"
                metricValue={leak.confidence || 0.85}
                onClick={() => onSelectInvoice(invoices[0]?.invoice_id || 'INV000001')}
                icon={Zap}
              />
            ))}
          </div>
        </div>
      )}

      {(activeTab === 'all' || activeTab === 'invoices') && invoices.length > 0 && (
        <div className="space-y-4 pt-4">
          <div className="flex items-center gap-2 text-lg font-bold font-display text-[#3D4852]">
            <Target size={20} className="text-[#6C63FF]" />
            <h2>High Priority Overdue Invoices (RECOVERY-SCORE)</h2>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {invoices.map((inv) => (
              <OpportunityCard
                key={inv.invoice_id}
                title={`Invoice ${inv.invoice_id}`}
                subtitle={`Customer: ${inv.customer_id} | Overdue: ${inv.days_overdue} days`}
                impact={formatRupees(inv.amount)}
                metricLabel="Recovery Score"
                metricValue={inv.recovery_score || 0.5}
                onClick={() => onSelectInvoice(inv.invoice_id)}
                icon={Target}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
