import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  Camera,
  Layers,
  Building2,
  MapPin,
  Plus,
  Trash2,
  ArrowRight,
  AlertCircle,
  FileImage,
} from 'lucide-react';
import { vendorsAPI, inspectionsAPI } from '../services/api';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { CameraModal } from '../components/inspection/CameraModal';
import { DesktopGuardModal } from '../components/inspection/DesktopGuardModal';
import { useToast } from '../context/ToastContext';

export const NewInspectionPage = () => {
  const navigate = useNavigate();
  const toast = useToast();
  const fileInputRef = useRef(null);

  // Form fields
  const [productType, setProductType] = useState('motherboard');
  const [vendorId, setVendorId] = useState('');
  const [location, setLocation] = useState('Assembly Line 01');
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  // Vendors list
  const [vendors, setVendors] = useState([]);
  const [loadingVendors, setLoadingVendors] = useState(true);

  // Add Vendor Modal
  const [addVendorModalOpen, setAddVendorModalOpen] = useState(false);
  const [newVendorName, setNewVendorName] = useState('');
  const [newVendorSite, setNewVendorSite] = useState('');
  const [newVendorCode, setNewVendorCode] = useState('');
  const [savingVendor, setSavingVendor] = useState(false);

  // Camera & Desktop Guard Modals
  const [cameraModalOpen, setCameraModalOpen] = useState(false);
  const [desktopGuardOpen, setDesktopGuardOpen] = useState(false);

  const fetchVendors = async () => {
    setLoadingVendors(true);
    try {
      const data = await vendorsAPI.list();
      setVendors(data || []);
      if (data && data.length > 0 && !vendorId) {
        setVendorId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load vendors:', err);
      toast.error('Failed to load vendor registry');
    } finally {
      setLoadingVendors(false);
    }
  };

  useEffect(() => {
    fetchVendors();
  }, []);

  const handleFilesAdded = (incomingFiles) => {
    const valid = Array.from(incomingFiles).filter((f) =>
      ['image/jpeg', 'image/png', 'image/jpg'].includes(f.type)
    );

    if (valid.length === 0) {
      toast.warning('Please select JPG or PNG image files only');
      return;
    }

    const newFiles = [...files, ...valid].slice(0, 6);
    setFiles(newFiles);

    // Generate previews
    const newPreviews = newFiles.map((f) => URL.createObjectURL(f));
    setPreviews(newPreviews);
  };

  const handleRemoveFile = (index) => {
    const updatedFiles = files.filter((_, i) => i !== index);
    setFiles(updatedFiles);

    // Revoke removed object URL
    URL.revokeObjectURL(previews[index]);
    const updatedPreviews = previews.filter((_, i) => i !== index);
    setPreviews(updatedPreviews);
  };

  const handleCameraClick = () => {
    const isDesktop = window.innerWidth >= 1024;
    if (isDesktop) {
      setDesktopGuardOpen(true);
    } else {
      setCameraModalOpen(true);
    }
  };

  const handleCreateVendor = async (e) => {
    e.preventDefault();
    if (!newVendorName || !newVendorCode) return;

    setSavingVendor(true);
    try {
      const created = await vendorsAPI.create({
        name: newVendorName,
        code: newVendorCode,
        site_name: newVendorSite || 'Main Facility',
      });
      toast.success(`Vendor "${created.name}" created!`);
      setAddVendorModalOpen(false);
      setNewVendorName('');
      setNewVendorSite('');
      setNewVendorCode('');
      await fetchVendors();
      setVendorId(created.id);
    } catch (err) {
      console.error('Failed to create vendor:', err);
      const msg = err.response?.data?.detail || 'Failed to create vendor';
      toast.error(msg);
    } finally {
      setSavingVendor(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (files.length === 0) {
      toast.warning('Please upload or capture at least one hardware image');
      return;
    }

    if (!vendorId) {
      toast.warning('Please select a supplier / vendor');
      return;
    }

    setSubmitting(true);
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('images', file);
    });
    formData.append('product_type', productType);
    formData.append('vendor_id', vendorId);
    formData.append('location', location);

    try {
      const res = await inspectionsAPI.create(formData);
      toast.success('Inspection initiated! Launching real-time analysis pipeline.');
      navigate(`/inspections/${res.id}`);
    } catch (err) {
      console.error('Failed to trigger inspection:', err);
      const detail =
        err.response?.data?.detail || 'Failed to trigger inspection pipeline. Please try again.';
      toast.error(detail);
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-hud-border/70">
        <div>
          <h2 className="text-xl font-black text-white tracking-tight uppercase font-telemetry">
            Hardware Inspection Intake
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Ingest hardware image captures for autonomous 8-stage fraud verification
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Product & Vendor Selection Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Product Type */}
          <div className="p-4 rounded-2xl bg-hud-surface border border-hud-border space-y-2">
            <label className="flex items-center gap-2 text-xs font-mono font-bold uppercase text-slate-400">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>Target Hardware</span>
            </label>
            <select
              value={productType}
              onChange={(e) => setProductType(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono focus:border-cyan-400"
            >
              <option value="motherboard">Motherboard / Microcontroller</option>
              <option value="battery">Industrial Battery Pack</option>
              <option value="ram">High-Speed DDR4 RAM</option>
            </select>
            <p className="text-[11px] text-slate-500 font-mono">
              Sets YOLO11n object classes & ROI templates
            </p>
          </div>

          {/* Vendor */}
          <div className="p-4 rounded-2xl bg-hud-surface border border-hud-border space-y-2">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs font-mono font-bold uppercase text-slate-400">
                <Building2 className="w-4 h-4 text-emerald-400" />
                <span>Supplier / Vendor</span>
              </label>
              <button
                type="button"
                onClick={() => setAddVendorModalOpen(true)}
                className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-0.5"
              >
                <Plus className="w-3 h-3" />
                <span>Add</span>
              </button>
            </div>
            <select
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
              disabled={loadingVendors}
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono focus:border-cyan-400"
            >
              {vendors.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.code})
                </option>
              ))}
            </select>
            <p className="text-[11px] text-slate-500 font-mono">
              Links audit trail for vendor risk analytics
            </p>
          </div>

          {/* Location */}
          <div className="p-4 rounded-2xl bg-hud-surface border border-hud-border space-y-2">
            <label className="flex items-center gap-2 text-xs font-mono font-bold uppercase text-slate-400">
              <MapPin className="w-4 h-4 text-amber-400" />
              <span>Inspection Location</span>
            </label>
            <input
              type="text"
              required
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Line 01 - Station B"
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono focus:border-cyan-400"
            />
            <p className="text-[11px] text-slate-500 font-mono">
              Factory station / geographical site tag
            </p>
          </div>
        </div>

        {/* Dual Intake Channel (Dropzone + Live Camera) */}
        <div className="p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-hud-border/70">
            <div className="flex items-center gap-2.5">
              <UploadCloud className="w-5 h-5 text-cyan-400" />
              <h3 className="text-base font-bold text-white tracking-wide">
                Hardware Intake Channel
              </h3>
            </div>

            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={Camera}
              onClick={handleCameraClick}
            >
              Live Camera Feed
            </Button>
          </div>

          {/* Drag & Drop Zone */}
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              handleFilesAdded(e.dataTransfer.files);
            }}
            className="p-8 border-2 border-dashed border-hud-border hover:border-cyan-400/80 rounded-2xl bg-hud-bg/50 hover:bg-hud-card/50 transition-all cursor-pointer text-center space-y-3"
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/jpeg,image/png,image/jpg"
              onChange={(e) => handleFilesAdded(e.target.files)}
              className="hidden"
            />
            <div className="p-3.5 rounded-2xl bg-slate-800/80 w-fit mx-auto text-cyan-400 border border-hud-border">
              <FileImage className="w-8 h-8" />
            </div>
            <div>
              <p className="text-sm font-bold text-white">
                Drag & drop high-resolution hardware images here, or{' '}
                <span className="text-cyan-400 underline">browse files</span>
              </p>
              <p className="text-xs text-slate-400 font-mono mt-1">
                Supports JPG, JPEG, PNG (Up to 6 multi-angle views)
              </p>
            </div>
          </div>

          {/* Preview Grid */}
          {previews.length > 0 && (
            <div className="pt-2">
              <h4 className="text-xs font-mono font-bold uppercase text-slate-400 mb-3">
                Selected Captures ({previews.length} / 6)
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
                {previews.map((url, i) => (
                  <div
                    key={i}
                    className="relative group rounded-xl overflow-hidden border border-hud-border bg-black aspect-square"
                  >
                    <img
                      src={url}
                      alt={`Capture ${i + 1}`}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-slate-950/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <button
                        type="button"
                        onClick={() => handleRemoveFile(i)}
                        className="p-1.5 rounded-lg bg-rose-600 text-white hover:bg-rose-500"
                        title="Remove image"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <span className="absolute bottom-1.5 left-1.5 text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/70 text-slate-300">
                      #{i + 1}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Submit Bar */}
        <div className="flex items-center justify-end gap-4 pt-2">
          <Button
            type="button"
            variant="ghost"
            size="md"
            onClick={() => navigate('/dashboard')}
          >
            Cancel
          </Button>

          <Button
            type="submit"
            variant="primary"
            size="lg"
            icon={ArrowRight}
            loading={submitting}
          >
            Run Autonomous Inspection (8 Stages)
          </Button>
        </div>
      </form>

      {/* Add Vendor Modal */}
      <Modal
        isOpen={addVendorModalOpen}
        onClose={() => setAddVendorModalOpen(false)}
        title="Register New Supplier / Vendor"
        subtitle="Add vendor profile into master database"
      >
        <form onSubmit={handleCreateVendor} className="space-y-4">
          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1">
              Vendor Name
            </label>
            <input
              type="text"
              required
              value={newVendorName}
              onChange={(e) => setNewVendorName(e.target.value)}
              placeholder="Shenzhen MicroTech Ltd."
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1">
              Vendor Code
            </label>
            <input
              type="text"
              required
              value={newVendorCode}
              onChange={(e) => setNewVendorCode(e.target.value)}
              placeholder="SMT-09"
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1">
              Facility / Site Name
            </label>
            <input
              type="text"
              value={newVendorSite}
              onChange={(e) => setNewVendorSite(e.target.value)}
              placeholder="Facility Plant 4"
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setAddVendorModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" loading={savingVendor}>
              Create Vendor
            </Button>
          </div>
        </form>
      </Modal>

      {/* Camera Modal (Mobile rear-camera) */}
      <CameraModal
        isOpen={cameraModalOpen}
        onClose={() => setCameraModalOpen(false)}
        onCapture={(file) => handleFilesAdded([file])}
      />

      {/* Desktop Guard Modal (Webcam block with QR code handoff) */}
      <DesktopGuardModal
        isOpen={desktopGuardOpen}
        onClose={() => setDesktopGuardOpen(false)}
        onContinueDesktop={() => fileInputRef.current?.click()}
      />
    </div>
  );
};
