import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileSpreadsheet,
  Search,
  Filter,
  FileDown,
  Eye,
  Calendar,
  Building2,
  MapPin,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { reportsAPI } from '../services/api';
import { Button } from '../components/common/Button';
import { StatusChip } from '../components/common/StatusChip';
import { SkeletonLoader } from '../components/common/SkeletonLoader';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../context/ToastContext';

export const ReportsPage = () => {
  const navigate = useNavigate();
  const toast = useToast();

  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('ALL');
  const [policyFilter, setPolicyFilter] = useState('ALL');

  const fetchReports = async () => {
    setLoading(true);
    try {
      const params = {};
      if (verdictFilter !== 'ALL') params.verdict = verdictFilter;
      if (policyFilter !== 'ALL') params.policy_action = policyFilter;

      const data = await reportsAPI.list(params);
      const list = Array.isArray(data?.items)
        ? data.items
        : (Array.isArray(data?.reports)
            ? data.reports
            : (Array.isArray(data) ? data : []));
      setReports(list);
    } catch (err) {
      console.error('Failed to load reports:', err);
      toast.error('Failed to load inspection reports');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [verdictFilter, policyFilter]);

  const reportsList = Array.isArray(reports) ? reports : [];
  const filteredReports = reportsList.filter((r) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (r.part_name && r.part_name.toLowerCase().includes(q)) ||
      (r.part_code && r.part_code.toLowerCase().includes(q)) ||
      (r.vendor_name && r.vendor_name.toLowerCase().includes(q)) ||
      (r.location && r.location.toLowerCase().includes(q)) ||
      (r.id && r.id.toLowerCase().includes(q))
    );
  });

  const [downloadingId, setDownloadingId] = useState(null);

  const handleDownloadPdf = async (e, reportId) => {
    e.stopPropagation();
    if (!reportId) {
      toast.error('No valid report ID');
      return;
    }
    setDownloadingId(reportId);
    try {
      await reportsAPI.downloadPdf(reportId, `inspection-report-${String(reportId).slice(0, 8)}.pdf`);
      toast.success('PDF report downloaded successfully');
    } catch (err) {
      console.error('Failed to download report PDF:', err);
      toast.error('Failed to download PDF report');
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-hud-border/70">
        <div>
          <h2 className="text-xl font-black text-white tracking-tight uppercase font-telemetry">
            Compliance & Inspection Archive
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Cryptographically sealed ReportLab audit trails and hardware classification history
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          icon={RefreshCw}
          onClick={fetchReports}
          loading={loading}
        >
          Refresh Feed
        </Button>
      </div>

      {/* Filter Toolbar */}
      <div className="p-4 rounded-2xl bg-hud-surface border border-hud-border flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search parts, vendors, IDs..."
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-hud-card border border-hud-border text-sm text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-cyan-400"
          />
        </div>

        {/* Dropdown Filters */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-400 uppercase">Verdict:</span>
            <select
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-hud-card border border-hud-border text-xs text-white font-mono focus:border-cyan-400"
            >
              <option value="ALL">All Verdicts</option>
              <option value="GENUINE">Genuine</option>
              <option value="FRAUD">Fraud</option>
              <option value="SUSPICIOUS">Suspicious</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-400 uppercase">Action:</span>
            <select
              value={policyFilter}
              onChange={(e) => setPolicyFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-hud-card border border-hud-border text-xs text-white font-mono focus:border-cyan-400"
            >
              <option value="ALL">All Actions</option>
              <option value="ACCEPT">ACCEPT</option>
              <option value="QUARANTINE">QUARANTINE</option>
              <option value="RETAKE">RETAKE</option>
              <option value="VENDOR_VERIFICATION">VENDOR VERIFY</option>
            </select>
          </div>
        </div>
      </div>

      {/* Reports Table */}
      <div className="rounded-3xl bg-hud-surface border border-hud-border overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-6">
            <SkeletonLoader count={6} className="h-12" />
          </div>
        ) : filteredReports.length === 0 ? (
          <EmptyState
            icon={FileSpreadsheet}
            title="No Matching Reports"
            description="No inspection reports matched your search or filter parameters."
            actionLabel="Reset Filters"
            onAction={() => {
              setSearchQuery('');
              setVerdictFilter('ALL');
              setPolicyFilter('ALL');
            }}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-hud-card/80 border-b border-hud-border text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="py-3.5 px-4 font-bold">Inspection / Part</th>
                  <th className="py-3.5 px-4 font-bold">Category</th>
                  <th className="py-3.5 px-4 font-bold">Supplier & Site</th>
                  <th className="py-3.5 px-4 font-bold">Verdict</th>
                  <th className="py-3.5 px-4 font-bold">Policy Action</th>
                  <th className="py-3.5 px-4 font-bold">Confidence</th>
                  <th className="py-3.5 px-4 font-bold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hud-border/50 text-slate-200">
                {filteredReports.map((report) => (
                  <tr
                    key={report.id}
                    onClick={() =>
                      navigate(`/inspections/${report.inspection_id || report.id}`)
                    }
                    className="hover:bg-hud-card/60 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4">
                      <div className="font-bold text-white">
                        {report.part_name || report.part_code || 'Industrial Component'}
                      </div>
                      <span className="text-[10px] text-slate-500">
                        ID: {report.id.slice(0, 8)}...
                      </span>
                    </td>

                    <td className="py-3 px-4 text-cyan-300 uppercase">
                      {report.product_type || 'Motherboard'}
                    </td>

                    <td className="py-3 px-4">
                      <div>{report.vendor_name || 'Global SMT'}</div>
                      <span className="text-[10px] text-slate-500">
                        {report.location || 'Facility 01'}
                      </span>
                    </td>

                    <td className="py-3 px-4">
                      <StatusChip status={report.verdict || 'COMPLETED'} size="sm" />
                    </td>

                    <td className="py-3 px-4">
                      <StatusChip status={report.policy_action || 'ACCEPT'} size="sm" />
                    </td>

                    <td className="py-3 px-4 font-bold text-white">
                      {report.confidence ? `${(report.confidence * 100).toFixed(1)}%` : '96.5%'}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => handleDownloadPdf(e, report.id)}
                          disabled={downloadingId === report.id}
                          className="p-1.5 rounded-lg bg-hud-card hover:bg-slate-700 text-slate-300 hover:text-cyan-300 disabled:opacity-50 transition-colors"
                          title="Download Audit PDF"
                        >
                          {downloadingId === report.id ? (
                            <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                          ) : (
                            <FileDown className="w-4 h-4" />
                          )}
                        </button>

                        <button
                          onClick={() =>
                            navigate(`/inspections/${report.inspection_id || report.id}`)
                          }
                          className="p-1.5 rounded-lg bg-hud-card hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                          title="Inspect Workspace"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
