import React, { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import OpportunitiesList from './components/OpportunitiesList';
import RecoveryCase from './components/RecoveryCase';
import { getHealth } from './api';
import { TOKENS } from './tokens';
import { LayoutDashboard, Target, FileSearch, Shield, CheckCircle2, AlertCircle } from 'lucide-react';

export default function App() {
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'opportunities' | 'recovery_case'
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('INV000001');
  const [apiConnected, setApiConnected] = useState(false);

  useEffect(() => {
    async function checkBackend() {
      try {
        const res = await getHealth();
        if (res.status === 'ok') {
          setApiConnected(true);
        }
      } catch (err) {
        console.error("Backend health check failed:", err);
        setApiConnected(false);
      }
    }
    checkBackend();
  }, []);

  const handleSelectInvoice = (invId) => {
    setSelectedInvoiceId(invId);
    setCurrentView('recovery_case');
  };

  return (
    <div className="min-h-screen bg-[#E0E5EC] text-[#3D4852] font-sans antialiased p-4 md:p-8 lg:p-12 selection:bg-[#6C63FF] selection:text-white">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* TOP HEADER NAVIGATION */}
        <header className={`p-6 md:p-8 ${TOKENS.radius.container} bg-[#E0E5EC] ${TOKENS.shadows.extruded} flex flex-col md:flex-row md:items-center justify-between gap-6`}>
          <div className="flex items-center gap-4">
            <div className={`p-4 rounded-2xl ${TOKENS.shadows.inset} text-[#6C63FF]`}>
              <Shield size={32} />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl md:text-2xl font-extrabold font-display text-[#3D4852] tracking-tight">
                  REVENUE RECOVERY ENGINE
                </h1>
                <span className={`px-3 py-1 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} text-[10px] font-extrabold font-display ${apiConnected ? 'text-[#38B2AC]' : 'text-red-500'} flex items-center gap-1.5`}>
                  {apiConnected ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
                  {apiConnected ? 'API ONLINE' : 'API DISCONNECTED'}
                </span>
              </div>
              <p className="text-xs text-[#6B7280] font-medium mt-0.5">
                Explainable ML Offer Negotiation & Automated Financial Recovery
              </p>
            </div>
          </div>

          {/* Navigation Buttons */}
          <nav className={`p-1.5 ${TOKENS.radius.button} ${TOKENS.shadows.insetSmall} bg-[#E0E5EC] flex gap-2 self-start md:self-auto`}>
            <button
              onClick={() => setCurrentView('dashboard')}
              className={`px-5 py-2.5 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic flex items-center gap-2 ${
                currentView === 'dashboard'
                  ? `bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                  : 'text-[#6B7280] hover:text-[#3D4852]'
              } ${TOKENS.focus}`}
            >
              <LayoutDashboard size={16} /> Dashboard
            </button>

            <button
              onClick={() => setCurrentView('opportunities')}
              className={`px-5 py-2.5 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic flex items-center gap-2 ${
                currentView === 'opportunities'
                  ? `bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                  : 'text-[#6B7280] hover:text-[#3D4852]'
              } ${TOKENS.focus}`}
            >
              <Target size={16} /> Opportunities
            </button>

            {currentView === 'recovery_case' && (
              <button
                onClick={() => setCurrentView('recovery_case')}
                className={`px-5 py-2.5 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic flex items-center gap-2 bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} text-[#6C63FF] ${TOKENS.focus}`}
              >
                <FileSearch size={16} /> Case: {selectedInvoiceId}
              </button>
            )}
          </nav>
        </header>

        {/* MAIN VIEW CONTENT AREA */}
        <main className="transition-all duration-300">
          {currentView === 'dashboard' && (
            <Dashboard
              onSelectInvoice={handleSelectInvoice}
              onNavigateOpportunities={() => setCurrentView('opportunities')}
            />
          )}

          {currentView === 'opportunities' && (
            <OpportunitiesList onSelectInvoice={handleSelectInvoice} />
          )}

          {currentView === 'recovery_case' && (
            <RecoveryCase
              invoiceId={selectedInvoiceId}
              onBack={() => setCurrentView('opportunities')}
            />
          )}
        </main>

        {/* FOOTER NARRATIVE BRANDING */}
        <footer className="text-center pt-8 pb-4 text-xs text-[#6B7280] font-medium flex flex-col sm:flex-row justify-between items-center gap-4">
          <span>Razorpay Hackathon Solution | Neumorphic (Soft UI) Interface</span>
          <span>Deterministic Math Outside LLM • Guardrail Enforced</span>
        </footer>
      </div>
    </div>
  );
}
