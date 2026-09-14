import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ScanEye,
  ShieldCheck,
  AlertTriangle,
  Percent,
  CheckCircle2,
  ArrowRight,
  Database,
  Clock,
  Layers,
} from 'lucide-react';
import { analyticsAPI, reportsAPI } from '../services/api';
import { StatCard } from '../components/common/StatCard';
import { StatusChip } from '../components/common/StatusChip';
import { Button } from '../components/common/Button';
import { SkeletonLoader } from '../components/common/SkeletonLoader';
import { GoldenRepositoryDrawer } from '../components/products/GoldenRepositoryDrawer';
import { useAuth } from '../context/AuthContext';

export const DashboardPage = () => {
  const navigate = useNavigate();
  const { user, isAdmin } = useAuth();

  const [summary, setSummary] = useState(null);
  const [recentReports, setRecentReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [goldenDrawerOpen, setGoldenDrawerOpen] = useState(false);

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        const [sumData, reportsData] = await Promise.all([
          analyticsAPI.getSummary(),
          reportsAPI.list({ limit: 6 }),
        ]);
        setSummary(sumData);
        const list = Array.isArray(reportsData?.items)
          ? reportsData.items
          : (Array.isArray(reportsData?.reports)
              ? reportsData.reports
              : (Array.isArray(reportsData) ? reportsData : []));
        setRecentReports(list);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Welcome Banner */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-hud-surface via-hud-card to-hud-surface border border-hud-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-mono font-bold text-emerald-400 uppercase tracking-wider">
              Terminal Active • Station 01
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight">
            Welcome back, {user?.full_name || 'Inspector'}
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Role: {user?.role?.toUpperCase()} • Hardware Multi-Agent Pipeline Ready
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isAdmin && (
            <Button
              variant="secondary"
              size="sm"
              icon={Database}
              onClick={() => setGoldenDrawerOpen(!goldenDrawerOpen)}
            >
              {goldenDrawerOpen ? 'Close Repositories' : 'Golden Repositories'}
            </Button>
          )}

          <Button
            variant="primary"
            size="md"
            icon={ScanEye}
            onClick={() => navigate('/inspections/new')}
          >
            New Inspection
          </Button>
        </div>
      </div>

      {/* Admin Golden Repository Drawer */}
      {isAdmin && (
        <GoldenRepositoryDrawer
          isOpen={goldenDrawerOpen}
          onClose={() => setGoldenDrawerOpen(false)}
        />
      )}

      {/* KPI Telemetry StatCards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          <SkeletonLoader count={4} className="h-28" />
        ) : (
          <>
            <StatCard
              title="Total Inspections"
              value={summary?.total_inspections ?? 0}
              subtitle="All historical processed units"
              icon={ScanEye}
              accentColor="cyan"
            />
            <StatCard
              title="Fraud Detected"
              value={summary?.total_fraud ?? 0}
              subtitle="Tampered or counterfeit parts"
              icon={AlertTriangle}
              accentColor="rose"
            />
            <StatCard
              title="Fraud Incident Rate"
              value={`${summary?.fraud_rate ? (summary.fraud_rate * 100).toFixed(1) : '0.0'}%`}
              subtitle="Quarantine / Total"
              icon={Percent}
              accentColor="amber"
            />
            <StatCard
              title="Pass Yield Rate"
              value={`${summary?.pass_rate ? (summary.pass_rate * 100).toFixed(1) : '100.0'}%`}
              subtitle="Factory floor genuine yield"
              icon={CheckCircle2}
              accentColor="emerald"
            />
          </>
        )}
      </div>

      {/* Recent Inspection Activity Feed */}
      <div className="p-6 rounded-3xl bg-hud-surface border border-hud-border shadow-xl">
        <div className="flex items-center justify-between pb-4 border-b border-hud-border/70 mb-4">
          <div className="flex items-center gap-2.5">
            <Clock className="w-5 h-5 text-cyan-400" />
            <h3 className="text-base font-bold text-white tracking-wide">
              Recent Inspection Activity
            </h3>
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon={ArrowRight}
            onClick={() => navigate('/reports')}
          >
            View All Reports
          </Button>
        </div>

        {loading ? (
          <SkeletonLoader count={3} className="h-12" />
        ) : !Array.isArray(recentReports) || recentReports.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs font-mono">
            No inspections recorded yet. Launch your first inspection to begin hardware QA.
          </div>
        ) : (
          <div className="divide-y divide-hud-border/50">
            {recentReports.map((item) => (
              <div
                key={item.id}
                onClick={() => navigate(`/inspections/${item.inspection_id || item.id}`)}
                className="py-3.5 px-2 flex items-center justify-between hover:bg-hud-card/60 rounded-xl transition-all cursor-pointer group"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 rounded-xl bg-slate-800 text-cyan-400 group-hover:scale-105 transition-transform">
                    <Layers className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-white font-mono">
                        {item.part_name || item.part_code || 'Hardware Component'}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">
                        ({item.product_type})
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-400 font-mono mt-0.5">
                      <span>Vendor: {item.vendor_name || 'Standard QA'}</span>
                      <span>•</span>
                      <span>Loc: {item.location || 'Site 1'}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <StatusChip status={item.verdict || item.policy_action || 'COMPLETED'} />
                  <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
