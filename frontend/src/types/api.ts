export interface PortfolioKPIs {
  total_projects: number;
  total_original_cost_cr: number;
  total_latest_cost_cr: number;
  total_cost_overrun_cr: number;
  avg_cost_overrun_pct: number;
  avg_schedule_delay_months: number;
  high_critical_risk_count: number;
  high_risk_projects_count: number;
  critical_risk_projects_count: number;
  data_as_of: string;
  top_sectors_by_cost_overrun?: Array<{
    sector: string;
    overrun_cr: number;
    project_count: number;
  }>;
  top_states_by_high_risk?: Array<{
    state: string;
    high_risk_count: number;
  }>;
}

export interface ProjectSummary {
  id?: number;
  project_code: string;
  project_name: string;
  sector: string;
  ministry?: string;
  state: string;
  original_cost_cr: number;
  revised_cost_cr?: number | null;
  latest_cost_cr: number;
  cost_overrun_cr: number;
  cost_overrun_pct: number;
  original_delay_months?: number;
  delay_months?: number;
  physical_progress_pct?: number;
  financial_progress_pct?: number;
  risk_score: number;
  risk_category: 'Normal' | 'Watchlist' | 'High' | 'Critical';
  operational_flag?: boolean;
  last_observation_date?: string;
}

export interface ProjectListResponse {
  total: number;
  page: number;
  page_size: number;
  projects: ProjectSummary[];
}

export interface EarlyWarningAlert {
  project_code: string;
  project_name: string;
  sector: string;
  risk_score: number;
  risk_category: 'Normal' | 'Watchlist' | 'High' | 'Critical';
  primary_trigger: string;
  cost_overrun_cr: number;
  delay_months: number;
  summary: string;
}

export interface EarlyWarningsResponse {
  total_alerts: number;
  threshold_used: number;
  alerts: EarlyWarningAlert[];
}

export interface RiskDriver {
  factor: string;
  plain_english: string;
  impact: 'Critical Increase' | 'Moderate Increase' | 'Low Impact' | 'Risk Reducing';
  shap_value: number;
}

export interface ShapTechnicalDetail {
  feature_name: string;
  feature_value: number | string;
  shap_contribution: number;
}

export interface EvidenceSnippet {
  document_name: string;
  doc_type: string;
  date?: string;
  excerpt: string;
  rrf_score: number;
  chunk_id?: string;
}

export interface RiskIntelligenceResponse {
  project_code: string;
  project_name: string;
  sector: string;
  ministry: string;
  state: string;
  risk_score: number;
  risk_category: 'Normal' | 'Watchlist' | 'High' | 'Critical';
  operational_flag: boolean;
  officer_summary: string;
  key_risk_drivers: RiskDriver[];
  shap_technical_details: ShapTechnicalDetail[];
  financial_metrics: {
    original_cost_cr: number;
    latest_cost_cr: number;
    overrun_cr: number;
    overrun_pct: number;
    expenditure_cr?: number;
    expenditure_pct?: number;
  };
  schedule_metrics: {
    original_date?: string;
    latest_date?: string;
    delay_months: number;
    physical_progress_pct: number;
  };
  evidence_snippets: EvidenceSnippet[];
}

export interface DocumentChunk {
  chunk_id: string;
  doc_name: string;
  doc_type: string;
  project_code: string | null;
  sector: string;
  report_date: string;
  chunk_text: string;
  rrf_score: number;
  dense_score?: number;
  sparse_score?: number;
}

export interface DocumentSearchResponse {
  total_results: number;
  query: string;
  results: DocumentChunk[];
}

export interface CitedDocument {
  doc_name: string;
  snippet: string;
  rrf_score: number;
}

export interface AssistantChatResponse {
  response: string;
  cited_documents: CitedDocument[];
  suggested_followups: string[];
  active_project_code: string | null;
}

export interface GeographicRiskItem {
  state: string;
  total_projects: number;
  high_risk_projects: number;
  critical_risk_projects: number;
  total_cost_overrun_cr: number;
  avg_delay_months: number;
}

export interface GeographicRiskResponse {
  states: GeographicRiskItem[];
}
