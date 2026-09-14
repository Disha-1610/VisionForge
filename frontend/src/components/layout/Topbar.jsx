import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ScanEye, Sun, Moon, Bell, ShieldCheck } from 'lucide-react';
import { Button } from '../common/Button';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

export const Topbar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAdmin } = useAuth();
  const { isDark, toggleTheme } = useTheme();

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
    <header className="h-16 px-6 bg-hud-surface/90 border-b border-hud-border/70 backdrop-blur-md flex items-center justify-between select-none z-20">
      <div>
        <h1 className="text-sm font-bold text-white tracking-wide uppercase font-telemetry">
          {getPageTitle()}
        </h1>
        <p className="text-[11px] text-slate-400 font-mono">
          Hardware Inspection Terminal • Line QA v1.0
        </p>
      </div>

      <div className="flex items-center gap-3">
        {/* Quick New Inspection Button */}
        {!location.pathname.startsWith('/inspections/new') && (
          <Button
            size="sm"
            variant="primary"
            icon={ScanEye}
            onClick={() => navigate('/inspections/new')}
          >
            New Inspection
          </Button>
        )}

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          className="p-2 rounded-xl text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-hud-border transition-colors"
        >
          {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Admin Badge */}
        {isAdmin && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-[11px] font-mono font-bold text-cyan-300">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>ADMIN MODE</span>
          </div>
        )}
      </div>
    </header>
  );
};
