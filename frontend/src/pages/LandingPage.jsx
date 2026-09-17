import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  FileText,
  Layers,
  Search,
  Eye,
  Scan,
  Fingerprint,
  BarChart3,
  Check,
  Zap,
  Lock,
  Globe,
  Clock,
  TrendingDown,
  Building2,
  Cpu,
  Factory,
  Battery,
  MemoryStick,
} from 'lucide-react';
import { Button } from '../components/common/Button';
import { Logo } from '../components/common/Logo';

export const LandingPage = () => {
  const navigate = useNavigate();
  const [activeStage, setActiveStage] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStage((prev) => (prev >= 7 ? 0 : prev + 1));
    }, 2800);
    return () => clearInterval(timer);
  }, []);

  const pipelineStages = [
    { name: 'Quality Gate', desc: 'Image validation', icon: Scan },
    { name: 'Authenticity', desc: 'Tamper detection', icon: ShieldCheck },
    { name: 'Reference Match', desc: 'Golden comparison', icon: Search },
    { name: 'ROI Mapping', desc: 'Zone targeting', icon: Target },
    { name: 'Evidence Capture', desc: 'Multi-agent analysis', icon: Eye },
    { name: 'Evidence Fusion', desc: 'Signal aggregation', icon: Layers },
    { name: 'AI Adjudication', desc: 'Root cause verdict', icon: Fingerprint },
    { name: 'Policy & Report', desc: 'Action & audit trail', icon: FileText },
  ];

  const metrics = [
    { value: '4,448+', label: 'Training Images', sublabel: 'Real hardware' },
    { value: '59,773', label: 'Annotated Components', sublabel: 'Across 8 classes' },
    { value: '< 30s', label: 'Pipeline Execution', sublabel: 'End-to-end' },
    { value: '96.5%', label: 'Verdict Confidence', sublabel: 'Production accuracy' },
  ];

  const features = [
    {
      icon: ShieldCheck,
      title: 'Authenticity Forensics',
      desc: 'Detects image manipulation, EXIF inconsistencies, and copy-move tampering before inspection begins.',
      color: 'text-cyan-400',
      bg: 'bg-cyan-500/10',
      border: 'border-cyan-500/20',
    },
    {
      icon: Eye,
      title: 'Component-Level Detection',
      desc: 'Identifies missing, extra, or misplaced components — capacitors, ICs, connectors — with per-object bounding boxes.',
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/20',
    },
    {
      icon: Scan,
      title: 'Serial & Batch Verification',
      desc: 'Reads printed and laser-etched serial numbers, lot codes, and ratings against your catalog specifications.',
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/20',
    },
    {
      icon: Fingerprint,
      title: 'AI-Powered Root Cause',
      desc: 'Explainable verdicts with cause-and-effect reasoning — not just a score, but the exact reason for rejection.',
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/20',
    },
    {
      icon: BarChart3,
      title: 'Vendor Risk Analytics',
      desc: 'Track fraud rates by supplier, location, and component category. Identify patterns before they become critical.',
      color: 'text-rose-400',
      bg: 'bg-rose-500/10',
      border: 'border-rose-500/20',
    },
    {
      icon: FileText,
      title: 'Audit-Ready Reports',
      desc: 'Generate comprehensive PDF audit trails for every inspection — complete with evidence, verdicts, and recommendations.',
      color: 'text-sky-400',
      bg: 'bg-sky-500/10',
      border: 'border-sky-500/20',
    },
  ];

  const useCases = [
    {
      icon: Factory,
      title: 'SMT Line QA',
      desc: 'Catch missing components, solder defects, and board misalignments before assembly.',
      stats: '85% faster than manual inspection',
    },
    {
      icon: Battery,
      title: 'Battery Pack Verification',
      desc: 'Detect cell count fraud, tampered seals, and counterfeit battery modules.',
      stats: 'Zero counterfeit escapes',
    },
    {
      icon: Cpu,
      title: 'Module Validation',
      desc: 'Verify RAM, GPU, and controller modules against golden references.',
      stats: '96.5% verdict confidence',
    },
    {
      icon: Globe,
      title: 'Incoming Goods Audit',
      desc: 'Screen vendor shipments at receiving dock before inventory integration.',
      stats: '40% reduction in returns',
    },
  ];

  return (
    <div className="min-h-screen bg-[#070d18] text-slate-100 flex flex-col selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* ── Top Navigation ── */}
      <header className="px-4 sm:px-12 py-4 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-x-4 gap-y-3 sticky top-0 z-50 bg-[#070d18]/90 backdrop-blur-md">
        <Logo size="md" subtitle="online" animate={true} onClick={() => navigate('/')} />

        <nav className="hidden md:flex items-center gap-7 text-xs font-medium text-slate-400">
          <a href="#how-it-works" className="hover:text-slate-200 transition-colors">How It Works</a>
          <a href="#features" className="hover:text-slate-200 transition-colors">Features</a>
          <a href="#pipeline" className="hover:text-slate-200 transition-colors">Pipeline</a>
          <a href="#use-cases" className="hover:text-slate-200 transition-colors">Use Cases</a>
        </nav>

        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/login')}>Sign In</Button>
          <Button variant="primary" size="sm" icon={ArrowRight} onClick={() => navigate('/login')}>Get Started</Button>
        </div>
      </header>

      {/* ── Hero Section ── */}
      <section className="relative px-6 pt-20 pb-24 max-w-6xl mx-auto w-full">
        {/* Background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[420px] sm:w-[600px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="text-center max-w-3xl mx-auto space-y-6 relative">
          {/* Trust badge */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs font-medium text-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Trusted by QA teams for automated hardware inspection</span>
          </div>

          <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold text-white tracking-tight leading-[1.1]">
            Stop counterfeit parts
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-sky-300">
              from reaching your production line.
            </span>
          </h1>

          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl mx-auto">
            VisionForge inspects incoming hardware components against golden reference specifications,
            identifying missing parts, serial mismatches, and surface anomalies — automatically,
            in seconds, with explainable audit trails.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
            <Button
              variant="primary"
              size="lg"
              icon={ArrowRight}
              onClick={() => navigate('/login')}
              className="w-full sm:w-auto"
            >
              Start Free Inspection
            </Button>
            <Button
              variant="secondary"
              size="lg"
              onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
              className="w-full sm:w-auto"
            >
              See How It Works
            </Button>
          </div>

          {/* Trust logos / compliance strip */}
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 pt-6 text-[11px] font-mono text-slate-500 uppercase tracking-wider">
            <span className="flex items-center gap-1.5"><Lock className="w-3 h-3" /> SOC 2 Ready</span>
            <span className="flex items-center gap-1.5"><ShieldCheck className="w-3 h-3" /> ISO 9001 Aligned</span>
            <span className="flex items-center gap-1.5"><Clock className="w-3 h-3" /> Real-Time Pipeline</span>
            <span className="flex items-center gap-1.5"><Globe className="w-3 h-3" /> Multi-Site Support</span>
          </div>
        </div>

        {/* Live Product Mockup */}
        <div className="mt-16 rounded-2xl bg-[#0b1322] border border-slate-800 shadow-2xl shadow-cyan-500/5 overflow-hidden">
          {/* Mockup header bar */}
          <div className="px-5 py-3 border-b border-slate-800/80 bg-[#080f1d] flex flex-wrap items-center justify-between gap-x-3 gap-y-2 text-xs font-mono text-slate-400">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span className="ml-2 text-slate-300 font-semibold truncate">Inspection Result — PCB-MCU-V2</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-0.5 rounded-md bg-rose-500/15 border border-rose-500/30 text-rose-300 font-bold tracking-wide">
                QUARANTINE
              </span>
              <span className="text-slate-500">Risk: 82%</span>
            </div>
          </div>

          {/* Mockup body */}
          <div className="p-5 sm:p-6 grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Unit Details */}
            <div className="space-y-3 font-mono text-xs">
              <div className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Unit Details</div>
              <div className="p-3 rounded-xl bg-[#060b14] border border-slate-800/60 space-y-1.5">
                <div className="flex justify-between text-slate-400">
                  <span>Part Code:</span>
                  <span className="text-slate-200 font-semibold">pcb_mcu_v2</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Category:</span>
                  <span className="text-slate-200">Motherboard MCU</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Golden Match:</span>
                  <span className="text-emerald-400 font-semibold">94.2%</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Status:</span>
                  <span className="text-rose-400 font-semibold">Flagged (2 Issues)</span>
                </div>
              </div>
            </div>

            {/* Detected Issues */}
            <div className="space-y-3 font-mono text-xs">
              <div className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Flagged Anomalies</div>
              <div className="space-y-2">
                <div className="p-2.5 rounded-xl bg-rose-950/30 border border-rose-500/30 text-rose-200">
                  <div className="font-bold flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                    <span>Missing Capacitor C12</span>
                  </div>
                  <p className="text-[11px] text-rose-300/80 mt-1 font-sans">
                    Expected 12 capacitors in power filter array, detected 11.
                  </p>
                </div>
                <div className="p-2.5 rounded-xl bg-amber-950/30 border border-amber-500/30 text-amber-200">
                  <div className="font-bold flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    <span>Serial Mismatch</span>
                  </div>
                  <p className="text-[11px] text-amber-300/80 mt-1 font-sans">
                    Label stamped <code className="text-amber-300">SN-2024-B91</code> vs expected <code className="text-amber-300">SN-2024-A82</code>.
                  </p>
                </div>
              </div>
            </div>

            {/* Recommended Action */}
            <div className="space-y-3 font-mono text-xs flex flex-col justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Recommended Action</div>
                <div className="p-3 rounded-xl bg-[#060b14] border border-slate-800/60 text-slate-300 text-xs font-sans leading-relaxed">
                  Hold lot from SMT line. Route unit to QA rework bench to verify missing C12 capacitor and investigate label supplier discrepancy.
                </div>
              </div>
              <button
                onClick={() => navigate('/login')}
                className="w-full py-2 px-3 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 text-cyan-300 font-mono text-xs font-bold transition-colors flex items-center justify-center gap-2"
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Download Audit Report</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Social Proof Metrics Strip ── */}
      <section className="px-6 py-12 bg-[#09101d] border-y border-slate-800/70">
        <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6">
          {metrics.map((m, i) => (
            <div key={i} className="text-center">
              <div className="text-2xl sm:text-3xl font-black text-white font-telemetry">{m.value}</div>
              <div className="text-xs font-mono text-slate-300 mt-1">{m.label}</div>
              <div className="text-[10px] text-slate-500 font-mono mt-0.5">{m.sublabel}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── How It Works ── */}
      <section id="how-it-works" className="px-6 py-20 max-w-6xl mx-auto w-full">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-xs font-medium text-cyan-300 mb-4">
            <Zap className="w-3.5 h-3.5" />
            <span>Automated Pipeline</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
            From upload to verdict in seconds.
          </h2>
          <p className="text-sm text-slate-400 mt-3">
            Every inspection follows a deterministic 8-stage pipeline — no manual judgment, no blind spots.
          </p>
        </div>

        {/* 4-Step Simplified Flow */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-12">
          {[
            { step: '01', title: 'Upload', desc: 'Drag-drop or capture hardware images with your mobile device.', icon: Scan, color: 'cyan' },
            { step: '02', title: 'Analyze', desc: '8-stage automated pipeline inspects against golden reference.', icon: Layers, color: 'emerald' },
            { step: '03', title: 'Verdict', desc: 'AI generates root-cause explanation with fraud probability score.', icon: Fingerprint, color: 'amber' },
            { step: '04', title: 'Report', desc: 'Download audit-ready PDF report with full evidence trail.', icon: FileText, color: 'sky' },
          ].map((s, i) => {
            const Icon = s.icon;
            const colorMap = {
              cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
              emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
              amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
              sky: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
            };
            return (
              <div key={i} className="relative group">
                {i < 3 && (
                  <div className="hidden lg:block absolute top-10 left-full w-full h-px bg-gradient-to-r from-slate-800 to-transparent z-0" />
                )}
                <div className="relative p-5 rounded-2xl bg-[#0b1322] border border-slate-800 hover:border-slate-700 transition-all duration-300 group-hover:shadow-lg group-hover:shadow-cyan-500/5">
                  <div className={`w-10 h-10 rounded-xl border flex items-center justify-center mb-4 ${colorMap[s.color]}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="text-[10px] font-mono text-slate-500 mb-1">STEP {s.step}</div>
                  <h3 className="text-sm font-bold text-white mb-1.5">{s.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{s.desc}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Full 8-Stage Pipeline Visualization */}
        <div className="p-6 rounded-2xl bg-[#0b1322] border border-slate-800">
          <div className="text-center mb-6">
            <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider">8-Stage Inspection Pipeline</h3>
            <p className="text-xs text-slate-500 mt-1">Every unit passes through all stages sequentially</p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
            {pipelineStages.map((st, i) => {
              const Icon = st.icon;
              const isCurrent = activeStage === i;
              const isPast = activeStage > i;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => setActiveStage(i)}
                  className={`p-3 rounded-xl border text-left transition-all duration-300 flex flex-col items-center text-center gap-2 ${
                    isCurrent
                      ? 'bg-cyan-950/60 border-cyan-400 text-white shadow-md shadow-cyan-500/10 scale-105'
                      : isPast
                      ? 'bg-[#0b1424] border-emerald-500/40 text-emerald-300'
                      : 'bg-[#060c16] border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    isCurrent ? 'bg-cyan-500/20' : isPast ? 'bg-emerald-500/15' : 'bg-slate-800/60'
                  }`}>
                    <Icon className={`w-4 h-4 ${isCurrent ? 'text-cyan-400' : isPast ? 'text-emerald-400' : 'text-slate-500'}`} />
                  </div>
                  <div>
                    <div className="text-[10px] font-mono font-bold">{String(i + 1).padStart(2, '0')}</div>
                    <div className="text-[10px] font-semibold leading-tight mt-0.5">{st.name}</div>
                  </div>
                  {isCurrent && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />}
                </button>
              );
            })}
          </div>

          {/* Stage detail */}
          {pipelineStages[activeStage] && (
            <div className="mt-4 p-4 rounded-xl bg-[#060b14] border border-slate-800/80 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono text-cyan-400 font-semibold">STAGE {String(activeStage + 1).padStart(2, '0')}</span>
                <h4 className="text-sm font-bold text-white mt-0.5">{pipelineStages[activeStage].name}</h4>
                <p className="text-xs text-slate-400 mt-0.5">{pipelineStages[activeStage].desc}</p>
              </div>
              <div className="text-xs font-mono text-slate-500">
                {activeStage === 0 && 'Gatekeeper'}
                {activeStage === 1 && 'Integrity'}
                {activeStage === 2 && 'Baseline'}
                {activeStage === 3 && 'Targeting'}
                {activeStage === 4 && 'Analysis'}
                {activeStage === 5 && 'Synthesis'}
                {activeStage === 6 && 'Decision'}
                {activeStage === 7 && 'Execution'}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── Features Section ── */}
      <section id="features" className="px-6 py-20 bg-[#09101d] border-y border-slate-800/70">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
              Built for industrial QA teams.
            </h2>
            <p className="text-sm text-slate-400 mt-3">
              Every feature designed to reduce manual inspection time and catch what human eyes miss.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((f, i) => {
              const Icon = f.icon;
              return (
                <div
                  key={i}
                  className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 hover:border-slate-700 transition-all duration-300 hover:shadow-lg hover:shadow-cyan-500/5 group"
                >
                  <div className={`w-10 h-10 rounded-xl border flex items-center justify-center mb-4 ${f.bg} ${f.border}`}>
                    <Icon className={`w-5 h-5 ${f.color}`} />
                  </div>
                  <h3 className="text-sm font-bold text-white mb-2">{f.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{f.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Supported Hardware ── */}
      <section id="hardware" className="px-6 py-20 max-w-6xl mx-auto w-full">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
            Inspect any hardware component.
          </h2>
          <p className="text-sm text-slate-400 mt-3">
            Pre-configured inspection profiles for the most common industrial components.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            {
              icon: Cpu,
              name: 'Motherboards & PCBs',
              code: 'PCB-MCU-V2',
              category: 'Electronics Assembly',
              checks: ['Capacitor & resistor presence', 'IC chip alignment', 'Connector seating', 'Solder bridge defects'],
              color: 'cyan',
            },
            {
              icon: Battery,
              name: 'Battery Modules',
              code: 'BAT-STD-V1',
              category: 'Power Systems',
              checks: ['Cell count & positioning', 'Terminal alignment', 'Tamper seal integrity', 'Casing scratch checks'],
              color: 'amber',
            },
            {
              icon: MemoryStick,
              name: 'RAM Modules',
              code: 'RAM-DDR4-V1',
              category: 'Memory & Expansion',
              checks: ['Gold edge connector pins', 'Batch serial OCR match', 'IC packaging layout', 'Warranty sticker condition'],
              color: 'emerald',
            },
          ].map((hw, i) => {
            const Icon = hw.icon;
            const colorMap = {
              cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
              amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
              emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
            };
            return (
              <div
                key={i}
                className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className={`w-10 h-10 rounded-xl border flex items-center justify-center ${colorMap[hw.color]}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/10 border border-cyan-500/20 text-cyan-300">
                      {hw.code}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-white mb-1">{hw.name}</h3>
                  <p className="text-[11px] text-slate-500 font-mono mb-3">{hw.category}</p>

                  <div className="space-y-1.5">
                    <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Verified Checks:</div>
                    {hw.checks.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-xs text-slate-300">
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
                  <span>Status</span>
                  <span className="text-emerald-400 font-semibold">Supported</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Use Cases ── */}
      <section id="use-cases" className="px-6 py-20 bg-[#09101d] border-y border-slate-800/70">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
              Where VisionForge delivers value.
            </h2>
            <p className="text-sm text-slate-400 mt-3">
              Deploy at any point in your supply chain where visual verification matters.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {useCases.map((uc, i) => {
              const Icon = uc.icon;
              return (
                <div
                  key={i}
                  className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 hover:border-slate-700 transition-all duration-300 flex gap-4"
                >
                  <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 shrink-0 h-fit">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1">{uc.title}</h3>
                    <p className="text-xs text-slate-400 leading-relaxed mb-2">{uc.desc}</p>
                    <div className="text-[11px] font-mono text-cyan-300 font-semibold">{uc.stats}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── CTA Section ── */}
      <section className="px-6 py-24 max-w-4xl mx-auto w-full text-center">
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-transparent to-cyan-500/10 rounded-3xl blur-2xl pointer-events-none" />
          <div className="relative p-10 rounded-3xl bg-[#0b1322] border border-slate-800">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
              Ready to automate your QA inspection?
            </h2>
            <p className="text-sm text-slate-400 max-w-xl mx-auto mt-4">
              Start inspecting hardware components in minutes. No setup fees, no long-term contracts.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-8">
              <Button
                variant="primary"
                size="lg"
                icon={ArrowRight}
                onClick={() => navigate('/login')}
              >
                Get Started Free
              </Button>
              <Button
                variant="secondary"
                size="lg"
                onClick={() => document.getElementById('pipeline')?.scrollIntoView({ behavior: 'smooth' })}
              >
                View Pipeline Details
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="px-6 sm:px-12 py-8 border-t border-slate-800/80 bg-[#070d18]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Logo size="sm" showText={true} />
            <span className="text-slate-700">|</span>
            <span className="text-xs text-slate-500 font-mono">Automated Hardware QA Platform</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-slate-500">
            <span className="flex items-center gap-1"><Lock className="w-3 h-3" /> Secure by Design</span>
            <span className="flex items-center gap-1"><ShieldCheck className="w-3 h-3" /> Audit Compliant</span>
            <span className="flex items-center gap-1"><Globe className="w-3 h-3" /> Multi-Site Ready</span>
          </div>
          <div className="text-xs text-slate-600 font-mono">&copy; {new Date().getFullYear()} VisionForge AI</div>
        </div>
      </footer>
    </div>
  );
};

/* Local helper for Target icon (not in lucide-react) */
function Target({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}
