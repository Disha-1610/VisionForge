import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  ShieldAlert,
  Building2,
  MapPin,
  Users,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { analyticsAPI } from '../services/api';
import { StatCard } from '../components/common/StatCard';
import { SkeletonLoader } from '../components/common/SkeletonLoader';
import { useAuth } from '../context/AuthContext';

export const AnalyticsPage = () => {
  const { isAdmin } = useAuth();

  const [summary, setSummary] = useState(null);
  const [monthlyTrend, setMonthlyTrend] = useState([]);
  const [vendorRisk, setVendorRisk] = useState([]);
  const [locationBreakdown, setLocationBreakdown] = useState([]);
  const [operatorBreakdown, setOperatorBreakdown] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const promises = [
          analyticsAPI.getSummary(),
          analyticsAPI.getMonthlyTrend(),
          analyticsAPI.getVendorRisk(),
          analyticsAPI.getByLocation(),
        ];

        if (isAdmin) {
          promises.push(analyticsAPI.getByOperator());
        }

        const results = await Promise.all(promises);
        setSummary(results[0]);
        setMonthlyTrend(results[1] || []);
        setVendorRisk(results[2] || []);
        setLocationBreakdown(results[3] || []);
        if (isAdmin && results[4]) {
          setOperatorBreakdown(results[4] || []);
        }
      } catch (err) {
        console.error('Failed to load analytics data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [isAdmin]);

  // Dark mode custom tooltip for Recharts
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="p-3 rounded-xl bg-slate-900/95 border border-hud-border text-xs font-mono shadow-xl backdrop-blur-md">
          <p className="text-slate-400 font-bold mb-1">{label}</p>
          {payload.map((item, index) => (
            <p key={index} style={{ color: item.color || '#06b6d4' }}>
              {item.name}: <span className="font-bold text-white">{item.value}</span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-hud-border/70">
        <h2 className="text-xl font-black text-white tracking-tight uppercase font-telemetry">
          Risk & Vulnerability Analytics
        </h2>
        <p className="text-xs text-slate-400 font-mono mt-0.5">
          Longitudinal fraud telemetry, supplier anomaly distribution & line risk hotspots
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          <SkeletonLoader count={4} className="h-28" />
        ) : (
          <>
            <StatCard
              title="Monitored Inspections"
              value={summary?.total_inspections ?? 0}
              subtitle="Aggregated production volume"
              icon={BarChart3}
              accentColor="cyan"
            />
            <StatCard
              title="Intercepted Fraud Units"
              value={summary?.fraud_detected_count ?? 0}
              subtitle="Quarantined from supply chain"
              icon={ShieldAlert}
              accentColor="rose"
            />
            <StatCard
              title="Systemic Defect Rate"
              value={`${summary?.fraud_rate_pct ?? 0.0}%`}
              subtitle="Global anomaly percentage"
              icon={TrendingUp}
              accentColor="amber"
            />
            <StatCard
              title="Station Compliance"
              value={`${summary?.total_inspections > 0 ? ((summary.accepted_count / summary.total_inspections) * 100).toFixed(1) : '100.0'}%`}
              subtitle="Genuine components accepted"
              icon={CheckCircle}
              accentColor="emerald"
            />
          </>
        )}
      </div>

      {/* Chart Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Trend Area Chart */}
        <div className="p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl">
          <div className="flex items-center justify-between pb-3 border-b border-hud-border/70">
            <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
              Monthly Fraud Incidents Trend
            </h3>
            <span className="text-[11px] font-mono text-cyan-400">Recharts Telemetry</span>
          </div>

          <div className="h-64 w-full">
            {loading ? (
              <SkeletonLoader count={1} className="h-full" />
            ) : monthlyTrend.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs font-mono text-slate-500">
                No historical trend data recorded.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={monthlyTrend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorFraud" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.6} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2e4f" />
                  <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="fraud_count"
                    name="Fraud Cases"
                    stroke="#ef4444"
                    fillOpacity={1}
                    fill="url(#colorFraud)"
                  />
                  <Area
                    type="monotone"
                    dataKey="total_inspections"
                    name="Total Inspected"
                    stroke="#06b6d4"
                    fillOpacity={1}
                    fill="url(#colorTotal)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Vendor Risk Matrix Bar Chart */}
        <div className="p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl">
          <div className="flex items-center justify-between pb-3 border-b border-hud-border/70">
            <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
              Supplier Risk Vulnerability Index
            </h3>
            <span className="text-[11px] font-mono text-rose-400">By Component Defect</span>
          </div>

          <div className="h-64 w-full">
            {loading ? (
              <SkeletonLoader count={1} className="h-full" />
            ) : vendorRisk.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs font-mono text-slate-500">
                No vendor risk points recorded.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={vendorRisk} layout="vertical" margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2e4f" />
                  <XAxis type="number" stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <YAxis
                    dataKey="vendor_name"
                    type="category"
                    stroke="#64748b"
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    width={80}
                    tickFormatter={(v) => (v && v.length > 12 ? `${v.slice(0, 11)}…` : v)}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="fraud_count" name="Fraud Findings" fill="#f59e0b" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Location Risk Hotspots & Operator Audit Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Location Breakdown */}
        <div className="p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl">
          <div className="flex items-center gap-2 pb-3 border-b border-hud-border/70">
            <MapPin className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
              Station & Location Hotspots
            </h3>
          </div>

          <div className="divide-y divide-hud-border/60 text-xs font-mono">
            {locationBreakdown.length === 0 ? (
              <p className="text-slate-500 text-center py-4">No location risk logs recorded.</p>
            ) : (
              locationBreakdown.map((loc, i) => (
                <div key={i} className="py-2.5 flex items-center justify-between gap-3">
                  <span className="text-white font-bold min-w-0 break-all leading-snug">{loc.location}</span>
                  <div className="flex items-center gap-2 sm:gap-3 shrink-0">
                    <span className="text-slate-400">Total: {loc.total_inspections}</span>
                    <span className="text-rose-400 font-bold">Fraud: {loc.fraud_count}</span>
                    <span className="px-2 py-0.5 rounded bg-hud-card border border-hud-border text-[10px] text-cyan-300">
                      {loc.fraud_rate_pct ? `${loc.fraud_rate_pct.toFixed(1)}%` : '0%'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Admin-Only Operator Audit Log */}
        {isAdmin && (
          <div className="p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-hud-border/70">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
                  Operator Audit & Throughput (Admin Only)
                </h3>
              </div>
            </div>

            <div className="divide-y divide-hud-border/60 text-xs font-mono">
              {operatorBreakdown.length === 0 ? (
                <p className="text-slate-500 text-center py-4">
                  No per-operator inspection metrics recorded.
                </p>
              ) : (
              operatorBreakdown.map((op, i) => (
                <div key={i} className="py-2.5 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <span className="text-white font-bold break-all">{op.operator_name || op.operator_email}</span>
                  </div>
                  <div className="flex items-center gap-2 sm:gap-3 shrink-0">
                    <span className="text-slate-400">Cases: {op.total_inspections}</span>
                    <span className="text-amber-400">Overrides: {op.overridden_count || 0}</span>
                  </div>
                </div>
              ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
