import React from 'react';

/**
 * Standalone VisionForge AI Vector Icon component.
 */
export const LogoIcon = ({ size = 32, className = '', animate = false }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 128 128"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className}`}
    >
      <defs>
        <linearGradient id="vf-icon-bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#050b14" />
          <stop offset="100%" stop-color="#0a192f" />
        </linearGradient>
        <linearGradient id="vf-icon-cyan-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#38bdf8" />
          <stop offset="50%" stop-color="#06b6d4" />
          <stop offset="100%" stop-color="#0284c7" />
        </linearGradient>
        <linearGradient id="vf-icon-amber-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#fbbf24" />
          <stop offset="100%" stop-color="#d97706" />
        </linearGradient>
        <linearGradient id="vf-icon-shield-stroke" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#38bdf8" />
          <stop offset="50%" stop-color="#06b6d4" />
          <stop offset="100%" stop-color="#0369a1" />
        </linearGradient>
        <filter id="vf-icon-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {/* Cybernetic Hex Base Container */}
      <rect
        width="128"
        height="128"
        rx="28"
        fill="url(#vf-icon-bg-grad)"
        stroke="#0e3a5a"
        strokeWidth="2"
      />

      {/* Outer Circuit Traces */}
      <path
        d="M16 44 L30 44 L38 52 M112 44 L98 44 L90 52 M16 84 L30 84 L38 76 M112 84 L98 84 L90 76"
        stroke="#0e4a6f"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="44" r="2.5" fill="#0284c7" />
      <circle cx="112" cy="44" r="2.5" fill="#0284c7" />
      <circle cx="16" cy="84" r="2.5" fill="#0284c7" />
      <circle cx="112" cy="84" r="2.5" fill="#0284c7" />

      {/* Outer HUD Corner Reticles */}
      <path
        d="M34 26 L22 26 L22 38 M94 26 L106 26 L106 38 M34 102 L22 102 L22 90 M94 102 L106 102 L106 90"
        stroke="#38bdf8"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={animate ? 'animate-pulse-slow' : ''}
      />

      {/* Cyber Forge Hexagonal Core Shield */}
      <path
        d="M64 18 L96 36 L96 74 L64 110 L32 74 L32 36 Z"
        fill="#081b33"
        fillOpacity="0.9"
        stroke="url(#vf-icon-shield-stroke)"
        strokeWidth="3.5"
        strokeLinejoin="round"
        filter="url(#vf-icon-glow)"
      />

      {/* Inner Reticle Crosshairs */}
      <line x1="64" y1="26" x2="64" y2="44" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" opacity="0.85" />
      <line x1="64" y1="84" x2="64" y2="102" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" opacity="0.85" />
      <line x1="38" y1="64" x2="52" y2="64" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" opacity="0.85" />
      <line x1="76" y1="64" x2="90" y2="64" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" opacity="0.85" />

      {/* Center Diamond Aperture / Laser Eye */}
      <polygon
        points="64,46 80,64 64,82 48,64"
        fill="url(#vf-icon-cyan-grad)"
        opacity="0.25"
        stroke="#22d3ee"
        strokeWidth="1.5"
      />
      <polygon points="64,52 74,64 64,76 54,64" fill="url(#vf-icon-cyan-grad)" />
      <circle cx="64" cy="64" r="3.5" fill="#ffffff" filter="url(#vf-icon-glow)" />

      {/* Solder Node Accent Points */}
      <circle cx="64" cy="18" r="3.5" fill="url(#vf-icon-amber-grad)" />
      <circle cx="96" cy="36" r="3" fill="#38bdf8" />
      <circle cx="96" cy="74" r="3" fill="#38bdf8" />
      <circle cx="64" cy="110" r="3.5" fill="url(#vf-icon-amber-grad)" />
      <circle cx="32" cy="74" r="3" fill="#38bdf8" />
      <circle cx="32" cy="36" r="3" fill="#38bdf8" />
    </svg>
  );
};

/**
 * Full VisionForge AI Logo Component with customizable size, status badge, and layout.
 */
export const Logo = ({
  size = 'md',
  showText = true,
  subtitle = null,
  animate = false,
  className = '',
  onClick = null,
}) => {
  const sizeMap = {
    sm: { icon: 28, text: 'text-sm', subText: 'text-[9px]', gap: 'gap-2' },
    md: { icon: 38, text: 'text-base sm:text-lg', subText: 'text-[10px]', gap: 'gap-3' },
    lg: { icon: 48, text: 'text-xl sm:text-2xl', subText: 'text-xs', gap: 'gap-3.5' },
    xl: { icon: 64, text: 'text-2xl sm:text-3xl', subText: 'text-xs sm:text-sm', gap: 'gap-4' },
  };

  const currentSize = typeof size === 'string' && sizeMap[size] ? sizeMap[size] : sizeMap.md;
  const iconPixelSize = typeof size === 'number' ? size : currentSize.icon;

  return (
    <div
      onClick={onClick}
      className={`inline-flex items-center ${currentSize.gap} ${onClick ? 'cursor-pointer' : ''} ${className}`}
    >
      <div className="relative group shrink-0">
        <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500/30 to-blue-600/30 rounded-2xl blur-md opacity-40 group-hover:opacity-80 transition duration-300" />
        <LogoIcon size={iconPixelSize} animate={animate} className="relative drop-shadow-md" />
      </div>

      {showText && (
        <div className="flex flex-col justify-center">
          <div className="flex items-center gap-1.5">
            <span
              className={`font-black tracking-wider text-white uppercase font-telemetry leading-none ${currentSize.text}`}
            >
              Vision<span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-sky-300">Forge</span>
            </span>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-cyan-500/10 border border-cyan-500/40 text-cyan-300 tracking-wider">
              AI
            </span>
          </div>

          {subtitle && (
            <div className={`mt-0.5 font-mono text-slate-400 flex items-center gap-1.5 ${currentSize.subText}`}>
              {subtitle === 'online' ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  <span className="text-emerald-400 font-bold uppercase tracking-wider">System Online</span>
                </>
              ) : (
                <span>{subtitle}</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
