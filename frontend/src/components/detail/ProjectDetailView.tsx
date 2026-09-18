import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  AlertTriangle,
  FileText,
  Clock,
  TrendingUp,
  Bot,
  ChevronDown,
  ChevronUp,
  Cpu,
  RefreshCcw,
  CheckCircle2,
  Info
} from 'lucide-react';
import api from '../../services/apiClient';
import { RiskIntelligenceResponse } from '../../types/api';

interface ProjectDetailViewProps {
  projectCode: string;
  onBack: () => void;
  onOpenAssistant: (initialQuery?: string) => void;
}

export const ProjectDetailView: React.FC<ProjectDetailViewProps> = ({
  projectCode,
  onBack,
  onOpenAssistant
}) => {
  const [data, setData] = useState<RiskIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTechnicalShap, setShowTechnicalShap] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    api.getRiskIntelligence(projectCode)
      .then((res) => {
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          console.error("Failed to load project risk intelligence:", err);
          setError(`Could not retrieve risk intelligence for project code: ${projectCode}. Check if code exists.`);
          setLoading(false);
        }
      });

    return () => { mounted = false; };
  }, [projectCode]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 flex flex-col items-center justify-center min-h-[400px]">
        <RefreshCcw className="w-8 h-8 text-blue-600 animate-spin mb-3" />
        <p className="text-slate-600 text-sm font-medium">Executing XGBoost Risk Inference & Retrieving RAG Evidence Snippets...</p>
        <span className="text-slate-400 font-mono text-xs mt-1">Project Code: {projectCode}</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12">
        <button
          onClick={onBack}
          className="mb-4 inline-flex items-center gap-1.5 text-slate-600 hover:text-gov-navy text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Portfolio
        </button>
        <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center text-red-700 max-w-2xl mx-auto">
          <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-2" />
          <h3 className="font-bold text-lg mb-1">Project Not Found</h3>
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <button
            onClick={onBack}
            className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded hover:bg-slate-800 transition"
          >
            Return to Portfolio Explorer
          </button>
        </div>
      </div>
    );
  }

  const {
    project_name,
    sector,
    ministry,
    state,
    risk_score,
    risk_category,
    officer_summary,
    key_risk_drivers,
    shap_technical_details,
    financial_metrics,
    schedule_metrics,
    evidence_snippets
  } = data;

  const scorePct = (risk_score * 100).toFixed(1);

  const getRiskCategoryBadge = () => {
    switch (risk_category) {
      case 'Critical':
        return <span className="bg-red-100 text-red-800 border border-red-300 font-bold px-3 py-1 rounded-md text-xs uppercase tracking-wider">Critical Risk ({scorePct}%)</span>;
      case 'High':
        return <span className="bg-orange-100 text-orange-800 border border-orange-300 font-bold px-3 py-1 rounded-md text-xs uppercase tracking-wider">High Risk ({scorePct}%)</span>;
      case 'Watchlist':
        return <span className="bg-amber-100 text-amber-800 border border-amber-300 font-bold px-3 py-1 rounded-md text-xs uppercase tracking-wider">Watchlist ({scorePct}%)</span>;
      default:
        return <span className="bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold px-3 py-1 rounded-md text-xs uppercase tracking-wider">Normal ({scorePct}%)</span>;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Top Back Navigation Bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 text-xs font-semibold shadow-sm transition"
        >
          <ArrowLeft className="w-4 h-4 text-slate-500" /> Back to Explorer
        </button>

        <button
          onClick={() => onOpenAssistant(`Give me a complete officer briefing for project ${projectCode}.`)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow transition"
        >
          <Bot className="w-4 h-4 text-blue-200" /> Ask AI Copilot About This Project
        </button>
      </div>

      {/* Main Project Header Box */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1 max-w-3xl">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-blue-700 bg-blue-100 border border-blue-300 px-2 py-0.5 rounded">
                CODE: {projectCode}
              </span>
              <span className="text-xs font-medium text-slate-500">|</span>
              <span className="text-xs font-semibold text-slate-600">{sector}</span>
              <span className="text-xs text-slate-400">({state || "Multi-state"})</span>
            </div>
            <h1 className="text-2xl font-extrabold text-gov-navy tracking-tight leading-snug">
              {project_name}
            </h1>
            {ministry && (
              <p className="text-xs text-slate-500">
                Nodal Ministry: <strong className="text-slate-700 font-semibold">{ministry}</strong>
              </p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            {getRiskCategoryBadge()}
            <span className="text-[11px] text-slate-400 font-mono">XGBoost Cutoff: T* &ge; 0.28</span>
          </div>
        </div>

        {/* Officer Executive Briefing Card */}
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs leading-relaxed text-slate-700">
          <h4 className="font-bold text-gov-navy text-xs mb-1 uppercase tracking-wider flex items-center gap-1.5">
            <Info className="w-4 h-4 text-blue-600" /> Officer Executive Summary
          </h4>
          <p>{officer_summary}</p>
        </div>
      </div>

      {/* Metrics Row: Financial Metrics + Schedule Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Financial Metrics */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <h3 className="text-base font-bold text-gov-navy flex items-center gap-2 border-b border-slate-100 pb-3">
            <TrendingUp className="w-5 h-5 text-red-600" />
            Financial Health &amp; Cost Escalation
          </h3>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-slate-500 block">Original Sanctioned Cost</span>
              <span className="text-lg font-bold font-mono text-slate-900">
                ₹{financial_metrics.original_cost_cr?.toLocaleString('en-IN') || "Not reported"} Cr
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-slate-500 block">Latest Anticipated Cost</span>
              <span className="text-lg font-bold font-mono text-slate-900">
                ₹{financial_metrics.latest_cost_cr?.toLocaleString('en-IN') || "Not reported"} Cr
              </span>
            </div>
            <div className="p-3 bg-red-50/70 rounded-lg border border-red-200 col-span-2">
              <div className="flex justify-between items-center">
                <span className="text-red-700 font-medium">Cumulative Cost Overrun</span>
                <span className="text-xs font-bold font-mono text-red-700">
                  +{financial_metrics.overrun_pct?.toFixed(1)}% Escalation
                </span>
              </div>
              <span className="text-2xl font-extrabold font-mono text-red-600 block mt-1">
                {financial_metrics.overrun_cr > 0 ? `+₹${financial_metrics.overrun_cr.toLocaleString('en-IN')} Cr` : '₹0 Cr'}
              </span>
            </div>
          </div>
        </div>

        {/* Schedule Metrics */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <h3 className="text-base font-bold text-gov-navy flex items-center gap-2 border-b border-slate-100 pb-3">
            <Clock className="w-5 h-5 text-amber-600" />
            Schedule Timeline &amp; Physical Progress
          </h3>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-slate-500 block">Original Date of Completion</span>
              <span className="text-sm font-semibold font-mono text-slate-800">
                {schedule_metrics.original_date || "Data unavailable"}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-slate-500 block">Latest Anticipated Date</span>
              <span className="text-sm font-semibold font-mono text-slate-800">
                {schedule_metrics.latest_date || "Data unavailable"}
              </span>
            </div>
            <div className="p-3 bg-amber-50/70 rounded-lg border border-amber-200 col-span-2">
              <div className="flex justify-between items-center mb-1">
                <span className="text-amber-800 font-medium">Total Delay Months</span>
                <span className="text-lg font-bold font-mono text-amber-700">
                  {schedule_metrics.delay_months || 0} Months
                </span>
              </div>
              <div className="mt-2">
                <div className="flex justify-between text-[11px] text-slate-600 mb-1">
                  <span>Physical Progress</span>
                  <span className="font-bold font-mono">{schedule_metrics.physical_progress_pct || 0}%</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, schedule_metrics.physical_progress_pct || 0)}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Explainable AI SHAP Risk Drivers Section */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-base font-bold text-gov-navy flex items-center gap-2">
              <Cpu className="w-5 h-5 text-blue-600" />
              XGBoost Explainable Risk Drivers (SHAP Attribution)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Identifies key physical and financial factors contributing to risk score escalation
            </p>
          </div>
          <button
            onClick={() => setShowTechnicalShap(!showTechnicalShap)}
            className="text-xs text-blue-600 font-semibold hover:underline flex items-center gap-1"
          >
            {showTechnicalShap ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            {showTechnicalShap ? "Hide Raw SHAP Weights" : "View Technical SHAP Values"}
          </button>
        </div>

        {/* Human-Readable Officer Risk Drivers */}
        <div className="space-y-3">
          {key_risk_drivers.map((driver, idx) => (
            <div
              key={idx}
              className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
            >
              <div className="space-y-0.5">
                <span className="font-bold text-gov-navy block">{driver.factor}</span>
                <span className="text-slate-600 text-[11px] block">{driver.plain_english}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-1 rounded font-semibold text-[11px] whitespace-nowrap ${
                  driver.impact === 'Critical Increase'
                    ? 'bg-red-100 text-red-700 border border-red-200'
                    : driver.impact === 'Moderate Increase'
                    ? 'bg-amber-100 text-amber-700 border border-amber-200'
                    : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                }`}>
                  {driver.impact}
                </span>
                <span className="font-mono text-slate-500 font-medium text-[11px]">
                  SHAP: {driver.shap_value > 0 ? `+${driver.shap_value.toFixed(3)}` : driver.shap_value.toFixed(3)}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Technical SHAP Expander View */}
        {showTechnicalShap && (
          <div className="mt-4 p-4 bg-slate-900 text-slate-200 rounded-lg text-xs font-mono space-y-2">
            <h4 className="text-amber-400 font-bold mb-2 text-[11px]">Raw Feature Attribution Ledger (XGBoost v1)</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-[11px]">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="py-1">Feature Name</th>
                    <th className="py-1">Feature Value</th>
                    <th className="py-1 text-right">SHAP Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {shap_technical_details.map((item, idx) => (
                    <tr key={idx}>
                      <td className="py-1.5 text-blue-300">{item.feature_name}</td>
                      <td className="py-1.5 text-slate-300">{String(item.feature_value)}</td>
                      <td className={`py-1.5 text-right font-bold ${item.shap_contribution > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                        {item.shap_contribution > 0 ? `+${item.shap_contribution.toFixed(4)}` : item.shap_contribution.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Contractual & Audit Evidence Snippets (RAG Vector Store) */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div>
          <h3 className="text-base font-bold text-gov-navy flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-600" />
            Audit Evidence &amp; Document Excerpts (RAG Vector Store)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Retrieved text chunks from 150 official PDF reports indexed in vector store
          </p>
        </div>

        {evidence_snippets.length === 0 ? (
          <p className="text-slate-500 text-xs py-4">No specific document snippets linked to this project code.</p>
        ) : (
          <div className="space-y-3">
            {evidence_snippets.map((snip, idx) => (
              <div key={idx} className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-semibold text-blue-700 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" /> {snip.document_name}
                  </span>
                  <span className="font-mono bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-[10px]">
                    RRF Score: {snip.rrf_score?.toFixed(3) || '0.950'}
                  </span>
                </div>
                <p className="text-slate-700 leading-relaxed italic bg-white p-3 rounded border border-slate-200">
                  "{snip.excerpt}"
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
