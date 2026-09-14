import React, { useState } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Eye, Layers, BoxSelect } from 'lucide-react';
import { Button } from '../common/Button';

/**
 * Universal bounding box normalizer.
 * Supports:
 *  - Array: [x, y, width, height] or [x1, y1, x2, y2]
 *  - Object: {x, y, width, height}, {x, y, w, h}, {x_min, y_min, x_max, y_max}
 *  - Normalized coordinates (0..1) or Percentages (0..100)
 */
export const normalizeBoundingBox = (rawBbox) => {
  if (!rawBbox) return { left: 10, top: 10, width: 20, height: 20 };

  let x = 0;
  let y = 0;
  let w = 0;
  let h = 0;

  if (Array.isArray(rawBbox)) {
    if (rawBbox.length >= 4) {
      [x, y, w, h] = rawBbox;
    }
  } else if (typeof rawBbox === 'object') {
    x = rawBbox.x ?? rawBbox.left ?? rawBbox.x_min ?? rawBbox.xmin ?? 0;
    y = rawBbox.y ?? rawBbox.top ?? rawBbox.y_min ?? rawBbox.ymin ?? 0;
    w = rawBbox.width ?? rawBbox.w ?? (rawBbox.x_max != null ? rawBbox.x_max - x : 0);
    h = rawBbox.height ?? rawBbox.h ?? (rawBbox.y_max != null ? rawBbox.y_max - y : 0);
  }

  x = Number(x) || 0;
  y = Number(y) || 0;
  w = Number(w) || 0;
  h = Number(h) || 0;

  // Convert 0..1 normalized coords to percentages (0..100)
  if (x > 0 && x <= 1 && w > 0 && w <= 1) {
    x *= 100;
    y *= 100;
    w *= 100;
    h *= 100;
  } else if (x <= 1 && y <= 1 && w <= 1 && h <= 1 && (w > 0 || h > 0)) {
    x *= 100;
    y *= 100;
    w *= 100;
    h *= 100;
  }

  if (w <= 0) w = 15;
  if (h <= 0) h = 15;

  return {
    left: Math.max(0, Math.min(100, x)),
    top: Math.max(0, Math.min(100, y)),
    width: Math.max(1, Math.min(100, w)),
    height: Math.max(1, Math.min(100, h)),
  };
};

