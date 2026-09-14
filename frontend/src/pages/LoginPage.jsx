import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Lock, Mail, User, AlertCircle, ArrowRight } from 'lucide-react';
import { Button } from '../components/common/Button';
import { Logo } from '../components/common/Logo';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export const LoginPage = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('operator');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const { login, register } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      if (isRegister) {
        await register(email, password, fullName, role);
        toast.success(`Account registered successfully as ${role.toUpperCase()}!`);
      } else {
        await login(email, password);
        toast.success('Authenticated successfully. Workstation online.');
      }
      navigate('/dashboard');
    } catch (err) {
      console.error('Auth error:', err);
      const detail =
        err.response?.data?.detail ||
        (err.response?.data?.message
          ? err.response.data.message
          : 'Authentication failed. Please verify your credentials.');
      setErrorMsg(detail);
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (targetRole) => {
    if (targetRole === 'admin') {
      setEmail('admin@visionforge.ai');
      setPassword('adminpassword123');
      setFullName('Admin Manager');
      setRole('admin');
    } else {
      setEmail('operator@visionforge.ai');
      setPassword('operatorpassword123');
      setFullName('Line Operator');
      setRole('operator');
    }
    setIsRegister(false);
    setErrorMsg('');
  };

  return (
    <div className="min-h-screen bg-hud-bg bg-grid-pattern flex items-center justify-center p-4 selection:bg-cyan-500/30 selection:text-cyan-200">
      <div className="max-w-4xl w-full grid grid-cols-1 md:grid-cols-2 rounded-3xl bg-hud-surface border border-hud-border shadow-2xl shadow-cyan-950/40 overflow-hidden">
        {/* Left Side: Auth Form */}
        <div className="p-8 sm:p-10 flex flex-col justify-between">
          <div>
            <div className="mb-6">
              <Logo size="lg" animate={true} />
            </div>

            <div className="mb-6">
              <h2 className="text-2xl font-black text-white tracking-tight">
                {isRegister ? 'Create Inspection Account' : 'Workstation Sign In'}
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                {isRegister
                  ? 'Provision operator or administrative access'
                  : 'Enter your credentials to access the inspection terminal'}
              </p>
            </div>

            {/* Error Banner */}
            {errorMsg && (
              <div className="mb-4 p-3 rounded-xl bg-rose-950/80 border border-rose-500/50 text-rose-200 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {isRegister && (
                <div>
                  <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1.5">
                    Full Name
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
                    <input
                      type="text"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Jane Doe"
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-hud-card border border-hud-border text-sm text-white focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition-colors"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1.5">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="operator@visionforge.ai"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-hud-card border border-hud-border text-sm text-white focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-hud-card border border-hud-border text-sm text-white focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition-colors"
                  />
                </div>
              </div>

              {isRegister && (
                <div>
                  <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1.5">
                    Assigned Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-hud-card border border-hud-border text-sm text-white focus:outline-none focus:border-cyan-400 font-mono"
                  >
                    <option value="operator">QA Operator (Line Intake & Inspection)</option>
                    <option value="admin">System Admin (Full Access & Golden Repositories)</option>
                  </select>
                </div>
              )}

              <Button
                type="submit"
                variant="primary"
                size="md"
                loading={loading}
                icon={ArrowRight}
                className="w-full mt-2"
              >
                {isRegister ? 'Register Account' : 'Authenticate & Enter'}
              </Button>
            </form>

            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={() => {
                  setIsRegister(!isRegister);
                  setErrorMsg('');
                }}
                className="text-xs text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                {isRegister
                  ? 'Already have an account? Sign in here'
                  : "Don't have an account? Register new user"}
              </button>
            </div>
          </div>

          {/* Quick Demo Fill Buttons */}
          <div className="mt-8 pt-6 border-t border-hud-border/70">
            <p className="text-[11px] font-mono text-slate-500 uppercase tracking-wider mb-2 text-center">
              Demo Credentials Quick Fill
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleQuickFill('operator')}
                className="px-2.5 py-1.5 rounded-lg bg-hud-card hover:bg-slate-800 border border-hud-border text-[11px] font-mono text-slate-300 hover:text-white transition-colors"
              >
                Fill Operator
              </button>
              <button
                type="button"
                onClick={() => handleQuickFill('admin')}
                className="px-2.5 py-1.5 rounded-lg bg-hud-card hover:bg-slate-800 border border-hud-border text-[11px] font-mono text-cyan-300 hover:text-cyan-200 transition-colors"
              >
                Fill Admin
              </button>
            </div>
          </div>
        </div>

        {/* Right Side: Visual Specs & Security Badge */}
        <div className="p-8 sm:p-10 bg-hud-card/80 border-t md:border-t-0 md:border-l border-hud-border flex flex-col justify-between">
          <div className="space-y-6">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <span className="text-xs font-mono font-bold text-emerald-300 uppercase tracking-wider">
                Quality Assurance Terminal
              </span>
            </div>

            <div>
              <h3 className="text-xl font-bold text-white tracking-tight">
                Hardware Inspection Workstation
              </h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                Streamline quality intake and defect tracking across incoming PCB assemblies, battery modules, and electronic components.
              </p>
            </div>

            <div className="space-y-3 font-mono text-xs text-slate-300">
              <div className="p-3 rounded-xl bg-hud-surface/90 border border-hud-border/70">
                <span className="text-cyan-400 font-bold">Automated Defect Flagging:</span> Identify missing components, solder bridges, and board surface anomalies.
              </div>
              <div className="p-3 rounded-xl bg-hud-surface/90 border border-hud-border/70">
                <span className="text-emerald-400 font-bold">Serial & Label Verification:</span> Verify batch numbers, printed markings, and warranty seals against catalog data.
              </div>
              <div className="p-3 rounded-xl bg-hud-surface/90 border border-hud-border/70">
                <span className="text-amber-400 font-bold">Audit-Ready Reports:</span> Generate comprehensive inspection dossiers and PDF reports with detailed evidence.
              </div>
            </div>
          </div>

          <div className="mt-8 pt-4 border-t border-hud-border/70 flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>Terminal: Workstation-01</span>
            <span>Session: Secure Local QA</span>
          </div>
        </div>
      </div>
    </div>
  );
};
