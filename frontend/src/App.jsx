import React, { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import OpportunitiesList from './components/OpportunitiesList';
import RecoveryCase from './pages/RecoveryCase';
import { getHealth } from './api';
import { TOKENS } from './tokens';
import {
  LayoutDashboard,
  Target,
  FileSearch,
  Shield,
  CheckCircle2,
  AlertCircle,
  Sun,
  Moon
} from 'lucide-react';

export default function App() {
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'opportunities' | 'recovery_case'
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('INV001184');
  const [apiConnected, setApiConnected] = useState(false);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    async function checkBackend() {
      try {
        const res = await getHealth();
        if (res && res.status === 'ok') {
          setApiConnected(true);
        }
      } catch (err) {
        console.error("Backend health check failed:", err);
        setApiConnected(false);
      }
    }
    checkBackend();
  }, []);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleSelectInvoice = (invId) => {
    setSelectedInvoiceId(invId);
    setCurrentView('recovery_case');
  };

  return (
    <div className="min-h-screen bg-neu-base text-neu-primary font-sans antialiased p-4 md:p-8 lg:p-12 selection:bg-[#6C63FF] selection:text-white transition-colors duration-300">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* TOP HEADER NAVIGATION */}
        <header className={`p-6 md:p-8 ${TOKENS.radius.container} bg-neu-surface ${TOKENS.shadows.extruded} flex flex-col md:flex-row md:items-center justify-between gap-6 transition-neumorphic`}>
          <div className="flex items-center gap-4">
            <div className={`p-4 rounded-2xl ${TOKENS.shadows.inset} text-[#6C63FF]`}>
              <Shield size={32} />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl md:text-2xl font-extrabold font-display text-neu-primary tracking-tight">
                  REVENUE RECOVERY ENGINE
                </h1>
                <span className={`px-3 py-1 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} text-[10px] font-extrabold font-display ${apiConnected ? 'text-[#38B2AC]' : 'text-red-500'} flex items-center gap-1.5`}>
                  {apiConnected ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
                  {apiConnected ? 'API ONLINE' : 'API DISCONNECTED'}
                </span>
              </div>
              <p className="text-xs text-neu-secondary font-medium mt-0.5">
                Explainable ML Offer Negotiation & Automated Financial Recovery
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 self-start md:self-auto flex-wrap">
            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              aria-label="Toggle Theme"
              title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              className={`p-3 ${TOKENS.radius.button} bg-neu-surface ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} text-neu-primary font-bold transition-neumorphic flex items-center gap-2 ${TOKENS.focus}`}
            >
              {theme === 'dark' ? (
                <>
                  <Sun size={18} className="text-amber-400" />
                  <span className="text-xs font-display hidden sm:inline">LIGHT</span>
                </>
              ) : (
                <>
                  <Moon size={18} className="text-[#6C63FF]" />
                  <span className="text-xs font-display hidden sm:inline">DARK</span>
                </>
              )}
            </button>

            {/* Navigation Buttons */}
            <nav className={`p-1.5 ${TOKENS.radius.button} ${TOKENS.shadows.insetSmall} bg-neu-surface flex gap-2`}>
              <button
                onClick={() => setCurrentView('dashboard')}
                className={`px-5 py-2.5 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic flex items-center gap-2 ${
                  currentView === 'dashboard'
                    ? `bg-neu-surface ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                    : 'text-neu-secondary hover:text-neu-primary'
                } ${TOKENS.focus}`}
              >
                <LayoutDashboard size={16} /> Dashboard
              </button>

              <button
                onClick={() => setCurrentView('opportunities')}
                className={`px-5 py-2.5 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic flex items-center gap-2 ${
                  currentView === 'opportunities'
                    ? `bg-neu-surface ${TOKENS.shadows.extrudedSmall} text-[#6C63FF]`
                    : 'text-neu-secondary hover:text-neu-primary'
                } ${TOKENS.focus}`}
              >
                <Target size={16} /> Opportunities
              </button>

              {currentView === 'recovery_case' && (
                <button
                  onClick={() => setCurrentView('recovery_case')}
                  className={`px-5 py-2.5 text-xs font-bold font-display ${TOKENS.radius.inner} transition-neumorphic flex items-center gap-2 bg-neu-surface ${TOKENS.shadows.extrudedSmall} text-[#6C63FF] ${TOKENS.focus}`}
                >
                  <FileSearch size={16} /> Case: {selectedInvoiceId}
                </button>
              )}
            </nav>
          </div>
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
        <footer className="text-center pt-8 pb-4 text-xs text-neu-secondary font-medium flex flex-col sm:flex-row justify-between items-center gap-4">
          <span>Razorpay Hackathon Solution | Neumorphic (Soft UI) Interface</span>
          <span>Deterministic Math Outside LLM • Guardrail Enforced</span>
        </footer>
      </div>
    </div>
  );
}
