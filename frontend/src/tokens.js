// Neumorphic (Soft UI) Token Definitions
export const TOKENS = {
  colors: {
    bg: '#E0E5EC',
    foreground: '#3D4852',
    muted: '#6B7280',
    accent: '#6C63FF',
    accentHover: '#8B84FF',
    accentSecondary: '#38B2AC', // Success metric / recovered color
  },
  shadows: {
    extruded: 'shadow-[9px_9px_16px_rgb(163,177,198,0.6),-9px_-9px_16px_rgba(255,255,255,0.5)]',
    extrudedHover: 'shadow-[12px_12px_20px_rgb(163,177,198,0.7),-12px_-12px_20px_rgba(255,255,255,0.6)]',
    extrudedSmall: 'shadow-[5px_5px_10px_rgb(163,177,198,0.6),-5px_-5px_10px_rgba(255,255,255,0.5)]',
    inset: 'shadow-[inset_6px_6px_10px_rgb(163,177,198,0.6),inset_-6px_-6px_10px_rgba(255,255,255,0.5)]',
    insetDeep: 'shadow-[inset_10px_10px_20px_rgb(163,177,198,0.7),inset_-10px_-10px_20px_rgba(255,255,255,0.6)]',
    insetSmall: 'shadow-[inset_3px_3px_6px_rgb(163,177,198,0.6),inset_-3px_-3px_6px_rgba(255,255,255,0.5)]',
  },
  radius: {
    container: 'rounded-[32px]',
    button: 'rounded-2xl',
    inner: 'rounded-xl',
    pill: 'rounded-full',
  },
  focus: 'focus:outline-none focus:ring-2 focus:ring-[#6C63FF] focus:ring-offset-2 focus:ring-offset-[#E0E5EC]',
};
