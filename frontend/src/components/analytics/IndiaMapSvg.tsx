import React, { useState, useMemo } from 'react';
import { GeographicRiskItem } from '../../types/api';
import { INDIA_STATE_FEATURES, findStateFeature, normalizeStateName, StateMapFeature } from './indiaMapData';

export type MetricType = 'risk' | 'cost' | 'delay' | 'projects';

interface IndiaMapSvgProps {
  statesData: GeographicRiskItem[];
  selectedState: string | null;
  onSelectState: (stateName: string) => void;
  activeMetric: MetricType;
}

export const IndiaMapSvg: React.FC<IndiaMapSvgProps> = ({
  statesData,
  selectedState,
  onSelectState,
  activeMetric
}) => {
  const [hoveredState, setHoveredState] = useState<{
    feature: StateMapFeature;
    data: GeographicRiskItem | null;
  } | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Map state name synonyms to database items
  const stateDataMap = useMemo(() => {
    const map = new Map<string, GeographicRiskItem>();
    statesData.forEach(item => {
      const norm = normalizeStateName(item.state);
      map.set(norm, item);
      
      // Also match feature aliases
      const feat = findStateFeature(item.state);
      if (feat) {
        map.set(normalizeStateName(feat.name), item);
        map.set(feat.id.toLowerCase(), item);
        feat.aliases.forEach(a => map.set(normalizeStateName(a), item));
      }
    });
    return map;
  }, [statesData]);

  const getStateTelemetry = (feature: StateMapFeature): GeographicRiskItem | null => {
    const norm = normalizeStateName(feature.name);
    if (stateDataMap.has(norm)) return stateDataMap.get(norm)!;
    if (stateDataMap.has(feature.id.toLowerCase())) return stateDataMap.get(feature.id.toLowerCase())!;
    for (const alias of feature.aliases) {
      const aNorm = normalizeStateName(alias);
      if (stateDataMap.has(aNorm)) return stateDataMap.get(aNorm)!;
    }
    return null;
  };

  // Metric max scale calculations
  const { maxHighRisk, maxOverrun, maxDelay, maxProjects } = useMemo(() => {
    let mHigh = 1;
    let mOverrun = 1;
    let mDelay = 1;
    let mProjects = 1;

    statesData.forEach(s => {
      const high = (s.high_risk_projects || 0) + (s.critical_risk_projects || 0);
      if (high > mHigh) mHigh = high;
      if (s.total_cost_overrun_cr > mOverrun) mOverrun = s.total_cost_overrun_cr;
      if (s.avg_delay_months > mDelay) mDelay = s.avg_delay_months;
      if (s.total_projects > mProjects) mProjects = s.total_projects;
    });

    return { maxHighRisk: mHigh, maxOverrun: mOverrun, maxDelay: mDelay, maxProjects: mProjects };
  }, [statesData]);

  // Color interpolation for choropleth mapping
  const getStateColor = (feature: StateMapFeature): string => {
    const data = getStateTelemetry(feature);
    if (!data || data.total_projects === 0) {
      return '#f1f5f9'; // Slate-100 for no active projects
    }

    if (activeMetric === 'risk') {
      const riskCount = (data.high_risk_projects || 0) + (data.critical_risk_projects || 0);
      const ratio = Math.min(1, riskCount / Math.max(maxHighRisk, 1));
      if (riskCount === 0) return '#bbf7d0'; // Light emerald
      if (ratio < 0.20) return '#fef08a'; // Soft yellow
      if (ratio < 0.45) return '#fed7aa'; // Light orange
      if (ratio < 0.75) return '#f87171'; // Coral red
      return '#b91c1c'; // Deep crimson
    } else if (activeMetric === 'cost') {
      const ratio = Math.min(1, data.total_cost_overrun_cr / Math.max(maxOverrun, 1));
      if (data.total_cost_overrun_cr <= 0) return '#bbf7d0';
      if (ratio < 0.15) return '#fef3c7'; // Amber-100
      if (ratio < 0.40) return '#fde047'; // Yellow-300
      if (ratio < 0.70) return '#fb923c'; // Orange-400
      return '#c2410c'; // Deep rust orange
    } else if (activeMetric === 'delay') {
      const ratio = Math.min(1, data.avg_delay_months / Math.max(maxDelay, 1));
      if (data.avg_delay_months <= 0) return '#f8fafc';
      if (ratio < 0.25) return '#e9d5ff'; // Purple-200
      if (ratio < 0.50) return '#c084fc'; // Purple-400
      if (ratio < 0.75) return '#9333ea'; // Purple-600
      return '#581c87'; // Deep violet
    } else {
      // Total Projects
      const ratio = Math.min(1, data.total_projects / Math.max(maxProjects, 1));
      if (ratio < 0.15) return '#dbeafe'; // Blue-100
      if (ratio < 0.40) return '#93c5fd'; // Blue-300
      if (ratio < 0.70) return '#3b82f6'; // Blue-500
      return '#1e3a8a'; // Deep Navy
    }
  };

  const handleMouseMove = (e: React.MouseEvent, feature: StateMapFeature) => {
    const data = getStateTelemetry(feature);
    setHoveredState({ feature, data });

    const svgRect = e.currentTarget.closest('svg')?.getBoundingClientRect();
    if (svgRect) {
      setTooltipPos({
        x: e.clientX - svgRect.left,
        y: e.clientY - svgRect.top
      });
    }
  };

  const isStateSelected = (feature: StateMapFeature): boolean => {
    if (!selectedState) return false;
    const targetNorm = normalizeStateName(selectedState);
    if (normalizeStateName(feature.name) === targetNorm) return true;
    if (feature.id.toLowerCase() === targetNorm) return true;
    return feature.aliases.some(a => normalizeStateName(a) === targetNorm);
  };

  return (
    <div className="relative w-full flex flex-col items-center select-none">
      {/* SVG Canvas with Accurate Survey Geometry */}
      <svg
        viewBox="0 0 800 900"
        className="w-full max-w-[700px] h-auto drop-shadow-lg cursor-pointer transition-all"
        onMouseLeave={() => setHoveredState(null)}
        role="img"
        aria-label="Interactive India Geospatial Risk Map"
      >
        <defs>
          <filter id="glow-selected" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#0284c7" floodOpacity="0.8" />
          </filter>
          <filter id="shadow-hover" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#0f172a" floodOpacity="0.3" />
          </filter>
          <linearGradient id="ocean-bg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#f8fafc" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#f1f5f9" stopOpacity="0.8" />
          </linearGradient>
        </defs>

        {/* Subtle Canvas Border */}
        <rect x="0" y="0" width="800" height="900" rx="16" fill="url(#ocean-bg)" stroke="#e2e8f0" strokeWidth="1" />

        {/* Compass & Geographic Meta Indicator */}
        <g transform="translate(690, 80)" opacity="0.75">
          <circle cx="0" cy="0" r="18" fill="#ffffff" stroke="#94a3b8" strokeWidth="1.5" />
          <path d="M 0 -14 L 4 -2 L 0 2 L -4 -2 Z" fill="#ef4444" />
          <path d="M 0 14 L 4 2 L 0 -2 L -4 2 Z" fill="#64748b" />
          <text x="0" y="-18" textAnchor="middle" className="text-[10px] font-extrabold fill-slate-700">N</text>
        </g>

        {/* State Boundary Paths */}
        {INDIA_STATE_FEATURES.map((feature) => {
          const selected = isStateSelected(feature);
          const isHovered = hoveredState?.feature.id === feature.id;
          const fillColor = getStateColor(feature);
          const data = getStateTelemetry(feature);
          const hasData = Boolean(data && data.total_projects > 0);

          return (
            <g key={feature.id} className="transition-all duration-150">
              <path
                d={feature.d}
                fill={fillColor}
                stroke={selected ? '#0284c7' : isHovered ? '#0f172a' : '#ffffff'}
                strokeWidth={selected ? 3.5 : isHovered ? 2.2 : 0.8}
                strokeLinejoin="round"
                strokeLinecap="round"
                className="transition-all duration-200 hover:brightness-105"
                style={{
                  filter: selected ? 'url(#glow-selected)' : isHovered ? 'url(#shadow-hover)' : undefined,
                  cursor: hasData ? 'pointer' : 'default'
                }}
                onMouseEnter={(e) => handleMouseMove(e, feature)}
                onMouseMove={(e) => handleMouseMove(e, feature)}
                onClick={() => onSelectState(feature.name)}
              />

              {/* Centroid Code Label for prominent states */}
              {feature.center && feature.center[0] > 0 && (
                <text
                  x={feature.center[0]}
                  y={feature.center[1]}
                  textAnchor="middle"
                  dominantBaseline="central"
                  pointerEvents="none"
                  className={`transition-all font-sans font-bold ${
                    selected
                      ? 'fill-blue-950 text-[11px] font-extrabold'
                      : isHovered
                      ? 'fill-slate-900 text-[10px] font-bold'
                      : 'fill-slate-800/80 text-[8.5px]'
                  }`}
                  style={{
                    textShadow: '0 0 3px rgba(255,255,255,0.9), 0 0 1px #fff'
                  }}
                >
                  {feature.id}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Floating Hover Telemetry Card */}
      {hoveredState && (
        <div
          className="absolute z-30 pointer-events-none bg-slate-900/95 text-white p-3.5 rounded-xl shadow-2xl border border-slate-700 backdrop-blur-md text-xs min-w-[240px] transition-all duration-75 ease-out"
          style={{
            left: `${Math.min(Math.max(tooltipPos.x + 15, 10), 450)}px`,
            top: `${Math.max(tooltipPos.y - 110, 10)}px`
          }}
        >
          <div className="flex items-center justify-between border-b border-slate-700 pb-2 mb-2">
            <div>
              <span className="font-bold text-white text-sm block">
                {hoveredState.feature.name}
              </span>
              <span className="text-[10px] text-slate-400 font-mono">
                Code: {hoveredState.feature.id}
              </span>
            </div>
            <span className="bg-blue-600/90 text-blue-100 px-2 py-0.5 rounded-full text-[10px] font-bold font-mono">
              {hoveredState.data?.total_projects || 0} Projects
            </span>
          </div>

          {hoveredState.data ? (
            <div className="space-y-1.5 text-[11px]">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">High &amp; Critical Risk:</span>
                <span className="font-bold text-red-400 font-mono bg-red-950/60 px-1.5 py-0.5 rounded border border-red-800/40">
                  {(hoveredState.data.high_risk_projects || 0) + (hoveredState.data.critical_risk_projects || 0)} projects
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Cost Escalation:</span>
                <span className="font-bold text-amber-300 font-mono">
                  ₹{hoveredState.data.total_cost_overrun_cr.toLocaleString('en-IN', { maximumFractionDigits: 1 })} Cr
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Average Delay:</span>
                <span className="font-bold text-purple-300 font-mono">
                  {hoveredState.data.avg_delay_months.toFixed(1)} Months
                </span>
              </div>
              <div className="mt-2 text-[10px] text-blue-300 text-center bg-slate-800/80 py-1 rounded-md border border-slate-700">
                Click to inspect state risk portfolio
              </div>
            </div>
          ) : (
            <div className="text-slate-400 text-[11px] italic py-1 text-center">
              No central sector project records for this territory.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
