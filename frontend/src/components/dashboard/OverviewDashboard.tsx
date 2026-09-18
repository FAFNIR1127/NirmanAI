import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  AlertTriangle,
  Clock,
  Layers,
  ArrowUpRight,
  ShieldAlert,
  ChevronRight,
  BarChart2,
  RefreshCcw,
  Info
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import api from '../../services/apiClient';
import { PortfolioKPIs, EarlyWarningAlert } from '../../types/api';

interface OverviewDashboardProps {
  onSelectProject: (code: string) => void;
  onOpenAssistant: (initialQuery?: string) => void;
}

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  onSelectProject,
  onOpenAssistant
}) => {
  const [kpis, setKpis] = useState<PortfolioKPIs | null>(null);
  const [alerts, setAlerts] = useState<EarlyWarningAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [kpiData, alertData] = await Promise.all([
        api.getPortfolioKPIs(),
        api.getEarlyWarnings()
      ]);
      setKpis(kpiData);
      setAlerts(alertData.alerts || []);
    } catch (err: any) {
      console.error("Failed to load overview data:", err);
      setError("Unable to connect to backend analytics server. Ensure FastAPI is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 flex flex-col items-center justify-center min-h-[400px]">
        <RefreshCcw className="w-8 h-8 text-blue-600 animate-spin mb-3" />
        <p className="text-slate-600 text-sm font-medium">Fetching Live Portfolio Analytics & XGBoost Risk Model Data...</p>
      </div>
    );
  }

  if (error || !kpis) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center text-red-700">
          <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-2" />
          <h3 className="font-bold text-lg mb-1">Data Connection Error</h3>
          <p className="text-sm text-red-600 mb-4">{error || "Data unavailable"}</p>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-red-600 text-white text-xs font-semibold rounded hover:bg-red-700 transition"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // Format currency in Indian Format (Cr)
  const formatCr = (num?: number) => {
    if (num === undefined || num === null) return "Data unavailable";
    return `₹${num.toLocaleString('en-IN', { maximumFractionDigits: 1 })} Cr`;
  };

  const chartData = kpis.top_sectors_by_cost_overrun?.slice(0, 7) || [];
  const barColors = ['#dc2626', '#ea580c', '#d97706', '#2563eb', '#4f46e5', '#0891b2', '#0d9488'];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header Title Section */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-gov-navy tracking-tight flex items-center gap-2">
            Infrastructure Monitoring Executive Summary
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Real-time portfolio surveillance across MoSPI central infrastructure projects (&gt; ₹150 Cr baseline)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 font-mono bg-slate-100 px-3 py-1.5 rounded border border-slate-200">
            Last Updated: {kpis.data_as_of ? new Date(kpis.data_as_of).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Live'}
          </span>
          <button
            onClick={fetchData}
            className="p-2 text-slate-500 hover:text-gov-navy bg-slate-100 rounded border border-slate-200 hover:bg-slate-200 transition"
            title="Refresh Data"
          >
            <RefreshCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Monitored Projects */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Monitored Projects</span>
            <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-gov-navy font-mono">
              {kpis.total_projects ? kpis.total_projects.toLocaleString('en-IN') : "Data unavailable"}
            </span>
            <span className="text-xs text-slate-500 block mt-1">Projects &gt; ₹150 Cr Baseline</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>Original Cost:</span>
            <span className="font-mono font-medium">{formatCr(kpis.total_original_cost_cr)}</span>
          </div>
        </div>

        {/* Card 2: Cumulative Cost Overrun */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Cumulative Overrun</span>
            <div className="p-2 rounded-lg bg-red-50 text-red-600">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-red-600 font-mono">
              {formatCr(kpis.total_cost_overrun_cr)}
            </span>
            <span className="text-xs text-red-600 font-medium block mt-1 flex items-center gap-1">
              <ArrowUpRight className="w-3.5 h-3.5" />
              +{kpis.avg_cost_overrun_pct ? kpis.avg_cost_overrun_pct.toFixed(1) : 0}% Portfolio Escalation
            </span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>Anticipated Total:</span>
            <span className="font-mono font-medium">{formatCr(kpis.total_latest_cost_cr)}</span>
          </div>
        </div>

        {/* Card 3: Avg Schedule Delay */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Avg Schedule Delay</span>
            <div className="p-2 rounded-lg bg-amber-50 text-amber-600">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-amber-600 font-mono">
              {kpis.avg_schedule_delay_months ? `${kpis.avg_schedule_delay_months.toFixed(1)} Months` : "Data unavailable"}
            </span>
            <span className="text-xs text-slate-500 block mt-1">Average slippage against original COD</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>Surveillance Period:</span>
            <span className="font-medium text-slate-700">2017 – 2026</span>
          </div>
        </div>

        {/* Card 4: High & Critical Risk Projects */}
        <div className="bg-white p-5 rounded-xl border border-red-200 shadow-sm relative overflow-hidden bg-gradient-to-br from-white to-red-50/30">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-red-700 uppercase tracking-wider">High / Critical Risk</span>
            <div className="p-2 rounded-lg bg-red-100 text-red-700">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-red-700 font-mono">
              {kpis.high_critical_risk_count ? kpis.high_critical_risk_count.toLocaleString('en-IN') : "Data unavailable"}
            </span>
            <span className="text-xs text-red-600 font-medium block mt-1">
              Triggered XGBoost Risk Cutoff (T* &ge; 0.28)
            </span>
          </div>
          <div className="mt-3 pt-3 border-t border-red-100 flex items-center justify-between text-xs text-slate-700">
            <span>Critical Category:</span>
            <span className="font-mono font-bold text-red-700">{kpis.critical_risk_projects_count || 0} Projects</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Sector Overrun Chart + Early Warning Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sector Overrun Chart (2 cols) */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-gov-navy flex items-center gap-2">
                  <BarChart2 className="w-5 h-5 text-blue-600" />
                  Top Sectors by Cost Overrun Exposure (₹ Cr)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Sectoral breakdown of accumulated financial slippage across major infrastructure categories
                </p>
              </div>
            </div>

            <div className="h-72 w-full mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 25 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="sector"
                    tick={{ fill: '#475569', fontSize: 11 }}
                    angle={-25}
                    textAnchor="end"
                    interval={0}
                  />
                  <YAxis
                    tick={{ fill: '#475569', fontSize: 11 }}
                    tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k Cr`}
                  />
                  <Tooltip
                    formatter={(value: any) => [`₹${Number(value).toLocaleString('en-IN')} Cr`, 'Cost Overrun']}
                    contentStyle={{ backgroundColor: '#0f172a', borderRadius: '6px', color: '#fff', fontSize: '12px' }}
                  />
                  <Bar dataKey="overrun_cr" radius={[4, 4, 0, 0]}>
                    {chartData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={barColors[index % barColors.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <Info className="w-3.5 h-3.5 text-blue-600" />
              Railways, Road Transport, and Petroleum account for the largest capital delays.
            </span>
          </div>
        </div>

        {/* Early Warning Stream (1 col) */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col h-[460px]">
          <div className="flex items-center justify-between mb-3 pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-base font-bold text-gov-navy flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-600" />
                Early Warning Stream
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">High-Risk Projects Requiring Officer Intervention</p>
            </div>
            <span className="bg-red-100 text-red-700 text-xs font-bold px-2 py-0.5 rounded-full font-mono">
              {alerts.length} Active
            </span>
          </div>

          <div className="flex-1 overflow-y-auto pr-1 space-y-3">
            {alerts.length === 0 ? (
              <p className="text-slate-500 text-xs text-center py-10">No critical alerts at this threshold.</p>
            ) : (
              alerts.map((alert, idx) => (
                <div
                  key={idx}
                  onClick={() => onSelectProject(alert.project_code)}
                  className="p-3 bg-slate-50 hover:bg-blue-50/50 border border-slate-200 hover:border-blue-300 rounded-lg transition cursor-pointer group"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-mono font-bold text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded">
                      {alert.project_code}
                    </span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                      alert.risk_category === 'Critical'
                        ? 'bg-red-100 text-red-700 border border-red-200'
                        : 'bg-amber-100 text-amber-700 border border-amber-200'
                    }`}>
                      {alert.risk_category} Risk ({alert.risk_score ? (alert.risk_score * 100).toFixed(0) : 0}%)
                    </span>
                  </div>

                  <h4 className="text-xs font-bold text-gov-navy group-hover:text-blue-700 transition line-clamp-1">
                    {alert.project_name}
                  </h4>

                  <div className="flex items-center justify-between text-[11px] text-slate-600 mt-1">
                    <span>Sector: <strong className="text-slate-800">{alert.sector}</strong></span>
                    <span className="font-mono text-red-600 font-semibold">+₹{alert.cost_overrun_cr} Cr</span>
                  </div>

                  <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-tight">
                    {alert.summary || alert.primary_trigger}
                  </p>

                  <div className="mt-2 pt-1.5 border-t border-slate-200/60 flex items-center justify-between text-[11px]">
                    <span className="text-blue-600 font-medium group-hover:underline flex items-center gap-0.5">
                      Inspect SHAP Drivers <ChevronRight className="w-3 h-3" />
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenAssistant(`Tell me why project ${alert.project_code} has high risk score.`);
                      }}
                      className="text-slate-500 hover:text-blue-700 text-[10px] font-medium underline"
                    >
                      Ask Copilot
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
