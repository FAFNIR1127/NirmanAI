import re
from pathlib import Path
import pandas as pd
import fitz  # PyMuPDF
from tqdm import tqdm

MANIFEST_PATH = Path("processed/documents/manifest.parquet")
RAW_DIR = Path("raw")
OUTPUT_CHUNKS = Path("processed/documents/chunks.parquet")

# Regex to detect 9-digit PAIMANA project codes (e.g., 020100044 or N04000073)
PROJECT_CODE_PATTERN = re.compile(r'\b([0N]\d{8})\b')

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def clean_text(text: str) -> str:
    """Clean extra spaces and non-printable characters."""
    if not text:
        return ""
    # Replace multiple spaces/newlines with single space/newline
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def chunk_text(text: str, target_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character chunks cleanly on sentence or line boundaries when possible."""
    if len(text) <= target_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + target_size
        if end >= len(text):
            chunks.append(text[start:].strip())
            break
        
        # Try to break at a line break or sentence end
        break_pos = text.rfind('\n', start + target_size // 2, end)
        if break_pos == -1:
            break_pos = text.rfind('. ', start + target_size // 2, end)
        if break_pos == -1 or break_pos <= start:
            break_pos = end
            
        chunk_content = text[start:break_pos].strip()
        if chunk_content:
            chunks.append(chunk_content)
        
        start = max(start + 1, break_pos - overlap)

    return chunks


def process_documents():
    print("=== EXTRACTING & CHUNKING PAIMANA DOCUMENTS ===")
    
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest file missing at {MANIFEST_PATH}. Run build_document_manifest.py first.")

    manifest_df = pd.read_parquet(MANIFEST_PATH)
    print(f"Loaded manifest with {len(manifest_df)} PDF documents.")

    all_chunks = []
    total_pages_processed = 0

    for idx, row in tqdm(manifest_df.iterrows(), total=len(manifest_df), desc="Extracting PDFs"):
        pdf_rel_path = Path(row["relative_path"])
        full_pdf_path = RAW_DIR / pdf_rel_path
        
        if not full_pdf_path.exists():
            # Try matching by filename inside RAW_DIR if relative path moved
            matches = list(RAW_DIR.glob(f"**/{row['source_file']}"))
            if matches:
                full_pdf_path = matches[0]
            else:
                print(f"Skipping missing file: {full_pdf_path}")
                continue

        try:
            doc = fitz.open(full_pdf_path)
        except Exception as e:
            print(f"Failed to open {full_pdf_path}: {e}")
            continue

        for page_num in range(len(doc)):
            total_pages_processed += 1
            page = doc[page_num]
            text = page.get_text("text")
            cleaned_text = clean_text(text)

            if not cleaned_text or len(cleaned_text) < 20:
                continue

            # Extract all project codes on this page
            page_project_codes = sorted(list(set(PROJECT_CODE_PATTERN.findall(cleaned_text))))

            # Chunk the page text
            sub_chunks = chunk_text(cleaned_text)
            
            for chunk_idx, sub_chunk in enumerate(sub_chunks):
                chunk_codes = sorted(list(set(PROJECT_CODE_PATTERN.findall(sub_chunk))))
                # Fall back to page-level project codes if chunk doesn't explicitly contain code
                effective_codes = chunk_codes if chunk_codes else page_project_codes
                primary_code = effective_codes[0] if effective_codes else None

                chunk_id = f"{row['source_file']}_p{page_num + 1}_c{chunk_idx + 1}"

                all_chunks.append({
                    "chunk_id": chunk_id,
                    "source_file": row["source_file"],
                    "relative_path": row["relative_path"],
                    "page_number": page_num + 1,
                    "reporting_year": row["reporting_year"],
                    "reporting_month": row["reporting_month"],
                    "document_type": row["document_type"],
                    "project_code": primary_code,
                    "project_codes": ",".join(effective_codes) if effective_codes else "",
                    "content": sub_chunk,
                    "char_count": len(sub_chunk),
                    "word_count": len(sub_chunk.split())
                })

        doc.close()

    chunks_df = pd.DataFrame(all_chunks)
    OUTPUT_CHUNKS.parent.mkdir(parents=True, exist_ok=True)
    chunks_df.to_parquet(OUTPUT_CHUNKS, index=False)

    print("\n" + "=" * 90)
    print("PAIMANA DOCUMENT CHUNKING COMPLETE")
    print("=" * 90)
    print(f"Total Pages Scanned: {total_pages_processed:,}")
    print(f"Total Chunks Extracted: {len(chunks_df):,}")
    print(f"Chunks with Identified Project Codes: {(chunks_df['project_code'].notna()).sum():,} ({(chunks_df['project_code'].notna()).mean()*100:.1f}%)")
    print(f"Saved Chunks Parquet: {OUTPUT_CHUNKS}")

    return chunks_df


if __name__ == "__main__":
    process_documents()
