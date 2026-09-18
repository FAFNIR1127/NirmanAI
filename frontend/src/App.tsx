import React, { useState } from 'react';
import { Header } from './components/layout/Header';
import { Navbar, TabType } from './components/layout/Navbar';
import { Footer } from './components/layout/Footer';
import { OverviewDashboard } from './components/dashboard/OverviewDashboard';
import { PortfolioExplorer } from './components/portfolio/PortfolioExplorer';
import { ProjectDetailView } from './components/detail/ProjectDetailView';
import { EvidenceSearch } from './components/rag/EvidenceSearch';
import { GeographicRiskMap } from './components/analytics/GeographicRiskMap';
import { ProjectComparison } from './components/portfolio/ProjectComparison';
import { SystemHealth } from './components/health/SystemHealth';
import { AIAssistantDrawer } from './components/assistant/AIAssistantDrawer';
import { ErrorBoundary } from './components/common/ErrorBoundary';

export function App() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [activeProjectCode, setActiveProjectCode] = useState<string | null>(null);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [assistantQuery, setAssistantQuery] = useState<string | undefined>(undefined);

  const handleSelectProject = (code: string) => {
    if (!code) {
      setActiveProjectCode(null);
      setActiveTab('portfolio');
    } else {
      setActiveProjectCode(code);
      setActiveTab('risk');
    }
  };

  const handleOpenAssistant = (query?: string) => {
    setAssistantQuery(query);
    setIsAssistantOpen(true);
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
      {/* Top Header */}
      <Header
        onSelectProject={handleSelectProject}
        onToggleAssistant={() => setIsAssistantOpen(!isAssistantOpen)}
        isAssistantOpen={isAssistantOpen}
        activeProjectCode={activeProjectCode}
      />

      {/* Main Tab Navbar */}
      <Navbar
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab)}
        activeProjectCode={activeProjectCode}
      />

      {/* Main Content Area Wrapped in Error Boundary */}
      <main className="flex-1">
        <ErrorBoundary fallbackTitle="Nirman Module Render Error">
          {activeTab === 'overview' && (
            <OverviewDashboard
              onSelectProject={handleSelectProject}
              onOpenAssistant={handleOpenAssistant}
            />
          )}

          {activeTab === 'portfolio' && (
            <PortfolioExplorer
              onSelectProject={handleSelectProject}
            />
          )}

          {activeTab === 'risk' && (
            activeProjectCode ? (
              <ProjectDetailView
                projectCode={activeProjectCode}
                onBack={() => handleSelectProject('')}
                onOpenAssistant={handleOpenAssistant}
              />
            ) : (
              <PortfolioExplorer
                onSelectProject={handleSelectProject}
              />
            )
          )}

          {activeTab === 'evidence' && (
            <EvidenceSearch
              onSelectProject={handleSelectProject}
              onOpenAssistant={handleOpenAssistant}
            />
          )}

          {activeTab === 'map' && (
            <GeographicRiskMap
              onSelectProject={handleSelectProject}
            />
          )}

          {activeTab === 'compare' && (
            <ProjectComparison
              onSelectProject={handleSelectProject}
            />
          )}

          {activeTab === 'health' && (
            <SystemHealth />
          )}
        </ErrorBoundary>
      </main>

      {/* AI Copilot Drawer */}
      <AIAssistantDrawer
        isOpen={isAssistantOpen}
        onClose={() => setIsAssistantOpen(false)}
        activeProjectCode={activeProjectCode}
        initialQuery={assistantQuery}
        onSelectProject={handleSelectProject}
      />

      {/* Footer */}
      <Footer />
    </div>
  );
}

export default App;
