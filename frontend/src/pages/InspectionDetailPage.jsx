import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ScanEye,
  ArrowLeft,
  Building2,
  MapPin,
  Layers,
  Calendar,
  Loader2,
  FileDown,
} from 'lucide-react';
import { inspectionsAPI } from '../services/api';
import { usePipelineSSE } from '../hooks/usePipelineSSE';
import { PipelineProgress } from '../components/inspection/PipelineProgress';
import { DualImageCanvas } from '../components/inspection/DualImageCanvas';
import { EvidenceCard } from '../components/inspection/EvidenceCard';
import { VerdictBanner } from '../components/inspection/VerdictBanner';
import { ReviewModal } from '../components/inspection/ReviewModal';
import { Button } from '../components/common/Button';
import { useToast } from '../context/ToastContext';

/**
 * Resolves local file paths or server endpoints into accessible static URLs.
 */
export const resolveImageUrl = (path) => {
  if (!path) return null;
  if (
    path.startsWith('http://') ||
    path.startsWith('https://') ||
    path.startsWith('blob:') ||
    path.startsWith('data:')
  ) {
    return path;
  }
  const normalized = path.replace(/\\/g, '/');
  if (normalized.startsWith('/static/')) {
    return normalized;
  }
  if (normalized.includes('data/inspection_uploads/')) {
    const rel = normalized.split('data/inspection_uploads/')[1];
    return `/static/uploads/${rel}`;
  }
  if (normalized.includes('inspection_uploads/')) {
    const rel = normalized.split('inspection_uploads/')[1];
    return `/static/uploads/${rel}`;
  }
  if (normalized.includes('data/golden_images/')) {
    const rel = normalized.split('data/golden_images/')[1];
    return `/static/golden/${rel}`;
  }
  if (normalized.includes('golden_images/')) {
    const rel = normalized.split('golden_images/')[1];
    return `/static/golden/${rel}`;
  }
  if (!normalized.startsWith('/')) {
    return `/${normalized}`;
  }
  return normalized;
};

