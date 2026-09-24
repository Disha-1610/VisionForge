import React from 'react';
import { CheckCircle2, AlertOctagon, AlertTriangle, Clock, RefreshCw } from 'lucide-react';

export const StatusChip = ({ status, className = '', size = 'md' }) => {
  if (!status) return null;

  const rawStatus =
    typeof status === 'object' && status !== null
      ? status.policy_action || status.action || status.status || status.verdict || status.value || JSON.stringify(status)
      : status;
  const upper = String(rawStatus || '').toUpperCase();

  let config = {
    label: upper,
    icon: Clock,
    color: 'bg-slate-800 text-slate-300 border-slate-700',
  };

  if (['GENUINE', 'ACCEPT', 'APPROVED', 'PASS', 'COMPLETED'].includes(upper)) {
    config = {
      label: upper === 'GENUINE' ? 'GENUINE (PASS)' : upper,
      icon: CheckCircle2,
      color: 'bg-emerald-950/80 text-emerald-300 border-emerald-500/50 shadow-sm shadow-emerald-500/20',
    };
  } else if (['FRAUD', 'QUARANTINE', 'REJECT', 'FAILED', 'TAMPERED'].includes(upper)) {
    config = {
      label: upper === 'FRAUD' ? 'FRAUD DETECTED' : upper,
      icon: AlertOctagon,
      color: 'bg-rose-950/80 text-rose-300 border-rose-500/50 shadow-sm shadow-rose-500/20',
    };
  } else if (['SUSPICIOUS', 'RETAKE', 'VENDOR_VERIFICATION', 'REVIEW'].includes(upper)) {
    config = {
      label: upper.replace('_', ' '),
      icon: AlertTriangle,
      color: 'bg-amber-950/80 text-amber-300 border-amber-500/50 shadow-sm shadow-amber-500/20',
    };
  } else if (['IN_PROGRESS', 'RUNNING', 'PROCESSING', 'PENDING'].includes(upper)) {
    config = {
      label: upper.replace('_', ' '),
      icon: RefreshCw,
      color: 'bg-cyan-950/80 text-cyan-300 border-cyan-500/50 shadow-sm shadow-cyan-500/20 animate-pulse',
    };
  }

  const Icon = config.icon;
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[11px] gap-1' : 'px-2.5 py-1 text-xs gap-1.5';

  return (
    <span
      className={`inline-flex items-center font-mono font-semibold uppercase tracking-wider rounded-full border ${sizeClasses} ${config.color} ${className}`}
    >
      <Icon className={`w-3.5 h-3.5 shrink-0 ${['RUNNING', 'IN_PROGRESS', 'PROCESSING'].includes(upper) ? 'animate-spin' : ''}`} />
      <span>{config.label}</span>
    </span>
  );
};
