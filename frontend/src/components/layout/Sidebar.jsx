import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  ScanEye,
  FileSpreadsheet,
  BarChart3,
  LogOut,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Logo } from '../common/Logo';

export const Sidebar = () => {
  const { user, role, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'New Inspection', path: '/inspections/new', icon: ScanEye },
    { name: 'Inspection Reports', path: '/reports', icon: FileSpreadsheet },
    { name: 'Analytics & Risk', path: '/analytics', icon: BarChart3 },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="w-64 bg-hud-surface border-r border-hud-border flex flex-col justify-between shrink-0 select-none">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-hud-border/70 flex items-center justify-between">
          <Logo size="md" subtitle="online" animate={true} />
        </div>

        {/* Navigation Items */}
        <nav className="p-4 space-y-1.5">
          <div className="px-3 py-1 text-[11px] font-mono uppercase text-slate-500 tracking-wider">
            Workstation
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* System Telemetry Box */}
        <div className="px-4 py-3 mx-4 rounded-xl bg-hud-bg/70 border border-hud-border/80 font-telemetry text-[11px] text-slate-400 space-y-1.5">
          <div className="flex items-center justify-between">
            <span>Vision Engine:</span>
            <span className="text-cyan-300 font-semibold">Multi-Model</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Golden Index:</span>
            <span className="text-emerald-300 font-semibold">Synchronized</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Pipeline:</span>
            <span className="text-amber-300 font-semibold">8-Stage Active</span>
          </div>
        </div>
      </div>

      {/* User Footer Profile & Role */}
      <div className="p-4 border-t border-hud-border/70 bg-hud-surface/90">
        <div className="flex items-center justify-between gap-3 mb-3 px-1">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="p-2 rounded-lg bg-slate-800 text-slate-300 shrink-0">
              {isAdmin ? (
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
              ) : (
                <UserCheck className="w-4 h-4 text-emerald-400" />
              )}
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-bold text-white truncate">
                {user?.full_name || user?.email?.split('@')[0] || 'QA Operator'}
              </p>
              <div className="flex items-center gap-1 mt-0.5">
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.2 rounded font-bold uppercase ${
                    isAdmin
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  }`}
                >
                  {role}
                </span>
              </div>
            </div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 border border-rose-500/20 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
