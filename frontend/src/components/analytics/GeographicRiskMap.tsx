import React, { useState, useEffect } from 'react';
import {
  Map,
  Layers,
  RefreshCcw,
  ShieldAlert,
  ArrowUpRight,
  TrendingUp,
  Clock,
  IndianRupee,
  Search,
  Filter,
  CheckCircle2,
  ChevronRight,
  Info
} from 'lucide-react';
import api from '../../services/apiClient';
import { GeographicRiskItem } from '../../types/api';
import { IndiaMapSvg, MetricType } from './IndiaMapSvg';

interface GeographicRiskMapProps {
  onSelectProject?: (code: string) => void;
  onNavigateToPortfolio?: (filterState?: string) => void;
}

export const GeographicRiskMap: React.FC<GeographicRiskMapProps> = ({
  onSelectProject,
  onNavigateToPortfolio
}) => {
  const [states, setStates] = useState<GeographicRiskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedStateName, setSelectedStateName] = useState<string | null>('Maharashtra');
  const [activeMetric, setActiveMetric] = useState<MetricType>('risk');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<'total_projects' | 'risk_count' | 'total_cost_overrun_cr' | 'avg_delay_months'>('risk_count');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const fetchGeographicRisk = () => {
    setLoading(true);
    api.getGeographicRisk()
      .then(res => {
        const list = res.states || [];
        setStates(list);
        if (list.length > 0 && !selectedStateName) {
          setSelectedStateName(list[0].state);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load geographic risk:", err);
        setStates([]);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchGeographicRisk();
  }, []);

  const selectedStateData = states.find(
    s => s.state.toLowerCase().trim() === (selectedStateName || '').toLowerCase().trim()
  ) || states[0];

  // Aggregated National Numbers
  const totalNationalProjects = states.reduce((acc, s) => acc + s.total_projects, 0);
  const totalNationalOverrun = states.reduce((acc, s) => acc + s.total_cost_overrun_cr, 0);
  const totalNationalHighRisk = states.reduce((acc, s) => acc + (s.high_risk_projects + s.critical_risk_projects), 0);

  // Filtered and sorted states table
  const filteredStates = states.filter(s =>
    s.state.toLowerCase().includes(searchQuery.toLowerCase().trim())
  );

  filteredStates.sort((a, b) => {
    let valA = 0;
    let valB = 0;
    if (sortField === 'risk_count') {
      valA = a.high_risk_projects + a.critical_risk_projects;
      valB = b.high_risk_projects + b.critical_risk_projects;
    } else {
      valA = a[sortField];
      valB = b[sortField];
    }
    return sortOrder === 'desc' ? valB - valA : valA - valB;
  });

  const topRiskStates = [...states]
    .sort((a, b) => (b.high_risk_projects + b.critical_risk_projects) - (a.high_risk_projects + a.critical_risk_projects))
    .slice(0, 5);

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gov-navy tracking-tight flex items-center gap-2">
            <Map className="w-5 h-5 text-blue-600" />
            Interactive Geographic Risk &amp; Spatial Exposure Map
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Real-time geospatial analytics across Indian States &amp; Union Territories (MoSPI Monitored Infrastructure)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchGeographicRisk}
            className="p-2 text-slate-600 hover:text-gov-navy bg-slate-100 rounded-lg border border-slate-200 hover:bg-slate-200 transition text-xs font-semibold flex items-center gap-1.5"
            title="Refresh Map Data"
          >
            <RefreshCcw className="w-4 h-4" />
            <span>Live Sync</span>
          </button>
        </div>
      </div>

      {/* Top National Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Tracked Regions</span>
          <span className="text-2xl font-extrabold text-gov-navy font-mono mt-1 block">
            {states.length} States / UTs
          </span>
          <span className="text-[11px] text-slate-500 mt-1 block">
            {totalNationalProjects.toLocaleString('en-IN')} Monitored Projects
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">High / Critical Risk</span>
          <span className="text-2xl font-extrabold text-red-600 font-mono mt-1 block">
            {totalNationalHighRisk.toLocaleString('en-IN')} Projects
          </span>
          <span className="text-[11px] text-slate-500 mt-1 block">
            {totalNationalProjects > 0 ? ((totalNationalHighRisk / totalNationalProjects) * 100).toFixed(1) : 0}% Risk Concentration
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">National Cost Escalation</span>
          <span className="text-2xl font-extrabold text-amber-600 font-mono mt-1 block">
            ₹{totalNationalOverrun.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr
          </span>
          <span className="text-[11px] text-slate-500 mt-1 block">Cumulative State Slippage</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Highest Exposure Region</span>
          <span className="text-2xl font-extrabold text-blue-700 font-mono mt-1 block truncate">
            {topRiskStates[0]?.state || 'Maharashtra'}
          </span>
          <span className="text-[11px] text-slate-500 mt-1 block">
            {topRiskStates[0] ? (topRiskStates[0].high_risk_projects + topRiskStates[0].critical_risk_projects) : 0} Critical Projects
          </span>
        </div>
      </div>

      {/* Main Interactive Map & Detail Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Map Container & Metric Selectors (7 Cols) */}
        <div className="lg:col-span-7 bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Heatmap Visualization Metric:
            </span>
            {/* Metric Mode Switcher */}
            <div className="flex flex-wrap gap-1 bg-slate-100 p-1 rounded-lg text-xs">
              <button
                onClick={() => setActiveMetric('risk')}
                className={`px-2.5 py-1 rounded-md font-semibold transition ${
                  activeMetric === 'risk'
                    ? 'bg-red-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                🔴 Risk Exposure
              </button>
              <button
                onClick={() => setActiveMetric('cost')}
                className={`px-2.5 py-1 rounded-md font-semibold transition ${
                  activeMetric === 'cost'
                    ? 'bg-amber-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                💰 Cost Overrun
              </button>
              <button
                onClick={() => setActiveMetric('delay')}
                className={`px-2.5 py-1 rounded-md font-semibold transition ${
                  activeMetric === 'delay'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                ⏱️ Avg Delay
              </button>
              <button
                onClick={() => setActiveMetric('projects')}
                className={`px-2.5 py-1 rounded-md font-semibold transition ${
                  activeMetric === 'projects'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                🏗️ Total Projects
              </button>
            </div>
          </div>

          {/* Map Area */}
          {loading ? (
            <div className="h-[480px] flex flex-col items-center justify-center text-slate-500 text-xs">
              <RefreshCcw className="w-8 h-8 animate-spin text-blue-600 mb-3" />
              <span>Rendering Interactive India Spatial Model...</span>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-2">
              <IndiaMapSvg
                statesData={states}
                selectedState={selectedStateName}
                onSelectState={(name) => setSelectedStateName(name)}
                activeMetric={activeMetric}
              />

              {/* Dynamic Legend */}
              <div className="mt-4 w-full flex items-center justify-between text-[11px] text-slate-500 px-4 bg-slate-50 py-2 rounded-lg border border-slate-200">
                <span className="font-semibold">Low Intensity</span>
                <div className="flex items-center gap-1.5">
                  {activeMetric === 'risk' && (
                    <>
                      <span className="w-3.5 h-3.5 rounded bg-[#dcfce7] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#fef08a] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#fed7aa] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#f87171] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#b91c1c] border border-slate-300"></span>
                    </>
                  )}
                  {activeMetric === 'cost' && (
                    <>
                      <span className="w-3.5 h-3.5 rounded bg-[#dcfce7] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#fed7aa] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#fb923c] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#ea580c] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#991b1b] border border-slate-300"></span>
                    </>
                  )}
                  {activeMetric === 'delay' && (
                    <>
                      <span className="w-3.5 h-3.5 rounded bg-[#f1f5f9] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#fde047] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#fb923c] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#dc2626] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#7f1d1d] border border-slate-300"></span>
                    </>
                  )}
                  {activeMetric === 'projects' && (
                    <>
                      <span className="w-3.5 h-3.5 rounded bg-[#dbeafe] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#93c5fd] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#3b82f6] border border-slate-300"></span>
                      <span className="w-3.5 h-3.5 rounded bg-[#1d4ed8] border border-slate-300"></span>
                    </>
                  )}
                </div>
                <span className="font-semibold">High Intensity</span>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Selected State Deep-Dive & Top Risk Leaderboard (5 Cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Selected State Intelligence Card */}
          {selectedStateData && (
            <div className="bg-white p-6 rounded-xl border-2 border-blue-600 shadow-md space-y-4">
              <div className="flex items-start justify-between border-b border-slate-100 pb-3">
                <div>
                  <span className="text-[10px] font-bold text-blue-700 uppercase tracking-widest bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                    Selected Region
                  </span>
                  <h3 className="text-xl font-extrabold text-gov-navy mt-1">
                    {selectedStateData.state}
                  </h3>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-500 block">Total Projects</span>
                  <span className="text-lg font-bold font-mono text-slate-800">
                    {selectedStateData.total_projects}
                  </span>
                </div>
              </div>

              {/* Key State Metrics Grid */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-red-50/80 rounded-lg border border-red-200">
                  <span className="text-red-700 font-medium block">Critical Risk</span>
                  <span className="text-lg font-bold font-mono text-red-700 block mt-0.5">
                    {selectedStateData.critical_risk_projects}
                  </span>
                  <span className="text-[10px] text-red-600">Highest Alert Tier</span>
                </div>

                <div className="p-3 bg-orange-50/80 rounded-lg border border-orange-200">
                  <span className="text-orange-700 font-medium block">High Risk</span>
                  <span className="text-lg font-bold font-mono text-orange-700 block mt-0.5">
                    {selectedStateData.high_risk_projects}
                  </span>
                  <span className="text-[10px] text-orange-600">Early Warning Tier</span>
                </div>

                <div className="p-3 bg-amber-50/80 rounded-lg border border-amber-200">
                  <span className="text-amber-800 font-medium block">Cost Overrun</span>
                  <span className="text-sm font-bold font-mono text-amber-700 block mt-0.5">
                    ₹{selectedStateData.total_cost_overrun_cr.toLocaleString('en-IN')} Cr
                  </span>
                  <span className="text-[10px] text-amber-600">Financial Exposure</span>
                </div>

                <div className="p-3 bg-purple-50/80 rounded-lg border border-purple-200">
                  <span className="text-purple-800 font-medium block">Average Delay</span>
                  <span className="text-sm font-bold font-mono text-purple-700 block mt-0.5">
                    {selectedStateData.avg_delay_months.toFixed(1)} Months
                  </span>
                  <span className="text-[10px] text-purple-600">Schedule Slippage</span>
                </div>
              </div>

              {/* Risk Density Meter */}
              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-xs font-semibold text-slate-700">
                  <span>High/Critical Risk Density</span>
                  <span className="font-mono text-red-600">
                    {selectedStateData.total_projects > 0
                      ? (((selectedStateData.high_risk_projects + selectedStateData.critical_risk_projects) / selectedStateData.total_projects) * 100).toFixed(1)
                      : 0}%
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden border border-slate-200">
                  <div
                    className="bg-gradient-to-r from-amber-500 to-red-600 h-2.5 rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(100, selectedStateData.total_projects > 0
                        ? (((selectedStateData.high_risk_projects + selectedStateData.critical_risk_projects) / selectedStateData.total_projects) * 100)
                        : 0)}%`
                    }}
                  ></div>
                </div>
              </div>
            </div>
          )}

          {/* Top 5 High-Risk States Leaderboard */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
            <h4 className="text-xs font-bold text-gov-navy uppercase tracking-wider flex items-center justify-between">
              <span>Top Critical Risk States</span>
              <span className="text-[10px] font-normal text-slate-500">Sorted by High/Critical Count</span>
            </h4>

            <div className="space-y-2">
              {topRiskStates.map((st, idx) => {
                const totalRisk = st.high_risk_projects + st.critical_risk_projects;
                const isSelected = selectedStateName && selectedStateName.toLowerCase() === st.state.toLowerCase();
                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedStateName(st.state)}
                    className={`p-2.5 rounded-lg border cursor-pointer transition flex items-center justify-between text-xs ${
                      isSelected
                        ? 'bg-blue-50 border-blue-500 shadow-sm'
                        : 'bg-slate-50 hover:bg-slate-100 border-slate-200'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                        idx === 0 ? 'bg-red-600 text-white' : idx === 1 ? 'bg-orange-500 text-white' : 'bg-slate-200 text-slate-700'
                      }`}>
                        {idx + 1}
                      </span>
                      <span className="font-semibold text-slate-800">{st.state}</span>
                    </div>
                    <div className="flex items-center gap-3 font-mono text-[11px]">
                      <span className="text-red-600 font-bold">{totalRisk} High Risk</span>
                      <span className="text-slate-400">|</span>
                      <span className="text-slate-600">{st.total_projects} Projs</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Full State/UT Risk Table Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-base font-bold text-gov-navy">
              Comprehensive State &amp; UT Surveillance Table
            </h3>
            <p className="text-xs text-slate-500">
              Click any state row to highlight its region on the map
            </p>
          </div>

          {/* Table Search Input */}
          <div className="relative w-64">
            <input
              type="text"
              placeholder="Search State / UT..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-50 text-xs rounded-md pl-8 pr-3 py-1.5 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-900 text-slate-200 font-semibold border-b border-slate-800">
                <th className="py-3 px-4">State / Union Territory</th>
                <th
                  className="py-3 px-4 text-center cursor-pointer hover:text-blue-300"
                  onClick={() => toggleSort('total_projects')}
                >
                  Total Projects {sortField === 'total_projects' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
                </th>
                <th
                  className="py-3 px-4 text-center cursor-pointer hover:text-blue-300"
                  onClick={() => toggleSort('risk_count')}
                >
                  High / Critical Risk {sortField === 'risk_count' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
                </th>
                <th
                  className="py-3 px-4 text-right cursor-pointer hover:text-blue-300"
                  onClick={() => toggleSort('total_cost_overrun_cr')}
                >
                  Cumulative Overrun (₹ Cr) {sortField === 'total_cost_overrun_cr' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
                </th>
                <th
                  className="py-3 px-4 text-right cursor-pointer hover:text-blue-300"
                  onClick={() => toggleSort('avg_delay_months')}
                >
                  Avg Delay (Months) {sortField === 'avg_delay_months' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {filteredStates.map((st, idx) => {
                const isSelected = selectedStateName && selectedStateName.toLowerCase() === st.state.toLowerCase();
                const totalRisk = st.high_risk_projects + st.critical_risk_projects;

                return (
                  <tr
                    key={idx}
                    onClick={() => setSelectedStateName(st.state)}
                    className={`cursor-pointer transition ${
                      isSelected ? 'bg-blue-50/90 font-semibold' : 'hover:bg-slate-50'
                    }`}
                  >
                    <td className="py-3 px-4 font-bold text-gov-navy flex items-center gap-2">
                      {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>}
                      <span>{st.state}</span>
                    </td>
                    <td className="py-3 px-4 text-center font-mono text-slate-700">{st.total_projects}</td>
                    <td className="py-3 px-4 text-center font-mono">
                      <span className={`px-2 py-0.5 rounded font-bold ${
                        totalRisk > 0 ? 'bg-red-100 text-red-700 border border-red-200' : 'bg-emerald-100 text-emerald-700'
                      }`}>
                        {totalRisk}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-red-600">
                      ₹{st.total_cost_overrun_cr.toLocaleString('en-IN')} Cr
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-amber-700">
                      {st.avg_delay_months.toFixed(1)} Mo
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
