import React from 'react';
import MarkdownText from './MarkdownText';
import {
  Bot,
  FileText,
  CheckCircle2,
  AlertOctagon,
  AlertTriangle,
  Cpu,
  Eye,
  Clock,
  Check,
  X,
  Layers,
} from 'lucide-react';

/**
 * Normalizes component findings from array or object into a structured list.
 */
const parseComponentFindings = (findings) => {
  if (!findings) return [];
  if (Array.isArray(findings)) {
    return findings.map((item, idx) => {
      if (typeof item === 'object' && item !== null) {
        const name = (item.class_name || item.name || `Component ${idx + 1}`).replace(/_/g, ' ');
        const golden = item.golden_count ?? item.expected_count ?? 0;
        const inspection = item.inspection_count ?? item.observed_count ?? item.count ?? 0;
        const missing = item.missing ?? Math.max(0, golden - inspection);
        const extra = item.extra ?? Math.max(0, inspection - golden);
        const isMatch = item.status === 'match' || (missing === 0 && extra === 0);
        return { name, golden, inspection, missing, extra, isMatch };
      }
      return { name: String(item), golden: '-', inspection: '-', missing: 0, extra: 0, isMatch: true };
    });
  }
  if (typeof findings === 'object') {
    return Object.entries(findings).map(([key, val]) => {
      if (typeof val === 'object' && val !== null) {
        const name = (val.class_name || val.name || key).replace(/_/g, ' ');
        const golden = val.golden_count ?? val.expected_count ?? 0;
        const inspection = val.inspection_count ?? val.observed_count ?? val.count ?? 0;
        const missing = val.missing ?? Math.max(0, golden - inspection);
        const extra = val.extra ?? Math.max(0, inspection - golden);
        const isMatch = val.status === 'match' || (missing === 0 && extra === 0);
        return { name, golden, inspection, missing, extra, isMatch };
      }
      return {
        name: key.replace(/_/g, ' '),
        golden: '-',
        inspection: typeof val === 'number' ? val : String(val),
        missing: 0,
        extra: 0,
        isMatch: true,
      };
    });
  }
  return [];
};

