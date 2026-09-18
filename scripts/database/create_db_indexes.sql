-- ============================================================================
-- Phase 9B — PostgreSQL Performance & Index Optimization Migration
-- Target Database: nirman_db
-- ============================================================================

-- 1. Enable PostgreSQL Trigram Extension for Fast Wildcard Text Searches (ILIKE '%name%')
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. Projects Table Indexes
-- Fast lookup for multi-attribute state/sector filtering and code lookup
CREATE INDEX IF NOT EXISTS idx_projects_code_state_sector 
ON public.projects (project_code, state, sector);

-- Trigram GIN index for high-speed wildcard text search on project name
CREATE INDEX IF NOT EXISTS idx_projects_name_trgm 
ON public.projects USING gin (project_name gin_trgm_ops);


-- 3. Project Observations Compound Index
CREATE INDEX IF NOT EXISTS idx_obs_code_month_cost 
ON public.project_observations (project_code, reporting_month DESC);

-- 4. Risk Scores Compound Index
-- Optimizes historical risk trajectory queries and latest risk classification filtering
CREATE INDEX IF NOT EXISTS idx_risk_code_month_cat 
ON public.risk_scores (project_code, reporting_month DESC, risk_category);

-- 5. Document Chunks Compound Index
-- Optimizes project-specific and month-filtered RAG document retrieval
CREATE INDEX IF NOT EXISTS idx_doc_chunks_code_month_type 
ON public.document_chunks (project_code, reporting_month, document_type);

-- ANALYZE tables to update query planner statistics
ANALYZE public.projects;
ANALYZE public.project_observations;
ANALYZE public.risk_scores;
ANALYZE public.document_chunks;
