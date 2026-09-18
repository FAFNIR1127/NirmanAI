import React, { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Eye,
  RefreshCw,
  SlidersHorizontal,
  X,
  Sliders,
  CheckCircle2,
  Building2,
  MapPin,
  Tag
} from 'lucide-react';
import api from '../../services/apiClient';
import { ProjectSummary, FilterOptionsResponse } from '../../types/api';

interface PortfolioExplorerProps {
  onSelectProject: (code: string) => void;
  initialSearch?: string;
}

const DEFAULT_MINISTRIES = [
  "All Ministries",
  "Ministry of Railways",
  "Ministry of Road Transport and Highways",
  "Ministry of Petroleum and Natural Gas",
  "Ministry of Power",
  "Ministry of Coal & Mines",
  "Ministry of Civil Aviation",
  "Ministry of Ports, Shipping and Waterways",
  "Ministry of Communications",
  "Ministry of Housing and Urban Affairs",
  "Ministry of Heavy Industries & Steel"
];

const DEFAULT_SECTORS = [
  "All Sectors",
  "Roads & Highways",
  "Railways",
  "Power & Energy",
  "Petroleum & Natural Gas",
  "Coal & Mines",
  "Telecommunications",
  "Civil Aviation",
  "Urban Infrastructure & Housing",
  "Shipping & Ports",
  "Steel & Heavy Industry",
  "Infrastructure & Development"
];

const RISK_CATEGORIES = ["All", "Critical", "High", "Moderate", "Low"];

const COST_TIERS = [
  { label: "All Outlays", min: undefined, max: undefined },
  { label: "Mega (> ₹1,000 Cr)", min: 1000, max: undefined },
  { label: "Major (₹500 - ₹1,000 Cr)", min: 500, max: 1000 },
  { label: "Standard (₹150 - ₹500 Cr)", min: 150, max: 500 }
];

