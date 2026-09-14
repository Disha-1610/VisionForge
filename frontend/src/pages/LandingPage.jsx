import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Cpu,
  FileText,
  Layers,
  Search,
  Eye,
  Microscope,
  Binary,
  Check,
  Zap,
  Sliders,
  Sparkles,
  ChevronRight,
} from 'lucide-react';
import { Button } from '../components/common/Button';
import { Logo } from '../components/common/Logo';

export const LandingPage = () => {
  const navigate = useNavigate();
  const [activeStage, setActiveStage] = useState(1);

  // Auto-advance simulation timer
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStage((prev) => (prev >= 8 ? 1 : prev + 1));
    }, 3200);
    return () => clearInterval(timer);
  }, []);

  const stages = [
    {
      num: 1,
      name: 'Image Preflight',
      role: 'Resolution & Lighting Check',
      summary: 'Verifies the captured image is sharp, well-lit, and meets minimum resolution requirements before running inspection.',
      input: 'Raw camera photo / upload',
      output: 'Validated image tensor',
      statusTag: 'Gatekeeper',
    },
    {
      num: 2,
      name: 'Authenticity & Forensics',
      role: 'Digital Tampering Check',
      summary: 'Inspects error levels, compression consistency, and camera metadata to ensure the image is an authentic physical photograph.',
      input: 'Image stream',
      output: 'Authenticity score & flags',
      statusTag: 'Integrity',
    },
    {
      num: 3,
      name: 'Reference Matching',
      role: 'Golden Master Comparison',
      summary: 'Compares the incoming unit against the verified golden reference for that part code to detect overall visual drift.',
      input: 'Part catalog & golden image',
      output: 'Visual similarity index',
      statusTag: 'Baseline',
    },
    {
      num: 4,
      name: 'Region Mapping',
      role: 'ROI Grid Scheduling',
      summary: 'Extracts coordinates for critical inspection zones — chips, capacitors, serial labels, and connectors.',
      input: 'Component template',
      output: 'Scheduled inspection zones',
      statusTag: 'Targeting',
    },
    {
      num: 5,
      name: 'Specialized Inspection',
      role: 'Parallel Visual Analysis',
      summary: 'Runs focused checks across discrete components, printed serial text, QC seal condition, and surface anomalies.',
      input: 'Targeted image crops',
      output: 'Independent evidence logs',
      statusTag: 'Analysis',
    },
    {
      num: 6,
      name: 'Evidence Fusion',
      role: 'Anomaly Aggregation',
      summary: 'Combines findings from all inspection zones into a single structured list, prioritizing high-severity defects.',
      input: 'All agent findings',
      output: 'Fused anomaly list',
      statusTag: 'Synthesis',
    },
    {
      num: 7,
      name: 'AI Adjudication',
      role: 'Root Cause & Risk Scoring',
      summary: 'Evaluates the complete evidence package to determine the overall risk score, root cause explanation, and suggested action.',
      input: 'Fused evidence + catalog spec',
      output: 'Verdict & technical justification',
      statusTag: 'Decision',
    },
    {
      num: 8,
      name: 'Policy & Report',
      role: 'Routing & PDF Generation',
      summary: 'Applies your QA policy (Accept, Quarantine, Reject, Retake) and compiles a comprehensive PDF audit report.',
      input: 'Verdict + policy rules',
      output: 'Final action & PDF dossier',
      statusTag: 'Execution',
    },
  ];

  const inspectionProfiles = [
    {
      name: 'Motherboard & MCU Boards',
      code: 'PCB-MCU-V2',
      category: 'Electronics Assembly',
      checks: ['Capacitor & resistor presence', 'IC chip alignment', 'Connector seating', 'Solder bridge defects'],
      status: 'Supported',
    },
    {
      name: 'Industrial Battery Modules',
      code: 'BAT-STD-V1',
      category: 'Power Systems',
      checks: ['Cell count & positioning', 'Terminal alignment', 'Tamper seal integrity', 'Casing scratch checks'],
      status: 'Supported',
    },
    {
      name: 'High-Speed RAM Modules',
      code: 'RAM-DDR4-V1',
      category: 'Memory & Expansion',
      checks: ['Gold edge connector pins', 'Batch serial OCR match', 'IC packaging layout', 'Warranty sticker condition'],
      status: 'Supported',
    },
  ];

  const coreChecks = [
    {
      title: 'Component Placement & Count',
      desc: 'Checks if every discrete chip, resistor, capacitor, and connector is present, correctly aligned, and in the right location.',
      icon: Microscope,
    },
    {
      title: 'Serial & Batch Code Verification',
      desc: 'Reads printed or laser-etched serials, lot numbers, and ratings, comparing them directly against your expected catalog data.',
      icon: Binary,
    },
    {
      title: 'Warranty & QC Seal Inspection',
      desc: 'Identifies scratched, peeled, broken, or misaligned security stickers and QC stamps indicating tampering or prior opening.',
      icon: Eye,
    },
    {
      title: 'Surface & Solder Defect Detection',
      desc: 'Spots physical anomalies like solder bridging, thermal discoloration, surface burns, and scratched PCB traces.',
      icon: Sparkles,
    },
  ];

  return (
    <div className="min-h-screen bg-[#070d18] text-slate-100 flex flex-col justify-between selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Top Navigation */}
      <header className="px-6 sm:px-12 py-4 border-b border-slate-800/80 flex items-center justify-between sticky top-0 z-50 bg-[#070d18]/90 backdrop-blur-md">
        <Logo size="md" subtitle="online" animate={true} onClick={() => navigate('/')} />

        <nav className="hidden md:flex items-center gap-7 text-xs font-medium text-slate-400">
          <a href="#pipeline" className="hover:text-slate-200 transition-colors">
            8-Stage Pipeline
          </a>
          <a href="#checks" className="hover:text-slate-200 transition-colors">
            What We Check
          </a>
          <a href="#hardware" className="hover:text-slate-200 transition-colors">
            Supported Hardware
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/login')}>
            Sign In
          </Button>
          <Button variant="primary" size="sm" icon={ArrowRight} onClick={() => navigate('/login')}>
            Open Workstation
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative px-6 pt-16 pb-16 max-w-6xl mx-auto w-full">
        <div className="text-center max-w-3xl mx-auto space-y-5">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-xs font-medium text-cyan-300">
            <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
            <span>Automated Visual Inspection for Electronics QA</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
            Catch hardware defects and serial mismatches{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-sky-300">
              before assembly.
            </span>
          </h1>

          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl mx-auto">
            VisionForge compares incoming boards and modules against golden reference specifications.
            It identifies missing components, verify printed serials, and flags surface anomalies through
            an automated 8-stage inspection pipeline.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button
              variant="primary"
              size="md"
              icon={ArrowRight}
              onClick={() => navigate('/login')}
              className="w-full sm:w-auto"
            >
              Start Inspection
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={() => {
                const el = document.getElementById('pipeline');
                el?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="w-full sm:w-auto"
            >
              See How It Works
            </Button>
          </div>
        </div>

        {/* Live UI Mockup / Sample Inspection Card */}
        <div className="mt-12 rounded-2xl bg-[#0b1322] border border-slate-800 shadow-xl overflow-hidden">
          {/* Mockup Header */}
          <div className="px-5 py-3 border-b border-slate-800/80 bg-[#080f1d] flex items-center justify-between text-xs font-mono text-slate-400">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span className="ml-2 text-slate-300 font-semibold">Inspection Result • PCB-MCU-V2</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-0.5 rounded bg-rose-500/15 border border-rose-500/30 text-rose-300 font-bold">
                QUARANTINE
              </span>
              <span className="text-slate-400">Risk: 82%</span>
            </div>
          </div>

          {/* Mockup Body */}
          <div className="p-5 sm:p-6 grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Left: Component Info */}
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

            {/* Middle: Detected Issues */}
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

            {/* Right: AI Adjudication & PDF Action */}
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
                <span>Download Audit PDF Report</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 8-Stage Pipeline Section */}
      <section id="pipeline" className="px-6 py-16 bg-[#09101d] border-y border-slate-800/70">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-10">
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              The 8-Stage Inspection Pipeline
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-2">
              Each unit passes through a deterministic sequence of visual and logical verification stages.
            </p>
          </div>

          {/* Pipeline Stage Buttons */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
            {stages.map((st) => {
              const isCurrent = activeStage === st.num;
              const isPast = activeStage > st.num;

              return (
                <button
                  key={st.num}
                  type="button"
                  onClick={() => setActiveStage(st.num)}
                  className={`p-3 rounded-xl border text-left transition-all duration-200 flex flex-col justify-between ${
                    isCurrent
                      ? 'bg-cyan-950/60 border-cyan-400 text-white shadow-md shadow-cyan-500/10 scale-102'
                      : isPast
                      ? 'bg-[#0b1424] border-emerald-500/40 text-emerald-300'
                      : 'bg-[#060c16] border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between w-full mb-1.5 font-mono text-xs">
                    <span className="font-bold">0{st.num}</span>
                    {isPast ? (
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    ) : isCurrent ? (
                      <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                    ) : null}
                  </div>
                  <div className="text-xs font-semibold leading-tight">{st.name}</div>
                  <div className="text-[10px] text-slate-500 font-mono mt-2 truncate">{st.statusTag}</div>
                </button>
              );
            })}
          </div>

          {/* Active Stage Detail Box */}
          {stages[activeStage - 1] && (
            <div className="mt-6 p-5 sm:p-6 rounded-2xl bg-[#0b1322] border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
              <div className="space-y-1.5 max-w-2xl">
                <div className="flex items-center gap-2 font-mono text-xs text-cyan-400 font-semibold">
                  <span>STAGE 0{stages[activeStage - 1].num}</span>
                  <span>•</span>
                  <span>{stages[activeStage - 1].role}</span>
                </div>
                <h3 className="text-base sm:text-lg font-bold text-white">
                  {stages[activeStage - 1].name}
                </h3>
                <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  {stages[activeStage - 1].summary}
                </p>
              </div>

              <div className="shrink-0 p-3.5 rounded-xl bg-[#060b14] border border-slate-800/80 font-mono text-xs space-y-1.5 w-full md:w-64">
                <div className="flex justify-between text-slate-400">
                  <span>Input:</span>
                  <span className="text-slate-200 text-right truncate ml-2">{stages[activeStage - 1].input}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Output:</span>
                  <span className="text-cyan-300 text-right truncate ml-2">{stages[activeStage - 1].output}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Core Checks Section */}
      <section id="checks" className="px-6 py-16 max-w-6xl mx-auto w-full">
        <div className="text-center max-w-xl mx-auto mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            What VisionForge Inspects
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-2">
            Targeted visual defect detection across critical physical features of the board.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {coreChecks.map((chk, i) => {
            const Icon = chk.icon;
            return (
              <div
                key={i}
                className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 hover:border-slate-700 transition-colors flex gap-4"
              >
                <div className="p-3 rounded-xl bg-[#060b14] border border-slate-800 text-cyan-400 shrink-0 h-fit">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white mb-1.5">{chk.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{chk.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Supported Hardware Catalog */}
      <section id="hardware" className="px-6 py-16 bg-[#09101d] border-t border-slate-800/70">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-xl mx-auto mb-10">
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Supported Hardware Profiles
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-2">
              Pre-configured ROI coordinate templates and golden reference specifications.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {inspectionProfiles.map((prof, i) => (
              <div
                key={i}
                className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3 text-xs font-mono">
                    <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 font-semibold">
                      {prof.code}
                    </span>
                    <span className="text-slate-500">{prof.category}</span>
                  </div>
                  <h3 className="text-sm font-bold text-white mb-3">{prof.name}</h3>

                  <div className="space-y-1.5">
                    <div className="text-[11px] font-mono text-slate-500 uppercase tracking-wider">
                      Verified Features:
                    </div>
                    {prof.checks.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-xs text-slate-300">
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
                  <span>Profile Status</span>
                  <span className="text-emerald-400 font-semibold">{prof.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Call to Action */}
      <section className="px-6 py-16 max-w-4xl mx-auto w-full text-center space-y-5">
        <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
          Ready to run an inspection?
        </h2>
        <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto">
          Sign in to the QA workstation to upload hardware images, run the 8-stage pipeline,
          and download complete audit reports.
        </p>
        <div className="pt-2">
          <Button variant="primary" size="md" icon={ArrowRight} onClick={() => navigate('/login')}>
            Open Workstation
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-6 sm:px-12 py-6 border-t border-slate-800/80 text-xs text-slate-500 font-mono flex flex-col sm:flex-row items-center justify-between gap-4 bg-[#070d18]">
        <div className="flex items-center gap-2">
          <Logo size="sm" showText={true} />
          <span className="text-slate-700">|</span>
          <span>Automated Hardware QA Platform</span>
        </div>
        <div>VisionForge AI • Fast, Grounded Visual Inspection</div>
      </footer>
    </div>
  );
};
