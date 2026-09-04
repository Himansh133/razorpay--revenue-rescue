import React from 'react';
import { TOKENS } from '../tokens';

export default function OfferTable({ candidates = [], formatRupees }) {
  return (
    <div className="space-y-3 max-h-80 overflow-y-auto pr-2 custom-scrollbar">
      {candidates.map((cand, idx) => {
        const isValid = cand.is_valid;

        return (
          <div
            key={idx}
            className={`p-4 ${TOKENS.radius.button} transition-all duration-300 flex items-center justify-between text-xs font-mono ${
              isValid
                ? `bg-[#E0E5EC] ${TOKENS.shadows.extrudedSmall} text-[#3D4852]`
                : `bg-[#E0E5EC] ${TOKENS.shadows.inset} opacity-50 text-[#6B7280]`
            }`}
          >
            <div className="flex items-center gap-4">
              <span className={isValid ? 'font-bold text-[#6C63FF]' : 'line-through'}>
                {formatRupees(cand.offer_amount)}
              </span>
              <span className="text-[11px]">
                {cand.discount_pct}% discount | {cand.days_to_payment}d terms
              </span>
            </div>

            <div className="flex items-center gap-4">
              <span>EV: {formatRupees(cand.expected_value)}</span>
              <span>Prob: {Math.round(cand.acceptance_probability * 100)}%</span>
              {isValid ? (
                <span className="text-[#38B2AC] font-bold uppercase text-[10px]">Valid</span>
              ) : (
                <span className="text-red-500 font-bold text-[10px] flex items-center gap-1">
                  ❌ rejected: below floor
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
