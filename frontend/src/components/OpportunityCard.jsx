import React from 'react';
import { TOKENS } from '../tokens';
import { ChevronRight } from 'lucide-react';

export default function OpportunityCard({ title, subtitle, impact, metricLabel, metricValue, onClick, icon: Icon }) {
  const pct = Math.round((metricValue || 0.8) * 100);

  return (
    <div
      onClick={onClick}
      className={`p-6 ${TOKENS.radius.button} bg-neu-surface ${TOKENS.shadows.extrudedSmall} hover:${TOKENS.shadows.extrudedHover} hover:-translate-y-1 transition-neumorphic cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 group border border-neu`}
    >
      <div className="flex items-start gap-4">
        {Icon && (
          <div className={`p-3 rounded-2xl ${TOKENS.shadows.insetSmall} text-[#6C63FF] mt-1`}>
            <Icon size={22} />
          </div>
        )}
        <div>
          <h3 className="text-base font-bold font-display text-neu-primary group-hover:text-[#6C63FF] transition-colors">
            {title}
          </h3>
          <p className="text-xs text-neu-secondary mt-1 line-clamp-1">
            {subtitle}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-6 self-end md:self-center">
        <div className="text-right">
          <div className="text-xs font-semibold text-neu-secondary mb-1">{metricLabel}</div>
          <div className="flex items-center gap-2">
            <div className={`w-24 h-3 rounded-full ${TOKENS.shadows.insetSmall} bg-neu-base overflow-hidden p-0.5`}>
              <div
                className="h-full bg-[#6C63FF] rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              ></div>
            </div>
            <span className="text-xs font-bold text-neu-primary font-mono">{pct}%</span>
          </div>
        </div>

        <div className="text-right min-w-[110px]">
          <div className="text-xs font-semibold text-neu-secondary">Impact / Amount</div>
          <div className="text-lg font-extrabold font-display text-neu-primary">
            {impact}
          </div>
        </div>

        <ChevronRight size={20} className="text-neu-secondary group-hover:text-[#6C63FF] group-hover:translate-x-1 transition-all" />
      </div>
    </div>
  );
}
