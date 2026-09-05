import React, { useState, useEffect, useRef } from 'react';
import { askAgent, getHealth } from '../api';
import { TOKENS } from '../tokens';
import {
  Bot,
  Send,
  Sparkles,
  Wrench,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  RefreshCw,
  AlertTriangle
} from 'lucide-react';

export default function GeminiAgentPanel({ invoiceId, customerName, onRefresh }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'agent',
      text: `Hello! I am the Revenue Rescue Gemini Agent. Ask me to analyze invoice ${invoiceId || ''}, evaluate candidate offers, or generate a payment link.`,
      toolCalls: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [healthData, setHealthData] = useState({
    status: 'checking',
    gemini_configured: false,
    active_provider: 'unknown',
    model: 'gemini-3.7-flash'
  });
  const [lastResponseProvider, setLastResponseProvider] = useState(null);
  const [lastResponseFallback, setLastResponseFallback] = useState(false);
  const [fallbackReason, setFallbackReason] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    async function checkHealth() {
      try {
        console.log("[GeminiAgentPanel] requesting health check...");
        const res = await getHealth();
        console.log("[GeminiAgentPanel] health response received:", res);
        if (res && res.status === 'ok') {
          setHealthData(res);
        } else {
          setHealthData({ status: 'offline', gemini_configured: false, active_provider: 'offline', model: 'offline' });
        }
      } catch (err) {
        console.error("[GeminiAgentPanel] health check failed:", err);
        setHealthData({ status: 'offline', gemini_configured: false, active_provider: 'offline', model: 'offline' });
      }
    }
    checkHealth();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (textToSend) => {
    const queryText = (textToSend || input).trim();
    if (!queryText || loading) return;

    const userMsg = {
      id: Date.now() + '-user',
      sender: 'user',
      text: queryText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    try {
      const res = await askAgent(queryText);
      setLastResponseProvider(res.provider || 'gemini');
      setLastResponseFallback(Boolean(res.is_fallback));
      setFallbackReason(res.fallback_reason || null);

      const agentMsg = {
        id: Date.now() + '-agent',
        sender: 'agent',
        text: res.final_response || 'Evaluation completed.',
        toolCalls: res.tool_calls_made || [],
        turnsUsed: res.turns_used || 0,
        provider: res.provider || (res.is_fallback ? 'fallback' : 'gemini'),
        model: res.model || 'gemini-3.7-flash',
        isFallback: res.is_fallback,
        fallbackReason: res.fallback_reason,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, agentMsg]);

      // If a payment link was successfully created by the agent, trigger parent refresh
      if (res.tool_calls_made?.some(t => t.tool_name === 'create_payment_link' && t.result?.status === 'success') && onRefresh) {
        onRefresh();
      }
    } catch (err) {
      setLastResponseFallback(true);
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + '-err',
          sender: 'agent',
          text: `Agent API Error: ${err.message || 'Failed to reach agent service.'}`,
          isError: true,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const quickPrompts = [
    `What is the best offer for ${invoiceId || 'this invoice'}?`,
    `Explain Decision`,
    `Find Best Opportunity`,
    `Create Payment Link`
  ];

  const isLiveGemini = (lastResponseProvider === 'gemini' && !lastResponseFallback) || 
                       (healthData.status === 'ok' && healthData.gemini_configured && !lastResponseFallback && !lastResponseProvider);
  const isFallback = lastResponseFallback || (healthData.status === 'ok' && !healthData.gemini_configured);

  return (
    <div className={`p-6 md:p-8 ${TOKENS.radius.container} bg-neu-surface ${TOKENS.shadows.extruded} space-y-6 border border-neu transition-neumorphic`}>
      {/* Panel Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neu pb-4">
        <div className="flex items-center gap-3">
          <div className={`p-3 ${TOKENS.radius.button} ${TOKENS.shadows.extrudedSmall} bg-[#6C63FF] text-white`}>
            <Bot size={24} />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xl font-extrabold font-display text-neu-primary tracking-tight">
                GEMINI AGENT PANEL
              </h2>
              <span className={`px-2.5 py-0.5 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} text-[10px] font-bold font-mono text-[#6C63FF] bg-neu-base flex items-center gap-1`}>
                <Sparkles size={12} /> {healthData.model || 'gemini-3.7-flash'}
              </span>
            </div>
            <p className="text-xs font-semibold text-neu-secondary">
              Interactive LLM Reasoning & Autonomous Tool Calling
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isLiveGemini ? (
            <div className={`px-3 py-1.5 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-neu-base text-xs font-bold font-display text-[#38B2AC] flex items-center gap-2`}>
              <span className="w-2 h-2 rounded-full bg-[#38B2AC] animate-pulse"></span>
              GEMINI LIVE
            </div>
          ) : isFallback ? (
            <div className={`px-3 py-1.5 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-neu-base text-xs font-bold font-display text-amber-500 flex items-center gap-2`}>
              <span className="w-2 h-2 rounded-full bg-amber-500"></span>
              DETERMINISTIC FALLBACK ({
                fallbackReason === 'NO_API_KEY' ? 'No Gemini Key' :
                fallbackReason === 'MISSING_GEMINI_SDK' ? 'Gemini SDK Missing' :
                fallbackReason === 'GEMINI_API_ERROR' ? 'Gemini API Error' :
                (fallbackReason || 'LLM Unavailable')
              })
            </div>
          ) : (
            <div className={`px-3 py-1.5 ${TOKENS.radius.pill} ${TOKENS.shadows.insetSmall} bg-neu-base text-xs font-bold font-display text-red-500 flex items-center gap-2`}>
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              {healthData.status === 'offline' ? 'HEALTH CHECK FAILED' : 'AGENT OFFLINE'}
            </div>
          )}
        </div>
      </div>

      {/* Quick Prompts Bar */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold text-neu-secondary font-display uppercase tracking-wider mr-1">
          Quick Prompts:
        </span>
        {quickPrompts.map((prompt, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(prompt)}
            disabled={loading}
            className={`px-3 py-1.5 ${TOKENS.radius.pill} bg-neu-surface ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} text-neu-primary font-semibold text-xs font-display flex items-center gap-1 transition-neumorphic active:translate-y-0.5 disabled:opacity-50 ${TOKENS.focus}`}
          >
            <ChevronRight size={13} className="text-[#6C63FF]" />
            {prompt}
          </button>
        ))}
      </div>

      {/* Message History Window */}
      <div className={`p-4 md:p-6 ${TOKENS.radius.inner} ${TOKENS.shadows.insetDeep} bg-neu-base max-h-[420px] overflow-y-auto space-y-4`}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'} space-y-2`}
          >
            <div className="flex items-center gap-2 text-[10px] font-bold text-neu-secondary font-mono px-1">
              <span>{msg.sender === 'user' ? 'MERCHANT USER' : (msg.provider === 'gemini' ? 'GEMINI AGENT (LIVE)' : 'REVENUE RESCUE AGENT')}</span>
              <span>•</span>
              <span>{msg.timestamp}</span>
            </div>

            <div
              className={`max-w-[90%] md:max-w-[80%] p-4 ${TOKENS.radius.button} text-sm font-medium leading-relaxed font-sans ${
                msg.sender === 'user'
                  ? `bg-[#6C63FF] text-white ${TOKENS.shadows.extrudedSmall}`
                  : msg.isError
                  ? `bg-red-950/20 text-red-400 border border-red-500/30 ${TOKENS.shadows.insetSmall}`
                  : `bg-neu-surface text-neu-primary ${TOKENS.shadows.extrudedSmall}`
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.text}</div>

              {/* Tool Execution Trace Box */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="mt-4 pt-3 border-t border-neu space-y-2">
                  <div className="text-[11px] font-extrabold uppercase font-display text-[#6C63FF] flex items-center gap-1.5">
                    <Wrench size={14} /> Agent Tool Execution Trace ({msg.toolCalls.length} tool calls):
                  </div>
                  <div className="space-y-2">
                    {msg.toolCalls.map((tCall, tIdx) => (
                      <div
                        key={tIdx}
                        className={`p-2.5 ${TOKENS.radius.inner} ${TOKENS.shadows.insetSmall} bg-neu-base text-xs space-y-1`}
                      >
                        <div className="flex items-center justify-between font-mono font-bold text-neu-primary">
                          <span className="flex items-center gap-1 text-[#6C63FF]">
                            <CheckCircle2 size={13} className="text-[#38B2AC]" /> {tCall.tool_name}
                          </span>
                          <span className="text-[10px] text-neu-secondary">Tool #{tIdx + 1}</span>
                        </div>
                        {tCall.input && (
                          <div className="font-mono text-[11px] text-neu-secondary truncate">
                            Input: {JSON.stringify(tCall.input)}
                          </div>
                        )}
                        {tCall.result?.payment_link_url && tCall.result?.status === 'success' && (
                          <div className="pt-1 flex items-center justify-between font-mono text-[11px] text-[#38B2AC] font-bold">
                            <span>Razorpay Payment Link Generated</span>
                            <a
                              href={tCall.result.payment_link_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[#6C63FF] underline flex items-center gap-1"
                            >
                              Open <ExternalLink size={12} />
                            </a>
                          </div>
                        )}
                        {tCall.result?.status === 'error' && (
                          <div className="pt-1 text-red-500 font-mono text-[11px] font-bold flex items-center gap-1">
                            <AlertTriangle size={12} /> {tCall.result.error || 'Execution Error'}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 p-3 text-xs font-bold text-[#6C63FF] font-display animate-pulse">
            <div className={`p-2 ${TOKENS.radius.pill} bg-neu-surface ${TOKENS.shadows.extrudedSmall}`}>
              <Sparkles size={16} className="animate-spin text-[#6C63FF]" />
            </div>
            <span>Gemini is thinking and executing backend tools...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder="Ask the Revenue Rescue Agent..."
          className={`flex-1 px-5 py-3.5 ${TOKENS.radius.button} bg-neu-input ${TOKENS.shadows.inset} text-neu-primary font-medium text-sm placeholder:text-neu-secondary ${TOKENS.focus} transition-neumorphic`}
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          className={`px-6 py-3.5 ${TOKENS.radius.button} bg-[#6C63FF] text-white font-bold text-sm font-display ${TOKENS.shadows.extrudedSmall} hover:bg-[#8B84FF] transition-neumorphic active:translate-y-0.5 flex items-center gap-2 disabled:opacity-50 ${TOKENS.focus}`}
        >
          {loading ? (
            <RefreshCw size={18} className="animate-spin" />
          ) : (
            <>
              <Send size={18} />
              <span>ASK AGENT</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
