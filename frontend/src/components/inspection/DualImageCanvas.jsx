import React, { useState, useRef } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  BoxSelect,
  Move,
  Tag,
  Crosshair,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react';

/**
 * Universal bounding box normalizer.
 * Accurately handles:
 *  - YOLO normalized center format: [xc, yc, w, h] where values are 0..1
 *  - Normalized top-left format: [x, y, w, h] or {x, y, w, h} (0..1)
 *  - Pixel coordinates in reference image space (e.g. 1045, 575 in 1672x941)
 *  - Explicit bounding box objects with x, y, width, height or xmin, ymin, xmax, ymax
 */
export const normalizeBoundingBox = (rawBbox, refWidth = 1672, refHeight = 941) => {
  if (!rawBbox) return { left: 10, top: 10, width: 20, height: 20 };

  let x = 0;
  let y = 0;
  let w = 0;
  let h = 0;
  let isCenter = false;

  if (Array.isArray(rawBbox)) {
    if (rawBbox.length >= 4) {
      [x, y, w, h] = rawBbox;
      // YOLO normalized center format [xc, yc, w, h] where all are <= 1.0
      if (x <= 1 && y <= 1 && w <= 1 && h <= 1 && (w > 0 || h > 0)) {
        isCenter = true;
      }
    }
  } else if (typeof rawBbox === 'object') {
    x = rawBbox.x ?? rawBbox.left ?? rawBbox.x_min ?? rawBbox.xmin ?? 0;
    y = rawBbox.y ?? rawBbox.top ?? rawBbox.y_min ?? rawBbox.ymin ?? 0;
    w = rawBbox.width ?? rawBbox.w ?? (rawBbox.x_max != null ? rawBbox.x_max - x : 0);
    h = rawBbox.height ?? rawBbox.h ?? (rawBbox.y_max != null ? rawBbox.y_max - y : 0);
    if (rawBbox.is_center || rawBbox.format === 'center') {
      isCenter = true;
    }
  }

  x = Number(x) || 0;
  y = Number(y) || 0;
  w = Number(w) || 0;
  h = Number(h) || 0;

  // Case 1: Normalized 0..1 coordinates
  if (x <= 1 && y <= 1 && w <= 1 && h <= 1 && (w > 0 || h > 0)) {
    let leftPct = x * 100;
    let topPct = y * 100;
    let widthPct = w * 100;
    let heightPct = h * 100;

    if (isCenter) {
      leftPct = (x - w / 2) * 100;
      topPct = (y - h / 2) * 100;
    }

    return {
      left: Math.max(0, Math.min(100, leftPct)),
      top: Math.max(0, Math.min(100, topPct)),
      width: Math.max(0.5, Math.min(100, widthPct)),
      height: Math.max(0.5, Math.min(100, heightPct)),
    };
  }

  // Case 2: Pixel coordinates in reference image space (e.g. 1045, 575 in 1672x941)
  const actualW = refWidth > 0 ? refWidth : 1672;
  const actualH = refHeight > 0 ? refHeight : 941;

  let leftPct = (x / actualW) * 100;
  let topPct = (y / actualH) * 100;
  let widthPct = (w / actualW) * 100;
  let heightPct = (h / actualH) * 100;

  if (isCenter) {
    leftPct = ((x - w / 2) / actualW) * 100;
    topPct = ((y - h / 2) / actualH) * 100;
  }

  return {
    left: Math.max(0, Math.min(100, leftPct)),
    top: Math.max(0, Math.min(100, topPct)),
    width: Math.max(0.5, Math.min(100, widthPct)),
    height: Math.max(0.5, Math.min(100, heightPct)),
  };
};

