-- ============================================================
-- Nirman / PAIMANA AI Infrastructure Monitoring Platform Schema
-- Database: PostgreSQL
-- ============================================================

-- 1. Master Projects Table
CREATE TABLE IF NOT EXISTS projects (
    project_code VARCHAR(32) PRIMARY KEY,
    project_name TEXT NOT NULL,
    agency VARCHAR(128),
    state VARCHAR(128),
    sector VARCHAR(128),
    approval_date VARCHAR(7),
    original_cost NUMERIC(14, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Longitudinal Monthly Project Observations Table
CREATE TABLE IF NOT EXISTS project_observations (
    id SERIAL PRIMARY KEY,
    project_code VARCHAR(32) REFERENCES projects(project_code) ON DELETE CASCADE,
    reporting_month VARCHAR(7) NOT NULL,
    revised_cost NUMERIC(14, 2),
    anticipated_cost NUMERIC(14, 2),
    cumulative_expenditure NUMERIC(14, 2),
    physical_progress NUMERIC(8, 2),
    original_doc VARCHAR(7),
    revised_doc VARCHAR(7),
    anticipated_doc VARCHAR(7),
    original_delay_months NUMERIC(10, 1),
    revised_delay_months NUMERIC(10, 1),
    milestones_achieved INTEGER,
    milestones_total INTEGER,
    source_file VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_project_reporting_month UNIQUE (project_code, reporting_month)
);

-- 3. Engineered Features & ML Prediction Targets Table
CREATE TABLE IF NOT EXISTS project_features (
    id SERIAL PRIMARY KEY,
    project_code VARCHAR(32) REFERENCES projects(project_code) ON DELETE CASCADE,
    reporting_month VARCHAR(7) NOT NULL,
    months_elapsed NUMERIC(14, 2),
    months_originally_planned NUMERIC(14, 2),
    months_remaining NUMERIC(14, 2),
    cost_expansion_ratio NUMERIC(14, 4),
    expenditure_ratio NUMERIC(14, 4),
    expenditure_progress_gap NUMERIC(14, 4),
    schedule_slippage_ratio NUMERIC(14, 4),
    progress_velocity NUMERIC(14, 4),
    target_cost_overrun_12m SMALLINT,
    target_time_overrun_12m SMALLINT,
    target_severe_risk_12m SMALLINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_feature_project_reporting_month UNIQUE (project_code, reporting_month)
);

-- 4. Risk Engine Scores & Model Predictions Table
CREATE TABLE IF NOT EXISTS risk_scores (
    id SERIAL PRIMARY KEY,
    project_code VARCHAR(32) REFERENCES projects(project_code) ON DELETE CASCADE,
    reporting_month VARCHAR(7) NOT NULL,
    composite_risk_score NUMERIC(5, 2) NOT NULL,
    cost_risk_score NUMERIC(5, 2),
    schedule_risk_score NUMERIC(5, 2),
    progress_risk_score NUMERIC(5, 2),
    risk_category VARCHAR(32) NOT NULL,
    shap_top_drivers JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_risk_project_reporting_month UNIQUE (project_code, reporting_month)
);

-- ============================================================
-- INDEXES FOR FAST ANALYTICS & DASHBOARD SERVING
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_obs_project_code ON project_observations(project_code);
CREATE INDEX IF NOT EXISTS idx_obs_reporting_month ON project_observations(reporting_month);
CREATE INDEX IF NOT EXISTS idx_feat_project_code ON project_features(project_code);
CREATE INDEX IF NOT EXISTS idx_feat_reporting_month ON project_features(reporting_month);
CREATE INDEX IF NOT EXISTS idx_risk_project_code ON risk_scores(project_code);
CREATE INDEX IF NOT EXISTS idx_risk_reporting_month ON risk_scores(reporting_month);
CREATE INDEX IF NOT EXISTS idx_risk_category ON risk_scores(risk_category);
