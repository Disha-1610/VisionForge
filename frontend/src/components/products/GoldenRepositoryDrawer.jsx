import React, { useState, useEffect } from 'react';
import { Database, Plus, Trash2, CheckCircle, Image as ImageIcon, Loader2, AlertCircle } from 'lucide-react';
import { productsAPI } from '../../services/api';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export const GoldenRepositoryDrawer = ({ isOpen, onClose }) => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  // Form state
  const [productType, setProductType] = useState('motherboard');
  const [partName, setPartName] = useState('');
  const [partCode, setPartCode] = useState('');
  const [imageFile, setImageFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const toast = useToast();

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const data = await productsAPI.list();
      setProducts(data || []);
    } catch (err) {
      console.error('Failed to load golden references:', err);
      toast.error('Failed to load golden references');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchProducts();
    }
  }, [isOpen]);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!imageFile) {
      toast.warning('Please select a reference image to upload');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('product_type', productType);
    formData.append('part_name', partName);
    formData.append('part_code', partCode);

    try {
      await productsAPI.upload(formData);
      toast.success('Golden Reference indexed into FAISS successfully!');
      setUploadModalOpen(false);
      setImageFile(null);
      setPartName('');
      setPartCode('');
      fetchProducts();
    } catch (err) {
      console.error('Upload failed:', err);
      const detail = err.response?.data?.detail || 'Failed to upload golden reference image';
      toast.error(detail);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete Golden Reference "${name}" and remove from FAISS index?`)) return;

    try {
      await productsAPI.delete(id);
      toast.success(`Removed "${name}" from Golden Repository`);
      fetchProducts();
    } catch (err) {
      console.error('Delete failed:', err);
      toast.error('Failed to delete golden reference');
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="p-4 sm:p-6 rounded-2xl bg-hud-surface border border-hud-border space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-4 border-b border-hud-border/70">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shrink-0">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white tracking-wide">
                Golden Reference Repository
              </h3>
              <p className="text-xs text-slate-400 font-mono">
                Admin Vector Intelligence & Ground Truth Repository (FAISS Connected)
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            <Button
              size="sm"
              variant="primary"
              icon={Plus}
              onClick={() => setUploadModalOpen(true)}
              className="flex-1 sm:flex-initial"
            >
              Upload Golden Ref
            </Button>
            <Button size="sm" variant="secondary" onClick={onClose} className="flex-1 sm:flex-initial">
              Collapse
            </Button>
          </div>
        </div>

        {/* Reference List */}
        {loading ? (
          <div className="flex items-center justify-center p-8 text-cyan-400 gap-2">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-xs font-mono">Querying FAISS repository...</span>
          </div>
        ) : products.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs font-mono">
            No golden reference templates uploaded yet. Click "Upload Golden Ref" to index your first
            standard.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {products.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-xl bg-hud-card border border-hud-border/80 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 uppercase">
                      {item.product_type || item.meta?.product_type || 'Motherboard'}
                    </span>
                    <span className="text-xs font-mono text-emerald-400 flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" />
                      <span>Indexed</span>
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-white truncate">{item.part_name}</h4>
                  <p className="text-xs font-mono text-slate-400 mt-0.5">
                    Code: <span className="text-cyan-400 font-semibold">{item.part_code || item.part_id}</span>
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-hud-border/60 flex items-center justify-between">
                  <span className="text-[11px] font-mono text-slate-500">
                    ID: {item.id.slice(0, 8)}...
                  </span>
                  <button
                    onClick={() => handleDelete(item.id, item.part_name)}
                    className="p-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors"
                    title="Delete Reference"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upload Modal */}
      <Modal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        title="Index New Golden Reference"
        subtitle="Upload standard baseline image and generate FAISS embedding vector"
      >
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1">
              Product Category
            </label>
            <select
              value={productType}
              onChange={(e) => setProductType(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono"
            >
              <option value="motherboard">Motherboard / Microcontroller</option>
              <option value="battery">Industrial Battery Pack</option>
              <option value="ram">High-Speed DDR4 RAM</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1">
              Part Name
            </label>
            <input
              type="text"
              required
              value={partName}
              onChange={(e) => setPartName(e.target.value)}
              placeholder="STM32F4-Discovery Golden PCB"
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1">
              Part Code
            </label>
            <input
              type="text"
              required
              value={partCode}
              onChange={(e) => setPartCode(e.target.value)}
              placeholder="pcb_mcu_v2"
              className="w-full px-3 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-400 mb-1">
              Reference Image File
            </label>
            <input
              type="file"
              required
              accept="image/jpeg,image/png"
              onChange={(e) => setImageFile(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-cyan-400 hover:file:bg-slate-700"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setUploadModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" loading={uploading}>
              Index to FAISS
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
};