export const EvidenceCard = ({ agentKey, result }) => {
  if (!result) return null;

  const agentConfig = {
    ocr_agent: {
      title: 'OCR Text & Serial Agent',
      icon: FileText,
      tech: 'OCR Engine',
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
      tech: 'LLM Vision Analysis',
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

  // Dynamic tech label from backend data
  const backendTech = result.techLabel || null;
  const techLabel = backendTech || config.tech;

  const isInconclusive = result.inconclusive === true || result.match_status === 'no_text_detected';

  const discreteComponents = parseComponentFindings(result.component_findings);
  const hasComponentMismatch = discreteComponents.some((c) => !c.isMatch);

  // Robust check: inspect text for obvious defects even if flag was missing
  const rawExplanation = typeof result.explanation === 'string' ? result.explanation : (typeof result.findings === 'string' ? result.findings : '');
  const lowerExplanation = rawExplanation.toLowerCase();
  const defectTerms = [
    'missing',
    'mismatch',
    'anomaly detected',
    'defect',
    'tamper',
    'swelling',
    'corrosion',
    'damage',
    'scratch',
    'crack',
    'burn',
    'absence',
    'below standard',
    'critical',
    'discrepanc',
    'counterfeit',
    'failed',
  ];
  const textHasDefect = defectTerms.some((term) => lowerExplanation.includes(term));

  const isSuspicious =
    !isInconclusive &&
    (result.suspicious === true ||
      result.is_suspicious === true ||
      result.has_defect === true ||
      result.failed === true ||
      hasComponentMismatch ||
      textHasDefect ||
      (result.confidence != null && result.confidence < 0.6));

  const displayExplanation = isSuspicious
    ? rawExplanation
        .replace(/\s*—\s*No visual defects detected\.?/gi, '')
        .replace(/\s*—\s*No visible defect\.?/gi, '')
    : rawExplanation;

  const hasConfidence = result.confidence != null && result.confidence !== undefined;
  const confidenceText = hasConfidence
    ? `${(Number(result.confidence) * (Number(result.confidence) <= 1 ? 100 : 1)).toFixed(1)}%`
    : '—';

  const latencyText =
    result.latency_ms != null && result.latency_ms !== undefined
      ? `${result.latency_ms}ms`
      : '—';

  return (
    <div
      className={`p-4 sm:p-5 rounded-2xl bg-hud-surface border transition-all flex flex-col justify-between ${
        isSuspicious
          ? 'border-rose-500/50 shadow-lg shadow-rose-950/20'
          : isInconclusive
          ? 'border-amber-500/50 shadow-lg shadow-amber-950/20'
          : 'border-hud-border hover:border-hud-border-light'
      }`}
    >
      <div>
        {/* Header */}
        <div className="flex items-start justify-between gap-3 pb-3 border-b border-hud-border/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-hud-card border border-hud-border text-cyan-400 shrink-0">
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white leading-tight">{config.title}</h4>
              <span className="text-[10px] font-mono text-slate-400">{techLabel}</span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-hud-card border border-hud-border text-[11px] font-mono shrink-0">
            {isInconclusive ? (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-amber-300 font-bold">INCONCLUSIVE</span>
              </>
            ) : isSuspicious ? (
              <>
                <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
                <span className="text-rose-300 font-bold">FLAGGED</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-300 font-bold">CLEAN</span>
              </>
            )}
          </div>
        </div>

        {/* Confidence & Timing Metrix */}
        <div className="grid grid-cols-2 gap-2 my-3 font-mono text-xs">
          <div className="p-2.5 rounded-xl bg-hud-bg/80 border border-hud-border">
            <span className="text-slate-400 text-[10px] uppercase tracking-wider">Confidence</span>
            <p className="text-white font-bold text-sm mt-0.5">{confidenceText}</p>
          </div>
          <div className="p-2.5 rounded-xl bg-hud-bg/80 border border-hud-border">
            <span className="text-slate-400 text-[10px] uppercase tracking-wider">Latency</span>
            <p className="text-white font-bold text-sm flex items-center gap-1.5 mt-0.5">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span>{latencyText}</span>
            </p>
          </div>
        </div>

        {/* Markdown Agent Explanation */}
        <div className="space-y-1.5 text-xs text-slate-300">
          <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
            Agent Explanation:
          </span>
          <div className="bg-hud-card/60 p-3.5 rounded-xl border border-hud-border/70">
            <MarkdownText text={displayExplanation || result.explanation || result.findings} />
          </div>
        </div>

        {/* VLM Specific Differences */}
        {Array.isArray(result.specific_differences) && result.specific_differences.length > 0 && (
          <div className="mt-3 space-y-1.5">
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
              Specific Differences Found:
            </span>
            <ul className="space-y-1">
              {result.specific_differences.map((diff, idx) => (
                <li
                  key={idx}
                  className="px-3 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-[11px] font-mono text-rose-200 flex items-start gap-2"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mt-1.5 shrink-0" />
                  <span>{diff}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* VLM Component Count Comparison */}
        {result.component_count_expected != null && result.component_count_observed != null && (
          <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[11px]">
            <div className="px-3 py-2 rounded-xl bg-hud-bg/80 border border-hud-border">
              <span className="text-slate-400 text-[10px] uppercase">Expected</span>
              <p className="text-cyan-300 font-bold text-sm mt-0.5">
                {result.component_count_expected}
              </p>
            </div>
            <div className="px-3 py-2 rounded-xl bg-hud-bg/80 border border-hud-border">
              <span className="text-slate-400 text-[10px] uppercase">Observed</span>
              <p
                className={`font-bold text-sm mt-0.5 ${
                  result.component_count_observed !== result.component_count_expected
                    ? 'text-rose-400'
                    : 'text-emerald-300'
                }`}
              >
                {result.component_count_observed}
              </p>
            </div>
          </div>
        )}

        {/* Discrete Components (YOLO11n) Structured HUD Table */}
        {discreteComponents.length > 0 && (
          <div className="mt-3 space-y-1.5">
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>Discrete Components (YOLO11n):</span>
              <span className="text-[10px] text-cyan-400 font-normal">
                {discreteComponents.length} Verified
              </span>
            </span>

            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {discreteComponents.map((comp, idx) => (
                <div
                  key={idx}
                  className="px-2.5 sm:px-3 py-2 rounded-xl bg-hud-card/70 border border-hud-border flex flex-wrap sm:flex-nowrap items-center justify-between gap-1.5 sm:gap-3 text-xs font-mono"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Layers className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                    <span className="text-white font-medium capitalize truncate">
                      {comp.name}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 sm:gap-3 shrink-0 flex-wrap sm:flex-nowrap">
                    <span className="text-slate-400 text-[11px]">
                      Ref: <strong className="text-slate-200">{comp.golden}</strong>
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      Found:{' '}
                      <strong className={comp.isMatch ? 'text-emerald-300' : 'text-rose-400'}>
                        {comp.inspection}
                      </strong>
                    </span>

                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase flex items-center gap-1 ${
                        comp.isMatch
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                      }`}
                    >
                      {comp.isMatch ? (
                        <>
                          <Check className="w-3 h-3" />
                          <span>MATCH</span>
                        </>
                      ) : (
                        <>
                          <X className="w-3 h-3" />
                          <span>MISMATCH</span>
                        </>
                      )}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-hud-border/60 flex items-center justify-between text-[10px] font-mono text-slate-500">
        <span>
          ROI: {typeof result.roi_name === 'object' ? JSON.stringify(result.roi_name) : (result.roi_name || 'Standard Region')}
        </span>
        <span>Stage 05 Output</span>
      </div>
    </div>
  );
};
