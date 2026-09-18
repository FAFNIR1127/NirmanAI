from pathlib import Path
import pymupdf
import re
import sys


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def inspect_pdf(pdf_path: str):
    path = Path(pdf_path)

    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)

    doc = pymupdf.open(path)

    print("=" * 100)
    print(f"FILE: {path}")
    print(f"PAGES: {len(doc)}")
    print("=" * 100)

    for page_number, page in enumerate(doc, start=1):
        text = page.get_text()
        images = page.get_images(full=True)

        cleaned = clean_text(text)

        # First ~180 characters give us a useful structural clue
        preview = cleaned[:180]

        print(
            f"Page {page_number:3d} | "
            f"text_chars={len(text):5d} | "
            f"images={len(images):2d} | "
            f"{preview}"
        )

    doc.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("python scripts/inspection/inspect_pdf.py <pdf_path>")
        sys.exit(1)

    inspect_pdf(sys.argv[1])
