import React, { useState, useEffect } from 'react';
import { Activity, Search, Bot, ShieldCheck, RefreshCw } from 'lucide-react';
import api from '../../services/apiClient';

interface HeaderProps {
  onSelectProject: (code: string) => void;
  onToggleAssistant: () => void;
  isAssistantOpen: boolean;
  activeProjectCode: string | null;
}

export const Header: React.FC<HeaderProps> = ({
  onSelectProject,
  onToggleAssistant,
  isAssistantOpen,
  activeProjectCode,
}) => {
  const [health, setHealth] = useState<{ status: string; database_status: string } | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    api.getHealth()
      .then(data => setHealth(data))
      .catch(() => setHealth(null));
  }, []);

  const handleQuickSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    onSelectProject(searchQuery.trim());
    setSearchQuery('');
  };

  return (
    <header className="bg-gov-navy text-white border-b border-slate-700 shadow-sm sticky top-0 z-30">
      {/* Top Govt Bar */}
      <div className="bg-slate-950 text-slate-400 text-xs py-1 px-4 flex justify-between items-center border-b border-slate-800">
        <div className="flex items-center gap-2 font-medium">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-gov-amber"></span>
          <span>GOVERNMENT OF INDIA — MINISTRY OF STATISTICS & PROGRAMME IMPLEMENTATION</span>
        </div>
        <div className="flex items-center gap-4 text-slate-300">
          <span className="flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            Official Infrastructure Monitoring Portal
          </span>
          {health ? (
            <span className="flex items-center gap-1 text-emerald-400 font-mono text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              API Online ({health.database_status})
            </span>
          ) : (
            <span className="flex items-center gap-1 text-amber-400 font-mono text-[11px]">
              <RefreshCw className="w-3 h-3 animate-spin" />
              Connecting...
            </span>
          )}
        </div>
      </div>

      {/* Main Header Container */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
        {/* Brand & Identity */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => onSelectProject('')}>
          <div className="w-10 h-10 rounded bg-gradient-to-br from-blue-600 to-gov-navy flex items-center justify-center font-bold text-xl text-white shadow border border-blue-400/30">
            N
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white leading-tight">
                NIRMAN
              </h1>
              <span className="bg-gov-amber/20 text-gov-amber border border-gov-amber/40 text-[10px] font-semibold px-2 py-0.5 rounded tracking-wide uppercase">
                PAIMANA AI v1.0
              </span>
            </div>
            <p className="text-xs text-slate-300 font-normal">
              Infrastructure Monitoring & XGBoost Explainable Risk Engine
            </p>
          </div>
        </div>

        {/* Quick Search & Project Jump */}
        <form onSubmit={handleQuickSearch} className="flex-1 max-w-md relative">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Quick Jump by Project Code (e.g. 201700140 or Metro)..."
              className="w-full bg-slate-800/90 text-white placeholder-slate-400 text-xs rounded-md pl-9 pr-20 py-2 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <button
              type="submit"
              className="absolute right-1 top-1 bottom-1 px-3 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded transition flex items-center gap-1"
            >
              Inspect
            </button>
          </div>
        </form>

        {/* Active Project & Copilot Drawer Toggle */}
        <div className="flex items-center gap-3">
          {activeProjectCode && (
            <div className="hidden lg:flex items-center gap-2 bg-blue-950/80 border border-blue-700/50 px-3 py-1.5 rounded-md text-xs">
              <span className="text-slate-400">Active Context:</span>
              <span className="font-mono text-blue-300 font-semibold">{activeProjectCode}</span>
            </div>
          )}

          <button
            onClick={onToggleAssistant}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-medium transition shadow-sm ${
              isAssistantOpen
                ? 'bg-blue-600 text-white shadow-blue-500/20'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
            }`}
          >
            <Bot className="w-4 h-4 text-blue-400" />
            <span>AI Copilot</span>
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          </button>
        </div>
      </div>
    </header>
  );
};
