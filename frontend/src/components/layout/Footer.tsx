import React from 'react';
import { Database, ShieldCheck, Cpu } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-slate-900 text-slate-400 text-xs py-8 border-t border-slate-800 mt-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-3 gap-6">
        <div>
          <h4 className="font-bold text-white text-sm mb-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-gov-amber"></span>
            NIRMAN Infrastructure Platform
          </h4>
          <p className="text-slate-400 leading-relaxed text-xs">
            Ministry of Statistics & Programme Implementation (MoSPI) infrastructure project monitoring and explainable AI risk intelligence system.
          </p>
        </div>

        <div>
          <h4 className="font-bold text-white text-sm mb-2">System Specs & Model Audit</h4>
          <ul className="space-y-1 text-slate-400 font-mono text-[11px]">
            <li className="flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-blue-400" />
              <span>5,469 Monitored Projects (14,893 Live Observations)</span>
            </li>
            <li className="flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-emerald-400" />
              <span>XGBoost Engine v1 (Calibrated Cutoff T* = 0.28)</span>
            </li>
            <li className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
              <span>331,206 Document Vector Chunks (150 PDFs)</span>
            </li>
          </ul>

        </div>

        <div className="text-right md:text-right">
          <p className="font-semibold text-slate-300">National Informatics Centre (NIC) Compliance</p>
          <p className="mt-1 text-slate-400 text-[11px]">
            Data updated live via PostgreSQL <code className="text-blue-300">nirman_db</code>.
          </p>
          <p className="mt-2 text-slate-400 text-[11px]">
            © 2026 Government of India. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
};
