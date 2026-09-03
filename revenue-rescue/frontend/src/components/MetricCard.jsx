import React from 'react';
import { TOKENS } from '../tokens';

export default function MetricCard({ title, value, subtitle, icon: Icon, isSuccess = false }) {
  return (
    <div className={`p-8 ${TOKENS.radius.container} bg-[#E0E5EC] ${TOKENS.shadows.extruded} transition-neumorphic hover:-translate-y-1 hover:${TOKENS.shadows.extrudedHover} flex flex-col justify-between`}>
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-semibold tracking-wide text-[#6B7280] uppercase font-display">{title}</span>
        {Icon && (
          <div className={`p-3 rounded-2xl ${TOKENS.shadows.insetSmall} ${isSuccess ? 'text-[#38B2AC]' : 'text-[#6C63FF]'}`}>
            <Icon size={22} />
          </div>
        )}
      </div>
      <div>
        <div className={`text-3xl lg:text-4xl font-extrabold font-display tracking-tight ${isSuccess ? 'text-[#38B2AC]' : 'text-[#3D4852]'}`}>
          {value}
        </div>
        {subtitle && (
          <p className={`text-xs mt-2 font-medium ${isSuccess ? 'text-[#38B2AC]' : 'text-[#6B7280]'}`}>
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
}
