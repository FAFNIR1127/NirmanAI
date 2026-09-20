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
import { RiskSimulator } from './components/simulator/RiskSimulator';
import { AIAssistantDrawer } from './components/assistant/AIAssistantDrawer';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginPage } from './components/auth/LoginPage';

function NirmanPlatform() {
  const { isAuthenticated, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [activeProjectCode, setActiveProjectCode] = useState<string | null>(null);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [assistantQuery, setAssistantQuery] = useState<string | undefined>(undefined);

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-900 text-white font-sans">
        <div className="w-10 h-10 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mb-4" />
        <h2 className="text-base font-bold tracking-tight">Verifying Authorised Admin Session...</h2>
        <p className="text-xs text-slate-400 mt-1 font-mono">Government of India &bull; MoSPI IPMD</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

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

  const handleCloseAssistant = () => {
    setIsAssistantOpen(false);
    setAssistantQuery(undefined);
  };

  const handleToggleAssistant = () => {
    if (isAssistantOpen) {
      handleCloseAssistant();
    } else {
      setAssistantQuery(undefined);
      setIsAssistantOpen(true);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
      {/* Top Header */}
      <Header
        onSelectProject={handleSelectProject}
        onToggleAssistant={handleToggleAssistant}
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

          {activeTab === 'simulator' && (
            <RiskSimulator />
          )}

          {activeTab === 'health' && (
            <SystemHealth />
          )}
        </ErrorBoundary>
      </main>

      {/* AI Copilot Drawer */}
      <AIAssistantDrawer
        isOpen={isAssistantOpen}
        onClose={handleCloseAssistant}
        activeProjectCode={activeProjectCode}
        initialQuery={assistantQuery}
        onSelectProject={handleSelectProject}
      />

      {/* Footer */}
      <Footer />
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <NirmanPlatform />
    </AuthProvider>
  );
}

export default App;
