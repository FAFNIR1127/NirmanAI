import React, { useState, useEffect } from 'react';
import {
  Sliders,
  Play,
  RotateCcw,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Cpu,
  Clock,
  Layers,
  Sparkles,
  ArrowRight,
  Search,
  RefreshCw
} from 'lucide-react';
import api from '../../services/apiClient';
import { MLPredictionRequest, MLPredictionResponse, ProjectSummary } from '../../types/api';

const SECTORS = [
  'Railways',
  'Roads & Highways',
  'Power & Energy',
  'Petroleum & Natural Gas',
  'Coal & Mines',
  'Civil Aviation',
  'Infrastructure & Development',
  'Shipping & Ports',
  'Steel & Heavy Industry',
  'Telecommunications',
  'Urban Infrastructure & Housing'
];

export const RiskSimulator: React.FC = () => {
  const [mode, setMode] = useState<'existing' | 'whatif'>('existing');
  const [projectSearch, setProjectSearch] = useState('');
  const [searchResults, setSearchResults] = useState<ProjectSummary[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectSummary | null>(null);
  const [searching, setSearching] = useState(false);

  // Form State
  const [originalCost, setOriginalCost] = useState<number>(1000);
  const [anticipatedCost, setAnticipatedCost] = useState<number>(1250);
  const [cumulativeExp, setCumulativeExp] = useState<number>(650);
  const [physicalProgress, setPhysicalProgress] = useState<number>(55);
  const [monthsElapsed, setMonthsElapsed] = useState<number>(36);
  const [monthsPlanned, setMonthsPlanned] = useState<number>(48);
  const [monthsRemaining, setMonthsRemaining] = useState<number>(18);
  const [delayMonths, setDelayMonths] = useState<number>(12);
  const [sector, setSector] = useState<string>('Railways');
  const [agency, setAgency] = useState<string>('NR');
  const [state, setState] = useState<string>('Multi-State');

  // Prediction State
  const [prediction, setPrediction] = useState<MLPredictionResponse | null>(null);
  const [baselinePrediction, setBaselinePrediction] = useState<MLPredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search Projects for Mode 1
  useEffect(() => {
    if (projectSearch.trim().length >= 2) {
      setSearching(true);
      const timer = setTimeout(() => {
        api.getProjects({ search: projectSearch.trim(), page_size: 6 })
          .then((res) => {
            setSearchResults(res.projects);
            setSearching(false);
          })
          .catch(() => setSearching(false));
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setSearchResults([]);
    }
  }, [projectSearch]);

  const handleSelectExistingProject = async (p: ProjectSummary) => {
    setSelectedProject(p);
    setProjectSearch(`${p.project_name} (${p.project_code})`);
    setSearchResults([]);

    // Populate inputs from actual project
    setOriginalCost(p.original_cost_cr || 1000);
    setAnticipatedCost(p.latest_cost_cr || p.original_cost_cr || 1000);
    setCumulativeExp(Math.round((p.latest_cost_cr || p.original_cost_cr || 1000) * 0.6));
    setPhysicalProgress(p.physical_progress_pct || 50);
    setMonthsElapsed(36);
    setMonthsPlanned(48);
    setMonthsRemaining(18);
    setDelayMonths(p.delay_months || 0);
    setSector(p.sector || 'Railways');
    setAgency(p.ministry || 'NR');
    setState(p.state || 'Multi-State');

    // Run baseline prediction on existing project
    setLoading(true);
    setError(null);
    try {
      const baseRes = await api.predictMLRisk({ project_code: p.project_code });
      setBaselinePrediction(baseRes);
      setPrediction(baseRes);
    } catch (err: any) {
      console.error("Failed baseline prediction:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleRunSimulation = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload: MLPredictionRequest = {
        original_cost: Number(originalCost),
        anticipated_cost: Number(anticipatedCost),
        cumulative_expenditure: Number(cumulativeExp),
        physical_progress: Number(physicalProgress),
        months_elapsed: Number(monthsElapsed),
        months_originally_planned: Number(monthsPlanned),
        months_remaining: Number(monthsRemaining),
        delay_months: Number(delayMonths),
        sector,
        agency,
        state
      };
      const res = await api.predictMLRisk(payload);
      setPrediction(res);
    } catch (err: any) {
      console.error("Simulation error:", err);
      setError(err?.response?.data?.message || err?.message || "Failed to execute ML simulation");
    } finally {
      setLoading(false);
    }
  };

  // Run default initial simulation
  useEffect(() => {
    handleRunSimulation();
  }, []);

  const handleEscalateCost = (pct: number) => {
    const newAnt = Math.round(originalCost * (1 + pct / 100));
    setAnticipatedCost(newAnt);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <Sliders className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold text-gov-navy tracking-tight">
              Interactive Risk Simulator &amp; What-If Studio
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Real-time counterfactual scenario stress-testing powered by <strong>Risk Engine v2.1</strong> with 5-Fold Isotonic Calibration and Tree SHAP Explainability.
          </p>
        </div>

        {/* Mode Toggle */}
        <div className="flex items-center bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs font-semibold">
          <button
            onClick={() => setMode('existing')}
            className={`px-3 py-1.5 rounded-md transition ${
              mode === 'existing'
                ? 'bg-gov-navy text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Project Stress-Testing
          </button>
          <button
            onClick={() => setMode('whatif')}
            className={`px-3 py-1.5 rounded-md transition ${
              mode === 'whatif'
                ? 'bg-gov-navy text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Custom Sandbox
          </button>
        </div>
      </div>

      {/* Main Grid: Parameters on Left, Prediction on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Input Parameters (7 Cols) */}
        <div className="lg:col-span-7 bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h2 className="text-sm font-bold text-gov-navy uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-600" /> Scenario Parameters
            </h2>
            <button
              onClick={handleRunSimulation}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold transition shadow-sm"
            >
              {loading ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5 fill-current" />
              )}
              Run Prediction
            </button>
          </div>

          {/* Mode 1: Search Existing Project */}
          {mode === 'existing' && (
            <div className="relative">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Select Base Project from Live Database (5,461 Projects):
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={projectSearch}
                  onChange={(e) => setProjectSearch(e.target.value)}
                  placeholder="Type project name or code (e.g. Chandigarh-Baddi, Pune Metro, N22000467)..."
                  className="w-full text-xs px-3 py-2 pl-8 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
                <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
                {searching && (
                  <RefreshCw className="w-3.5 h-3.5 text-blue-500 animate-spin absolute right-3 top-2.5" />
                )}
              </div>

              {/* Search Dropdown */}
              {searchResults.length > 0 && (
                <div className="absolute z-30 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto divide-y divide-slate-100 text-xs">
                  {searchResults.map((p) => (
                    <button
                      key={p.project_code}
                      onClick={() => handleSelectExistingProject(p)}
                      className="w-full text-left p-2.5 hover:bg-blue-50 transition flex items-center justify-between"
                    >
                      <div>
                        <span className="font-bold text-slate-900">{p.project_name}</span>
                        <div className="text-[10px] text-slate-500 flex items-center gap-2 mt-0.5">
                          <span>{p.project_code}</span>
                          <span>&bull;</span>
                          <span>{p.sector}</span>
                          <span>&bull;</span>
                          <span>₹{(p.original_cost_cr || 0).toLocaleString()} Cr</span>
                        </div>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Form Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            {/* Original Cost */}
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Original Sanctioned Cost (₹ Cr):
              </label>
              <input
                type="number"
                value={originalCost}
                onChange={(e) => setOriginalCost(Number(e.target.value))}
                min="1"
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Anticipated Cost */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="font-semibold text-slate-700">Latest Anticipated Cost (₹ Cr):</label>
                <div className="space-x-1">
                  <button
                    onClick={() => handleEscalateCost(15)}
                    className="text-[10px] bg-slate-100 hover:bg-slate-200 px-1.5 py-0.5 rounded text-slate-600"
                  >
                    +15%
                  </button>
                  <button
                    onClick={() => handleEscalateCost(30)}
                    className="text-[10px] bg-amber-100 hover:bg-amber-200 px-1.5 py-0.5 rounded text-amber-800"
                  >
                    +30%
                  </button>
                  <button
                    onClick={() => handleEscalateCost(50)}
                    className="text-[10px] bg-red-100 hover:bg-red-200 px-1.5 py-0.5 rounded text-red-800"
                  >
                    +50%
                  </button>
                </div>
              </div>
              <input
                type="number"
                value={anticipatedCost}
                onChange={(e) => setAnticipatedCost(Number(e.target.value))}
                min="1"
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono focus:ring-1 focus:ring-blue-500"
              />
              <span className="text-[10px] text-slate-500 mt-0.5 block">
                Cost Escalation:{' '}
                <strong className={anticipatedCost > originalCost ? 'text-red-600' : 'text-emerald-600'}>
                  {(((anticipatedCost - originalCost) / Math.max(1, originalCost)) * 100).toFixed(1)}%
                </strong>
              </span>
            </div>

            {/* Cumulative Expenditure */}
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Cumulative Expenditure (₹ Cr):</label>
              <input
                type="number"
                value={cumulativeExp}
                onChange={(e) => setCumulativeExp(Number(e.target.value))}
                min="0"
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Physical Progress Slider */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="font-semibold text-slate-700">Physical Progress (%):</label>
                <span className="font-mono font-bold text-blue-600">{physicalProgress}%</span>
              </div>
              <input
                type="range"
                value={physicalProgress}
                onChange={(e) => setPhysicalProgress(Number(e.target.value))}
                min="0"
                max="100"
                className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
            </div>

            {/* Elapsed Months */}
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Months Elapsed Since Approval:</label>
              <input
                type="number"
                value={monthsElapsed}
                onChange={(e) => setMonthsElapsed(Number(e.target.value))}
                min="1"
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Planned Duration */}
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Sanctioned Planned Timeline (Months):</label>
              <input
                type="number"
                value={monthsPlanned}
                onChange={(e) => setMonthsPlanned(Number(e.target.value))}
                min="1"
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Remaining Months */}
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Anticipated Remaining Runway (Months):</label>
              <input
                type="number"
                value={monthsRemaining}
                onChange={(e) => setMonthsRemaining(Number(e.target.value))}
                min="1"
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Delay Months */}
            <div>
              <label className="font-semibold text-slate-700 block mb-1">Milestone Delay (Months):</label>
              <input
                type="number"
                value={delayMonths}
                onChange={(e) => setDelayMonths(Number(e.target.value))}
                min="0"
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Sector Dropdown */}
            <div className="sm:col-span-2">
              <label className="font-semibold text-slate-700 block mb-1">Infrastructure Sector:</label>
              <select
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded bg-white focus:ring-1 focus:ring-blue-500"
              >
                {SECTORS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Right: Prediction Output & SHAP Waterfall (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
              <div>{error}</div>
            </div>
          )}

          {prediction && (
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-5">
              {/* Card Header */}
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                  <Cpu className="w-4 h-4 text-emerald-600" /> ML Calibrated Assessment
                </span>
                <span className="text-[10px] font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-500">
                  ⚡ {prediction.inference_latency_ms}ms
                </span>
              </div>

              {/* Main Score & Risk Tier */}
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-3xl font-extrabold text-gov-navy tracking-tight">
                    {prediction.risk_score}
                    <span className="text-xs text-slate-400 font-normal ml-1">/ 100</span>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5 font-mono">
                    P(Severe Risk) = {(prediction.predicted_risk_probability * 100).toFixed(1)}%
                  </div>
                </div>

                <div className="text-right">
                  <span
                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold ${
                      prediction.risk_tier === 'High'
                        ? 'bg-red-100 text-red-800'
                        : prediction.risk_tier === 'Moderate'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-emerald-100 text-emerald-800'
                    }`}
                  >
                    {prediction.risk_tier} Risk
                  </span>
                  <div className="text-[10px] text-slate-400 mt-1">
                    Threshold T* &ge; {(prediction.operational_threshold * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Decision Alert Banner */}
              {prediction.is_severe_risk_alert ? (
                <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded text-xs text-red-800 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block font-semibold">Severe Risk Alert Triggered</strong>
                    Project exceeds operational safety threshold ({prediction.operational_threshold}). Requires CCEA oversight.
                  </div>
                </div>
              ) : (
                <div className="bg-emerald-50 border-l-4 border-emerald-500 p-3 rounded text-xs text-emerald-800 flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block font-semibold">Within Operational Tolerance</strong>
                    Risk score remains below operational cutoff. Routine monitoring applies.
                  </div>
                </div>
              )}

              {/* Counterfactual Delta (If in Mode 1) */}
              {mode === 'existing' && baselinePrediction && (
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs">
                  <div className="font-semibold text-slate-700 mb-1 flex items-center justify-between">
                    <span>Counterfactual Shift vs Baseline:</span>
                    <span
                      className={`font-bold font-mono ${
                        prediction.risk_score > baselinePrediction.risk_score
                          ? 'text-red-600'
                          : prediction.risk_score < baselinePrediction.risk_score
                          ? 'text-emerald-600'
                          : 'text-slate-600'
                      }`}
                    >
                      {prediction.risk_score >= baselinePrediction.risk_score ? '+' : ''}
                      {(prediction.risk_score - baselinePrediction.risk_score).toFixed(1)} pts
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Baseline: {baselinePrediction.risk_score}/100 ({baselinePrediction.risk_tier}) &rarr; Simulated: {prediction.risk_score}/100 ({prediction.risk_tier})
                  </div>
                </div>
              )}

              {/* SHAP Risk Drivers (Red) */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-red-500" /> Top Risk Accelerators (SHAP +)
                </h4>
                {prediction.key_risk_drivers && prediction.key_risk_drivers.length > 0 ? (
                  prediction.key_risk_drivers.map((d, i) => (
                    <div key={i} className="bg-red-50/60 p-2.5 rounded border border-red-100 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-red-950 font-mono text-[11px]">{d.feature}</span>
                        <span className="font-bold font-mono text-red-600">+{d.attribution.toFixed(3)}</span>
                      </div>
                      <p className="text-[11px] text-red-800 leading-snug">{d.description}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-400 italic">No significant positive risk drivers identified.</p>
                )}
              </div>

              {/* SHAP Protective Factors (Green) */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Protective Stabilizers (SHAP -)
                </h4>
                {prediction.protective_factors && prediction.protective_factors.length > 0 ? (
                  prediction.protective_factors.map((d, i) => (
                    <div key={i} className="bg-emerald-50/60 p-2.5 rounded border border-emerald-100 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-emerald-950 font-mono text-[11px]">{d.feature}</span>
                        <span className="font-bold font-mono text-emerald-600">{d.attribution.toFixed(3)}</span>
                      </div>
                      <p className="text-[11px] text-emerald-800 leading-snug">{d.description}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-400 italic">No significant protective stabilizers identified.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