export const PortfolioExplorer: React.FC<PortfolioExplorerProps> = ({
  onSelectProject,
  initialSearch = ''
}) => {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [loading, setLoading] = useState(true);

  // Dynamic Options from DB
  const [filterOptions, setFilterOptions] = useState<FilterOptionsResponse | null>(null);

  // Filters State
  const [search, setSearch] = useState(initialSearch);
  const [selectedMinistry, setSelectedMinistry] = useState("All Ministries");
  const [selectedAgency, setSelectedAgency] = useState("All Agencies");
  const [selectedState, setSelectedState] = useState("All States");
  const [selectedSector, setSelectedSector] = useState("All Sectors");
  const [selectedRisk, setSelectedRisk] = useState("All");
  const [selectedCostTier, setSelectedCostTier] = useState("All Outlays");

  // Sorting State
  const [sortBy, setSortBy] = useState("cost_overrun_cr");
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Load filter options on mount
  useEffect(() => {
    api.getFilterOptions()
      .then(opts => setFilterOptions(opts))
      .catch(err => console.error("Failed to fetch filter options", err));
  }, []);

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const tierObj = COST_TIERS.find(t => t.label === selectedCostTier);

      const res = await api.getProjects({
        search: search.trim() || undefined,
        ministry: selectedMinistry === "All Ministries" ? undefined : selectedMinistry,
        agency: selectedAgency === "All Agencies" ? undefined : selectedAgency,
        state: selectedState === "All States" ? undefined : selectedState,
        sector: selectedSector === "All Sectors" ? undefined : selectedSector,
        risk_category: selectedRisk === "All" ? undefined : selectedRisk,
        min_cost: tierObj?.min,
        max_cost: tierObj?.max,
        page,
        page_size: pageSize,
        sort_by: sortBy,
        order: sortOrder
      });

      setProjects(res.projects || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error("Failed to fetch projects:", err);
      setProjects([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, [
    page,
    pageSize,
    selectedMinistry,
    selectedAgency,
    selectedState,
    selectedSector,
    selectedRisk,
    selectedCostTier,
    sortBy,
    sortOrder
  ]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchProjects();
  };

  const handleClearFilters = () => {
    setSearch('');
    setSelectedMinistry('All Ministries');
    setSelectedAgency('All Agencies');
    setSelectedState('All States');
    setSelectedSector('All Sectors');
    setSelectedRisk('All');
    setSelectedCostTier('All Outlays');
    setSortBy('cost_overrun_cr');
    setSortOrder('desc');
    setPage(1);
  };

  const hasActiveFilters =
    search.trim() !== '' ||
    selectedMinistry !== 'All Ministries' ||
    selectedAgency !== 'All Agencies' ||
    selectedState !== 'All States' ||
    selectedSector !== 'All Sectors' ||
    selectedRisk !== 'All' ||
    selectedCostTier !== 'All Outlays';

  const formatCr = (val?: number) => {
    if (val === undefined || val === null) return "—";
    return `₹${val.toLocaleString('en-IN', { maximumFractionDigits: 1 })} Cr`;
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  const agencyList = ["All Agencies", ...(filterOptions?.agencies || [])];
  const stateList = ["All States", ...(filterOptions?.states || [])];
  const ministryList = filterOptions?.ministries ? ["All Ministries", ...filterOptions.ministries] : DEFAULT_MINISTRIES;
  const sectorList = filterOptions?.sectors ? ["All Sectors", ...filterOptions.sectors] : DEFAULT_SECTORS;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">
      {/* Title & Stats Summary Banner */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gov-navy tracking-tight flex items-center gap-2">
            Central Projects Portfolio Explorer
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Multi-dimensional surveillance across central sector infrastructure assets (&gt; ₹150 Cr baseline)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-xs font-semibold text-slate-500 block">Matching Projects</span>
            <span className="text-lg font-bold font-mono text-gov-navy">
              {total.toLocaleString('en-IN')}
            </span>
          </div>
          <button
            onClick={fetchProjects}
            disabled={loading}
            className="p-2 text-slate-600 hover:text-gov-navy bg-slate-100 rounded-lg border border-slate-200 hover:bg-slate-200 transition"
            title="Refresh Portfolio Query"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Multi-Dimensional Filter Controls Card */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
        {/* Row 1: Search Bar & Primary Sort Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Quick Search */}
          <form onSubmit={handleSearchSubmit} className="flex-1 min-w-[260px] relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by Project Code or Name (e.g. Metro, Highway, 220100262)..."
              className="w-full pl-9 pr-20 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
            />
            <button
              type="submit"
              className="absolute right-1 top-1 bottom-1 px-3 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded transition"
            >
              Search
            </button>
          </form>

          {/* Sort By Field */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="font-semibold text-slate-600">Sort By:</span>
            <select
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
              className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="cost_overrun_cr">Cost Overrun (₹ Cr)</option>
              <option value="delay_months">Schedule Delay (Months)</option>
              <option value="risk_score">Risk Score (%)</option>
              <option value="original_cost">Baseline Sanctioned Cost</option>
              <option value="project_name">Project Name (A-Z)</option>
            </select>
          </div>

          {/* Sort Order Direction Toggle */}
          <button
            onClick={() => { setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'); setPage(1); }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-100 transition"
            title="Toggle Sort Direction"
          >
            <ArrowUpDown className="w-3.5 h-3.5 text-blue-600" />
            <span>{sortOrder === 'desc' ? 'High to Low' : 'Low to High'}</span>
          </button>
        </div>

        {/* Row 2: Dimensional Dropdowns */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-2 border-t border-slate-100 text-xs">
          {/* Filter: Ministry */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Central Ministry
            </label>
            <select
              value={selectedMinistry}
              onChange={(e) => { setSelectedMinistry(e.target.value); setPage(1); }}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 truncate"
            >
              {ministryList.map((m, i) => (
                <option key={i} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* Filter: Executing Agency */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Executing Agency
            </label>
            <select
              value={selectedAgency}
              onChange={(e) => { setSelectedAgency(e.target.value); setPage(1); }}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 truncate"
            >
              {agencyList.slice(0, 45).map((a, i) => (
                <option key={i} value={a}>{a}</option>
              ))}
            </select>
          </div>

          {/* Filter: State / UT */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              State / Region
            </label>
            <select
              value={selectedState}
              onChange={(e) => { setSelectedState(e.target.value); setPage(1); }}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 truncate"
            >
              {stateList.map((s, i) => (
                <option key={i} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {/* Filter: Sector */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Sector
            </label>
            <select
              value={selectedSector}
              onChange={(e) => { setSelectedSector(e.target.value); setPage(1); }}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 truncate"
            >
              {sectorList.map((sec, i) => (
                <option key={i} value={sec}>{sec}</option>
              ))}
            </select>
          </div>

          {/* Filter: Risk Category */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Risk Category
            </label>
            <select
              value={selectedRisk}
              onChange={(e) => { setSelectedRisk(e.target.value); setPage(1); }}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {RISK_CATEGORIES.map((r, i) => (
                <option key={i} value={r}>{r}</option>
              ))}
            </select>
          </div>

          {/* Filter: Cost Tier */}
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Capital Outlay Tier
            </label>
            <select
              value={selectedCostTier}
              onChange={(e) => { setSelectedCostTier(e.target.value); setPage(1); }}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {COST_TIERS.map((tier, i) => (
                <option key={i} value={tier.label}>{tier.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Active Filter Chips Bar */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 text-xs">
            <span className="text-[11px] font-semibold text-slate-500">Active Filters:</span>

            {search && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[11px]">
                Search: "{search}"
                <button onClick={() => { setSearch(''); setPage(1); }} className="hover:text-blue-900"><X className="w-3 h-3" /></button>
              </span>
            )}
            {selectedMinistry !== 'All Ministries' && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 text-[11px]">
                {selectedMinistry}
                <button onClick={() => { setSelectedMinistry('All Ministries'); setPage(1); }} className="hover:text-slate-900"><X className="w-3 h-3" /></button>
              </span>
            )}
            {selectedAgency !== 'All Agencies' && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 text-[11px]">
                Agency: {selectedAgency}
                <button onClick={() => { setSelectedAgency('All Agencies'); setPage(1); }} className="hover:text-slate-900"><X className="w-3 h-3" /></button>
              </span>
            )}
            {selectedState !== 'All States' && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 text-[11px]">
                State: {selectedState}
                <button onClick={() => { setSelectedState('All States'); setPage(1); }} className="hover:text-slate-900"><X className="w-3 h-3" /></button>
              </span>
            )}
            {selectedSector !== 'All Sectors' && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 text-[11px]">
                Sector: {selectedSector}
                <button onClick={() => { setSelectedSector('All Sectors'); setPage(1); }} className="hover:text-slate-900"><X className="w-3 h-3" /></button>
              </span>
            )}
            {selectedRisk !== 'All' && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-200 text-[11px]">
                Risk: {selectedRisk}
                <button onClick={() => { setSelectedRisk('All'); setPage(1); }} className="hover:text-red-900"><X className="w-3 h-3" /></button>
              </span>
            )}
            {selectedCostTier !== 'All Outlays' && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[11px]">
                {selectedCostTier}
                <button onClick={() => { setSelectedCostTier('All Outlays'); setPage(1); }} className="hover:text-amber-900"><X className="w-3 h-3" /></button>
              </span>
            )}

            <button
              onClick={handleClearFilters}
              className="text-xs text-red-600 hover:text-red-700 font-semibold underline ml-1"
            >
              Reset All Filters
            </button>
          </div>
        )}
      </div>

      {/* Projects Table View */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 font-bold text-slate-700 select-none">
              <tr>
                <th className="py-3 px-4">Project Identity</th>
                <th className="py-3 px-4">Sector / Agency</th>
                <th className="py-3 px-4 text-right">Sanctioned Cost</th>
                <th className="py-3 px-4 text-right">Latest Anticipated</th>
                <th className="py-3 px-4 text-right">Cost Overrun</th>
                <th className="py-3 px-4 text-center">Delay (Months)</th>
                <th className="py-3 px-4 text-center">XGBoost Risk Tier</th>
                <th className="py-3 px-4 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mx-auto mb-2" />
                    Querying live project portfolio...
                  </td>
                </tr>
              ) : projects.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    No projects found matching the active multi-parameter filters.
                  </td>
                </tr>
              ) : (
                projects.map((p) => {
                  const isCritical = p.risk_category?.toUpperCase() === 'CRITICAL';
                  const isHigh = p.risk_category?.toUpperCase() === 'HIGH';
                  const isMod = p.risk_category?.toUpperCase() === 'MODERATE' || p.risk_category?.toUpperCase() === 'WATCHLIST';

                  return (
                    <tr
                      key={p.project_code}
                      onClick={() => onSelectProject(p.project_code)}
                      className="hover:bg-blue-50/40 transition cursor-pointer group"
                    >
                      {/* Project Code & Name */}
                      <td className="py-3 px-4 max-w-xs">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono font-bold text-blue-700 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded text-[10px]">
                            {p.project_code}
                          </span>
                        </div>
                        <div className="font-semibold text-slate-900 mt-1 line-clamp-2 group-hover:text-blue-700 transition">
                          {p.project_name}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          <span>{p.state || 'Multi-State'}</span>
                        </div>
                      </td>

                      {/* Sector / Agency */}
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-800">{p.sector}</div>
                        <div className="text-[11px] text-slate-500 font-mono">{p.ministry || 'Executing Agency'}</div>
                      </td>

                      {/* Sanctioned Cost */}
                      <td className="py-3 px-4 text-right font-mono text-slate-700">
                        {formatCr(p.original_cost_cr)}
                      </td>

                      {/* Latest Anticipated Cost */}
                      <td className="py-3 px-4 text-right font-mono font-semibold text-slate-900">
                        {formatCr(p.latest_cost_cr)}
                      </td>

                      {/* Cost Overrun */}
                      <td className="py-3 px-4 text-right font-mono">
                        {p.cost_overrun_cr > 0 ? (
                          <div>
                            <span className="font-bold text-red-600">+{formatCr(p.cost_overrun_cr)}</span>
                            <span className="text-[10px] text-red-500 block">
                              +{p.cost_overrun_pct?.toFixed(1)}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-emerald-600 font-medium">On Budget</span>
                        )}
                      </td>

                      {/* Delay Months */}
                      <td className="py-3 px-4 text-center font-mono">
                        {p.delay_months && p.delay_months > 0 ? (
                          <span className="font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                            {p.delay_months.toFixed(0)}m
                          </span>
                        ) : (
                          <span className="text-emerald-700 text-[11px]">On Schedule</span>
                        )}
                      </td>

                      {/* Risk Category */}
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                          isCritical
                            ? 'bg-red-100 text-red-700 border border-red-200'
                            : isHigh
                            ? 'bg-orange-100 text-orange-700 border border-orange-200'
                            : isMod
                            ? 'bg-amber-100 text-amber-700 border border-amber-200'
                            : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            isCritical ? 'bg-red-500 animate-pulse' : isHigh ? 'bg-orange-500' : isMod ? 'bg-amber-500' : 'bg-emerald-500'
                          }`} />
                          {p.risk_category || 'Low'} ({(p.risk_score * 100).toFixed(0)}%)
                        </span>
                      </td>

                      {/* Action */}
                      <td className="py-3 px-4 text-center" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => onSelectProject(p.project_code)}
                          className="px-2.5 py-1 text-xs font-semibold text-blue-600 hover:text-white bg-blue-50 hover:bg-blue-600 border border-blue-200 rounded-md transition inline-flex items-center gap-1"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Inspect</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
          <div className="flex items-center gap-2">
            <span>Showing</span>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              className="bg-white border border-slate-200 rounded p-1 text-xs font-medium text-slate-800"
            >
              <option value={15}>15</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
            <span>projects per page &bull; Total: <strong className="font-mono text-slate-900">{total.toLocaleString('en-IN')}</strong></span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-slate-700 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-1"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Previous</span>
            </button>
            <span className="font-mono text-slate-800 px-2 font-semibold">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-slate-700 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-1"
            >
              <span>Next</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PortfolioExplorer;
