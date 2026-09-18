from pathlib import Path
import pymupdf
import json
import re
from collections import Counter, defaultdict

ROOT = Path("raw")
OUTPUT = Path("processed/extracted/pdf_inventory.json")


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def get_year(path):
    for part in path.parts:
        if re.match(r"^\d{4}-\d{2}$", part):
            return part
    return None


def get_report_type(path):
    if "monthly" in path.parts:
        return "monthly"

    if "quarterly" in path.parts:
        return "quarterly"

    return "unknown"


def classify_pdf(path):

    try:

        doc = pymupdf.open(path)

        page_count = len(doc)

        # Sample beginning, middle and end of document.
        sample_indices = sorted(
            set(
                [
                    0,
                    1,
                    2,
                    3,
                    4,
                    page_count // 2,
                    max(0, page_count - 3),
                    max(0, page_count - 2),
                    max(0, page_count - 1),
                ]
            )
        )

        texts = []

        for page_index in sample_indices:

            text = doc[page_index].get_text("text")

            if text:
                texts.append(text)

        sample = "\n".join(texts)

        doc.close()

        sample_clean = clean_text(sample)

        # --------------------------------------------------
        # Schema indicators
        # --------------------------------------------------

        indicators = {

            "all_ongoing":
                "All Ongoing Projects" in sample,

            "project_code":
                "Project Code" in sample
                or "Project Code)" in sample
                or "(Project Code)" in sample,

            "physical_progress":
                "Physical Progress" in sample,

            "cumulative_expenditure":
                "Cumulative Expenditure" in sample,

            "cost_overrun":
                "Cost Overrun" in sample
                or "Cost Overruns" in sample,

            "time_overrun":
                "Time Overrun" in sample
                or "Time Overruns" in sample,

            "sector_wise":
                "Sector-wise" in sample,

            "executive_summary":
                "Executive Summary" in sample,

            "project_status":
                "Project Status" in sample,

            "milestone":
                "Milestone" in sample,

            "ministry":
                "Ministry" in sample,

            "state":
                "State" in sample,

            "original_cost":
                "Original Cost" in sample,

            "revised_cost":
                "Revised Cost" in sample,

            "anticipated_cost":
                "Anticipated Cost" in sample,

            "expenditure":
                "Expenditure" in sample,
        }

        # --------------------------------------------------
        # Broad schema classification
        # --------------------------------------------------

        if indicators["all_ongoing"]:

            schema = "CURRENT_ALL_ONGOING"

        elif (
            indicators["project_code"]
            and indicators["physical_progress"]
            and indicators["cumulative_expenditure"]
        ):

            schema = "PROJECT_CODE_PROGRESS"

        elif (
            indicators["cost_overrun"]
            or indicators["time_overrun"]
            or indicators["sector_wise"]
        ):

            schema = "LEGACY_ANALYTICAL"

        else:

            schema = "OTHER"

        return {

            "file": str(path),

            "filename": path.name,

            "year": get_year(path),

            "report_type": get_report_type(path),

            "pages": page_count,

            "sample_text_chars": len(sample_clean),

            "schema": schema,

            "indicators": indicators,

        }

    except Exception as e:

        return {

            "file": str(path),

            "filename": path.name,

            "year": get_year(path),

            "report_type": get_report_type(path),

            "pages": None,

            "sample_text_chars": None,

            "schema": "ERROR",

            "error": str(e),

        }


def print_section(title):

    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():

    print("=" * 70)
    print("PAIMANA PDF INVENTORY")
    print("=" * 70)

    pdf_files = sorted(
        ROOT.rglob("*.pdf")
    )

    print(
        f"\nPDF files found: {len(pdf_files)}"
    )

    records = []

    for number, pdf in enumerate(
        pdf_files,
        start=1
    ):

        print(
            f"[{number:3d}/{len(pdf_files)}] {pdf}"
        )

        result = classify_pdf(pdf)

        records.append(result)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            records,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ------------------------------------------------------
    # Schema summary
    # ------------------------------------------------------

    schemas = Counter(
        r["schema"]
        for r in records
    )

    print_section("SCHEMA SUMMARY")

    for schema, count in schemas.most_common():

        print(
            f"{schema:30s} {count}"
        )

    # ------------------------------------------------------
    # Year summary
    # ------------------------------------------------------

    years = Counter(
        r["year"]
        for r in records
    )

    print_section("YEAR SUMMARY")

    # None-safe sorting
    valid_years = sorted(
        y for y in years
        if y is not None
    )

    for year in valid_years:

        print(
            f"{year:15s} {years[year]}"
        )

    if None in years:

        print(
            f"{'UNKNOWN':15s} {years[None]}"
        )

    # ------------------------------------------------------
    # Report type summary
    # ------------------------------------------------------

    report_types = Counter(
        r["report_type"]
        for r in records
    )

    print_section("REPORT TYPE SUMMARY")

    for report_type, count in report_types.items():

        print(
            f"{report_type:15s} {count}"
        )

    # ------------------------------------------------------
    # Schema by year
    # ------------------------------------------------------

    schema_by_year = defaultdict(Counter)

    for record in records:

        year = record["year"]

        if year is None:
            year = "UNKNOWN"

        schema_by_year[year][
            record["schema"]
        ] += 1

    print_section("SCHEMA BY YEAR")

    for year in sorted(schema_by_year):

        print(f"\n{year}")

        for schema, count in (
            schema_by_year[year]
            .most_common()
        ):

            print(
                f"  {schema:28s} {count}"
            )

    # ------------------------------------------------------
    # Errors
    # ------------------------------------------------------

    errors = [
        r
        for r in records
        if r["schema"] == "ERROR"
    ]

    print_section("PDF ERRORS")

    print(
        f"Error count: {len(errors)}"
    )

    for record in errors:

        print(
            f"\n{record['file']}"
        )

        print(
            f"  Error: {record.get('error')}"
        )

    # ------------------------------------------------------
    # Other files
    # ------------------------------------------------------

    other = [
        r
        for r in records
        if r["schema"] == "OTHER"
    ]

    print_section("OTHER SCHEMA FILES")

    print(
        f"Other count: {len(other)}"
    )

    for record in other:

        print(
            f"{record['file']}"
        )

    # ------------------------------------------------------
    # Project-code-progress files
    # ------------------------------------------------------

    project_code_progress = [
        r
        for r in records
        if r["schema"] == "PROJECT_CODE_PROGRESS"
    ]

    print_section(
        "PROJECT_CODE_PROGRESS FILES"
    )

    print(
        f"Count: {len(project_code_progress)}"
    )

    for record in project_code_progress:

        print(
            f"{record['file']}"
        )

    # ------------------------------------------------------
    # Current all-ongoing files
    # ------------------------------------------------------

    current = [
        r
        for r in records
        if r["schema"] == "CURRENT_ALL_ONGOING"
    ]

    print_section(
        "CURRENT_ALL_ONGOING FILES"
    )

    print(
        f"Count: {len(current)}"
    )

    for record in current:

        print(
            f"{record['file']}"
        )

    # ------------------------------------------------------
    # Final
    # ------------------------------------------------------

    print_section(
        "INVENTORY COMPLETE"
    )

    print(
        f"\nRecords written: {len(records)}"
    )

    print(
        f"Output: {OUTPUT}"
    )


if __name__ == "__main__":
    main()
