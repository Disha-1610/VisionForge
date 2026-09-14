import React from 'react';
import { ShieldAlert } from 'lucide-react';
import { Button } from './Button';

export const EmptyState = ({
  icon: Icon = ShieldAlert,
  title = 'No Records Found',
  description = 'There are currently no items matching your criteria in the system.',
  actionLabel,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-2xl bg-hud-surface/50 border border-hud-border/60 border-dashed my-6">
      <div className="p-4 rounded-2xl bg-hud-card border border-hud-border text-cyan-400 mb-4 shadow-inner">
        <Icon className="w-8 h-8" />
      </div>
      <h4 className="text-base font-bold text-white tracking-wide">{title}</h4>
      <p className="text-sm text-slate-400 max-w-sm mt-1 mb-6 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button variant="primary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};
