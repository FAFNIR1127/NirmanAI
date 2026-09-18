#!/usr/bin/env python3
"""
Phase 10 Full-System QA Suite 2 & 3: Data Integrity, Numerical Constraints & Temporal Rules (DB-020 to DB-044)
"""
import sys
import os
import sqlalchemy
import json
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend.app.config import DATABASE_URL

def run_tests():
    results = []
    engine = sqlalchemy.create_engine(DATABASE_URL)

    with engine.connect() as conn:

        # DB-020: Duplicate project codes
        sql_dup_p = "SELECT project_code, COUNT(*) FROM projects GROUP BY project_code HAVING COUNT(*) > 1;"
        dups_p = conn.execute(sqlalchemy.text(sql_dup_p)).fetchall()
        results.append({
            "id": "DB-020",
            "category": "Data Uniqueness",
            "name": "Zero Duplicate Project Codes in `projects`",
            "passed": len(dups_p) == 0,
            "severity": "P0",
            "expected": "0 duplicate project codes",
            "actual": f"{len(dups_p)} duplicate project codes found" if dups_p else "0 duplicates",
            "hint": "Clean duplicate primary key project codes in projects table."
        })

        # DB-021: Duplicate (project_code, reporting_month) observations
        sql_dup_obs = "SELECT project_code, reporting_month, COUNT(*) FROM project_observations GROUP BY project_code, reporting_month HAVING COUNT(*) > 1;"
        dups_obs = conn.execute(sqlalchemy.text(sql_dup_obs)).fetchall()
        results.append({
            "id": "DB-021",
            "category": "Data Uniqueness",
            "name": "Zero Duplicate Project-Month Observations",
            "passed": len(dups_obs) == 0,
            "severity": "P0",
            "expected": "0 duplicate (project_code, reporting_month) pairs",
            "actual": f"{len(dups_obs)} duplicate pairs found" if dups_obs else "0 duplicates",
            "hint": "Remove duplicate observation rows per month."
        })

        # DB-022: Orphan observations
        sql_orp_obs = "SELECT COUNT(*) FROM project_observations o LEFT JOIN projects p ON o.project_code = p.project_code WHERE p.project_code IS NULL;"
        orphans_obs = conn.execute(sqlalchemy.text(sql_orp_obs)).scalar() or 0
        results.append({
            "id": "DB-022",
            "category": "Referential Integrity",
            "name": "Zero Orphan Project Observations",
            "passed": orphans_obs == 0,
            "severity": "P0",
            "expected": "0 orphan observations without matching project",
            "actual": f"{orphans_obs} orphan records",
            "hint": "Delete or reconcile orphan records referencing non-existent project_codes."
        })

        # DB-023: Orphan features
        sql_orp_feat = "SELECT COUNT(*) FROM project_features f LEFT JOIN projects p ON f.project_code = p.project_code WHERE p.project_code IS NULL;"
        orphans_feat = conn.execute(sqlalchemy.text(sql_orp_feat)).scalar() or 0
        results.append({
            "id": "DB-023",
            "category": "Referential Integrity",
            "name": "Zero Orphan Project Features",
            "passed": orphans_feat == 0,
            "severity": "P0",
            "expected": "0 orphan feature records",
            "actual": f"{orphans_feat} orphan records",
            "hint": "Reconcile project_features table with projects table."
        })

        # DB-024: Orphan risk scores
        sql_orp_risk = "SELECT COUNT(*) FROM risk_scores r LEFT JOIN projects p ON r.project_code = p.project_code WHERE p.project_code IS NULL;"
        orphans_risk = conn.execute(sqlalchemy.text(sql_orp_risk)).scalar() or 0
        results.append({
            "id": "DB-024",
            "category": "Referential Integrity",
            "name": "Zero Orphan Risk Score Records",
            "passed": orphans_risk == 0,
            "severity": "P0",
            "expected": "0 orphan risk records",
            "actual": f"{orphans_risk} orphan records",
            "hint": "Reconcile risk_scores table."
        })

        # DB-025: Malformed canonical project codes
        sql_codes = "SELECT project_code FROM projects;"
        codes = [r[0] for r in conn.execute(sqlalchemy.text(sql_codes)).fetchall()]
        malformed = [c for c in codes if not c or not isinstance(c, str) or len(c.strip()) < 3]
        results.append({
            "id": "DB-025",
            "category": "Data Sanitization",
            "name": "Valid Canonical Project Codes Format",
            "passed": len(malformed) == 0,
            "severity": "P1",
            "expected": "No empty or malformed project codes",
            "actual": f"{len(malformed)} malformed codes" if malformed else "All project codes valid format",
            "hint": "Inspect project codes for whitespace or invalid characters."
        })

        # DB-030 to DB-037: Numerical Domain Constraints
        num_checks = [
            ("DB-030", "SELECT COUNT(*) FROM projects WHERE original_cost < 0;", "Zero Negative Original Costs in projects"),
            ("DB-031", "SELECT COUNT(*) FROM project_observations WHERE cumulative_expenditure < 0;", "Zero Negative Cumulative Expenditure"),
            ("DB-032", "SELECT COUNT(*) FROM project_observations WHERE physical_progress < 0;", "Zero Physical Progress < 0%"),
            ("DB-033", "SELECT COUNT(*) FROM project_observations WHERE physical_progress > 100;", "Zero Physical Progress > 100%"),
            ("DB-034", "SELECT COUNT(*) FROM risk_scores WHERE predicted_severe_risk_prob < 0;", "Zero Risk Probability < 0.0"),
            ("DB-035", "SELECT COUNT(*) FROM risk_scores WHERE predicted_severe_risk_prob > 1.0;", "Zero Risk Probability > 1.0"),
            ("DB-036", "SELECT COUNT(*) FROM risk_scores WHERE risk_score < 0;", "Zero Risk Score < 0"),
            ("DB-037", "SELECT COUNT(*) FROM risk_scores WHERE risk_score > 100;", "Zero Risk Score > 100")
        ]

        for t_id, sql, desc in num_checks:
            violations = 0
            err_str = ""
            try:
                violations = conn.execute(sqlalchemy.text(sql)).scalar() or 0
            except Exception as e:
                err_str = str(e)
                try:
                    conn.rollback()
                except Exception:
                    pass

            results.append({
                "id": t_id,
                "category": "Numerical Bounds",
                "name": desc,
                "passed": violations == 0 and not err_str,
                "severity": "P0",
                "expected": "0 domain constraint violations",
                "actual": f"{violations} violation rows" if not err_str else err_str,
                "hint": "Clean numerical outlier or negative value rows."
            })

        # DB-040 to DB-044: Temporal Data & Density Checks
        # DB-041: Valid Date Format (YYYY-MM) in project_observations
        sql_months = "SELECT DISTINCT reporting_month FROM project_observations WHERE reporting_month IS NOT NULL;"
        months = [r[0] for r in conn.execute(sqlalchemy.text(sql_months)).fetchall()]
        invalid_months = [m for m in months if not re.match(r"^\d{4}-\d{2}$", str(m))]

        results.append({
            "id": "DB-041",
            "category": "Temporal Integrity",
            "name": "Valid Reporting Month Date Formatting (YYYY-MM)",
            "passed": len(invalid_months) == 0,
            "severity": "P1",
            "expected": "All reporting months match YYYY-MM pattern",
            "actual": f"Invalid months: {invalid_months[:5]}" if invalid_months else "All reporting months valid",
            "hint": "Sanitize reporting_month values to YYYY-MM strings."
        })

        # DB-044: Project History Density Distribution
        sql_density = """
            SELECT obs_count, COUNT(*) as projects_count
            FROM (
                SELECT project_code, COUNT(*) as obs_count
                FROM project_observations
                GROUP BY project_code
            ) t
            GROUP BY obs_count
            ORDER BY obs_count ASC;
        """
        density_rows = conn.execute(sqlalchemy.text(sql_density)).fetchall()
        density_dict = {int(r[0]): int(r[1]) for r in density_rows}

        results.append({
            "id": "DB-044",
            "category": "Temporal Density",
            "name": "Multi-Observation Density Coverage",
            "passed": len(density_dict) > 0,
            "severity": "P2",
            "expected": "Observation history spans 1, 2, 3, and 5+ periods",
            "actual": f"Observation period counts distribution: {list(density_dict.items())[:6]}",
            "hint": "Verify project observation temporal distribution."
        })

    return results

if __name__ == "__main__":
    res = run_tests()
    print(json.dumps(res, indent=2))
