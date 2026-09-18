from pathlib import Path
import json
import re
import pymupdf


# ============================================================
# CONFIGURATION
# ============================================================

PDF = Path("raw/2023-24/monthly/FR_APril_2023.pdf")

OUTPUT = Path(
    "processed/extracted/historical_2023_april.json"
)

START_PAGE = 114
END_PAGE = 218

EXPECTED_PROJECTS = 1605


# ============================================================
# REGEX
# ============================================================

PROJ_CODE_RE = re.compile(
    r"\[([A-Za-z0-9]{8,10})\]"
)

DATE_RE = re.compile(
    r"^\(?\[?(\d{1,2}/\d{4})\]?\)?$"
)

NUMBER_RE = re.compile(
    r"^[(\[]?-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)[)\]]?$"
)

DELAY_RE = re.compile(
    r"^[(\[]?(-?\d+)(?:\[(\d+)\])?\s*\(([OR])\)[)\]]?$"
)


SECTOR_HEADERS = {
    "ATOMIC ENERGY", "CIVIL AVIATION", "COAL", "FERTILIZERS", "MINES",
    "PETROLEUM", "POWER", "RAILWAYS", "ROAD TRANSPORT & HIGHWAYS",
    "ROAD TRANSPORT AND HIGHWAYS", "STEEL", "TELECOMMUNICATIONS",
    "URBAN DEVELOPMENT", "WATER RESOURCES", "HEALTH & FAMILY WELFARE",
    "HEAVY INDUSTRY", "POSTS", "SHIPPING", "PORTS", "OTHER SECTOR"
}


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
    value = str(value).replace(",", "").replace("[", "").replace("]", "").replace("(", "").replace(")", "").strip()
    if not NUMBER_RE.match(value):
        return None
    try:
        return float(value)
    except ValueError:
        return None


# ============================================================
# LOAD PDF
# ============================================================

def load_pages():
    if not PDF.exists():
        raise FileNotFoundError(f"PDF not found: {PDF}")

    doc = pymupdf.open(PDF)
    pages = []

    for page_number in range(START_PAGE, END_PAGE + 1):
        page = doc[page_number - 1]
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

        pages.append({
            "page": page_number,
            "words": words,
        })

    doc.close()
    return pages


# ============================================================
# FIND PROJECT CODE ANCHORS
# ============================================================

def find_code_anchors(pages):
    anchors = []
    seen = set()

    for page_data in pages:
        page_no = page_data["page"]
        words = page_data["words"]

        for word in words:
            match = PROJ_CODE_RE.search(word["text"])
            if not match:
                continue

            code = match.group(1)
            if not re.match(r"^(N\d{8}|\d{9})$", code):
                continue

            if code in seen:
                continue

            seen.add(code)
            anchors.append({
                "serial": len(anchors) + 1,
                "project_code": code,
                "page": page_no,
                "code_y": word["y0"],
                "code_index": word["index"],
            })

    return anchors


def anchors_by_page(anchors):
    grouped = {}
    for anchor in anchors:
        grouped.setdefault(anchor["page"], []).append(anchor)

    for page in grouped:
        grouped[page].sort(key=lambda x: x["code_y"])

    return grouped


# ============================================================
# FIND NUMERIC ROW FOR A PROJECT
# ============================================================

def find_numeric_row(words, code_y, next_code_y=None):
    candidates = []

    for word in words:
        x = word["x0"]
        y = word["y0"]
        text = word["text"].strip()

        if not (200 <= x <= 245):
            continue

        m = DATE_RE.match(text)
        if not m:
            continue

        if y >= code_y + 5:
            continue

        if code_y - y > 35:
            continue

        candidates.append(word)

    if not candidates:
        return None

    candidates.sort(key=lambda w: w["y0"], reverse=True)
    return candidates[0]["y0"]


# ============================================================
# PARSE NUMERIC FIELDS
# ============================================================

