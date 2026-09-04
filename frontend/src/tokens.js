// Neumorphic (Soft UI) Token Definitions mapping to CSS variables
export const TOKENS = {
  colors: {
    bg: 'var(--bg-color)',
    foreground: 'var(--text-primary)',
    muted: 'var(--text-secondary)',
    accent: '#6C63FF',
    accentHover: '#8B84FF',
    accentSecondary: '#38B2AC', // Success metric / recovered color
  },
  shadows: {
    extruded: 'shadow-neu-extruded',
    extrudedHover: 'shadow-neu-extruded-hover',
    extrudedSmall: 'shadow-neu-extruded-small',
    inset: 'shadow-neu-inset',
    insetDeep: 'shadow-neu-inset-deep',
    insetSmall: 'shadow-neu-inset-small',
  },
  radius: {
    container: 'rounded-[32px]',
    button: 'rounded-2xl',
    inner: 'rounded-xl',
    pill: 'rounded-full',
  },
  focus: 'focus:outline-none focus:ring-2 focus:ring-[#6C63FF]',
};
