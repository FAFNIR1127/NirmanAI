import React, { useState, useEffect } from 'react';
import { GitCompare, Search, ArrowRight, RefreshCcw, AlertTriangle, ShieldCheck, Filter, Layers, Building2, TrendingUp, Clock, CheckCircle2, ChevronRight, Zap } from 'lucide-react';
import api from '../../services/apiClient';
import { RiskIntelligenceResponse } from '../../types/api';

interface ProjectComparisonProps {
  onSelectProject: (code: string) => void;
  initialCodeA?: string;
  initialCodeB?: string;
}

interface ProjectSearchResult {
  project_code: string;
  project_name: string;
  sector: string;
  agency: string;
  state: string;
  original_cost: number;
  anticipated_cost?: number;
  risk_category?: string;
}

const PRESET_COMPARISONS = [
  {
    title: "Mega Railway Corridors",
    codeA: "N22000464",
    nameA: "Western Dedicated Freight Corridor",
    codeB: "220100133",
    nameB: "Udhampur-Srinagar-Baramulla (NL)"
  },
  {
    title: "Urban Transit Arteries",
    codeA: "702637",
    nameA: "Mumbai Metro Line 3 (Colaba-SEEPZ)",
    codeB: "702632",
    nameB: "DMRTS Phase-IV (Delhi Metro)"
  },
  {
    title: "Hydrocarbon Refining Capex",
    codeA: "701289",
    nameA: "Panipat Refinery Capacity Expansion",
    codeB: "604795",
    nameB: "CBR 9 MMTPA Project (CPCL)"
  },
  {
    title: "National Water Infrastructure",
    codeA: "701415",
    nameA: "Polavaram Irrigation Project",
    codeB: "701372",
    nameB: "Sardar Sarovar Multipurpose Project"
  }
];

const SECTORS = [
  "All Sectors",
  "Railways",
  "Road Transport and Highways",
  "Petroleum and Natural Gas",
  "Power",
  "Coal",
  "Urban Development",
  "Water Resources",
  "Atomic Energy",
  "Civil Aviation",
  "Shipping and Ports",
  "Telecommunications"
];