def parse_numeric_fields(words, row_y, next_code_y=None):
    empty = {
        "approval_date": None,
        "original_cost": None,
        "revised_cost": None,
        "anticipated_cost": None,
        "cumulative_expenditure": None,
        "original_doc": None,
        "revised_doc": None,
        "anticipated_doc": None,
        "original_delay_months": None,
        "revised_delay_months": None,
        "milestones_achieved": None,
        "milestones_total": None,
    }

    if row_y is None:
        return empty

    lower_limit = row_y + 28
    if next_code_y is not None:
        lower_limit = min(lower_limit, next_code_y - 2)

    project_words = [
        w for w in words
        if row_y - 1.5 <= w["y0"] <= lower_limit
    ]
    project_words.sort(key=lambda w: (w["y0"], w["x0"]))

    # Approval date
    approval_date = None
    for w in project_words:
        if 200 <= w["x0"] < 250:
            m = DATE_RE.match(w["text"])
            if m:
                approval_date = m.group(1)
                break

    # Original / Revised / Anticipated Cost
    costs = []
    for w in project_words:
        if not (330 <= w["x0"] < 420):
            continue
        val = w["text"].strip()
        if val in {"-", "N/A"}:
            continue
        n = number(val)
        if n is not None:
            costs.append((w["y0"], w["x0"], n))

    costs.sort(key=lambda item: (item[0], item[1]))

    original_cost = costs[0][2] if len(costs) >= 1 else None
    revised_cost = costs[1][2] if len(costs) >= 2 else None
    anticipated_cost = costs[2][2] if len(costs) >= 3 else (revised_cost if revised_cost else original_cost)

    # Cumulative Expenditure
    cumulative_expenditure = None
    for w in project_words:
        if 420 <= w["x0"] < 510:
            n = number(w["text"])
            if n is not None:
                cumulative_expenditure = n
                break

    # Original / Revised / Anticipated DoC
    docs = []
    for w in project_words:
        if 250 <= w["x0"] < 330:
            m = DATE_RE.match(w["text"])
            if m:
                docs.append((w["y0"], w["x0"], m.group(1)))

    docs.sort()
    original_doc = docs[0][2] if len(docs) >= 1 else None
    revised_doc = docs[1][2] if len(docs) >= 2 else None
    anticipated_doc = docs[2][2] if len(docs) >= 3 else None

    # Delay
    original_delay_months = None
    revised_delay_months = None

    for w in project_words:
        if 450 <= w["x0"] < 520:
            val = w["text"].strip()
            val_clean = val.replace("[", "").replace("]", "").replace("(", "").replace(")", "").strip()
            if val_clean.isdigit():
                revised_delay_months = int(val_clean)
                break

    # Milestones
    milestones_achieved = None
    milestones_total = None

    for w in project_words:
        if 520 <= w["x0"] < 580:
            value = w["text"].strip()
            if "/" in value:
                parts = value.split("/")
                if len(parts) == 2:
                    try:
                        milestones_achieved = int(parts[0])
                        milestones_total = int(parts[1])
                        break
                    except ValueError:
                        pass

    return {
        "approval_date": approval_date,
        "original_cost": original_cost,
        "revised_cost": revised_cost,
        "anticipated_cost": anticipated_cost,
        "cumulative_expenditure": cumulative_expenditure,
        "original_doc": original_doc,
        "revised_doc": revised_doc,
        "anticipated_doc": anticipated_doc,
        "original_delay_months": original_delay_months,
        "revised_delay_months": revised_delay_months,
        "milestones_achieved": milestones_achieved,
        "milestones_total": milestones_total,
    }


# ============================================================
# PARSE IDENTITY
# ============================================================

def parse_identity(words, anchor, previous_anchor=None, pages_lookup=None):
    code_index = anchor["code_index"]
    code_y = anchor["code_y"]
    code_word = words[code_index]
    page_no = anchor["page"]

    if previous_anchor and previous_anchor["page"] == page_no:
        prev_y = previous_anchor["code_y"] + 3
    else:
        prev_y = 240 if page_no == START_PAGE else 0

    name_words = []
    for w in words:
        x = w["x0"]
        y = w["y0"]

        if x < 40 or x >= 210:
            continue
        if y < prev_y:
            continue
        if y > code_y + 1:
            continue
        if abs(y - code_y) <= 1.5 and x >= code_word["x0"]:
            continue

        text = w["text"].strip()
        if text in {"SI.No", "Project", "Total", "Projects", "Central", "Sector"}:
            continue

        name_words.append(w)

    # Check previous page tail if first project on page and no words collected
    if not name_words and previous_anchor and previous_anchor["page"] < page_no and pages_lookup:
        prev_page_words = pages_lookup[page_no - 1]["words"]
        last_code_y = previous_anchor["code_y"]
        for w in prev_page_words:
            if w["x0"] < 40 or w["x0"] >= 210:
                continue
            if w["y0"] <= last_code_y + 12:
                continue
            text = w["text"].strip()
            if text in {"SI.No", "Project", "Total", "Projects", "Central", "Sector"}:
                continue
            name_words.append(w)

    name_words.sort(key=lambda w: (w["y0"], w["x0"]))
    name_text = clean_text(" ".join(w["text"].strip() for w in name_words))

    name_text = re.sub(r"^\d+\s+", "", name_text)
    name_text = re.sub(r"\s+-\s*$", "", name_text)
    name_text = re.sub(r"^\d+\s*-\s*", "", name_text)

    for header in SECTOR_HEADERS:
        if name_text.startswith(header):
            name_text = name_text[len(header):].strip()

    agency = None
    state_parts = []

    code_text = code_word["text"]
    match = re.match(r"\[[A-Za-z0-9]+\],?\s*([^,]+)(?:,(.*))?", code_text)
    if match:
        agency = clean_text(match.group(1))
        if match.group(2):
            state_parts.append(clean_text(match.group(2)))

    for word in words:
        if abs(word["y0"] - code_y) > 14:
            continue
        if word["index"] <= code_index:
            continue
        x = word["x0"]
        if not (45 <= x < 210):
            continue
        val = word["text"].strip()
        if val in {",", "-", "Central", "Sector", "Projects", "Total"}:
            continue
        state_parts.append(val)

    state = clean_text(" ".join(p for p in state_parts if p))
    if not state:
        state = None

    return {
        "project_name": name_text if name_text else None,
        "agency": agency if agency else None,
        "state": state,
    }


