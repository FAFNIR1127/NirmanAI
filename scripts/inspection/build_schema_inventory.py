from pathlib import Path
import json
import re
import pymupdf

ROOT = Path("raw")
OUTPUT = Path("processed/extracted/schema_inventory.json")


def normalize(text):
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def has_any(text, patterns):
    return any(pattern in text for pattern in patterns)


def classify_page(text):
    t = normalize(text)

    modern_signals = 0
    historical_signals = 0

    # ---------------------------------------------------------
    # MODERN FORMAT SIGNALS
    # ---------------------------------------------------------

    if "all ongoing projects" in t:
        modern_signals += 3

    if "physical progress" in t:
        modern_signals += 2

    if "project code" in t:
        modern_signals += 2

    if "original cost" in t and "revised cost" in t:
        modern_signals += 2

    if "cumulative expenditure" in t:
        modern_signals += 1

    if "state" in t and "approval date" in t:
        modern_signals += 1

    # ---------------------------------------------------------
    # HISTORICAL FORMAT SIGNALS
    # ---------------------------------------------------------

    historical_patterns = [
        "detail of ongoing projects",
        "details of ongoing projects",
        "sector wise details",
        "date of commissioning",
        "anticipated cost",
        "original / revised cost",
        "original/revised cost",
        "anticipated cost",
        "delay w.r.t.",
        "milestones achieved",
        "costing rs. 150 crore and above",
        "original / revised",
        "cumulative expenditure",
    ]

    for pattern in historical_patterns:
        if pattern in t:
            historical_signals += 1

    # Strong historical indicators
    if "date of commissioning" in t:
        historical_signals += 3

    if "anticipated cost" in t:
        historical_signals += 2

    if "milestones achieved" in t:
        historical_signals += 2

    if "delay w.r.t." in t:
        historical_signals += 2

    # ---------------------------------------------------------
    # CLASSIFICATION
    # ---------------------------------------------------------

    if modern_signals >= 5 and modern_signals > historical_signals:
        return "MODERN_ALL_ONGOING", modern_signals, historical_signals

    if historical_signals >= 4:
        return "HISTORICAL_DETAILED", modern_signals, historical_signals

    if historical_signals >= 2:
        return "HISTORICAL_ANALYTICAL", modern_signals, historical_signals

    if modern_signals >= 2:
        return "MODERN_CANDIDATE", modern_signals, historical_signals

    return "UNKNOWN", modern_signals, historical_signals


def inspect_pdf(path):
    result = {
        "file": str(path),
        "year": path.parts[-3],
        "report_type": path.parts[-2],
        "classification": "UNKNOWN",
        "page_count": None,
        "matched_pages": [],
        "max_modern_score": 0,
        "max_historical_score": 0,
    }

    try:
        doc = pymupdf.open(path)
        result["page_count"] = len(doc)

        page_classifications = []

        for page_number, page in enumerate(doc, start=1):

            try:
                text = page.get_text()
            except Exception:
                continue

            if not text.strip():
                continue

            classification, modern_score, historical_score = classify_page(text)

            result["max_modern_score"] = max(
                result["max_modern_score"],
                modern_score
            )

            result["max_historical_score"] = max(
                result["max_historical_score"],
                historical_score
            )

            if classification != "UNKNOWN":
                page_classifications.append(classification)

                result["matched_pages"].append({
                    "page": page_number,
                    "classification": classification,
                    "modern_score": modern_score,
                    "historical_score": historical_score,
                    "preview": re.sub(
                        r"\s+",
                        " ",
                        text
                    ).strip()[:400],
                })

        doc.close()

        # -----------------------------------------------------
        # FILE-LEVEL CLASSIFICATION
        # -----------------------------------------------------

        if "MODERN_ALL_ONGOING" in page_classifications:
            result["classification"] = "MODERN_ALL_ONGOING"

        elif "HISTORICAL_DETAILED" in page_classifications:
            result["classification"] = "HISTORICAL_DETAILED"

        elif "MODERN_CANDIDATE" in page_classifications:
            result["classification"] = "MODERN_CANDIDATE"

        elif "HISTORICAL_ANALYTICAL" in page_classifications:
            result["classification"] = "HISTORICAL_ANALYTICAL"

        else:
            result["classification"] = "UNKNOWN"

    except Exception as e:
        result["classification"] = "ERROR"
        result["error"] = str(e)

    return result


def main():

    pdfs = sorted(ROOT.rglob("*.pdf"))

    print(f"PDF files found: {len(pdfs)}")

    results = []

    for i, pdf in enumerate(pdfs, start=1):

        print(
            f"[{i}/{len(pdfs)}] "
            f"{pdf}"
        )

        results.append(
            inspect_pdf(pdf)
        )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("=" * 80)
    print("SCHEMA SUMMARY")
    print("=" * 80)

    from collections import Counter

    counts = Counter(
        x["classification"]
        for x in results
    )

    for key, value in counts.most_common():
        print(
            f"{key:30} {value}"
        )

    print()
    print("=" * 80)
    print("BY YEAR")
    print("=" * 80)

    years = sorted(
        set(x["year"] for x in results)
    )

    for year in years:

        subset = [
            x for x in results
            if x["year"] == year
        ]

        counts = Counter(
            x["classification"]
            for x in subset
        )

        print(
            f"{year}: {dict(counts)}"
        )

    print()
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
