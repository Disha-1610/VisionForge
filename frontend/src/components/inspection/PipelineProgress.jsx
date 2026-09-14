import React from 'react';
import { CheckCircle2, AlertCircle, Loader2, Zap } from 'lucide-react';

/**
 * Defensively format arbitrary telemetry payloads into clean human-readable strings.
 */
export const formatTelemetryDetail = (detail) => {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  if (typeof detail === 'number' || typeof detail === 'boolean') return String(detail);
  if (typeof detail === 'object') {
    if (detail.explanation) return String(detail.explanation);
    if (detail.root_cause) return String(detail.root_cause);
    if (detail.detail) {
      return typeof detail.detail === 'object'
        ? formatTelemetryDetail(detail.detail)
        : String(detail.detail);
    }
    if (detail.error) return String(detail.error);
    if (detail.reason) return String(detail.reason);
    if (detail.policy_action) return `Policy Action: ${String(detail.policy_action).toUpperCase()}`;
    if (detail.template_id) return `Template: ${detail.template_id} (${detail.total_rois || 0} ROIs)`;
    if (detail.fraud_score !== undefined) {
      return `Composite Fraud Score: ${(Number(detail.fraud_score) * 100).toFixed(1)}%`;
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return 'Active telemetry signal received';
    }
  }
  return String(detail);
};

export const PipelineProgress = ({
  stages,
  currentStage,
  completedStages = [],
  status, // 'running' | 'completed' | 'failed'
  stageDetails,
}) => {
  const displayDetail = formatTelemetryDetail(stageDetails);

  return (
    <div className="p-6 rounded-3xl bg-hud-surface border border-hud-border shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-hud-border/70 mb-6">
        <div className="flex items-center gap-3">
          <span
            className={`w-3 h-3 rounded-full ${
              status === 'completed'
                ? 'bg-emerald-400'
                : status === 'failed'
                ? 'bg-rose-400'
                : 'bg-cyan-400 animate-ping'
            }`}
          />
          <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
            Autonomous 8-Stage Execution Pipeline
          </h3>
        </div>

        <div className="text-xs font-mono text-slate-400">
          Status:{' '}
          <span
            className={`font-bold uppercase ${
              status === 'completed'
                ? 'text-emerald-400'
                : status === 'failed'
                ? 'text-rose-400'
                : 'text-cyan-400'
            }`}
          >
            {status}
          </span>
        </div>
      </div>

      {/* 8-Node Horizontal Connector Stepper */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 relative">
        {stages.map((st) => {
          const isDone = completedStages.includes(st.id);
          const isCurrent = currentStage === st.id && status === 'running';
          const isFailed = status === 'failed' && currentStage === st.id;

          let nodeStyle = 'bg-hud-card/60 border-hud-border/50 text-slate-500';
          let icon = <span className="text-xs font-mono font-bold">0{st.id}</span>;

          if (isDone) {
            nodeStyle = 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300';
            icon = <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
          } else if (isCurrent) {
            nodeStyle =
              'bg-cyan-950/70 border-cyan-400 text-cyan-200 shadow-lg shadow-cyan-500/25 animate-pulse';
            icon = <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />;
          } else if (isFailed) {
            nodeStyle = 'bg-rose-950/70 border-rose-500 text-rose-300';
            icon = <AlertCircle className="w-4 h-4 text-rose-400" />;
          }

          return (
            <div
              key={st.id}
              className={`p-3.5 rounded-2xl border transition-all duration-300 flex flex-col justify-between ${nodeStyle}`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono text-slate-400">Stage {st.id}</span>
                  {icon}
                </div>
                <h4 className="text-xs font-bold text-white leading-tight">{st.label}</h4>
              </div>
              <p className="text-[10px] text-slate-400 font-mono mt-2 leading-relaxed">
                {st.description}
              </p>
            </div>
          );
        })}
      </div>

      {displayDetail && (
        <div className="mt-4 p-3 rounded-xl bg-hud-bg/80 border border-hud-border text-xs font-mono text-slate-300 flex items-center justify-between gap-4">
          <span className="shrink-0 text-slate-400">Active Pipeline Telemetry:</span>
          <span className="text-cyan-400 font-bold truncate text-right">{displayDetail}</span>
        </div>
      )}
    </div>
  );
};
