import React, { useState, useEffect } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Smartphone, MonitorX, ArrowRight } from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';

const isLocalHost = () => {
  const h = window.location.hostname;
  return h === 'localhost' || h === '127.0.0.1' || h === '0.0.0.0';
};

export const DesktopGuardModal = ({ isOpen, onClose, onContinueDesktop }) => {
  const [qrUrl, setQrUrl] = useState(window.location.href);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;

    const resolveQrUrl = async () => {
      // 1) Explicit override wins (e.g. ngrok/cloudflared public tunnel URL)
      const override = import.meta.env.VITE_PUBLIC_URL;
      if (override) {
        setQrUrl(override);
        return;
      }

      const { protocol, port, pathname, search } = window.location;

      // 2) Production / non-local host → use the current URL as-is
      if (!isLocalHost()) {
        setQrUrl(window.location.href);
        return;
      }

      // 3) Dev on localhost → substitute host with this machine's LAN IP
      //    so a phone on the same Wi-Fi can actually reach the server.
      try {
        const res = await fetch('/api/v1/system/network');
        const data = await res.json();
        if (!cancelled && data?.ip && data.ip !== 'localhost') {
          const p = port || '5173';
          setQrUrl(`${protocol}//${data.ip}:${p}${pathname}${search}`);
          return;
        }
      } catch (err) {
        console.warn('Could not resolve LAN IP for QR handoff:', err);
      }

      if (!cancelled) setQrUrl(window.location.href);
    };

    resolveQrUrl();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  const displayUrl = qrUrl.replace(/^https?:\/\//, '');

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
          <QRCodeSVG value={qrUrl} size={160} level="M" includeMargin />
          <p className="text-[11px] font-mono font-bold mt-2 text-slate-600 flex items-center gap-1.5">
            <Smartphone className="w-3.5 h-3.5 text-cyan-600" />
            <span>Scan with Smartphone Rear Camera</span>
          </p>
          <p className="mt-1.5 px-2 py-0.5 rounded bg-slate-100 text-[10px] font-mono text-slate-500 max-w-full break-all">
            {displayUrl}
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