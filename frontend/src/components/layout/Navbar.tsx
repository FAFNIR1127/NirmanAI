import React from 'react';
import { LayoutDashboard, Table, AlertTriangle, FileSearch, Map, GitCompare, ShieldCheck } from 'lucide-react';

export type TabType = 'overview' | 'portfolio' | 'risk' | 'evidence' | 'map' | 'compare' | 'health';

interface NavbarProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  activeProjectCode: string | null;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onSelectTab, activeProjectCode }) => {
  const tabs = [
    { id: 'overview', label: 'Executive Overview', icon: LayoutDashboard },
    { id: 'portfolio', label: 'Portfolio Explorer', icon: Table },
    { id: 'risk', label: 'Risk Intelligence', icon: AlertTriangle, badge: activeProjectCode ? activeProjectCode : null },
    { id: 'evidence', label: 'Audit Evidence (RAG)', icon: FileSearch },
    { id: 'map', label: 'Geographic Risk', icon: Map },
    { id: 'compare', label: 'Project Compare', icon: GitCompare },
    { id: 'health', label: 'System Health', icon: ShieldCheck },
  ];

  return (
    <nav className="bg-white border-b border-slate-200 shadow-sm sticky top-[73px] z-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex space-x-1 sm:space-x-4 overflow-x-auto py-2 scrollbar-none">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id as TabType)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-semibold whitespace-nowrap transition ${
                  isActive
                    ? 'bg-gov-navy text-white shadow-sm'
                    : 'text-slate-600 hover:text-gov-navy hover:bg-slate-100'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-300' : 'text-slate-500'}`} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                    isActive ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-700'
                  }`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
};