# ============================================================
# EXTRACT ONE PROJECT
# ============================================================

def extract_project(page_data, anchor, previous_anchor, next_anchor, pages_lookup):
    words = page_data["words"]
    identity = parse_identity(words, anchor, previous_anchor, pages_lookup)

    row_y = find_numeric_row(
        words,
        anchor["code_y"],
        next_anchor["code_y"] if next_anchor and next_anchor["page"] == anchor["page"] else None
    )

    next_code_y = next_anchor["code_y"] if next_anchor and next_anchor["page"] == anchor["page"] else None
    numeric = parse_numeric_fields(words, row_y, next_code_y)

    record = {
        "serial": anchor["serial"],
        "project_code": anchor["project_code"],
        "page": anchor["page"],
        **identity,
        **numeric,
    }

    return record


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 100)
    print("2023-24 APRIL HISTORICAL EXTRACTION")
    print("=" * 100)

    pages = load_pages()
    anchors = find_code_anchors(pages)

    print(f"Expected code anchors : {EXPECTED_PROJECTS}")
    print(f"Detected code anchors : {len(anchors)}")

    unique_codes = len(set(a["project_code"] for a in anchors))
    print(f"Unique codes          : {unique_codes}")

    if len(anchors) != EXPECTED_PROJECTS:
        raise RuntimeError("Code-anchor count does not match expected project count.")

    if unique_codes != EXPECTED_PROJECTS:
        raise RuntimeError("Project codes are not unique.")

    pages_lookup = {p["page"]: p for p in pages}
    page_groups = anchors_by_page(anchors)

    records = []

    for page_no, page_anchors in page_groups.items():
        page_data = pages_lookup[page_no]

        for i, anchor in enumerate(page_anchors):
            previous_anchor = None
            if i > 0:
                previous_anchor = page_anchors[i - 1]
            else:
                global_index = anchors.index(anchor)
                if global_index > 0:
                    previous_anchor = anchors[global_index - 1]

            next_anchor = None
            if i + 1 < len(page_anchors):
                next_anchor = page_anchors[i + 1]
            else:
                global_index = anchors.index(anchor)
                if global_index + 1 < len(anchors):
                    next_anchor = anchors[global_index + 1]

            record = extract_project(
                page_data,
                anchor,
                previous_anchor,
                next_anchor,
                pages_lookup
            )
            records.append(record)

    records.sort(key=lambda r: r["serial"])

    codes = [r["project_code"] for r in records]
    serials = [r["serial"] for r in records]
    missing_names = [r for r in records if r["project_name"] is None]

    print("\n" + "=" * 100)
    print(f"Extracted records     : {len(records)}")
    print(f"Unique codes          : {len(set(codes))}")
    print(f"Missing names         : {len(missing_names)}")
    print(f"Serial range          : {min(serials)} - {max(serials)}")
    print(f"Duplicate serials     : {len(serials) - len(set(serials))}")
    print(f"Missing serials       : {len(set(range(1, len(records) + 1)) - set(serials))}")

    if missing_names:
        print("\nMISSING NAMES")
        for r in missing_names[:50]:
            print(f"{r['serial']} | {r['project_code']} | page {r['page']}")

    print("\nKEY VALIDATION RECORDS")
    key_serials = [1, 2, 3, 4, 5, 762, 790, 803, len(records) - 4, len(records) - 3, len(records) - 2, len(records) - 1, len(records)]

    for r in records:
        if r["serial"] in key_serials:
            print(
                f"{r['serial']} | {r['project_code']} | {r['project_name']} | "
                f"{r['agency']} | {r['state']} | OrigCost={r['original_cost']} | "
                f"RevisedCost={r['revised_cost']} | AntCost={r['anticipated_cost']} | "
                f"Exp={r['cumulative_expenditure']}"
            )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"\nSaved: {OUTPUT}")


if __name__ == "__main__":
    main()
