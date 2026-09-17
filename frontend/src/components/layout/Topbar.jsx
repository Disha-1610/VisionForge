import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Menu, ScanEye, Bell, ShieldCheck } from 'lucide-react';
import { Button } from '../common/Button';
import { useAuth } from '../../context/AuthContext';

export const Topbar = ({ onMenuClick }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAdmin } = useAuth();

  const getPageTitle = () => {
    const path = location.pathname;
    if (path.startsWith('/dashboard')) return 'Operational Overview';
    if (path.startsWith('/inspections/new')) return 'Intake & Inspection Pipeline';
    if (path.startsWith('/inspections/')) return 'Inspection Workspace & Diagnostics';
    if (path.startsWith('/reports')) return 'Compliance & Audit Archive';
    if (path.startsWith('/analytics')) return 'Vendor & Location Risk Intelligence';
    return 'VisionForge Platform';
  };

  return (
    <header className="h-16 px-4 sm:px-6 bg-hud-surface/90 border-b border-hud-border/70 backdrop-blur-md flex items-center justify-between gap-3 select-none z-20">
      <div className="flex items-center gap-3 min-w-0">
        {/* Mobile hamburger */}
        <button
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="lg:hidden p-2 rounded-xl text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="min-w-0">
          <h1 className="text-sm font-bold text-white tracking-wide uppercase font-telemetry truncate">
            {getPageTitle()}
          </h1>
          <p className="text-[11px] text-slate-400 font-mono truncate hidden sm:block">
            Hardware Inspection Terminal • Line QA v1.0
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Quick New Inspection Button */}
        {!location.pathname.startsWith('/inspections/new') && (
          <Button
            size="sm"
            variant="primary"
            icon={ScanEye}
            onClick={() => navigate('/inspections/new')}
          >
            <span className="hidden sm:inline">New Inspection</span>
            <span className="sm:hidden">New</span>
          </Button>
        )}

        {/* Admin Badge */}
        {isAdmin && (
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-[11px] font-mono font-bold text-cyan-300">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>ADMIN MODE</span>
          </div>
        )}
      </div>
    </header>
  );
};
