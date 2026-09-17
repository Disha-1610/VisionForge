import { useState, useEffect, useRef, useCallback } from 'react';
import { inspectionsAPI } from '../services/api';

export const STAGES = [
  { id: 1, name: 'quality_check', label: 'Quality & Intake', description: 'Resolution, blur & lighting validation' },
  { id: 2, name: 'authenticity_check', label: 'Authenticity Check', description: 'EXIF metadata, ELA & noise consistency' },
  { id: 3, name: 'reference_match', label: 'Reference Intelligence', description: 'CLIP/FAISS golden template retrieval' },
  { id: 4, name: 'roi_scheduler', label: 'ROI Scheduler', description: 'Multi-agent region priority dispatch' },
  { id: 5, name: 'evidence_execution', label: 'Evidence Execution', description: 'OCR, Label, YOLO11n & VLM agents' },
  { id: 6, name: 'evidence_fusion', label: 'Evidence Fusion', description: 'Multi-view signal weighting & max-pooling' },
  { id: 7, name: 'ai_judge', label: 'AI Judge', description: 'Multimodal root-cause reasoning' },
  { id: 8, name: 'policy_engine', label: 'Policy Engine', description: 'Industrial action mapping & audit report' },
];

/**
 * Defensively extracts a plain display string from telemetry payloads.
 */
const extractDetailString = (raw) => {
  if (!raw) return null;
  if (typeof raw === 'string') return raw;
  if (typeof raw === 'number' || typeof raw === 'boolean') return String(raw);
  if (typeof raw === 'object') {
    return (
      raw.explanation ||
      raw.root_cause ||
      raw.error ||
      raw.detail ||
      raw.reason ||
      (raw.policy_action ? `Policy Action: ${String(raw.policy_action).toUpperCase()}` : null) ||
      (raw.template_id ? `Template: ${raw.template_id}` : null) ||
      JSON.stringify(raw)
    );
  }
  return String(raw);
};

export const usePipelineSSE = (inspectionId, onComplete) => {
  const [currentStage, setCurrentStage] = useState(1);
  const [stageName, setStageName] = useState('quality_check');
  const [completedStages, setCompletedStages] = useState([]);
  const [status, setStatus] = useState('running'); // 'running' | 'completed' | 'failed'
  const [verdict, setVerdict] = useState(null);
  const [policyAction, setPolicyAction] = useState(null);
  const [error, setError] = useState(null);
  const [detail, setDetail] = useState(null);
  const [isDone, setIsDone] = useState(false);

  const eventSourceRef = useRef(null);
  const pollingTimerRef = useRef(null);
  const isDoneRef = useRef(false);
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const handleProgressData = useCallback((data) => {
    if (!data) return;

    if (data.stage) {
      setCurrentStage(data.stage);
      setStageName(data.stage_name || '');
      // Mark all previous stages as completed
      const doneList = [];
      for (let i = 1; i < data.stage; i++) {
        doneList.push(i);
      }
      setCompletedStages(doneList);
    }

    const formattedDetail = extractDetailString(data.detail || data.error || data.data);
    if (formattedDetail) {
      setDetail(formattedDetail);
    }

    if (data.status === 'completed' || data.status === 'failed') {
      setStatus(data.status);
      setVerdict(data.verdict || null);
      setPolicyAction(data.policy_action || null);
      if (formattedDetail) {
        setDetail(formattedDetail);
      }
      if (data.status === 'completed') {
        setCompletedStages([1, 2, 3, 4, 5, 6, 7, 8]);
        setCurrentStage(8);
      }
      setIsDone(true);
      isDoneRef.current = true;

      if (eventSourceRef.current) {
        try {
          eventSourceRef.current.close();
        } catch (_) {}
      }
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }

      if (typeof onCompleteRef.current === 'function') {
        try {
          onCompleteRef.current(data);
        } catch (err) {
          console.error('Error in onComplete callback:', err);
        }
      }
    }
  }, []);

  // Fallback Polling Function
  const startPolling = useCallback(() => {
    if (isDoneRef.current || pollingTimerRef.current) return;

    pollingTimerRef.current = setInterval(async () => {
      if (isDoneRef.current) {
        if (pollingTimerRef.current) {
          clearInterval(pollingTimerRef.current);
          pollingTimerRef.current = null;
        }
        return;
      }
      try {
        const data = await inspectionsAPI.getStatus(inspectionId);
        handleProgressData(data);
        if (data.status === 'completed' || data.status === 'failed') {
          if (pollingTimerRef.current) {
            clearInterval(pollingTimerRef.current);
            pollingTimerRef.current = null;
          }
        }
      } catch (err) {
        console.warn('Status polling error:', err);
      }
    }, 2500);
  }, [inspectionId, handleProgressData]);

  useEffect(() => {
    if (!inspectionId) return;

    isDoneRef.current = false;
    setIsDone(false);
    setStatus('running');

    const sseUrl = `/api/v1/inspections/${inspectionId}/events`;
    const eventSource = new EventSource(sseUrl);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleProgressData(data);
      } catch (e) {
        console.warn('SSE parse error:', e);
      }
    };

    eventSource.addEventListener('verdict', (event) => {
      try {
        const data = JSON.parse(event.data);
        handleProgressData(data);
      } catch (e) {
        console.warn('Verdict event error:', e);
      } finally {
        eventSource.close();
      }
    });

    eventSource.onerror = () => {
      // Degrade to polling on SSE failure/closure
      eventSource.close();
      if (!isDoneRef.current) {
        startPolling();
      }
    };

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [inspectionId, handleProgressData, startPolling]);

  return {
    currentStage,
    stageName,
    completedStages,
    status,
    verdict,
    policyAction,
    error,
    detail,
    isDone,
    stages: STAGES,
  };
};
