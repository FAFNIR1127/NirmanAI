"""
create_model_governance_and_audit.py

Generates complete cryptographic model versioning metadata (hashes, provenance)
and populates the persistent `project_risk_predictions` historical audit table
in both PostgreSQL and SQLite.
"""

from pathlib import Path
import hashlib
import json
import pandas as pd
import numpy as np
import sqlalchemy
import sqlite3

ROOT_DIR = Path("/Users/sanket/SIH/NirmanAnti")
DATA_DIR = ROOT_DIR / "processed" / "features"
VERSION_DIR = ROOT_DIR / "models" / "risk_engine_v2"
SQLITE_PATH = ROOT_DIR / "database" / "nirman.db"
PG_DSN = "postgresql://postgres:hulk@localhost:5432/nirman_db"


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_governance_artifacts():
    print("=" * 80)
    print("STEP 6: MODEL GOVERNANCE, CRYPTOGRAPHIC HASHING & AUDIT TRAIL")
    print("=" * 80)

    train_hash = compute_sha256(DATA_DIR / "train_dataset_v2.parquet")
    holdout_hash = compute_sha256(DATA_DIR / "val_holdout_v2.parquet")
    schema_hash = compute_sha256(VERSION_DIR / "feature_schema.json")
    model_hash = compute_sha256(VERSION_DIR / "xgboost_base.joblib")
    calibrator_hash = compute_sha256(VERSION_DIR / "calibrator.joblib")

    metadata = {
        "model_version": "risk_engine_v2.1",
        "algorithm": "XGBoost Classifier + 5-Fold Isotonic CalibratedClassifierCV",
        "target": "target_severe_risk_12m (Cost Overrun >= 5% or Delay >= 3m within 12 months)",
        "training_period": {
            "start": "2018-04",
            "end": "2023-04",
            "observations": 7377,
            "prevalence": 0.3348
        },
        "locked_holdout_period": {
            "start": "2024-04",
            "end": "2025-04",
            "observations": 1772,
            "prevalence": 0.2094
        },
        "feature_count": 34,
        "operational_threshold": 0.25,
        "f1_optimal_threshold": 0.35,
        "loss_asymmetry": "5 * FN + 1 * FP",
        "provenance_hashes": {
            "training_dataset_sha256": train_hash,
            "holdout_dataset_sha256": holdout_hash,
            "feature_schema_sha256": schema_hash,
            "base_model_weights_sha256": model_hash,
            "calibrator_weights_sha256": calibrator_hash
        },
        "evaluation_summary": {
            "temporal_cv_expanding_window": {
                "roc_auc": "0.6144 ± 0.0548",
                "pr_auc": "0.5235 ± 0.1275",
                "brier_score": "0.2770 ± 0.0279",
                "brier_skill_score": "+0.1232"
            },
            "project_group_cv": {
                "roc_auc": "0.7768 ± 0.0050",
                "pr_auc": "0.6352 ± 0.0229",
                "brier_score": "0.1807"
            },
            "locked_holdout_2024_2025": {
                "roc_auc": 0.5209,
                "pr_auc": 0.2235,
                "prevalence_base_rate": 0.2094,
                "brier_score": 0.1927,
                "operational_recall": 0.8383,
                "operational_precision": 0.2280,
                "false_negatives": 60,
                "false_positives": 1053
            }
        }
    }

    meta_path = VERSION_DIR / "model_version_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Cryptographic Model Metadata saved to {meta_path}")

    # Build persistent audit records from risk_scores.parquet
    risk_scores_path = DATA_DIR / "risk_scores.parquet"
    rs_df = pd.read_parquet(risk_scores_path)

    audit_records = pd.DataFrame({
        "project_code": rs_df["project_code"],
        "observation_date": rs_df["reporting_month"],
        "model_version": "risk_engine_v2.1",
        "predicted_probability": rs_df["predicted_severe_risk_prob"],
        "risk_score": rs_df["risk_score"],
        "risk_tier": rs_df["risk_category"],
        "operational_threshold": 0.25,
        "is_severe_risk": rs_df["predicted_severe_risk_prob"] >= 0.25,
        "key_risk_drivers": rs_df["key_risk_drivers"]
    })

    # Ingest to PostgreSQL
    print("Updating PostgreSQL `project_risk_predictions` audit table...")
    pg_engine = sqlalchemy.create_engine(PG_DSN)
    with pg_engine.begin() as conn:
        conn.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS project_risk_predictions (
                id SERIAL PRIMARY KEY,
                project_code VARCHAR(50) NOT NULL REFERENCES projects(project_code) ON DELETE CASCADE,
                observation_date VARCHAR(10) NOT NULL,
                model_version VARCHAR(50) NOT NULL,
                predicted_probability NUMERIC(6,4) NOT NULL,
                risk_score NUMERIC(5,2) NOT NULL,
                risk_tier VARCHAR(20) NOT NULL,
                operational_threshold NUMERIC(4,2) NOT NULL,
                is_severe_risk BOOLEAN NOT NULL,
                key_risk_drivers JSONB,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_predictions_lookup ON project_risk_predictions(project_code, observation_date, model_version);
        """))
        # Delete existing entries for this model_version to allow idempotent rerun
        conn.execute(sqlalchemy.text("DELETE FROM project_risk_predictions WHERE model_version = 'risk_engine_v2.1';"))
        audit_records.to_sql("project_risk_predictions", conn, if_exists="append", index=False)
    print("PostgreSQL project_risk_predictions updated successfully.")

    # Ingest to SQLite
    print("Updating SQLite `project_risk_predictions` audit table...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.execute("""
        CREATE TABLE IF NOT EXISTS project_risk_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_code TEXT NOT NULL,
            observation_date TEXT NOT NULL,
            model_version TEXT NOT NULL,
            predicted_probability REAL NOT NULL,
            risk_score REAL NOT NULL,
            risk_tier TEXT NOT NULL,
            operational_threshold REAL NOT NULL,
            is_severe_risk INTEGER NOT NULL,
            key_risk_drivers TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    sqlite_conn.execute("DELETE FROM project_risk_predictions WHERE model_version = 'risk_engine_v2.1';")
    audit_records["is_severe_risk"] = audit_records["is_severe_risk"].astype(int)
    audit_records.to_sql("project_risk_predictions", sqlite_conn, if_exists="append", index=False)
    sqlite_conn.commit()
    sqlite_conn.close()
    print("SQLite project_risk_predictions updated successfully.")


if __name__ == "__main__":
    generate_governance_artifacts()