export const DualImageCanvas = ({
  goldenImageUrl,
  inspectionImageUrl,
  yoloDetections = [],
  roiRegions = [],
  roiTemplate,
  partCode,
}) => {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  const [showYolo, setShowYolo] = useState(true);
  const [showRoi, setShowRoi] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [selectedClass, setSelectedClass] = useState('all');

  const [hoveredRoiId, setHoveredRoiId] = useState(null);
  const [hoveredBoxIdx, setHoveredBoxIdx] = useState(null);

  // Track natural dimensions of loaded images so overlays fit the exact image content (no letterbox distortion)
  const [goldenDims, setGoldenDims] = useState({ width: 0, height: 0, aspect: null });
  const [inspectionDims, setInspectionDims] = useState({ width: 0, height: 0, aspect: null });

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

  const defaultRefWidth =
    roiTemplate?.reference_image_width ||
    roiTemplate?.referenceImageWidth ||
    (partCode?.toUpperCase().includes('PCB') ? 1536 : 1672);

  const defaultRefHeight =
    roiTemplate?.reference_image_height ||
    roiTemplate?.referenceImageHeight ||
    (partCode?.toUpperCase().includes('PCB') ? 1024 : 941);

  const handleZoom = (delta) => {
    setZoomLevel((prev) => {
      const next = Math.min(Math.max(Number((prev + delta).toFixed(1)), 1), 3);
      if (next === 1) {
        setPanOffset({ x: 0, y: 0 });
      }
      return next;
    });
  };

  const handleResetZoom = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
  };

  const handleMouseDown = (e) => {
    if (zoomLevel <= 1) return;
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX - panOffset.x,
      y: e.clientY - panOffset.y,
    };
  };

  const handleMouseMove = (e) => {
    if (!isDragging || zoomLevel <= 1) return;
    const maxPan = 260 * (zoomLevel - 1);
    const newX = Math.max(-maxPan, Math.min(maxPan, e.clientX - dragStartRef.current.x));
    const newY = Math.max(-maxPan, Math.min(maxPan, e.clientY - dragStartRef.current.y));
    setPanOffset({ x: newX, y: newY });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleImageLoad = (isGolden, e) => {
    const { naturalWidth, naturalHeight } = e.target;
    if (naturalWidth && naturalHeight) {
      const aspect = naturalWidth / naturalHeight;
      if (isGolden) {
        setGoldenDims({ width: naturalWidth, height: naturalHeight, aspect });
      } else {
        setInspectionDims({ width: naturalWidth, height: naturalHeight, aspect });
      }
    }
  };

  const filteredDetections =
    selectedClass === 'all'
      ? yoloDetections
      : yoloDetections.filter((d) => (d.class_name || d.name) === selectedClass);

  const hoveredRoi = roiRegions.find((r) => (r.id || r.name) === hoveredRoiId);
  const hoveredYolo = hoveredBoxIdx !== null ? filteredDetections[hoveredBoxIdx] : null;

  return (
    <div className="p-4 sm:p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl">
      {/* Viewport Control Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4 pb-4 border-b border-hud-border/70">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shrink-0">
            <BoxSelect className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide font-telemetry">
              Synchronized Dual-Inspection Canvas
            </h3>
            <p className="text-xs text-slate-400 font-mono">
              Ground Truth Reference vs. Ingested Physical Capture ({partCode || 'Target Board'})
            </p>
          </div>
        </div>

        {/* Toolbar controls */}
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {/* Zoom & Pan controls */}
          <div className="flex items-center gap-1 bg-hud-card p-1 rounded-xl border border-hud-border">
            <button
              onClick={() => handleZoom(-0.25)}
              disabled={zoomLevel <= 1}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-xs font-mono text-cyan-400 px-1.5 font-bold min-w-[28px] text-center">
              {zoomLevel}x
            </span>
            <button
              onClick={() => handleZoom(0.25)}
              disabled={zoomLevel >= 3}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={handleResetZoom}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white transition-colors"
              title="Reset View"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>

          {zoomLevel > 1 && (
            <span className="hidden lg:flex items-center gap-1 px-2.5 py-1 rounded-xl bg-cyan-950/60 border border-cyan-500/40 text-[11px] font-mono text-cyan-300">
              <Move className="w-3 h-3 text-cyan-400" />
              <span>Drag to Pan</span>
            </span>
          )}

          {/* Toggle Labels */}
          <button
            onClick={() => setShowLabels(!showLabels)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-mono font-semibold transition-colors ${
              showLabels
                ? 'bg-slate-800 border-slate-600 text-slate-200'
                : 'bg-hud-card border-hud-border text-slate-500'
            }`}
            title="Toggle Bounding Box Labels"
          >
            <Tag className="w-3.5 h-3.5" />
            <span>Labels</span>
          </button>

          {/* Layer toggles */}
          <button
            onClick={() => setShowYolo(!showYolo)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-mono font-semibold transition-colors ${
              showYolo
                ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 shadow-sm'
                : 'bg-hud-card border-hud-border text-slate-400'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${showYolo ? 'bg-cyan-400' : 'bg-slate-600'}`} />
            <span>YOLO ({filteredDetections.length})</span>
          </button>

          <button
            onClick={() => setShowRoi(!showRoi)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-mono font-semibold transition-colors ${
              showRoi
                ? 'bg-purple-500/20 border-purple-500 text-purple-300 shadow-sm'
                : 'bg-hud-card border-hud-border text-slate-400'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${showRoi ? 'bg-purple-400' : 'bg-slate-600'}`} />
            <span>ROI ({roiRegions.length})</span>
          </button>
        </div>
      </div>

      {/* Synchronized Side-by-Side Viewport */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: Golden Reference Standard (Clean Ground Truth - Zero Overlays) */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono px-2 text-slate-400">
            <span className="font-bold text-cyan-400 uppercase flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
              Golden Reference Standard
            </span>
            <span className="text-[11px] text-slate-500">FAISS Indexed Ground Truth</span>
          </div>

          <div
            className="relative w-full h-[380px] sm:h-[460px] rounded-2xl overflow-hidden bg-slate-950/95 border border-hud-border flex items-center justify-center p-2 select-none"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{ cursor: zoomLevel > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default' }}
          >
            {goldenImageUrl ? (
              <div
                className="relative max-w-full max-h-full transition-transform duration-100 ease-out origin-center"
                style={{
                  aspectRatio: goldenDims.aspect
                    ? `${goldenDims.aspect}`
                    : `${defaultRefWidth}/${defaultRefHeight}`,
                  transform: `scale(${zoomLevel}) translate(${panOffset.x / zoomLevel}px, ${panOffset.y / zoomLevel}px)`,
                }}
              >
                <img
                  src={goldenImageUrl}
                  alt="Golden Reference Ground Truth"
                  onLoad={(e) => handleImageLoad(true, e)}
                  className="w-full h-full object-fill block select-none pointer-events-none rounded-lg"
                />
              </div>
            ) : (
              <div className="text-center text-xs font-mono text-slate-500 p-4">
                No explicit golden reference image loaded.
              </div>
            )}
            <span className="absolute top-3 left-3 px-2.5 py-0.5 rounded bg-black/85 border border-cyan-500/30 text-[10px] font-mono text-cyan-300 shadow flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-cyan-400" />
              REF-STD (BENCHMARK)
            </span>
          </div>
        </div>

        {/* Right: Physical Inspection Capture with YOLO & ROI Overlays */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono px-2 text-slate-400">
            <span className="font-bold text-emerald-400 uppercase flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Physical Inspection Capture
            </span>
            <span className="text-[11px] text-slate-500">Live Ingest Analysis</span>
          </div>

          <div
            className="relative w-full h-[380px] sm:h-[460px] rounded-2xl overflow-hidden bg-slate-950/95 border border-hud-border flex items-center justify-center p-2 select-none"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{ cursor: zoomLevel > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default' }}
          >
            {inspectionImageUrl ? (
              <div
                className="relative max-w-full max-h-full transition-transform duration-100 ease-out origin-center"
                style={{
                  aspectRatio: inspectionDims.aspect
                    ? `${inspectionDims.aspect}`
                    : `${defaultRefWidth}/${defaultRefHeight}`,
                  transform: `scale(${zoomLevel}) translate(${panOffset.x / zoomLevel}px, ${panOffset.y / zoomLevel}px)`,
                }}
              >
                <img
                  src={inspectionImageUrl}
                  alt="Inspection Capture"
                  onLoad={(e) => handleImageLoad(false, e)}
                  className="w-full h-full object-fill block select-none pointer-events-none rounded-lg"
                />

                {/* YOLO Bounding Box Overlay */}
                {showYolo &&
                  filteredDetections.map((box, i) => {
                    const clsName = box.class_name || box.name || 'component';
                    const styleClass =
                      classColorMap[clsName] || 'border-cyan-400 text-cyan-300 bg-cyan-500/20';
                    const normalized = normalizeBoundingBox(
                      box.bounding_box || box.bbox || box.box,
                      defaultRefWidth,
                      defaultRefHeight
                    );
                    const isHovered = hoveredBoxIdx === i;
                    const isTopEdge = normalized.top < 6;

                    return (
                      <div
                        key={`yolo-${i}`}
                        onMouseEnter={() => setHoveredBoxIdx(i)}
                        onMouseLeave={() => setHoveredBoxIdx(null)}
                        className={`absolute border-2 rounded-sm transition-colors duration-150 pointer-events-auto cursor-pointer ${styleClass} ${
                          isHovered
                            ? 'ring-2 ring-white z-30 shadow-[0_0_14px_rgba(255,255,255,0.7)] brightness-110'
                            : 'z-20'
                        }`}
                        style={{
                          left: `${normalized.left}%`,
                          top: `${normalized.top}%`,
                          width: `${normalized.width}%`,
                          height: `${normalized.height}%`,
                        }}
                      >
                        {showLabels && (
                          <span
                            className={`absolute left-0 px-1 py-0.2 rounded text-[8px] sm:text-[9px] font-mono font-bold uppercase whitespace-nowrap bg-black/90 border border-slate-700 pointer-events-none shadow-md z-30 ${
                              isTopEdge ? 'top-1' : '-top-4'
                            }`}
                          >
                            {clsName} {box.confidence ? `(${(box.confidence * 100).toFixed(0)}%)` : ''}
                          </span>
                        )}
                      </div>
                    );
                  })}

                {/* ROI Regions Overlay on Inspection Capture */}
                {showRoi &&
                  roiRegions.map((roi, i) => {
                    const isHovered = hoveredRoiId === (roi.id || roi.name);
                    const normalized = normalizeBoundingBox(
                      roi.bounding_box || roi.bbox || roi.box,
                      defaultRefWidth,
                      defaultRefHeight
                    );
                    const isTopEdge = normalized.top < 6;

                    return (
                      <div
                        key={`roi-${i}`}
                        onMouseEnter={() => setHoveredRoiId(roi.id || roi.name)}
                        onMouseLeave={() => setHoveredRoiId(null)}
                        className={`absolute border border-dashed rounded transition-colors duration-150 pointer-events-auto cursor-pointer ${
                          isHovered
                            ? 'border-purple-300 bg-purple-400/25 ring-2 ring-purple-400 shadow-[0_0_12px_rgba(192,132,252,0.45)] z-25 brightness-110'
                            : 'border-purple-400/60 bg-purple-500/10 hover:border-purple-300 hover:bg-purple-500/20 z-10'
                        }`}
                        style={{
                          left: `${normalized.left}%`,
                          top: `${normalized.top}%`,
                          width: `${normalized.width}%`,
                          height: `${normalized.height}%`,
                        }}
                      >
                        {showLabels && (
                          <span
                            className={`absolute right-1 px-1.5 py-0.5 rounded text-[8px] sm:text-[9px] font-mono font-bold uppercase tracking-wider text-purple-200 bg-slate-950/90 border border-purple-500/40 shadow-sm pointer-events-none truncate max-w-[140px] z-30 ${
                              isTopEdge ? 'top-1' : '-top-4'
                            }`}
                          >
                            ROI: {roi.name || roi.id}
                          </span>
                        )}
                      </div>
                    );
                  })}
              </div>
            ) : (
              <div className="text-center text-xs font-mono text-slate-500 p-4">
                Inspection image not available.
              </div>
            )}
            <span className="absolute top-3 left-3 px-2.5 py-0.5 rounded bg-black/85 border border-emerald-500/30 text-[10px] font-mono text-emerald-300 shadow">
              CAPTURE-LIVE
            </span>
          </div>
        </div>
      </div>

      {/* Permanent Fixed-Height Live Telemetry Readout (Zero Layout Shift, No Blinking) */}
      <div className="h-12 px-4 rounded-xl bg-hud-card border border-hud-border flex items-center justify-between gap-3 text-xs font-mono overflow-hidden">
        {hoveredYolo ? (
          <div className="flex items-center gap-3 text-cyan-300 truncate">
            <span className="px-2 py-0.5 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 font-bold text-[10px] tracking-wider uppercase shrink-0">
              YOLO Component
            </span>
            <span className="font-bold text-white text-sm truncate">
              {hoveredYolo.class_name || hoveredYolo.name || 'Component'}
            </span>
            <span className="text-slate-400 shrink-0">
              Confidence:{' '}
              <strong className="text-cyan-400">
                {hoveredYolo.confidence ? `${(hoveredYolo.confidence * 100).toFixed(1)}%` : 'N/A'}
              </strong>
            </span>
            {Array.isArray(hoveredYolo.bounding_box) && (
              <span className="text-slate-500 hidden lg:inline truncate">
                Coord: [{hoveredYolo.bounding_box.map((v) => (typeof v === 'number' ? v.toFixed(2) : v)).join(', ')}]
              </span>
            )}
          </div>
        ) : hoveredRoi ? (
          <div className="flex items-center gap-3 text-purple-200 truncate">
            <span className="px-2 py-0.5 rounded bg-purple-500/20 border border-purple-500/40 text-purple-200 font-bold text-[10px] tracking-wider uppercase shrink-0">
              Inspection ROI
            </span>
            <span className="font-bold text-white text-sm truncate">
              {hoveredRoi.name || hoveredRoi.id}
            </span>
            <span className="text-slate-400 shrink-0">
              Type: <strong className="text-purple-300 uppercase">{hoveredRoi.type}</strong>
            </span>
            <span className="text-slate-400 shrink-0">
              Target Agent: <strong className="text-purple-300 uppercase">{hoveredRoi.agent}</strong>
            </span>
            <span className="text-slate-400 hidden sm:inline shrink-0">
              Priority: <strong className="text-purple-300 uppercase">{hoveredRoi.priority || 'NORMAL'}</strong>
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-slate-500">
            <Crosshair className="w-4 h-4 text-slate-500 shrink-0" />
            <span className="text-[11px] truncate">
              Telemetry Standby — Hover cursor over physical capture components or ROI regions for live readout
            </span>
          </div>
        )}

        <div className="shrink-0 text-[10px] text-slate-500 hidden sm:flex items-center gap-2 font-mono">
          <span>{filteredDetections.length} Detections</span>
          <span>•</span>
          <span>{roiRegions.length} ROIs</span>
        </div>
      </div>

      {/* Legend strip with YOLO filtering */}
      <div className="p-3 rounded-xl bg-hud-card border border-hud-border/80 flex flex-wrap items-center justify-between text-[11px] font-mono gap-2">
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-bold uppercase">YOLO11n Classes:</span>
          {selectedClass !== 'all' && (
            <span
              onClick={() => setSelectedClass('all')}
              className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-cyan-400 cursor-pointer hover:bg-slate-700"
            >
              Reset Filter
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {Object.entries(classColorMap).map(([cls, color]) => {
            const count = yoloDetections.filter((d) => (d.class_name || d.name) === cls).length;
            return (
              <span
                key={cls}
                onClick={() => setSelectedClass(selectedClass === cls ? 'all' : cls)}
                className={`px-2 py-0.5 rounded border text-[10px] cursor-pointer transition-all ${
                  selectedClass === cls
                    ? 'ring-2 ring-white scale-105 font-bold shadow-md'
                    : count > 0
                    ? 'opacity-85 hover:opacity-100'
                    : 'opacity-40 hover:opacity-75'
                } ${color}`}
                title={`Click to filter by ${cls} (${count} detected)`}
              >
                {cls} {count > 0 ? `(${count})` : ''}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
};