export const ProjectComparison: React.FC<ProjectComparisonProps> = ({
  onSelectProject,
  initialCodeA = 'N22000464',
  initialCodeB = '702637'
}) => {
  const [codeA, setCodeA] = useState(initialCodeA);
  const [codeB, setCodeB] = useState(initialCodeB);

  const [projectA, setProjectA] = useState<RiskIntelligenceResponse | null>(null);
  const [projectB, setProjectB] = useState<RiskIntelligenceResponse | null>(null);

  const [loadingA, setLoadingA] = useState(false);
  const [loadingB, setLoadingB] = useState(false);

  const [errorA, setErrorA] = useState<string | null>(null);
  const [errorB, setErrorB] = useState<string | null>(null);

  // Search and Section state
  const [selectedSector, setSelectedSector] = useState("All Sectors");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ProjectSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);

  const fetchA = async (code: string) => {
    if (!code.trim()) return;
    setLoadingA(true);
    setErrorA(null);
    try {
      const res = await api.getRiskIntelligence(code.trim());
      setProjectA(res);
    } catch (err) {
      console.error(err);
      setErrorA(`Project code ${code} not found`);
      setProjectA(null);
    } finally {
      setLoadingA(false);
    }
  };

  const fetchB = async (code: string) => {
    if (!code.trim()) return;
    setLoadingB(true);
    setErrorB(null);
    try {
      const res = await api.getRiskIntelligence(code.trim());
      setProjectB(res);
    } catch (err) {
      console.error(err);
      setErrorB(`Project code ${code} not found`);
      setProjectB(null);
    } finally {
      setLoadingB(false);
    }
  };

  useEffect(() => {
    fetchA(codeA);
    fetchB(codeB);
  }, []);

  // Live project search and sector filter
  useEffect(() => {
    const handler = setTimeout(async () => {
      if (!searchQuery.trim() && selectedSector === "All Sectors") {
        setSearchResults([]);
        return;
      }
      setSearching(true);
      try {
        const sectorParam = selectedSector !== "All Sectors" ? selectedSector : undefined;
        const res = await api.getProjects({
          search: searchQuery.trim() || undefined,
          sector: sectorParam,
          page_size: 8
        });
        const mapped = res.projects.map(p => ({
          project_code: p.project_code,
          project_name: p.project_name,
          sector: p.sector,
          agency: p.ministry || "",
          state: p.state,
          original_cost: p.original_cost_cr,
          anticipated_cost: p.latest_cost_cr,
          risk_category: p.risk_category
        }));
        setSearchResults(mapped);
        setShowSearchDropdown(true);
      } catch (err) {
        console.error("Search failed:", err);
      } finally {
        setSearching(false);
      }
    }, 250);

    return () => clearTimeout(handler);
  }, [searchQuery, selectedSector]);

  const loadPreset = (codeAVal: string, codeBVal: string) => {
    setCodeA(codeAVal);
    setCodeB(codeBVal);
    fetchA(codeAVal);
    fetchB(codeBVal);
  };

  const handleSelectAsA = (code: string) => {
    setCodeA(code);
    fetchA(code);
    setShowSearchDropdown(false);
  };

  const handleSelectAsB = (code: string) => {
    setCodeB(code);
    fetchB(code);
    setShowSearchDropdown(false);
  };

  const formatCr = (val?: number) => {
    if (val === undefined || val === null) return "Not reported";
    return `₹${val.toLocaleString('en-IN')} Cr`;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header Box */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-gov-navy tracking-tight flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-blue-600" />
              Infrastructure Project Comparison Workspace
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Side-by-side surveillance analysis across sanctioned baselines, cost escalations, schedule delays, and calibrated XGBoost risk attributions.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
            <Layers className="w-4 h-4 text-blue-600" />
            <span>Surveillance Base: <strong>5,461 Projects</strong></span>
          </div>
        </div>

        {/* Preset Quick-Load Pills */}
        <div className="pt-3 flex flex-wrap items-center gap-2 border-t border-slate-100">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <Zap className="w-3.5 h-3.5 text-amber-500" />
            Strategic Presets:
          </span>
          {PRESET_COMPARISONS.map((p, idx) => (
            <button
              key={idx}
              onClick={() => loadPreset(p.codeA, p.codeB)}
              className="text-xs font-medium px-2.5 py-1 rounded-md bg-blue-50/80 hover:bg-blue-100 text-blue-800 border border-blue-200 transition flex items-center gap-1"
            >
              <span>{p.title}</span>
              <span className="text-[10px] text-blue-500 font-mono">({p.codeA} vs {p.codeB})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Quick Project Finder & Sector Section Loader */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3 relative">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-blue-600" />
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Project Finder &amp; Sector Loader
            </h3>
          </div>
          <span className="text-[11px] text-slate-500">
            Search any of the 5,461 projects and load directly into Project A or Project B
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          {/* Sector / Section Filter */}
          <div className="md:col-span-4">
            <label className="text-[11px] font-bold text-slate-600 block mb-1">Filter by Section / Sector</label>
            <div className="relative">
              <select
                value={selectedSector}
                onChange={(e) => setSelectedSector(e.target.value)}
                className="w-full bg-slate-50 text-slate-900 text-xs rounded-lg px-3 py-2 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium"
              >
                {SECTORS.map((s, idx) => (
                  <option key={idx} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Search Input */}
          <div className="md:col-span-8">
            <label className="text-[11px] font-bold text-slate-600 block mb-1">Search by Project Name, Code, or Implementing Agency</label>
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => { if (searchResults.length > 0) setShowSearchDropdown(true); }}
                placeholder="e.g. Western Dedicated Freight Corridor, Mumbai Metro, Panipat, N22000464..."
                className="w-full bg-slate-50 text-slate-900 text-xs rounded-lg px-3 py-2 pl-8 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
              {searching && (
                <RefreshCcw className="w-3.5 h-3.5 text-blue-600 animate-spin absolute right-3 top-2.5" />
              )}
            </div>
          </div>
        </div>

        {/* Live Search Suggestions Dropdown */}
        {showSearchDropdown && searchResults.length > 0 && (
          <div className="absolute left-5 right-5 top-[110px] z-30 bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden max-h-80 overflow-y-auto divide-y divide-slate-100">
            <div className="bg-slate-50 px-3 py-2 text-[11px] font-bold text-slate-600 flex items-center justify-between">
              <span>Matching Infrastructure Projects ({searchResults.length})</span>
              <button
                onClick={() => setShowSearchDropdown(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-semibold"
              >
                Close
              </button>
            </div>
            {searchResults.map((proj) => (
              <div key={proj.project_code} className="p-3 hover:bg-slate-50/80 flex flex-wrap items-center justify-between gap-2 transition">
                <div className="flex-1 min-w-[240px]">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                      {proj.project_code}
                    </span>
                    <span className="text-xs font-bold text-slate-900">
                      {proj.project_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-1">
                    <span>{proj.sector}</span>
                    <span>•</span>
                    <span>{proj.agency || 'MoSPI'}</span>
                    <span>•</span>
                    <span className="font-mono font-semibold text-slate-700">Orig: ₹{proj.original_cost.toLocaleString('en-IN')} Cr</span>
                    {proj.anticipated_cost && (
                      <span className="font-mono font-semibold text-red-600">Latest: ₹{proj.anticipated_cost.toLocaleString('en-IN')} Cr</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleSelectAsA(proj.project_code)}
                    className="px-2.5 py-1 text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-md shadow-sm transition"
                  >
                    Set as Project A
                  </button>
                  <button
                    onClick={() => handleSelectAsB(proj.project_code)}
                    className="px-2.5 py-1 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-md shadow-sm transition"
                  >
                    Set as Project B
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Selectors Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Project A Input */}
        <div className="bg-white p-4 rounded-xl border border-blue-200 shadow-sm space-y-2 bg-gradient-to-br from-white to-blue-50/20">
          <div className="flex items-center justify-between">
            <label className="text-xs font-extrabold text-blue-900 block flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
              Primary Benchmark (Project A)
            </label>
            {projectA && (
              <span className="text-[11px] font-mono font-bold text-blue-700">
                {projectA.project_code}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={codeA}
              onChange={(e) => setCodeA(e.target.value)}
              placeholder="Enter Project Code A (e.g. N22000464)..."
              className="flex-1 bg-slate-50 text-slate-900 text-xs rounded-lg px-3 py-2 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
            <button
              onClick={() => fetchA(codeA)}
              disabled={loadingA}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition shadow-sm"
            >
              {loadingA ? <RefreshCcw className="w-3.5 h-3.5 animate-spin" /> : "Load A"}
            </button>
          </div>
          {projectA && (
            <p className="text-[11px] font-bold text-slate-700 truncate">
              {projectA.project_name}
            </p>
          )}
        </div>

        {/* Project B Input */}
        <div className="bg-white p-4 rounded-xl border border-indigo-200 shadow-sm space-y-2 bg-gradient-to-br from-white to-indigo-50/20">
          <div className="flex items-center justify-between">
            <label className="text-xs font-extrabold text-indigo-900 block flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-600"></span>
              Secondary Comparison (Project B)
            </label>
            {projectB && (
              <span className="text-[11px] font-mono font-bold text-indigo-700">
                {projectB.project_code}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={codeB}
              onChange={(e) => setCodeB(e.target.value)}
              placeholder="Enter Project Code B (e.g. 702637)..."
              className="flex-1 bg-slate-50 text-slate-900 text-xs rounded-lg px-3 py-2 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
            />
            <button
              onClick={() => fetchB(codeB)}
              disabled={loadingB}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg transition shadow-sm"
            >
              {loadingB ? <RefreshCcw className="w-3.5 h-3.5 animate-spin" /> : "Load B"}
            </button>
          </div>
          {projectB && (
            <p className="text-[11px] font-bold text-slate-700 truncate">
              {projectB.project_name}
            </p>
          )}
        </div>
      </div>

      {/* Comparison Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden text-xs">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-900 text-slate-200 font-semibold border-b border-slate-800">
              <th className="py-3.5 px-4 w-1/4">Surveillance Metric</th>
              <th className="py-3.5 px-4 w-3/8 border-l border-slate-800">
                <span className="text-blue-400 font-mono font-bold mr-1">[A]</span>
                {projectA ? `${projectA.project_code} • ${projectA.project_name.slice(0, 32)}...` : codeA}
              </th>
              <th className="py-3.5 px-4 w-3/8 border-l border-slate-800">
                <span className="text-indigo-400 font-mono font-bold mr-1">[B]</span>
                {projectB ? `${projectB.project_code} • ${projectB.project_name.slice(0, 32)}...` : codeB}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {/* Row: Name */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Full Project Title</td>
              <td className="py-3 px-4 border-l border-slate-100 font-bold text-gov-navy">
                {loadingA ? <RefreshCcw className="w-4 h-4 animate-spin text-blue-600" /> : projectA?.project_name || errorA || 'Not loaded'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-bold text-gov-navy">
                {loadingB ? <RefreshCcw className="w-4 h-4 animate-spin text-blue-600" /> : projectB?.project_name || errorB || 'Not loaded'}
              </td>
            </tr>

            {/* Row: Implementing Agency */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Implementing Agency</td>
              <td className="py-3 px-4 border-l border-slate-100 font-semibold text-slate-800">
                {projectA?.ministry || '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-semibold text-slate-800">
                {projectB?.ministry || '-'}
              </td>
            </tr>

            {/* Row: Sector & Location */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Sector &amp; Location</td>
              <td className="py-3 px-4 border-l border-slate-100">
                {projectA ? `${projectA.sector} (${projectA.state || 'Multi-State'})` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100">
                {projectB ? `${projectB.sector} (${projectB.state || 'Multi-State'})` : '-'}
              </td>
            </tr>

            {/* Row: Risk Category & Score */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">XGBoost Risk Tier (Score)</td>
              <td className="py-3 px-4 border-l border-slate-100">
                {projectA ? (
                  <span className={`px-2.5 py-1 rounded-md font-extrabold text-xs inline-flex items-center gap-1.5 ${
                    projectA.risk_category === 'Critical'
                      ? 'bg-red-100 text-red-800 border border-red-300'
                      : projectA.risk_category === 'High'
                      ? 'bg-orange-100 text-orange-800 border border-orange-300'
                      : projectA.risk_category === 'Watchlist'
                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                      : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                  }`}>
                    <span className="w-2 h-2 rounded-full bg-current"></span>
                    {projectA.risk_category.toUpperCase()} ({(projectA.risk_score > 1 ? projectA.risk_score : projectA.risk_score * 100).toFixed(1)}/100)
                  </span>
                ) : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100">
                {projectB ? (
                  <span className={`px-2.5 py-1 rounded-md font-extrabold text-xs inline-flex items-center gap-1.5 ${
                    projectB.risk_category === 'Critical'
                      ? 'bg-red-100 text-red-800 border border-red-300'
                      : projectB.risk_category === 'High'
                      ? 'bg-orange-100 text-orange-800 border border-orange-300'
                      : projectB.risk_category === 'Watchlist'
                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                      : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                  }`}>
                    <span className="w-2 h-2 rounded-full bg-current"></span>
                    {projectB.risk_category.toUpperCase()} ({(projectB.risk_score > 1 ? projectB.risk_score : projectB.risk_score * 100).toFixed(1)}/100)
                  </span>
                ) : '-'}
              </td>
            </tr>

            {/* Row: Original vs Latest Cost */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Sanctioned vs Latest Cost</td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono font-semibold">
                {projectA ? `${formatCr(projectA.financial_metrics.original_cost_cr)} → ${formatCr(projectA.financial_metrics.latest_cost_cr)}` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono font-semibold">
                {projectB ? `${formatCr(projectB.financial_metrics.original_cost_cr)} → ${formatCr(projectB.financial_metrics.latest_cost_cr)}` : '-'}
              </td>
            </tr>

            {/* Row: Cost Overrun */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Cumulative Cost Escalation</td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono font-extrabold text-red-600">
                {projectA ? `+${formatCr(projectA.financial_metrics.overrun_cr)} (+${projectA.financial_metrics.overrun_pct.toFixed(1)}%)` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono font-extrabold text-red-600">
                {projectB ? `+${formatCr(projectB.financial_metrics.overrun_cr)} (+${projectB.financial_metrics.overrun_pct.toFixed(1)}%)` : '-'}
              </td>
            </tr>

            {/* Row: Delay Months */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Schedule Delay Slip</td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono text-amber-700 font-extrabold">
                {projectA ? `${projectA.schedule_metrics.delay_months || 0} Months` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono text-amber-700 font-extrabold">
                {projectB ? `${projectB.schedule_metrics.delay_months || 0} Months` : '-'}
              </td>
            </tr>

            {/* Row: Physical Progress */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Physical Completion Pace</td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono font-extrabold text-slate-900">
                <div className="flex items-center gap-2">
                  <span>{projectA ? `${projectA.schedule_metrics.physical_progress_pct || 0}%` : '-'}</span>
                  {projectA && (
                    <div className="w-24 bg-slate-200 h-2 rounded-full overflow-hidden">
                      <div className="bg-emerald-600 h-full rounded-full" style={{ width: `${projectA.schedule_metrics.physical_progress_pct || 0}%` }}></div>
                    </div>
                  )}
                </div>
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono font-extrabold text-slate-900">
                <div className="flex items-center gap-2">
                  <span>{projectB ? `${projectB.schedule_metrics.physical_progress_pct || 0}%` : '-'}</span>
                  {projectB && (
                    <div className="w-24 bg-slate-200 h-2 rounded-full overflow-hidden">
                      <div className="bg-emerald-600 h-full rounded-full" style={{ width: `${projectB.schedule_metrics.physical_progress_pct || 0}%` }}></div>
                    </div>
                  )}
                </div>
              </td>
            </tr>

            {/* Row: Primary Risk Signal */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Primary SHAP Risk Driver</td>
              <td className="py-3 px-4 border-l border-slate-100 text-slate-700 font-medium">
                {projectA?.key_risk_drivers?.[0]?.plain_english || 'Sanctioned timeline slippage'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 text-slate-700 font-medium">
                {projectB?.key_risk_drivers?.[0]?.plain_english || 'Sanctioned timeline slippage'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};
