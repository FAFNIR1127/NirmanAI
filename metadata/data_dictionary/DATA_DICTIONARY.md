# Nirman / PAIMANA AI Infrastructure Monitoring Platform - Data Dictionary & Pipeline Documentation

This document describes the unified longitudinal dataset, feature schema, extraction methodology, quality validation rules, and dataset statistics for **Project Nirman** (SIH Problem Statement 26103).

---

## 1. Unified Dataset Summary

- **Total Longitudinal Observations**: `13,098` project-month records
- **Unique Monitored Infrastructure Projects**: `3,589`
- **Active Historical Range**: 2017–18 through 2026–27 (10 Years of PAIMANA / OCMS Data)
- **Primary Data Format**: Apache Parquet (`processed/features/ml_features.parquet`) & CSV (`processed/normalized/longitudinal_projects.csv`)

---

## 2. Field Schema & Definitions

| Field Name | Type | Description | Range / Values |
| :--- | :--- | :--- | :--- |
| `project_code` | `String` | Canonical unique project identification code across PAIMANA | e.g. `N02000010`, `020100044` |
| `reporting_month` | `String` | Monthly observation timestamp (`YYYY-MM`) | `2017-04` to `2026-07` |
| `project_name` | `String` | Standardized infrastructure project title | Text string |
| `agency` | `String` | Implementing agency | e.g. `NPCIL`, `AAI`, `NHAI`, `IOCL` |
| `state` | `String` | Location State / Territory | e.g. `GUJARAT`, `TAMIL NADU`, `MULTI STATE` |
| `approval_date` | `String` | Date of government sanction / project approval (`YYYY-MM`) | `YYYY-MM` |
| `original_cost` | `Float` | Original approved project cost (INR Crore) | $> 0$ |
| `revised_cost` | `Float` | Revised approved cost if applicable (INR Crore) | $\ge 0$ |
| `anticipated_cost` | `Float` | Latest projected completion cost (INR Crore) | $\ge 0$ |
| `cumulative_expenditure` | `Float` | Total cumulative expenditure to date (INR Crore) | $\ge 0$ |
| `physical_progress` | `Float` | Physical progress completion percentage | $0.00\%$ to $100.00\%$ |
| `original_doc` | `String` | Original target Date of Commissioning (`YYYY-MM`) | `YYYY-MM` |
| `revised_doc` | `String` | Revised Date of Commissioning (`YYYY-MM`) | `YYYY-MM` |
| `anticipated_doc` | `String` | Anticipated Date of Commissioning (`YYYY-MM`) | `YYYY-MM` |
| `original_delay_months` | `Float` | Schedule delay relative to original completion date | Months |
| `revised_delay_months` | `Float` | Schedule delay relative to revised completion date | Months |

---

## 3. Engineered Features

| Feature Name | Formula / Logic | Domain Purpose |
| :--- | :--- | :--- |
| `cost_expansion_ratio` | $\text{anticipated\_cost} / \text{original\_cost}$ | Quantifies cost escalation magnitude |
| `expenditure_ratio` | $\text{cumulative\_expenditure} / \text{anticipated\_cost}$ | Financial execution progress ratio |
| `expenditure_progress_gap` | $\text{expenditure\_ratio} - (\text{physical\_progress} / 100)$ | Key indicator of financial vs physical execution divergence |
| `months_elapsed` | $(\text{reporting\_month} - \text{approval\_date})$ in months | Time elapsed since project sanction |
| `months_remaining` | $(\text{anticipated\_doc} - \text{reporting\_month})$ in months | Time remaining to target completion |
| `schedule_slippage_ratio` | $\text{delay\_months} / \text{months\_originally\_planned}$ | Relative schedule delay proportion |
| `progress_velocity` | $\Delta \text{physical\_progress} / \Delta \text{months}$ | Monthly physical progress rate of execution |

---

## 4. Forward Prediction Targets (No Data Leakage)

- **`target_cost_overrun_12m`**: `1` if project experiences $> 15\%$ cost escalation over next 12 months, `0` otherwise.
- **`target_time_overrun_12m`**: `1` if project experiences $> 6$ months additional delay over next 12 months, `0` otherwise.
- **`target_severe_risk_12m`**: `1` if project experiences $> 25\%$ cost escalation OR $> 12$ months delay over next 12 months, `0` otherwise.

---

## 5. Dataset Split & Machine Learning Strategy

- **Train Set (`train_dataset.parquet`)**: `9,368` observations (2018-04 to 2023-04)
- **Validation Set (`val_dataset.parquet`)**: `2,606` observations (2024-04 to 2025-04)
- **Live Prediction Set (`live_dataset.parquet`)**: `1,124` active ongoing project observations (2025-07 to 2026-07)
