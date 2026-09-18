import React, { useState, useEffect } from 'react';
import { GitCompare, Search, ArrowRight, RefreshCcw, AlertTriangle, ShieldCheck } from 'lucide-react';
import api from '../../services/apiClient';
import { RiskIntelligenceResponse } from '../../types/api';

interface ProjectComparisonProps {
  onSelectProject: (code: string) => void;
  initialCodeA?: string;
  initialCodeB?: string;
}

export const ProjectComparison: React.FC<ProjectComparisonProps> = ({
  onSelectProject,
  initialCodeA = '201700140',
  initialCodeB = '201800022'
}) => {
  const [codeA, setCodeA] = useState(initialCodeA);
  const [codeB, setCodeB] = useState(initialCodeB);

  const [projectA, setProjectA] = useState<RiskIntelligenceResponse | null>(null);
  const [projectB, setProjectB] = useState<RiskIntelligenceResponse | null>(null);

  const [loadingA, setLoadingA] = useState(false);
  const [loadingB, setLoadingB] = useState(false);

  const [errorA, setErrorA] = useState<string | null>(null);
  const [errorB, setErrorB] = useState<string | null>(null);

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

  const formatCr = (val?: number) => {
    if (val === undefined || val === null) return "Not reported";
    return `₹${val.toLocaleString('en-IN')} Cr`;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header Box */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-2">
        <h2 className="text-xl font-bold text-gov-navy tracking-tight flex items-center gap-2">
          <GitCompare className="w-5 h-5 text-blue-600" />
          Infrastructure Project Comparison Workspace
        </h2>
        <p className="text-xs text-slate-500">
          Side-by-side metric comparison across financial exposure, schedule delay, physical completion, and XGBoost risk attribution
        </p>
      </div>

      {/* Selectors Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Project A Input */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-2">
          <label className="text-xs font-bold text-slate-700 block">Select Primary Project (Project A)</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={codeA}
              onChange={(e) => setCodeA(e.target.value)}
              placeholder="Enter Project Code A..."
              className="flex-1 bg-slate-50 text-slate-900 text-xs rounded-lg px-3 py-2 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
            <button
              onClick={() => fetchA(codeA)}
              disabled={loadingA}
              className="px-3 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700 transition"
            >
              Load A
            </button>
          </div>
        </div>

        {/* Project B Input */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-2">
          <label className="text-xs font-bold text-slate-700 block">Select Secondary Project (Project B)</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={codeB}
              onChange={(e) => setCodeB(e.target.value)}
              placeholder="Enter Project Code B..."
              className="flex-1 bg-slate-50 text-slate-900 text-xs rounded-lg px-3 py-2 border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
            <button
              onClick={() => fetchB(codeB)}
              disabled={loadingB}
              className="px-3 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700 transition"
            >
              Load B
            </button>
          </div>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden text-xs">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-900 text-slate-200 font-semibold border-b border-slate-800">
              <th className="py-3.5 px-4 w-1/4">Metric / Dimension</th>
              <th className="py-3.5 px-4 w-3/8 border-l border-slate-800">
                Project A ({projectA ? projectA.project_code : codeA})
              </th>
              <th className="py-3.5 px-4 w-3/8 border-l border-slate-800">
                Project B ({projectB ? projectB.project_code : codeB})
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {/* Row: Name & Ministry */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Project Name</td>
              <td className="py-3 px-4 border-l border-slate-100 font-semibold text-gov-navy">
                {loadingA ? <RefreshCcw className="w-4 h-4 animate-spin text-blue-600" /> : projectA?.project_name || errorA || 'Not loaded'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-semibold text-gov-navy">
                {loadingB ? <RefreshCcw className="w-4 h-4 animate-spin text-blue-600" /> : projectB?.project_name || errorB || 'Not loaded'}
              </td>
            </tr>

            {/* Row: Sector & Location */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Sector &amp; Location</td>
              <td className="py-3 px-4 border-l border-slate-100">
                {projectA ? `${projectA.sector} (${projectA.state || 'Multi-state'})` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100">
                {projectB ? `${projectB.sector} (${projectB.state || 'Multi-state'})` : '-'}
              </td>
            </tr>

            {/* Row: Risk Category & Score */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Risk Category (Score)</td>
              <td className="py-3 px-4 border-l border-slate-100">
                {projectA ? (
                  <span className={`px-2 py-0.5 rounded font-bold ${
                    projectA.risk_category === 'Critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                  }`}>
                    {projectA.risk_category} ({(projectA.risk_score * 100).toFixed(0)}%)
                  </span>
                ) : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100">
                {projectB ? (
                  <span className={`px-2 py-0.5 rounded font-bold ${
                    projectB.risk_category === 'Critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                  }`}>
                    {projectB.risk_category} ({(projectB.risk_score * 100).toFixed(0)}%)
                  </span>
                ) : '-'}
              </td>
            </tr>

            {/* Row: Original vs Latest Cost */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Sanctioned vs Latest Cost</td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono">
                {projectA ? `${formatCr(projectA.financial_metrics.original_cost_cr)} → ${formatCr(projectA.financial_metrics.latest_cost_cr)}` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono">
                {projectB ? `${formatCr(projectB.financial_metrics.original_cost_cr)} → ${formatCr(projectB.financial_metrics.latest_cost_cr)}` : '-'}
              </td>
            </tr>

            {/* Row: Cost Overrun */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Cumulative Cost Overrun</td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono font-bold text-red-600">
                {projectA ? `+${formatCr(projectA.financial_metrics.overrun_cr)} (+${projectA.financial_metrics.overrun_pct.toFixed(1)}%)` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono font-bold text-red-600">
                {projectB ? `+${formatCr(projectB.financial_metrics.overrun_cr)} (+${projectB.financial_metrics.overrun_pct.toFixed(1)}%)` : '-'}
              </td>
            </tr>

            {/* Row: Delay Months */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Schedule Delay</td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono text-amber-700 font-semibold">
                {projectA ? `${projectA.schedule_metrics.delay_months || 0} Months` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono text-amber-700 font-semibold">
                {projectB ? `${projectB.schedule_metrics.delay_months || 0} Months` : '-'}
              </td>
            </tr>

            {/* Row: Physical Progress */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Physical Completion</td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono">
                {projectA ? `${projectA.schedule_metrics.physical_progress_pct || 0}%` : '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 font-mono">
                {projectB ? `${projectB.schedule_metrics.physical_progress_pct || 0}%` : '-'}
              </td>
            </tr>

            {/* Row: Primary Risk Signal */}
            <tr>
              <td className="py-3 px-4 font-bold text-slate-700 bg-slate-50">Primary Risk Driver</td>
              <td className="py-3 px-4 border-l border-slate-100 text-slate-700">
                {projectA?.key_risk_drivers?.[0]?.plain_english || '-'}
              </td>
              <td className="py-3 px-4 border-l border-slate-100 text-slate-700">
                {projectB?.key_risk_drivers?.[0]?.plain_english || '-'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};
