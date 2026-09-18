from pathlib import Path
import json
import re
import pymupdf


# ============================================================
# CONFIGURATION
# ============================================================

PDF = Path("raw/2026-27/monthly/FlashReport_April2026.pdf")

OUTPUT = Path(
    "processed/extracted/historical_2026_april.json"
)

START_PAGE = 1
END_PAGE = 163


# ============================================================
# REGEX
# ============================================================

PROJ_CODE_RE = re.compile(
    r"(N\d{8}|\d{9})"
)

DATE_RE = re.compile(
    r"^\(?\{?\[?(\d{1,2}[/-]\d{4})\]?\}?\)?$"
)

NUMBER_RE = re.compile(
    r"^[({[\]}]?-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)[)}\]]?$"
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value))
    return value.strip()


def number(value):
    if value is None:
        return None
    v = str(value).replace(",", "").replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace("{", "").replace("}", "").strip()
    if not NUMBER_RE.match(v) or v in {"N.A.", "NA", "-"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ============================================================
# PARSE 2026 PDF
# ============================================================

def extract_2026_projects():
    if not PDF.exists():
        raise FileNotFoundError(f"PDF not found: {PDF}")

    doc = pymupdf.open(PDF)
    records = []
    seen_codes = set()

    for page_no in range(START_PAGE, END_PAGE + 1):
        page = doc[page_no - 1]
        raw_words = page.get_text("words")
        words = []

        for index, item in enumerate(raw_words):
            x0, y0, x1, y1, text, *_ = item
            words.append({
                "index": index,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "text": text.strip(),
            })

        words.sort(key=lambda w: (w["y0"], w["x0"]))

        code_words = []
        for w in words:
            m = PROJ_CODE_RE.search(w["text"])
            if m:
                code_words.append((w, m.group(1)))

        for i, (cw, code) in enumerate(code_words):
            if code in seen_codes:
                continue
            seen_codes.add(code)

            c_y = cw["y0"]
            next_y = code_words[i+1][0]["y0"] if i + 1 < len(code_words) else 800.0

            p_words = [w for w in words if c_y - 45 <= w["y0"] <= min(next_y - 2, c_y + 45)]
            p_words.sort(key=lambda w: (w["y0"], w["x0"]))

            name_parts = []
            agency = None
            for w in p_words:
                if w["x0"] < 210:
                    t = w["text"]
                    if t.startswith("(") and t.endswith(")") and len(t) > 3 and not PROJ_CODE_RE.search(t):
                        if not t.strip("()").isdigit():
                            agency = t.strip("()")
                    elif not PROJ_CODE_RE.search(t) and t not in {"State", "Sector", "Sl", "No", "Project", "Name"}:
                        if not t.isdigit():
                            name_parts.append(t)

            name_text = clean_text(" ".join(name_parts))

            approval_date = None
            docs = []
            for w in p_words:
                if 200 <= w["x0"] < 340:
                    m = DATE_RE.match(w["text"])
                    if m:
                        d = m.group(1).replace("-", "/")
                        if approval_date is None:
                            approval_date = d
                        else:
                            docs.append(d)

            original_doc = docs[0] if len(docs) >= 1 else None
            revised_doc = docs[1] if len(docs) >= 2 else None
            anticipated_doc = docs[2] if len(docs) >= 3 else (revised_doc if revised_doc else original_doc)

            costs = []
            for w in p_words:
                if 340 <= w["x0"] < 470:
                    n = number(w["text"])
                    if n is not None:
                        costs.append(n)

            original_cost = costs[0] if len(costs) >= 1 else None
            revised_cost = costs[1] if len(costs) >= 2 else None
            anticipated_cost = costs[2] if len(costs) >= 3 else (revised_cost if revised_cost else original_cost)

            cumulative_expenditure = None
            for w in p_words:
                if 470 <= w["x0"] < 540:
                    n = number(w["text"])
                    if n is not None:
                        cumulative_expenditure = n
                        break

            physical_progress = None
            for w in p_words:
                if w["x0"] >= 540:
                    n = number(w["text"])
                    if n is not None and 0 <= n <= 100:
                        physical_progress = n
                        break

            record = {
                "serial": len(records) + 1,
                "project_code": code,
                "project_name": name_text,
                "agency": agency,
                "state": None,
                "page": page_no,
                "approval_date": approval_date,
                "original_cost": original_cost,
                "revised_cost": revised_cost,
                "anticipated_cost": anticipated_cost,
                "cumulative_expenditure": cumulative_expenditure,
                "physical_progress": physical_progress,
                "original_doc": original_doc,
                "revised_doc": revised_doc,
                "anticipated_doc": anticipated_doc,
                "original_delay_months": None,
                "revised_delay_months": None,
                "milestones_achieved": None,
                "milestones_total": None,
            }
            records.append(record)

    doc.close()
    return records


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 100)
    print("2026-27 APRIL HISTORICAL EXTRACTION")
    print("=" * 100)

    records = extract_2026_projects()
    codes = [r["project_code"] for r in records]
    missing_names = [r for r in records if r["project_name"] is None]

    print(f"\nExtracted records     : {len(records)}")
    print(f"Unique codes          : {len(set(codes))}")
    print(f"Missing names         : {len(missing_names)}")

    print("\nKEY VALIDATION RECORDS")
    for r in records[:10]:
        print(
            f"{r['serial']} | {r['project_code']} | {r['project_name']} | "
            f"{r['agency']} | OrigCost={r['original_cost']} | "
            f"RevisedCost={r['revised_cost']} | AntCost={r['anticipated_cost']} | "
            f"Exp={r['cumulative_expenditure']} | Progress={r['physical_progress']}%"
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"\nSaved: {OUTPUT}")


if __name__ == "__main__":
    main()
