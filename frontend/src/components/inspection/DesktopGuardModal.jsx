import React from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Smartphone, MonitorX, ArrowRight } from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';

export const DesktopGuardModal = ({ isOpen, onClose, onContinueDesktop }) => {
  const currentUrl = window.location.href;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Live Camera Intake Guard"
      subtitle="Factory Floor Environmental QA Check"
      maxWidth="max-w-md"
    >
      <div className="space-y-5 text-center">
        <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-start gap-3 text-left">
          <MonitorX className="w-6 h-6 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-bold">Desktop Webcam Detected</p>
            <p className="text-slate-300 leading-relaxed">
              Standard fixed-focus laptop webcams produce motion blur and insufficient resolution
              (often 720p), triggering immediate rejection in <strong>Stage 1 (Quality Check)</strong>.
            </p>
          </div>
        </div>

        <div className="flex flex-col items-center justify-center p-5 rounded-2xl bg-white text-slate-900 shadow-inner">
          <QRCodeSVG value={currentUrl} size={160} level="M" includeMargin />
          <p className="text-[11px] font-mono font-bold mt-2 text-slate-600 flex items-center gap-1.5">
            <Smartphone className="w-3.5 h-3.5 text-cyan-600" />
            <span>Scan with Smartphone Rear Camera</span>
          </p>
        </div>

        <p className="text-xs text-slate-400 leading-relaxed">
          Open this inspection session on your mobile device to utilize its high-resolution autofocus camera,
          or proceed on desktop using the <strong>High-Res File Dropzone</strong>.
        </p>

        <div className="pt-2 flex items-center justify-end gap-3">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={ArrowRight}
            onClick={() => {
              onClose();
              if (onContinueDesktop) onContinueDesktop();
            }}
          >
            Use File Dropzone
          </Button>
        </div>
      </div>
    </Modal>
  );
};
