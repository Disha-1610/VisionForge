import React, { useState } from 'react';
import { Scale, CheckCircle2, AlertOctagon, AlertTriangle } from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { inspectionsAPI } from '../../services/api';
import { useToast } from '../../context/ToastContext';

export const ReviewModal = ({ isOpen, onClose, inspectionId, currentVerdict, onReviewComplete }) => {
  const [reviewAction, setReviewAction] = useState('APPROVED'); // 'APPROVED' | 'OVERRIDDEN'
  const [newVerdict, setNewVerdict] = useState(currentVerdict === 'GENUINE' ? 'FRAUD' : 'GENUINE');
  const [reviewerNotes, setReviewerNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (reviewAction === 'OVERRIDDEN' && !reviewerNotes.trim()) {
      toast.warning('Audit compliance requires justification notes when overriding AI verdict.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        review_status: reviewAction,
        reviewer_notes: reviewerNotes.trim() || `Approved AI verdict (${currentVerdict})`,
        overridden_verdict: reviewAction === 'OVERRIDDEN' ? newVerdict : undefined,
      };

      await inspectionsAPI.review(inspectionId, payload);
      toast.success(
        reviewAction === 'APPROVED' ? 'AI Verdict Approved!' : `Verdict Overridden to ${newVerdict}!`
      );
      if (onReviewComplete) onReviewComplete();
      onClose();
    } catch (err) {
      console.error('Failed to submit review:', err);
      const msg = err.response?.data?.detail || 'Failed to record human review';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Human Review & Override Workstation"
      subtitle="Record inspector sign-off and audit accountability log"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Action Radio Choice */}
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setReviewAction('APPROVED')}
            className={`p-4 rounded-2xl border text-left transition-all ${
              reviewAction === 'APPROVED'
                ? 'bg-emerald-950/60 border-emerald-500 text-emerald-200 shadow-md shadow-emerald-500/20'
                : 'bg-hud-card border-hud-border text-slate-400 hover:border-slate-600'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <span className="text-sm font-bold">Approve AI Verdict</span>
            </div>
            <p className="text-[11px] font-mono opacity-80">
              Confirm current model classification as correct.
            </p>
          </button>

          <button
            type="button"
            onClick={() => setReviewAction('OVERRIDDEN')}
            className={`p-4 rounded-2xl border text-left transition-all ${
              reviewAction === 'OVERRIDDEN'
                ? 'bg-amber-950/60 border-amber-500 text-amber-200 shadow-md shadow-amber-500/20'
                : 'bg-hud-card border-hud-border text-slate-400 hover:border-slate-600'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <AlertOctagon className="w-5 h-5 text-amber-400" />
              <span className="text-sm font-bold">Override Verdict</span>
            </div>
            <p className="text-[11px] font-mono opacity-80">
              Manually reverse classification with audit reasoning.
            </p>
          </button>
        </div>

        {/* If Overriding: Select New Verdict */}
        {reviewAction === 'OVERRIDDEN' && (
          <div className="p-4 rounded-2xl bg-hud-card border border-amber-500/40 space-y-3">
            <div className="flex items-center gap-2 text-xs font-mono font-bold text-amber-400">
              <AlertTriangle className="w-4 h-4" />
              <span>Select New Authoritative Verdict</span>
            </div>

            <select
              value={newVerdict}
              onChange={(e) => setNewVerdict(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-hud-surface border border-hud-border text-sm text-white font-mono"
            >
              <option value="GENUINE">GENUINE (Accept Part)</option>
              <option value="FRAUD">FRAUD / TAMPERED (Quarantine)</option>
            </select>
          </div>
        )}

        {/* Reviewer Justification Notes */}
        <div>
          <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1.5">
            Inspector Notes & Justification{' '}
            {reviewAction === 'OVERRIDDEN' && <span className="text-rose-400">*Required</span>}
          </label>
          <textarea
            rows={3}
            value={reviewerNotes}
            onChange={(e) => setReviewerNotes(e.target.value)}
            placeholder={
              reviewAction === 'OVERRIDDEN'
                ? 'e.g. Visual inspection confirms IC marking re-etched by vendor despite high structural similarity.'
                : 'Optional reviewer sign-off comment...'
            }
            className="w-full p-3 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono focus:border-cyan-400 focus:outline-none"
          />
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant={reviewAction === 'APPROVED' ? 'success' : 'amber'}
            size="sm"
            loading={submitting}
          >
            Submit Review Record
          </Button>
        </div>
      </form>
    </Modal>
  );
};
