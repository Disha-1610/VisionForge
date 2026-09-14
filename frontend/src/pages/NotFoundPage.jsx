import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { Button } from '../components/common/Button';

export const NotFoundPage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-hud-bg bg-grid-pattern flex items-center justify-center p-6 text-center">
      <div className="max-w-md w-full p-8 rounded-3xl bg-hud-surface border border-hud-border shadow-2xl shadow-cyan-950/40 space-y-4">
        <div className="p-4 rounded-2xl bg-hud-card border border-hud-border text-rose-400 w-fit mx-auto">
          <ShieldAlert className="w-10 h-10" />
        </div>
        <h2 className="text-2xl font-black text-white uppercase font-telemetry tracking-wide">
          404 — Route Anomaly
        </h2>
        <p className="text-xs text-slate-400 font-mono leading-relaxed">
          The requested inspection telemetry endpoint does not exist or has been relocated within the
          firmware architecture.
        </p>
        <div className="pt-2">
          <Button
            variant="primary"
            size="md"
            icon={ArrowLeft}
            onClick={() => navigate('/dashboard')}
            className="w-full"
          >
            Return to Workstation
          </Button>
        </div>
      </div>
    </div>
  );
};
