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
  ShieldCheck,
  UserCheck,
  Activity,
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
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Timeline Trend Area Chart */}
        <div className="p-4 sm:p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-3 border-b border-hud-border/70">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400 shrink-0" />
              <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
                Inspection & Anomaly Telemetry Timeline
              </h3>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <span className="flex items-center gap-1.5 text-[10px] font-mono text-cyan-400">
                <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" /> Total Volume
              </span>
              <span className="flex items-center gap-1.5 text-[10px] font-mono text-rose-400">
                <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" /> Quarantined Fraud
              </span>
            </div>
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
                <AreaChart data={monthlyTrend} margin={{ top: 12, right: 12, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.45} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="colorFraud" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.5} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2e4f" opacity={0.6} />
                  <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="total_inspections"
                    name="Total Inspected"
                    stroke="#06b6d4"
                    strokeWidth={2.5}
                    dot={{ r: 3.5, fill: '#06b6d4', stroke: '#083344', strokeWidth: 1.5 }}
                    activeDot={{ r: 6, fill: '#22d3ee', stroke: '#fff', strokeWidth: 2 }}
                    fillOpacity={1}
                    fill="url(#colorTotal)"
                  />
                  <Area
                    type="monotone"
                    dataKey="fraud_count"
                    name="Fraud Cases"
                    stroke="#ef4444"
                    strokeWidth={2.5}
                    dot={{ r: 3.5, fill: '#ef4444', stroke: '#450a0a', strokeWidth: 1.5 }}
                    activeDot={{ r: 6, fill: '#f87171', stroke: '#fff', strokeWidth: 2 }}
                    fillOpacity={1}
                    fill="url(#colorFraud)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Vendor Risk Matrix Bar Chart */}
        <div className="p-4 sm:p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-3 border-b border-hud-border/70">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-amber-400 shrink-0" />
              <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
                Supplier Risk Vulnerability Index
              </h3>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <span className="flex items-center gap-1.5 text-[10px] font-mono text-cyan-400">
                <span className="w-2 h-2 rounded-full bg-cyan-500 inline-block" /> Total Volume
              </span>
              <span className="flex items-center gap-1.5 text-[10px] font-mono text-rose-400">
                <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" /> Fraud Detected
              </span>
            </div>
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
                <BarChart
                  data={vendorRisk}
                  layout="vertical"
                  margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                  barGap={3}
                  barCategoryGap={14}
                >
                  <defs>
                    <linearGradient id="barTotal" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#0891b2" stopOpacity={0.7} />
                      <stop offset="100%" stopColor="#06b6d4" stopOpacity={1} />
                    </linearGradient>
                    <linearGradient id="barFraud" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#b91c1c" stopOpacity={0.8} />
                      <stop offset="100%" stopColor="#f43f5e" stopOpacity={1} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2e4f" opacity={0.6} horizontal={false} />
                  <XAxis type="number" stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <YAxis
                    dataKey="vendor_name"
                    type="category"
                    stroke="#64748b"
                    tick={{ fontSize: 9.5, fill: '#cbd5e1' }}
                    width={110}
                    tickFormatter={(v) => {
                      if (!v) return '';
                      return v
                        .replace(' Ltd.', '')
                        .replace(' Industrial Internet', ' Industrial')
                        .replace(' Electronics QA', ' Electronics');
                    }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="total_inspections" name="Total Volume" fill="url(#barTotal)" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="fraud_count" name="Fraud Cases" fill="url(#barFraud)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Location Risk Hotspots & Operator Audit Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Location Breakdown */}
        <div className="p-4 sm:p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-hud-border/70">
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-amber-400 shrink-0" />
              <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
                Station & Location Hotspots
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              {locationBreakdown.length} Facilities Monitored
            </span>
          </div>

          <div className="divide-y divide-hud-border/60 text-xs font-mono max-h-80 overflow-y-auto pr-1">
            {locationBreakdown.length === 0 ? (
              <p className="text-slate-500 text-center py-4">No location risk logs recorded.</p>
            ) : (
              locationBreakdown.map((loc, i) => (
                <div key={i} className="py-2.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1.5 sm:gap-3">
                  <span className="text-white font-bold min-w-0 break-words leading-snug">{loc.location}</span>
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
          <div className="p-4 sm:p-6 rounded-3xl bg-hud-surface border border-hud-border space-y-4 shadow-xl flex flex-col">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1 sm:gap-2 pb-3 border-b border-hud-border/70">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-cyan-400 shrink-0" />
                <h3 className="text-sm font-bold text-white font-telemetry uppercase tracking-wider">
                  Operator Audit & Throughput (Admin Only)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-cyan-400">
                {operatorBreakdown.length} Registered Accounts
              </span>
            </div>

            {/* Dynamic Telemetry Mini-KPI Summary (All computed live from real DB state) */}
            <div className="grid grid-cols-3 gap-2 p-3 rounded-2xl bg-hud-card/60 border border-hud-border/60 text-center">
              <div>
                <p className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Active Staff</p>
                <p className="text-base font-bold font-mono text-cyan-400">
                  {operatorBreakdown.filter((op) => (op.total_inspections || 0) > 0).length || operatorBreakdown.length}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Audit Overrides</p>
                <p className="text-base font-bold font-mono text-amber-400">
                  {operatorBreakdown.reduce((acc, curr) => acc + (curr.overridden_count || 0), 0)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Audit Integrity</p>
                <p className="text-base font-bold font-mono text-emerald-400">
                  {(() => {
                    const total = operatorBreakdown.reduce((acc, curr) => acc + (curr.total_inspections || 0), 0);
                    const overrides = operatorBreakdown.reduce((acc, curr) => acc + (curr.overridden_count || 0), 0);
                    return total > 0 ? `${(((total - overrides) / total) * 100).toFixed(1)}%` : '100.0%';
                  })()}
                </p>
              </div>
            </div>

            {/* Operator Roster with Workload Distribution */}
            <div className="divide-y divide-hud-border/60 text-xs font-mono max-h-60 overflow-y-auto pr-1">
              {operatorBreakdown.length === 0 ? (
                <p className="text-slate-500 text-center py-4">
                  No per-operator inspection metrics recorded.
                </p>
              ) : (
                operatorBreakdown.map((op, i) => {
                  const totalSys = summary?.total_inspections || operatorBreakdown.reduce((sum, o) => sum + (o.total_inspections || 0), 0) || 1;
                  const sharePct = ((op.total_inspections / totalSys) * 100).toFixed(1);
                  return (
                    <div key={i} className="py-3 space-y-1.5">
                      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="w-7 h-7 rounded-lg bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-[10px] font-bold text-cyan-300 shrink-0">
                            {(op.operator_name || op.operator_email || 'OP').slice(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <p className="text-white font-bold truncate leading-tight">{op.operator_name || op.operator_email}</p>
                            <p className="text-[10px] text-slate-400 truncate">{op.operator_email}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
                          <span className="px-2 py-0.5 rounded bg-hud-card border border-hud-border text-[10px] text-slate-300">
                            Cases: <strong className="text-white">{op.total_inspections}</strong>
                          </span>
                          <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-[10px] text-amber-300">
                            Overrides: <strong>{op.overridden_count || 0}</strong>
                          </span>
                        </div>
                      </div>

                      {/* Workload Progress Bar (Only when inspections exist) */}
                      {op.total_inspections > 0 ? (
                        <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden flex items-center">
                          <div
                            className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full rounded-full transition-all duration-500"
                            style={{ width: `${Math.min(100, Math.max(8, Number(sharePct)))}%` }}
                          />
                        </div>
                      ) : (
                        <p className="text-[10px] text-slate-500 italic">No assigned inspections on record</p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
