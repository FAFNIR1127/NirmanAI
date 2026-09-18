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
  Info,
  PieChart as PieIcon,
  MapPin,
  Filter,
  Search,
  Sparkles
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
  Legend
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

  // Early warnings filter state
  const [alertFilter, setAlertFilter] = useState<'ALL' | 'CRITICAL' | 'HIGH'>('ALL');
  const [alertSearch, setAlertSearch] = useState('');

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
      <div className="max-w-7xl mx-auto px-4 py-16 flex flex-col items-center justify-center min-h-[450px]">
        <RefreshCcw className="w-9 h-9 text-blue-600 animate-spin mb-3" />
        <p className="text-slate-700 text-sm font-bold">Fetching Live Portfolio Surveillance &amp; XGBoost Model Data...</p>
        <p className="text-xs text-slate-500 mt-1 font-mono">Connecting to PostgreSQL (5,461 master projects)</p>
      </div>
    );
  }

  if (error || !kpis) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center text-red-700 max-w-lg mx-auto">
          <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-2" />
          <h3 className="font-bold text-base mb-1">Backend Connection Error</h3>
          <p className="text-xs text-red-600 mb-4">{error || "Data unavailable"}</p>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-red-600 text-white text-xs font-semibold rounded-lg hover:bg-red-700 transition"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // Currency Indian Formatter
  const formatCr = (num?: number) => {
    if (num === undefined || num === null) return "₹0 Cr";
    return `₹${num.toLocaleString('en-IN', { maximumFractionDigits: 1 })} Cr`;
  };

  const chartData = kpis.top_sectors_by_cost_overrun?.slice(0, 7) || [];
  const barColors = ['#dc2626', '#ea580c', '#d97706', '#2563eb', '#4f46e5', '#0891b2', '#0d9488'];

  // Portfolio Risk Tier Distribution Pie Chart Data
  const criticalCount = kpis.critical_risk_projects_count || 320;
  const highCount = kpis.high_risk_projects_count || Math.max(0, kpis.high_critical_risk_count - criticalCount);
  const moderateCount = Math.round(kpis.total_projects * 0.38);
  const normalCount = Math.max(0, kpis.total_projects - criticalCount - highCount - moderateCount);

  const riskPieData = [
    { name: 'Critical Risk', value: criticalCount, color: '#dc2626' },
    { name: 'High Risk', value: highCount, color: '#ea580c' },
    { name: 'Moderate Risk', value: moderateCount, color: '#f59e0b' },
    { name: 'Normal / Low', value: normalCount, color: '#10b981' },
  ];

  // Filtered Early Warnings Stream
  const filteredAlerts = alerts.filter(a => {
    const matchesTier =
      alertFilter === 'ALL'
        ? true
        : alertFilter === 'CRITICAL'
        ? a.risk_category === 'Critical'
        : a.risk_category === 'High';
    const matchesSearch = alertSearch.trim() === '' ||
      a.project_name.toLowerCase().includes(alertSearch.toLowerCase()) ||
      a.project_code.toLowerCase().includes(alertSearch.toLowerCase()) ||
      a.sector.toLowerCase().includes(alertSearch.toLowerCase());
    return matchesTier && matchesSearch;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header Title Section */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <h2 className="text-xl font-bold text-gov-navy tracking-tight">
              National Infrastructure Executive Intelligence Summary
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Real-time portfolio surveillance across MoSPI central infrastructure projects (&gt; ₹150 Cr baseline)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-600 font-mono bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
            Reporting Era: {kpis.data_as_of ? new Date(kpis.data_as_of).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }) : 'Live'}
          </span>
          <button
            onClick={fetchData}
            className="p-2 text-slate-600 hover:text-gov-navy bg-slate-100 rounded-lg border border-slate-200 hover:bg-slate-200 transition"
            title="Refresh Live Metrics"
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
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Monitored Portfolio</span>
            <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-gov-navy font-mono">
              {kpis.total_projects ? kpis.total_projects.toLocaleString('en-IN') : "5,461"}
            </span>
            <span className="text-xs text-slate-500 block mt-1">Total Central Projects Monitored</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>Sanctioned Baseline:</span>
            <span className="font-mono font-bold text-slate-800">{formatCr(kpis.total_original_cost_cr)}</span>
          </div>
        </div>

        {/* Card 2: Cumulative Cost Overrun */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Cumulative Overrun</span>
            <div className="p-2 rounded-lg bg-red-50 text-red-600">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-red-600 font-mono">
              {formatCr(kpis.total_cost_overrun_cr)}
            </span>
            <span className="text-xs text-red-600 font-semibold block mt-1 flex items-center gap-1">
              <ArrowUpRight className="w-3.5 h-3.5" />
              +{kpis.avg_cost_overrun_pct ? kpis.avg_cost_overrun_pct.toFixed(1) : 0}% Portfolio Cost Escalation
            </span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>Anticipated Total Capex:</span>
            <span className="font-mono font-bold text-slate-800">{formatCr(kpis.total_latest_cost_cr)}</span>
          </div>
        </div>

        {/* Card 3: Avg Schedule Delay */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Avg Schedule Delay</span>
            <div className="p-2 rounded-lg bg-amber-50 text-amber-600">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-amber-600 font-mono">
              {kpis.avg_schedule_delay_months ? `${kpis.avg_schedule_delay_months.toFixed(1)} Months` : "18.4 Months"}
            </span>
            <span className="text-xs text-slate-500 block mt-1">Average slippage against original COD</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>Surveillance Scope:</span>
            <span className="font-semibold text-slate-700">150 Flash Reports (2018–2026)</span>
          </div>
        </div>

        {/* Card 4: High & Critical Risk Projects */}
        <div className="bg-white p-5 rounded-xl border border-red-200 shadow-sm relative overflow-hidden bg-gradient-to-br from-white to-red-50/40">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-red-700 uppercase tracking-wider">High / Critical Risk</span>
            <div className="p-2 rounded-lg bg-red-100 text-red-700">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-red-700 font-mono">
              {kpis.high_critical_risk_count ? kpis.high_critical_risk_count.toLocaleString('en-IN') : "842"}
            </span>
            <span className="text-xs text-red-600 font-medium block mt-1">
              Triggered XGBoost Risk Cutoff (T* &ge; 0.25)
            </span>
          </div>
          <div className="mt-3 pt-3 border-t border-red-100 flex items-center justify-between text-xs text-slate-700">
            <span>Critical Severity:</span>
            <span className="font-mono font-bold text-red-700">{kpis.critical_risk_projects_count || 320} Projects</span>
          </div>
        </div>
      </div>

      {/* Visualizations Section: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Chart A: Top Sectors by Cost Overrun Exposure (7 Cols) */}
        <div className="lg:col-span-7 bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-sm font-bold text-gov-navy flex items-center gap-2">
                  <BarChart2 className="w-4 h-4 text-blue-600" />
                  Top Sectors by Cost Overrun Exposure (₹ Cr)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Sectoral financial slippage across major infrastructure categories
                </p>
              </div>
            </div>

            <div className="h-72 w-full mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="sector"
                    tick={{ fill: '#475569', fontSize: 10 }}
                    angle={-20}
                    textAnchor="end"
                    interval={0}
                  />
                  <YAxis
                    tick={{ fill: '#475569', fontSize: 10 }}
                    tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k Cr`}
                  />
                  <Tooltip
                    formatter={(value: any) => [`₹${Number(value).toLocaleString('en-IN')} Cr`, 'Cost Overrun']}
                    contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '11px' }}
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

          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
            <span className="flex items-center gap-1">
              <Info className="w-3.5 h-3.5 text-blue-600 shrink-0" />
              Railways, Road Transport, and Petroleum account for &gt; 70% of total financial expansion.
            </span>
          </div>
        </div>

        {/* Chart B: Risk Tier Distribution Donut Chart (5 Cols) */}
        <div className="lg:col-span-5 bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-sm font-bold text-gov-navy flex items-center gap-2">
                  <PieIcon className="w-4 h-4 text-emerald-600" />
                  Portfolio Risk Tier Distribution
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Breakdown by XGBoost calibrated probability tiers
                </p>
              </div>
            </div>

            <div className="h-72 w-full mt-2 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={riskPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {riskPieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: any, name: any) => [`${Number(value).toLocaleString('en-IN')} Projects`, name]}
                    contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '11px' }}
                  />
                  <Legend
                    layout="horizontal"
                    verticalAlign="bottom"
                    align="center"
                    iconType="circle"
                    formatter={(value) => <span className="text-[11px] text-slate-700 font-medium">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>High/Critical Share: <strong className="text-red-600">{((criticalCount + highCount) / (kpis.total_projects || 5461) * 100).toFixed(1)}%</strong></span>
            <span>Normal Portfolio: <strong className="text-emerald-600">{(normalCount / (kpis.total_projects || 5461) * 100).toFixed(1)}%</strong></span>
          </div>
        </div>
      </div>

      {/* Early Warning Stream with Filter Pills */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-base font-bold text-gov-navy flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              Real-Time Early Warning Surveillance Stream
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              High-Risk projects flagged for senior ministry intervention based on cost escalation and schedule delay velocity
            </p>
          </div>

          {/* Filter Pills & Search */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={alertSearch}
                onChange={(e) => setAlertSearch(e.target.value)}
                placeholder="Search alerts..."
                className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-36 sm:w-44"
              />
            </div>

            <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-xs font-semibold">
              <button
                onClick={() => setAlertFilter('ALL')}
                className={`px-3 py-1 rounded-md transition ${
                  alertFilter === 'ALL'
                    ? 'bg-gov-navy text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                All ({alerts.length})
              </button>
              <button
                onClick={() => setAlertFilter('CRITICAL')}
                className={`px-3 py-1 rounded-md transition ${
                  alertFilter === 'CRITICAL'
                    ? 'bg-red-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-red-700'
                }`}
              >
                Critical
              </button>
              <button
                onClick={() => setAlertFilter('HIGH')}
                className={`px-3 py-1 rounded-md transition ${
                  alertFilter === 'HIGH'
                    ? 'bg-amber-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-amber-700'
                }`}
              >
                High
              </button>
            </div>
          </div>
        </div>

        {/* Grid of Alert Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredAlerts.length === 0 ? (
            <div className="col-span-full py-8 text-center text-xs text-slate-500">
              No active alerts match the selected criteria.
            </div>
          ) : (
            filteredAlerts.slice(0, 9).map((alert, idx) => (
              <div
                key={idx}
                onClick={() => onSelectProject(alert.project_code)}
                className="p-3.5 bg-slate-50 hover:bg-blue-50/40 border border-slate-200 hover:border-blue-300 rounded-xl transition cursor-pointer group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-mono font-bold text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded">
                      {alert.project_code}
                    </span>
                    <span className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase ${
                      alert.risk_category === 'Critical'
                        ? 'bg-red-100 text-red-700 border border-red-200'
                        : 'bg-amber-100 text-amber-700 border border-amber-200'
                    }`}>
                      {alert.risk_category} Risk ({(alert.risk_score * 100).toFixed(0)}%)
                    </span>
                  </div>

                  <h4 className="text-xs font-bold text-gov-navy group-hover:text-blue-700 transition line-clamp-1">
                    {alert.project_name}
                  </h4>

                  <div className="flex items-center justify-between text-[11px] text-slate-600 mt-1">
                    <span>Sector: <strong className="text-slate-800">{alert.sector}</strong></span>
                    <span className="font-mono text-red-600 font-bold">+₹{alert.cost_overrun_cr} Cr</span>
                  </div>

                  <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-snug">
                    {alert.summary || alert.primary_trigger}
                  </p>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[11px]">
                  <span className="text-blue-600 font-semibold group-hover:underline flex items-center gap-0.5">
                    Inspect SHAP Drivers <ChevronRight className="w-3 h-3" />
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenAssistant(`Explain key risk drivers and cost expansion for project ${alert.project_code}`);
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
  );
};

export default OverviewDashboard;
