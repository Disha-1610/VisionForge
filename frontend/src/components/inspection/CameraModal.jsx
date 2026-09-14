import React, { useRef, useState, useEffect } from 'react';
import { Camera, RefreshCw, X, Check, AlertCircle } from 'lucide-react';
import { Button } from '../common/Button';

export const CameraModal = ({ isOpen, onClose, onCapture }) => {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [error, setError] = useState(null);
  const [capturedImage, setCapturedImage] = useState(null);
  const [starting, setStarting] = useState(true);

  useEffect(() => {
    if (!isOpen) return;

    setError(null);
    setCapturedImage(null);
    setStarting(true);

    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        });

        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.error('Camera access error:', err);
        setError(
          'Could not access mobile rear camera. Please check camera permissions or use high-resolution file upload.'
        );
      } finally {
        setStarting(false);
      }
    };

    startCamera();

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, [isOpen]);

  const handleSnap = () => {
    if (!videoRef.current) return;

    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 1920;
    canvas.height = video.videoHeight || 1080;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          const file = new File([blob], `mobile_capture_${Date.now()}.jpg`, {
            type: 'image/jpeg',
          });
          const previewUrl = URL.createObjectURL(blob);
          setCapturedImage({ file, previewUrl });
        }
      },
      'image/jpeg',
      0.95
    );
  };

  const handleConfirm = () => {
    if (capturedImage?.file) {
      onCapture(capturedImage.file);
      onClose();
    }
  };

  const handleRetake = () => {
    setCapturedImage(null);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex flex-col justify-between p-4">
      {/* Top Header */}
      <div className="flex items-center justify-between z-10">
        <div className="flex items-center gap-2">
          <Camera className="w-5 h-5 text-cyan-400" />
          <span className="text-sm font-bold text-white font-telemetry">
            High-Res Alignment Viewfinder
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-xl bg-slate-800 text-slate-300 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Main Viewfinder Box */}
      <div className="relative flex-1 my-4 rounded-3xl overflow-hidden bg-black flex items-center justify-center border border-hud-border">
        {error ? (
          <div className="p-6 text-center text-rose-300 max-w-sm">
            <AlertCircle className="w-8 h-8 mx-auto mb-2 text-rose-400" />
            <p className="text-xs font-mono">{error}</p>
          </div>
        ) : capturedImage ? (
          <img
            src={capturedImage.previewUrl}
            alt="Captured Preview"
            className="w-full h-full object-contain"
          />
        ) : (
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
            />

            {/* Industrial Overlay Crosshairs & Bounding Guide */}
            <div className="absolute inset-8 sm:inset-16 border-2 border-cyan-400/60 rounded-2xl pointer-events-none flex items-center justify-center">
              <div className="w-8 h-8 border-t-2 border-l-2 border-cyan-400 absolute top-0 left-0 -mt-0.5 -ml-0.5" />
              <div className="w-8 h-8 border-t-2 border-r-2 border-cyan-400 absolute top-0 right-0 -mt-0.5 -mr-0.5" />
              <div className="w-8 h-8 border-b-2 border-l-2 border-cyan-400 absolute bottom-0 left-0 -mb-0.5 -ml-0.5" />
              <div className="w-8 h-8 border-b-2 border-r-2 border-cyan-400 absolute bottom-0 right-0 -mb-0.5 -mr-0.5" />

              <span className="text-[11px] font-mono font-bold tracking-widest text-cyan-300/80 uppercase bg-slate-950/70 px-3 py-1 rounded-full border border-cyan-500/40">
                ALIGN HARDWARE WITHIN RECTANGLE
              </span>
            </div>
          </>
        )}
      </div>

      {/* Action Controls */}
      <div className="flex items-center justify-center gap-4 z-10">
        {capturedImage ? (
          <>
            <Button variant="secondary" size="md" icon={RefreshCw} onClick={handleRetake}>
              Retake Capture
            </Button>
            <Button variant="success" size="md" icon={Check} onClick={handleConfirm}>
              Use Captured Image
            </Button>
          </>
        ) : (
          <Button
            variant="primary"
            size="lg"
            icon={Camera}
            onClick={handleSnap}
            disabled={starting || !!error}
          >
            Capture Frame
          </Button>
        )}
      </div>
    </div>
  );
};
