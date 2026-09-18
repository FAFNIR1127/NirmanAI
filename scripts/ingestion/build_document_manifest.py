import re
from pathlib import Path
import pandas as pd
import fitz  # PyMuPDF

# ============================================================
# PATHS
# ============================================================

RAW_DIR = Path("raw")
OUTPUT_MANIFEST = Path("processed/documents/manifest.parquet")
OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

MONTH_MAP = {
    'jan': '01', 'january': '01',
    'feb': '02', 'february': '02',
    'mar': '03', 'march': '03',
    'apr': '04', 'april': '04',
    'may': '05',
    'jun': '06', 'june': '06',
    'jul': '07', 'july': '07',
    'aug': '08', 'august': '08',
    'sep': '09', 'september': '09', 'sept': '09',
    'oct': '10', 'october': '10',
    'nov': '11', 'november': '11',
    'dec': '12', 'december': '12'
}


def parse_reporting_month(file_path):
    name = file_path.name.lower()
    parent_year = file_path.parts[1] if len(file_path.parts) > 1 else "2020-21"
    
    # Try month name matching
    found_month = None
    for m_name, m_num in MONTH_MAP.items():
        if m_name in name:
            found_month = m_num
            break
            
    # Try year in filename
    year_match = re.search(r'20[1-2][0-9]', name)
    if year_match:
        yr = year_match.group(0)
    else:
        # Default from directory name (e.g. 2020-21 -> 2020)
        yr = "20" + parent_year.split("-")[0] if "-" in parent_year else "2020"
        
    if not found_month:
        found_month = "04"  # Default April if unparsed
        
    return f"{yr}-{found_month}"


def classify_document_type(file_path):
    name = file_path.name.lower()
    rel_path = str(file_path).lower()
    
    if "quarterly" in rel_path:
        return "QUARTERLY"
    elif "part-i" in name or "synopsis" in name or "overview" in name:
        return "PART_I_SYNOPSIS"
    elif "all_ongoing" in name or "portal" in name or "2025" in rel_path or "2026" in rel_path:
        return "MODERN_PORTAL"
    else:
        return "PRIMARY_DETAILED"


def build_manifest():
    print("=== BUILDING PAIMANA DOCUMENT INVENTORY MANIFEST ===")
    
    pdf_files = sorted(list(RAW_DIR.glob("**/*.pdf")))
    print(f"Found {len(pdf_files)} PDF files in `raw/`.")

    records = []
    for pdf_path in pdf_files:
        rel_path = pdf_path.relative_to(RAW_DIR)
        parent_dir = pdf_path.parts[1] if len(pdf_path.parts) > 1 else "Unknown"
        
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
        except Exception as e:
            print(f"Error reading {pdf_path}: {e}")
            page_count = 0

        rep_month = parse_reporting_month(pdf_path)
        doc_type = classify_document_type(pdf_path)

        records.append({
            "source_file": pdf_path.name,
            "relative_path": str(rel_path),
            "reporting_year": parent_dir,
            "reporting_month": rep_month,
            "document_type": doc_type,
            "page_count": page_count,
            "file_size_bytes": pdf_path.stat().st_size,
            "extraction_status": "READY" if page_count > 0 else "ERROR"
        })

    manifest_df = pd.DataFrame(records)
    manifest_df.to_parquet(OUTPUT_MANIFEST, index=False)

    print("\n" + "=" * 90)
    print("PAIMANA DOCUMENT MANIFEST GENERATED SUCCESSFULLY")
    print("=" * 90)
    print(f"Total Document Inventory: {len(manifest_df)} PDFs ({manifest_df['page_count'].sum():,} Total Pages)")
    print("\nBreakdown by Document Type:")
    print(manifest_df["document_type"].value_counts().to_string())
    print(f"\nSaved Manifest Parquet: {OUTPUT_MANIFEST}")

    return manifest_df


if __name__ == "__main__":
    build_manifest()
