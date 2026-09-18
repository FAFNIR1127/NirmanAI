import React from 'react';
import { CheckCircle2, AlertCircle, HelpCircle } from 'lucide-react';

export type QualityStatus = 'complete' | 'partial' | 'unreported';

interface DataQualityBadgeProps {
  status?: QualityStatus | string;
  label?: string;
}

export const DataQualityBadge: React.FC<DataQualityBadgeProps> = ({ status = 'complete', label }) => {
  const normStatus = (status || 'complete').toLowerCase();

  if (normStatus === 'complete') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
        {label || 'Complete Data'}
      </span>
    );
  }

  if (normStatus === 'partial' || normStatus === 'partially reported') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
        <AlertCircle className="w-3 h-3 text-amber-600" />
        {label || 'Partially Reported'}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">
      <HelpCircle className="w-3 h-3 text-slate-500" />
      {label || 'Not Reported'}
    </span>
  );
};
