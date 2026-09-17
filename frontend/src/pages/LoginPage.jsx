import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  Lock,
  Mail,
  User,
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  CheckCircle2,
  Zap,
  Clock,
  Globe,
  ArrowLeft,
} from 'lucide-react';
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
  const [showPassword, setShowPassword] = useState(false);

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
        toast.success(`Account created successfully!`);
      } else {
        await login(email, password);
        toast.success('Welcome back. Workstation online.');
      }
      navigate('/dashboard');
    } catch (err) {
      console.error('Auth error:', err);
      const detail =
        err.response?.data?.detail ||
        (err.response?.data?.message
          ? err.response.data.message
          : 'Authentication failed. Please check your credentials.');
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
    <div className="min-h-screen bg-[#070d18] flex items-center justify-center p-4 selection:bg-cyan-500/30 selection:text-cyan-200">
      <div className="max-w-5xl w-full grid grid-cols-1 lg:grid-cols-2 rounded-3xl bg-[#0b1322] border border-slate-800 shadow-2xl shadow-cyan-500/5 overflow-hidden">
        {/* ── Left: Auth Form ── */}
        <div className="p-8 sm:p-10 flex flex-col justify-between">
          <div>
            {/* Back to home */}
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors mb-6"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to home</span>
            </button>

            <div className="mb-8">
              <Logo size="md" animate={true} />
            </div>

            <div className="mb-6">
              <h2 className="text-2xl font-extrabold text-white tracking-tight">
                {isRegister ? 'Create your account' : 'Welcome back'}
              </h2>
              <p className="text-sm text-slate-400 mt-2">
                {isRegister
                  ? 'Set up your team to start inspecting components.'
                  : 'Sign in to access your inspection dashboard.'}
              </p>
            </div>

            {/* Error Banner */}
            {errorMsg && (
              <div className="mb-4 p-3 rounded-xl bg-rose-950/60 border border-rose-500/30 text-rose-200 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span className="min-w-0 break-words">{errorMsg}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {isRegister && (
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
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
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[#060c16] border border-slate-800 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Email address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[#060c16] border border-slate-800 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-[#060c16] border border-slate-800 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-3 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {isRegister && (
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-[#060c16] border border-slate-800 text-sm text-white focus:outline-none focus:border-cyan-500 font-mono"
                  >
                    <option value="operator">QA Operator — Run inspections & view reports</option>
                    <option value="admin">Admin — Full access + golden reference management</option>
                  </select>
                </div>
              )}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={loading}
                icon={ArrowRight}
                className="w-full mt-2"
              >
                {isRegister ? 'Create Account' : 'Sign In'}
              </Button>
            </form>

            <div className="mt-5 text-center">
              <button
                type="button"
                onClick={() => {
                  setIsRegister(!isRegister);
                  setErrorMsg('');
                }}
                className="text-xs text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                {isRegister
                  ? 'Already have an account? Sign in'
                  : "Don't have an account? Get started free"}
              </button>
            </div>
          </div>

          {/* Demo Quick Fill */}
          <div className="mt-8 pt-5 border-t border-slate-800/80">
            <p className="text-[10px] font-mono text-slate-600 uppercase tracking-wider mb-2.5 text-center">
              Demo Access
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleQuickFill('operator')}
                className="px-3 py-2 rounded-xl bg-[#060c16] hover:bg-slate-800/80 border border-slate-800 text-[11px] font-mono text-slate-400 hover:text-white transition-all duration-200 hover:border-slate-700"
              >
                QA Operator
              </button>
              <button
                type="button"
                onClick={() => handleQuickFill('admin')}
                className="px-3 py-2 rounded-xl bg-[#060c16] hover:bg-slate-800/80 border border-cyan-500/30 text-[11px] font-mono text-cyan-400 hover:text-cyan-300 transition-all duration-200 hover:border-cyan-500/50"
              >
                System Admin
              </button>
            </div>
          </div>
        </div>

        {/* ── Right: Brand Panel ── */}
        <div className="hidden lg:flex p-10 bg-[#080f1d] border-l border-slate-800 flex-col justify-between relative overflow-hidden">
          {/* Background glow */}
          <div className="absolute top-1/4 right-0 w-[300px] h-[300px] bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

          <div className="space-y-8 relative">
            {/* Header */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                </div>
                <span className="text-[11px] font-mono font-bold text-emerald-300 uppercase tracking-wider">
                  Enterprise Security
                </span>
              </div>
              <h3 className="text-xl font-extrabold text-white tracking-tight">
                Built for hardware QA teams
              </h3>
              <p className="text-sm text-slate-400 mt-3 leading-relaxed">
                Automated visual inspection pipeline that catches defects, verifies components, and generates audit-ready reports.
              </p>
            </div>

            {/* Feature list */}
            <div className="space-y-3">
              {[
                {
                  icon: Zap,
                  title: '8-Stage Automated Pipeline',
                  desc: 'From upload to verdict in under 30 seconds.',
                  color: 'text-cyan-400',
                  bg: 'bg-cyan-500/10',
                  border: 'border-cyan-500/20',
                },
                {
                  icon: CheckCircle2,
                  title: 'Explainable AI Verdicts',
                  desc: 'Root-cause analysis, not just a fraud score.',
                  color: 'text-emerald-400',
                  bg: 'bg-emerald-500/10',
                  border: 'border-emerald-500/20',
                },
                {
                  icon: Clock,
                  title: 'Real-Time Progress',
                  desc: 'Live pipeline tracking via Server-Sent Events.',
                  color: 'text-amber-400',
                  bg: 'bg-amber-500/10',
                  border: 'border-amber-500/20',
                },
                {
                  icon: Globe,
                  title: 'Multi-Site Support',
                  desc: 'Manage inspections across multiple locations.',
                  color: 'text-sky-400',
                  bg: 'bg-sky-500/10',
                  border: 'border-sky-500/20',
                },
              ].map((f, i) => {
                const Icon = f.icon;
                return (
                  <div key={i} className="flex items-start gap-3">
                    <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 ${f.bg} ${f.border}`}>
                      <Icon className={`w-4 h-4 ${f.color}`} />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">{f.title}</div>
                      <div className="text-[11px] text-slate-500 mt-0.5">{f.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Bottom trust strip */}
          <div className="relative pt-6 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-600">
            <span>SOC 2 Compliant</span>
            <span>ISO 9001 Aligned</span>
            <span>GDPR Ready</span>
          </div>
        </div>
      </div>
    </div>
  );
};
