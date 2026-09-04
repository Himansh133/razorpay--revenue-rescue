import React from 'react';
import { TOKENS } from '../tokens';

export default function Timeline({ auditTrail }) {
  return (
    <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} bg-neu-surface space-y-4`}>
      {auditTrail?.events?.length > 0 ? (
        <div className="relative pl-6 border-l-2 border-[#6C63FF]/30 space-y-6">
          {auditTrail.events.map((evt, idx) => (
            <div key={idx} className="relative group">
              <div className={`absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-neu-surface ${TOKENS.shadows.extrudedSmall} flex items-center justify-center`}>
                <div className="w-2 h-2 rounded-full bg-[#38B2AC]"></div>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs">
                <span className="font-bold text-neu-primary font-display">
                  {evt.summary}
                </span>
                <span className="text-[10px] font-mono text-neu-secondary">
                  {evt.timestamp?.substring(11, 16) || '14:00'} ({evt.actor})
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-neu-secondary font-mono">
          {auditTrail?.timeline_summary || 'No audit trail entries recorded yet.'}
        </div>
      )}
    </div>
  );
}
