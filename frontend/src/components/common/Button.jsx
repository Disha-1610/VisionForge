import React from 'react';
import { Loader2 } from 'lucide-react';

export const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon: Icon,
  className = '',
  onClick,
  type = 'button',
  ...props
}) => {
  const baseClasses =
    'inline-flex items-center justify-center font-medium rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-50 disabled:cursor-not-allowed select-none active:scale-[0.98]';

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-6 py-3 text-base gap-2.5',
  };

  const variantClasses = {
    primary:
      'bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold shadow-lg shadow-cyan-500/20 focus:ring-cyan-400 hover:shadow-cyan-500/35 border border-cyan-400/50',
    secondary:
      'bg-hud-surface hover:bg-hud-card text-slate-200 border border-hud-border hover:border-hud-border-light focus:ring-cyan-500/50',
    danger:
      'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/25 focus:ring-rose-500 border border-rose-400/30',
    success:
      'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25 focus:ring-emerald-500 border border-emerald-400/30',
    amber:
      'bg-amber-600 hover:bg-amber-500 text-white shadow-lg shadow-amber-600/25 focus:ring-amber-500 border border-amber-400/30',
    ghost:
      'bg-transparent hover:bg-slate-800/60 text-slate-300 hover:text-white focus:ring-slate-500',
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`${baseClasses} ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin text-current" />
      ) : Icon ? (
        <Icon className="w-4 h-4 shrink-0" />
      ) : null}
      <span>{children}</span>
    </button>
  );
};
