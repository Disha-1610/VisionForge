import React from 'react';

export const StatCard = ({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendPositive = true,
  className = '',
  accentColor = 'cyan', // 'cyan' | 'emerald' | 'rose' | 'amber'
}) => {
  const accentClasses = {
    cyan: 'border-cyan-500/30 text-cyan-400 bg-cyan-500/10',
    emerald: 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10',
    rose: 'border-rose-500/30 text-rose-400 bg-rose-500/10',
    amber: 'border-amber-500/30 text-amber-400 bg-amber-500/10',
  };

  return (
    <div
      className={`relative p-5 rounded-2xl bg-hud-surface/90 border border-hud-border backdrop-blur-md transition-all duration-300 hover:border-hud-border-light hover:shadow-xl hover:shadow-cyan-950/20 ${className}`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </span>
        {Icon && (
          <div className={`p-2.5 rounded-xl border ${accentClasses[accentColor]}`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <span className="text-3xl font-extrabold tracking-tight text-white font-telemetry">
          {value}
        </span>
        {trend && (
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-md ${
              trendPositive
                ? 'bg-emerald-500/20 text-emerald-300'
                : 'bg-rose-500/20 text-rose-300'
            }`}
          >
            {trend}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="mt-1 text-xs text-slate-400 font-medium">{subtitle}</p>
      )}
    </div>
  );
};
