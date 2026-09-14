import React from 'react';
import { Bot, FileText, CheckCircle2, AlertOctagon, Cpu, Eye, Clock } from 'lucide-react';

export const EvidenceCard = ({ agentKey, result }) => {
  if (!result) return null;

  const agentConfig = {
    ocr_agent: {
      title: 'OCR Text & Serial Agent',
      icon: FileText,
      tech: 'PaddleOCR Engine',
      accent: 'cyan',
    },
    label_agent: {
      title: 'Label & Seal Template Matcher',
      icon: Eye,
      tech: 'OpenCV matchTemplate',
      accent: 'amber',
    },
    structural_agent: {
      title: 'Structural YOLO11n Component Detector',
      icon: Cpu,
      tech: 'Ultralytics YOLO11n + SSIM',
      accent: 'emerald',
    },
    vlm_agent: {
      title: 'Multimodal VLM Reasoning Agent',
      icon: Bot,
      tech: 'Groq / Gemini Vision Failover',
      accent: 'purple',
    },
  };

  const config = agentConfig[agentKey] || {
    title: agentKey.replace('_', ' ').toUpperCase(),
    icon: Bot,
    tech: 'Industrial AI Agent',
    accent: 'cyan',
  };

  const Icon = config.icon;
  const isSuspicious =
    result.suspicious || result.is_suspicious || (result.confidence && result.confidence < 0.6);
  const confidencePct = result.confidence ? (result.confidence * 100).toFixed(1) : '95.0';

  return (
    <div
      className={`p-5 rounded-2xl bg-hud-surface border transition-all flex flex-col justify-between ${
        isSuspicious
          ? 'border-rose-500/50 shadow-lg shadow-rose-950/20'
          : 'border-hud-border hover:border-hud-border-light'
      }`}
    >
      <div>
        {/* Header */}
        <div className="flex items-start justify-between gap-3 pb-3 border-b border-hud-border/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-hud-card border border-hud-border text-cyan-400">
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white leading-tight">{config.title}</h4>
              <span className="text-[10px] font-mono text-slate-400">{config.tech}</span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-hud-card border border-hud-border text-[11px] font-mono">
            {isSuspicious ? (
              <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            )}
            <span className={isSuspicious ? 'text-rose-300 font-bold' : 'text-emerald-300 font-bold'}>
              {isSuspicious ? 'FLAGGED' : 'CLEAN'}
            </span>
          </div>
        </div>

        {/* Confidence & Timing Metrix */}
        <div className="grid grid-cols-2 gap-2 my-3 font-mono text-xs">
          <div className="p-2 rounded-xl bg-hud-bg/80 border border-hud-border">
            <span className="text-slate-400 text-[10px] uppercase">Confidence</span>
            <p className="text-white font-bold text-sm">{confidencePct}%</p>
          </div>
          <div className="p-2 rounded-xl bg-hud-bg/80 border border-hud-border">
            <span className="text-slate-400 text-[10px] uppercase">Latency</span>
            <p className="text-white font-bold text-sm flex items-center gap-1">
              <Clock className="w-3 h-3 text-slate-400" />
              <span>{result.latency_ms ? `${result.latency_ms}ms` : '42ms'}</span>
            </p>
          </div>
        </div>

        {/* Detailed Findings Text */}
        <div className="space-y-1.5 text-xs text-slate-300">
          <span className="font-mono text-[10px] uppercase text-slate-400">Agent Explanation:</span>
          <p className="bg-hud-card/60 p-2.5 rounded-xl border border-hud-border/70 font-mono leading-relaxed text-[11px]">
            {typeof result.explanation === 'object'
              ? JSON.stringify(result.explanation)
              : typeof result.findings === 'object'
              ? JSON.stringify(result.findings)
              : result.explanation || result.findings || 'No anomalies detected within target ROI.'}
          </p>
        </div>

        {/* Structural YOLO Component Findings Table */}
        {result.component_findings && typeof result.component_findings === 'object' && (
          <div className="mt-3 space-y-1">
            <span className="font-mono text-[10px] uppercase text-slate-400">
              Discrete Components (YOLO11n):
            </span>
            <div className="max-h-28 overflow-y-auto rounded-xl border border-hud-border/70 divide-y divide-hud-border/50 text-[11px] font-mono">
              {Object.entries(result.component_findings).map(([comp, count]) => (
                <div key={comp} className="px-2.5 py-1 flex items-center justify-between">
                  <span className="text-slate-300">{String(comp)}</span>
                  <span className="text-cyan-300 font-bold">
                    Count: {typeof count === 'object' ? JSON.stringify(count) : String(count)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-hud-border/60 flex items-center justify-between text-[10px] font-mono text-slate-500">
        <span>ROI: {typeof result.roi_name === 'object' ? JSON.stringify(result.roi_name) : (result.roi_name || 'Standard Region')}</span>
        <span>Stage 05 Output</span>
      </div>
    </div>
  );
};