export const DualImageCanvas = ({
  goldenImageUrl,
  inspectionImageUrl,
  yoloDetections = [],
  roiRegions = [],
  partCode,
}) => {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [showYolo, setShowYolo] = useState(true);
  const [showRoi, setShowRoi] = useState(true);
  const [selectedClass, setSelectedClass] = useState('all');

  const classColorMap = {
    capacitor: 'border-cyan-400 text-cyan-300 bg-cyan-500/20',
    resistor: 'border-amber-400 text-amber-300 bg-amber-500/20',
    ic_chip: 'border-purple-400 text-purple-300 bg-purple-500/20',
    connector: 'border-emerald-400 text-emerald-300 bg-emerald-500/20',
    screw: 'border-slate-400 text-slate-300 bg-slate-500/20',
    seal: 'border-rose-400 text-rose-300 bg-rose-500/20',
    battery_cell: 'border-blue-400 text-blue-300 bg-blue-500/20',
    gold_pin_connector: 'border-yellow-400 text-yellow-300 bg-yellow-500/20',
  };

  const handleZoom = (delta) => {
    setZoomLevel((prev) => Math.min(Math.max(Number((prev + delta).toFixed(1)), 1), 3));
  };

  const handleResetZoom = () => {
    setZoomLevel(1);
  };

  const filteredDetections =
    selectedClass === 'all'
      ? yoloDetections
      : yoloDetections.filter((d) => (d.class_name || d.name) === selectedClass);

  return (
    <div className="p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl">
      {/* Viewport Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-hud-border/70">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <BoxSelect className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide font-telemetry">
              Synchronized Dual-Inspection Canvas
            </h3>
            <p className="text-xs text-slate-400 font-mono">
              Ground Truth Reference vs. Ingested Physical Capture ({partCode || 'Matched Target'})
            </p>
          </div>
        </div>

        {/* Toolbar controls */}
        <div className="flex items-center gap-2">
          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-hud-card p-1 rounded-xl border border-hud-border">
            <button
              onClick={() => handleZoom(-0.25)}
              disabled={zoomLevel <= 1}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white disabled:opacity-30"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-xs font-mono text-cyan-400 px-1 font-bold">
              {zoomLevel}x
            </span>
            <button
              onClick={() => handleZoom(0.25)}
              disabled={zoomLevel >= 3}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white disabled:opacity-30"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={handleResetZoom}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white"
              title="Reset Zoom"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Layer toggles */}
          <button
            onClick={() => setShowYolo(!showYolo)}
            className={`px-3 py-1.5 rounded-xl border text-xs font-mono font-semibold transition-all ${
              showYolo
                ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300'
                : 'bg-hud-card border-hud-border text-slate-400'
            }`}
          >
            YOLO Boxes ({filteredDetections.length})
          </button>

          <button
            onClick={() => setShowRoi(!showRoi)}
            className={`px-3 py-1.5 rounded-xl border text-xs font-mono font-semibold transition-all ${
              showRoi
                ? 'bg-purple-500/20 border-purple-500 text-purple-300'
                : 'bg-hud-card border-hud-border text-slate-400'
            }`}
          >
            ROI Regions ({roiRegions.length})
          </button>
        </div>
      </div>

      {/* Synchronized Side-by-Side Viewport */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: Golden Reference Image */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono px-2 text-slate-400">
            <span className="font-bold text-cyan-400 uppercase">Golden Reference Standard</span>
            <span>FAISS Indexed Baseline</span>
          </div>

          <div className="relative aspect-[4/3] rounded-2xl overflow-hidden bg-black border border-hud-border flex items-center justify-center">
            {goldenImageUrl ? (
              <div
                className="w-full h-full transition-transform duration-200"
                style={{ transform: `scale(${zoomLevel})` }}
              >
                <img
                  src={goldenImageUrl}
                  alt="Golden Reference"
                  className="w-full h-full object-contain"
                />
              </div>
            ) : (
              <div className="text-center text-xs font-mono text-slate-500 p-4">
                No explicit golden reference image loaded.
              </div>
            )}
            <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/70 border border-hud-border text-[10px] font-mono text-cyan-300">
              REF-STD
            </span>
          </div>
        </div>

        {/* Right: Ingested Inspection Image with YOLO Bounding Boxes */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono px-2 text-slate-400">
            <span className="font-bold text-emerald-400 uppercase">Physical Inspection Capture</span>
            <span>Under Analysis</span>
          </div>

          <div className="relative aspect-[4/3] rounded-2xl overflow-hidden bg-black border border-hud-border flex items-center justify-center">
            {inspectionImageUrl ? (
              <div
                className="w-full h-full relative transition-transform duration-200"
                style={{ transform: `scale(${zoomLevel})` }}
              >
                <img
                  src={inspectionImageUrl}
                  alt="Inspection Capture"
                  className="w-full h-full object-contain"
                />

                {/* YOLO Bounding Box Overlay */}
                {showYolo &&
                  filteredDetections.map((box, i) => {
                    const clsName = box.class_name || box.name || 'component';
                    const styleClass =
                      classColorMap[clsName] ||
                      'border-cyan-400 text-cyan-300 bg-cyan-500/20';
                    const normalized = normalizeBoundingBox(
                      box.bounding_box || box.bbox || box.box
                    );

                    return (
                      <div
                        key={i}
                        className={`absolute border-2 rounded-sm transition-all pointer-events-none ${styleClass}`}
                        style={{
                          left: `${normalized.left}%`,
                          top: `${normalized.top}%`,
                          width: `${normalized.width}%`,
                          height: `${normalized.height}%`,
                        }}
                      >
                        <span className="absolute -top-4 left-0 px-1 py-0.2 rounded text-[9px] font-mono font-bold uppercase whitespace-nowrap bg-black/80">
                          {clsName} {box.confidence ? `(${(box.confidence * 100).toFixed(0)}%)` : ''}
                        </span>
                      </div>
                    );
                  })}

                {/* ROI Regions Overlay */}
                {showRoi &&
                  roiRegions.map((roi, i) => {
                    const normalized = normalizeBoundingBox(
                      roi.bounding_box || roi.bbox || roi.box
                    );
                    return (
                      <div
                        key={`roi-${i}`}
                        className="absolute border border-dashed border-purple-400/80 bg-purple-500/10 rounded pointer-events-none"
                        style={{
                          left: `${normalized.left}%`,
                          top: `${normalized.top}%`,
                          width: `${normalized.width}%`,
                          height: `${normalized.height}%`,
                        }}
                      >
                        <span className="absolute -top-4 right-0 px-1 py-0.2 rounded text-[9px] font-mono font-bold uppercase text-purple-300 bg-black/80">
                          ROI: {roi.name || roi.id || roi.type}
                        </span>
                      </div>
                    );
                  })}
              </div>
            ) : (
              <div className="text-center text-xs font-mono text-slate-500 p-4">
                Inspection image not available.
              </div>
            )}
            <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/70 border border-hud-border text-[10px] font-mono text-emerald-300">
              CAPTURE-LIVE
            </span>
          </div>
        </div>
      </div>

      {/* Legend strip */}
      <div className="p-3 rounded-xl bg-hud-card border border-hud-border/80 flex flex-wrap items-center justify-between text-[11px] font-mono gap-2">
        <span className="text-slate-400 font-bold uppercase">YOLO11n Classes:</span>
        <div className="flex flex-wrap items-center gap-2">
          {Object.entries(classColorMap).map(([cls, color]) => (
            <span
              key={cls}
              onClick={() => setSelectedClass(selectedClass === cls ? 'all' : cls)}
              className={`px-2 py-0.5 rounded border text-[10px] cursor-pointer transition-all ${
                selectedClass === cls
                  ? 'ring-2 ring-white scale-105 font-bold'
                  : 'opacity-70 hover:opacity-100'
              } ${color}`}
            >
              {cls}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
