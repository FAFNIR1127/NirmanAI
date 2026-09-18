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
  SlidersHorizontal
} from 'lucide-react';
import api from '../../services/apiClient';
import { ProjectSummary } from '../../types/api';

interface PortfolioExplorerProps {
  onSelectProject: (code: string) => void;
  initialSearch?: string;
}

const SECTORS = [
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

export const PortfolioExplorer: React.FC<PortfolioExplorerProps> = ({
  onSelectProject,
  initialSearch = ''
}) => {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [loading, setLoading] = useState(true);

  // Filters State
  const [search, setSearch] = useState(initialSearch);
  const [selectedSector, setSelectedSector] = useState("All Sectors");
  const [selectedRisk, setSelectedRisk] = useState("All");
  const [sortBy, setSortBy] = useState("cost_overrun_cr");
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const sectorParam = selectedSector === "All Sectors" ? undefined : selectedSector;
      const riskParam = selectedRisk === "All" ? undefined : selectedRisk;

      const res = await api.getProjects({
        search: search.trim() || undefined,
        sector: sectorParam,
        risk_category: riskParam,
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
  }, [page, pageSize, selectedSector, selectedRisk, sortBy, sortOrder]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchProjects();
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  const getRiskBadge = (category: string, score: number) => {
    const scorePct = (score * 100).toFixed(0);
    const catUpper = (category || '').toUpperCase();
    switch (catUpper) {
      case 'CRITICAL':
        return <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-red-100 text-red-700 border border-red-200">Critical ({scorePct}%)</span>;
      case 'HIGH':
        return <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-orange-100 text-orange-700 border border-orange-200">High ({scorePct}%)</span>;
      case 'MODERATE':
      case 'WATCHLIST':
        return <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-amber-100 text-amber-700 border border-amber-200">Moderate ({scorePct}%)</span>;
      default:
        return <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-emerald-100 text-emerald-700 border border-emerald-200">Low ({scorePct}%)</span>;
    }
  };


  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Search & Filter Header Control Box */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-gov-navy tracking-tight flex items-center gap-2">
              <SlidersHorizontal className="w-5 h-5 text-blue-600" />
              Infrastructure Project Portfolio Explorer
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Filter and search across {total.toLocaleString('en-IN')} monitored infrastructure projects
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-600 bg-slate-100 px-3 py-1.5 rounded">
            <span>Showing {projects.length} of {total.toLocaleString('en-IN')} Records</span>
          </div>
        </div>

        {/* Filter Controls Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
          {/* Search Field */}
          <form onSubmit={handleSearchSubmit} className="relative">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search Project Code or Name..."
              className="w-full bg-slate-50 text-slate-900 placeholder-slate-400 text-xs rounded-lg pl-9 pr-8 py-2 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            {search && (
              <button
                type="button"
                onClick={() => { setSearch(''); setPage(1); }}
                className="absolute right-2 top-2 text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ×
              </button>
            )}
          </form>

          {/* Sector Filter */}
          <select
            value={selectedSector}
            onChange={(e) => { setSelectedSector(e.target.value); setPage(1); }}
            className="bg-slate-50 text-slate-900 text-xs rounded-lg px-3 py-2 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {SECTORS.map((sec) => (
              <option key={sec} value={sec}>{sec}</option>
            ))}
          </select>

          {/* Risk Level Filter Buttons */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200 col-span-1 sm:col-span-2 lg:col-span-2">
            <span className="text-[11px] font-semibold text-slate-500 px-2 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Risk:
            </span>
            {RISK_CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => { setSelectedRisk(cat); setPage(1); }}
                className={`flex-1 text-[11px] font-semibold py-1 rounded transition ${
                  selectedRisk === cat
                    ? 'bg-gov-navy text-white shadow-sm'
                    : 'text-slate-600 hover:bg-slate-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Projects Data Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-xs flex flex-col items-center">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mb-2" />
            <span>Querying PostgreSQL Project Ledger...</span>
          </div>
        ) : projects.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-xs">
            <p className="font-semibold text-sm mb-1">No Projects Found</p>
            <p>Try clearing your search query or adjusting sector/risk filter selections.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-900 text-slate-200 font-semibold border-b border-slate-800">
                  <th className="py-3 px-4 font-mono text-[11px]">Code</th>
                  <th className="py-3 px-4">Project Details</th>
                  <th className="py-3 px-4">Sector & Location</th>
                  <th
                    className="py-3 px-4 cursor-pointer hover:bg-slate-800 transition"
                    onClick={() => toggleSort('latest_cost_cr')}
                  >
                    <div className="flex items-center gap-1">
                      <span>Latest Cost</span>
                      <ArrowUpDown className="w-3 h-3 text-slate-400" />
                    </div>
                  </th>
                  <th
                    className="py-3 px-4 cursor-pointer hover:bg-slate-800 transition text-right"
                    onClick={() => toggleSort('cost_overrun_cr')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      <span>Cost Overrun</span>
                      <ArrowUpDown className="w-3 h-3 text-slate-400" />
                    </div>
                  </th>
                  <th
                    className="py-3 px-4 cursor-pointer hover:bg-slate-800 transition text-right"
                    onClick={() => toggleSort('delay_months')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      <span>Delay</span>
                      <ArrowUpDown className="w-3 h-3 text-slate-400" />
                    </div>
                  </th>
                  <th className="py-3 px-4 text-center">XGBoost Risk Score</th>
                  <th className="py-3 px-4 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {projects.map((proj) => (
                  <tr
                    key={proj.project_code}
                    className="hover:bg-blue-50/40 transition cursor-pointer"
                    onClick={() => onSelectProject(proj.project_code)}
                  >
                    {/* Project Code */}
                    <td className="py-3 px-4 font-mono font-bold text-blue-700">
                      {proj.project_code}
                    </td>

                    {/* Project Name & Ministry */}
                    <td className="py-3 px-4 max-w-xs">
                      <div className="font-bold text-gov-navy hover:text-blue-700 transition line-clamp-1">
                        {proj.project_name}
                      </div>
                      {proj.ministry && (
                        <div className="text-[10px] text-slate-400 line-clamp-1 mt-0.5">
                          {proj.ministry}
                        </div>
                      )}
                    </td>

                    {/* Sector & Location */}
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-800">{proj.sector}</div>
                      <div className="text-[10px] text-slate-500">{proj.state || "Multi-state"}</div>
                    </td>

                    {/* Latest Cost */}
                    <td className="py-3 px-4 font-mono text-slate-700">
                      ₹{proj.latest_cost_cr ? proj.latest_cost_cr.toLocaleString('en-IN') : 0} Cr
                      <span className="block text-[10px] text-slate-400">
                        Orig: ₹{proj.original_cost_cr ? proj.original_cost_cr.toLocaleString('en-IN') : 0} Cr
                      </span>
                    </td>

                    {/* Cost Overrun */}
                    <td className="py-3 px-4 text-right font-mono">
                      <span className={`font-bold ${proj.cost_overrun_cr > 0 ? 'text-red-600' : 'text-slate-600'}`}>
                        {proj.cost_overrun_cr > 0 ? `+₹${proj.cost_overrun_cr.toLocaleString('en-IN')} Cr` : 'Nil'}
                      </span>
                      {proj.cost_overrun_pct > 0 && (
                        <span className="block text-[10px] font-semibold text-red-500">
                          (+{proj.cost_overrun_pct.toFixed(1)}%)
                        </span>
                      )}
                    </td>

                    {/* Delay Months */}
                    <td className="py-3 px-4 text-right font-mono">
                      <span className={`font-semibold ${ (proj.delay_months || 0) > 0 ? 'text-amber-700' : 'text-slate-600'}`}>
                        {(proj.delay_months || proj.original_delay_months || 0)} Mo
                      </span>
                    </td>

                    {/* Risk Badge */}
                    <td className="py-3 px-4 text-center">
                      {getRiskBadge(proj.risk_category, proj.risk_score)}
                    </td>

                    {/* Action Button */}
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectProject(proj.project_code);
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-blue-600 hover:text-white text-slate-700 text-[11px] font-medium rounded border border-slate-200 transition"
                      >
                        <Eye className="w-3 h-3" />
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Table Pagination Footer */}
        <div className="bg-slate-50 px-4 py-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <div>
            Page <strong className="font-mono text-slate-900">{page}</strong> of <strong className="font-mono text-slate-900">{totalPages}</strong>
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="px-3 py-1.5 rounded bg-white border border-slate-300 disabled:opacity-50 hover:bg-slate-100 flex items-center gap-1 font-medium transition"
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Previous
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              className="px-3 py-1.5 rounded bg-white border border-slate-300 disabled:opacity-50 hover:bg-slate-100 flex items-center gap-1 font-medium transition"
            >
              Next <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