export const InspectionDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [inspection, setInspection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reviewModalOpen, setReviewModalOpen] = useState(false);

  // Fetch complete inspection data from API
  const fetchInspection = useCallback(async () => {
    if (!id) return;
    try {
      const data = await inspectionsAPI.get(id);
      setInspection(data);
    } catch (err) {
      console.error('Failed to load inspection:', err);
      toast.error('Failed to load inspection details');
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  const handlePipelineComplete = useCallback(() => {
    fetchInspection();
  }, [fetchInspection]);

  // Hook for live SSE 8-stage progress stream
  const {
    currentStage,
    stageName,
    completedStages,
    status: sseStatus,
    verdict: sseVerdict,
    policyAction: ssePolicyAction,
    detail: sseDetail,
    isDone,
    stages,
  } = usePipelineSSE(id, handlePipelineComplete);

  useEffect(() => {
    fetchInspection();
  }, [fetchInspection]);

  const effectiveStatus = isDone
    ? 'completed'
    : inspection?.status?.toLowerCase() || sseStatus;
  const effectiveVerdict = inspection?.verdict || sseVerdict;
  const effectivePolicy = inspection?.policy_action || ssePolicyAction;

  // Extract memory state
  const memory = inspection?.working_memory || inspection?.memory || {};

  // Extract URLs
  const rawGoldenPath =
    memory.golden_image_path ||
    memory.golden_image_url ||
    inspection?.golden_reference?.image_path;
  const goldenImageUrl = resolveImageUrl(rawGoldenPath);

  const rawInspectionPath =
    (inspection?.image_paths && inspection.image_paths[0]) ||
    (memory.image_paths && memory.image_paths[0]) ||
    inspection?.image_url;
  const inspectionImageUrl = resolveImageUrl(rawInspectionPath);

  // Extract fused evidence and recommendations
  const fusedEvidence = memory.fused_evidence || {};
  const judgeStage = (memory.stage_history || []).find(
    (s) => s.stage === 'judge' || s.stage === 'Stage 7'
  );
  const judgeData = judgeStage?.data || {};

  const effectiveFraudProb =
    inspection?.fraud_probability ??
    memory.fraud_probability ??
    fusedEvidence.fraud_score;

  const effectiveFraudCategory =
    inspection?.fraud_category ??
    memory.fraud_category ??
    fusedEvidence.primary_category;

  const judgeRecommendations =
    Array.isArray(judgeData.recommendations) && judgeData.recommendations.length > 0
      ? judgeData.recommendations
      : (Array.isArray(memory?.judge_verdict?.recommendations) && memory.judge_verdict.recommendations.length > 0
          ? memory.judge_verdict.recommendations
          : (Array.isArray(fusedEvidence?.recommendations) && fusedEvidence.recommendations.length > 0
              ? fusedEvidence.recommendations
              : null));
  const effectiveRecommendations =
    judgeRecommendations ||
    (effectiveVerdict === 'reject' || effectivePolicy === 'quarantine'
      ? [
          'Quarantine batch immediately from active production line',
          'Initiate supplier counterfeit/rework root cause inquiry',
          'Inspect serial marking under 20x optical magnification',
        ]
      : effectiveVerdict === 'review' || effectivePolicy === 'vendor_verification' || effectivePolicy === 'retake'
      ? [
          'Perform manual optical inspection on target ROI',
          'Verify component lot date code with authorized distributor',
        ]
      : ['Release batch for production assembly and fulfillment']);

  const effectiveDetectedIssues =
    fusedEvidence.detected_issue_descriptions ||
    fusedEvidence.detected_issues ||
    (judgeData.detected_issues || []);

  // Map evidence records from DB to the 4 Agent Cards
  const evidenceRecords = inspection?.evidence_records || [];

  const findRecord = (agentKeywords) => {
    return evidenceRecords.find((r) => {
      const agentType = (r.agent_type || r.detector_name || '').toLowerCase();
      return agentKeywords.some((k) => agentType.includes(k));
    });
  };

  const ocrRecord = findRecord(['ocr']);
  const labelRecord = findRecord(['label']);
  const structuralRecord = findRecord(['structural', 'yolo']);
  const vlmRecord = findRecord(['vlm', 'visual', 'judge']);

  const formatFinding = (rec, defaultConfig) => {
    if (rec) {
      const raw = rec.raw_output || {};
      const ev = rec.evidence || {};
      // Build dynamic engine/provider label from backend telemetry
      let techLabel = null;
      if (rec.detector_name && rec.detector_name.includes('ocr')) {
        const engine = ev.engine_used;
        techLabel = engine === 'paddleocr' ? 'PaddleOCR Engine' : engine === 'easyocr' ? 'EasyOCR Engine' : 'OCR Engine';
      } else if (rec.detector_name && (rec.detector_name.includes('vlm') || rec.detector_name.includes('visual'))) {
        const provider = ev.provider || raw.provider;
        const model = ev.model || raw.model;
        techLabel = provider
          ? `${provider === 'gemini' ? 'Gemini' : 'Groq'}${model ? ` ${model}` : ''}`
          : 'LLM Vision Analysis';
      } else if (rec.detector_name && rec.detector_name.includes('structural')) {
        techLabel = 'Ultralytics YOLO11n + SSIM';
      } else if (rec.detector_name && rec.detector_name.includes('label')) {
        techLabel = 'OpenCV matchTemplate';
      }

      return {
        explanation:
          rec.explanation ||
          rec.evidence_summary ||
          raw.explanation ||
          defaultConfig.explanation,
        confidence: rec.confidence ?? raw.confidence ?? null,
        latency_ms:
          rec.processing_time_ms ?? raw.processing_time_ms ?? null,
        inconclusive: ev.inconclusive === true || rec.inconclusive === true || ev.match_status === 'no_text_detected',
        has_defect: ev.has_defect === true || rec.has_defect === true || raw.has_defect === true,
        failed: rec.failed === true || raw.failed === true || ev.failed === true,
        is_suspicious:
          rec.failed ||
          raw.failed ||
          ev.failed ||
          (rec.confidence != null && rec.confidence < 0.65) ||
          raw.is_anomaly ||
          raw.is_suspicious ||
          ev.is_anomaly ||
          ev.is_suspicious ||
          false,
        component_findings:
          rec.component_findings || raw.component_findings || raw.counts || null,
        specific_differences: ev.specific_differences || raw.specific_differences || [],
        component_count_expected: ev.component_count_expected ?? raw.component_count_expected ?? null,
        component_count_observed: ev.component_count_observed ?? raw.component_count_observed ?? null,
        roi_name: rec.roi_id || rec.roi_type || defaultConfig.roi_name || 'Target ROI',
        techLabel,
      };
    }
    return {
      explanation: defaultConfig.explanation,
      confidence: null,
      latency_ms: null,
      inconclusive: false,
      has_defect: false,
      is_suspicious: false,
      roi_name: defaultConfig.roi_name,
      techLabel: defaultConfig.techLabel,
    };
  };

  const findings = {
    ocr_agent: formatFinding(ocrRecord, {
      explanation: 'OCR engine extracts and validates markings and serial codes against reference baseline.',
      roi_name: 'Serial & Batch Block',
      techLabel: 'OCR Engine',
    }),
    label_agent: formatFinding(labelRecord, {
      explanation: 'OpenCV template correlation inspects QC seals, logos, and print alignment.',
      roi_name: 'QC Label Region',
      techLabel: 'OpenCV matchTemplate',
    }),
    structural_agent: formatFinding(structuralRecord, {
      explanation: 'YOLO11n + SSIM verifies discrete components, counts, and spatial layout.',
      roi_name: 'Component Matrix',
      techLabel: 'Ultralytics YOLO11n + SSIM',
    }),
    vlm_agent: formatFinding(vlmRecord, {
      explanation: 'Multimodal VLM performs cognitive reasoning over surface defects and physical anomalies.',
      roi_name: 'Surface Inspection Field',
      techLabel: 'LLM Vision Analysis',
    }),
  };

  // Extract YOLO detections from structural record or memory
  const structuralRaw = structuralRecord?.raw_output || {};
  const yoloDetections =
    structuralRaw.detections ||
    structuralRaw.yolo_detections ||
    memory.yolo_detections ||
    [];

  // Extract ROI regions from template, execution plan, or memory
  const roiTemplate = memory.roi_template || inspection?.roi_template || {};
  const roiSchedulerStage = (memory.stage_history || []).find(
    (s) => s.stage === 'roi_scheduler' || s.stage === 'Stage 4'
  );
  const roiSchedulerData = roiSchedulerStage?.data || {};
  const roiRegions =
    roiTemplate.regions ||
    roiSchedulerData.items ||
    memory.roi_regions ||
    inspection?.roi_regions ||
    [];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-hud-border/70">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="p-2.5 rounded-xl bg-hud-surface border border-hud-border text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider">
                Inspection Session
              </span>
              <span className="text-xs font-mono text-slate-500">ID: {id?.slice(0, 12)}...</span>
            </div>
            <h2 className="text-xl font-black text-white tracking-tight uppercase font-telemetry mt-0.5">
              {inspection?.part_code ||
                memory.part_code ||
                inspection?.product_type?.toUpperCase() ||
                'Hardware QA Target'}
            </h2>
          </div>
        </div>

        {/* Metadata Badges */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-slate-300">
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-hud-surface border border-hud-border min-w-0 max-w-full">
            <Building2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <span className="truncate">Vendor: {inspection?.vendor_name || '—'}</span>
          </span>
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-hud-surface border border-hud-border">
            <MapPin className="w-3.5 h-3.5 text-amber-400" />
            <span>Loc: {inspection?.location || '—'}</span>
          </span>
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-hud-surface border border-hud-border">
            <Layers className="w-3.5 h-3.5 text-purple-400" />
            <span>Type: {inspection?.product_type?.toUpperCase() || memory?.product_type?.toUpperCase() || '—'}</span>
          </span>
        </div>
      </div>

      {/* 8-Stage Execution Pipeline Stepper */}
      <PipelineProgress
        stages={stages}
        currentStage={currentStage}
        completedStages={completedStages}
        status={effectiveStatus}
        stageDetails={sseDetail}
      />

      {/* When completed or has verdict: Render Decision Banner */}
      {(effectivePolicy || effectiveVerdict) && (
        <VerdictBanner
          inspectionId={id}
          reportId={id}
          verdict={effectiveVerdict}
          policyAction={effectivePolicy}
          confidence={inspection?.judge_confidence || memory.overall_confidence}
          fraudProbability={effectiveFraudProb}
          fraudCategory={effectiveFraudCategory}
          rootCause={inspection?.root_cause || memory.root_cause}
          recommendations={effectiveRecommendations}
          detectedIssues={effectiveDetectedIssues}
          reviewStatus={inspection?.review_decision || inspection?.review_status}
          reviewerNotes={inspection?.reviewer_comment || inspection?.reviewer_notes}
          onOpenReview={() => setReviewModalOpen(true)}
        />
      )}

      {/* Synchronized Dual Image Canvas */}
      <DualImageCanvas
        goldenImageUrl={goldenImageUrl}
        inspectionImageUrl={inspectionImageUrl}
        yoloDetections={yoloDetections}
        roiRegions={roiRegions}
        partCode={inspection?.part_code || memory.part_code || inspection?.product_type}
      />

      {/* 4 Specialized AI Evidence Cards */}
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-hud-border/70 mb-4">
          <h3 className="text-base font-bold text-white tracking-wide font-telemetry">
            Multi-Agent Evidence Swarm Findings
          </h3>
          <span className="text-xs font-mono text-slate-400">
            Stage 05 Parallel Agent Dissection
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <EvidenceCard agentKey="ocr_agent" result={findings.ocr_agent} />
          <EvidenceCard agentKey="label_agent" result={findings.label_agent} />
          <EvidenceCard agentKey="structural_agent" result={findings.structural_agent} />
          <EvidenceCard agentKey="vlm_agent" result={findings.vlm_agent} />
        </div>
      </div>

      {/* Human Review Modal */}
      <ReviewModal
        isOpen={reviewModalOpen}
        onClose={() => setReviewModalOpen(false)}
        inspectionId={id}
        currentVerdict={effectiveVerdict || 'ACCEPT'}
        onReviewComplete={fetchInspection}
      />
    </div>
  );
};
