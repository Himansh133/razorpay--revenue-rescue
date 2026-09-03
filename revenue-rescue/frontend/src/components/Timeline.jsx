import React from 'react';
import { TOKENS } from '../tokens';

export default function Timeline({ auditTrail }) {
  return (
    <div className={`p-6 ${TOKENS.radius.button} ${TOKENS.shadows.inset} space-y-4`}>
      {auditTrail?.events?.length > 0 ? (
        <div className="relative pl-6 border-l-2 border-[#6C63FF]/30 space-y-6">
          {auditTrail.events.map((evt, idx) => (
            <div key={idx} className="relative group">
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
  );
}
