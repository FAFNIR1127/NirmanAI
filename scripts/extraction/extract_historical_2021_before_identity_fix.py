from pathlib import Path
import json
import re
import pymupdf


# ============================================================
# CONFIGURATION
# ============================================================

PDF = Path("raw/2021-22/monthly/FR_APr_2021.pdf")

OUTPUT = Path(
    "processed/extracted/historical_2021_april.json"
)

START_PAGE = 84
END_PAGE = 176

EXPECTED_PROJECTS = 1737


# ============================================================
# REGEX
# ============================================================

CODE_RE = re.compile(
    r"\[([A-Za-z0-9]+)\]"
)

DATE_RE = re.compile(
    r"^\d{2}/\d{4}$"
)

NUMBER_RE = re.compile(
    r"^-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)$"
)

DELAY_RE = re.compile(
    r"^(-?\d+)\(([OR])\)$"
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):

    if value is None:
        return None

    value = re.sub(
        r"\s+",
        " ",
        str(value)
    )

    return value.strip()


def number(value):

    if value is None:
        return None

    value = value.replace(",", "").strip()

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

        raise FileNotFoundError(
            f"PDF not found: {PDF}"
        )

    doc = pymupdf.open(PDF)

    pages = []

    for page_number in range(
        START_PAGE,
        END_PAGE + 1
    ):

        page = doc[page_number - 1]

        raw_words = page.get_text(
            "words"
        )

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

            match = CODE_RE.search(
                word["text"]
            )

            if not match:
                continue

            code = match.group(1)

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


# ============================================================
# GROUP ANCHORS BY PAGE
# ============================================================

def anchors_by_page(anchors):

    grouped = {}

    for anchor in anchors:

        grouped.setdefault(
            anchor["page"],
            []
        ).append(anchor)

    for page in grouped:

        grouped[page].sort(
            key=lambda x: x["code_y"]
        )

    return grouped


# ============================================================
# FIND NUMERIC ROW FOR A PROJECT
# ============================================================


def find_numeric_row(
    words,
    code_y,
    next_code_y=None
):

    """
    Find the primary numeric row associated with a project.

    In these PAIMANA PDFs the project code may appear several
    lines BELOW the project's numeric row. Therefore the numeric
    row must be identified from the approval-date column and
    spatial project structure rather than simply choosing the
    date closest to code_y.
    """

    candidates = []

    for word in words:

        x = word["x0"]
        y = word["y0"]
        text = word["text"].strip()

        # Approval-date column.
        if not (220 <= x <= 245):
            continue

        if not DATE_RE.match(text):
            continue

        # The project's numeric row must be above its code.
        if y >= code_y:
            continue

        # Do not go arbitrarily far upward.
        if code_y - y > 30:
            continue

        candidates.append(word)

    if not candidates:
        return None

    # The correct numeric row is the closest approval-date row
    # ABOVE the project code.
    candidates.sort(
        key=lambda w: w["y0"],
        reverse=True
    )

    return candidates[0]["y0"]


def row_words(
    words,
    row_y
):

    result = []

    for word in words:

        if abs(
            word["y0"] - row_y
        ) <= 1.2:

            result.append(word)

    result.sort(
        key=lambda w: w["x0"]
    )

    return result


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

    # Allow the current project to span multiple PDF lines,
    # but never cross into the next project's code region.
    lower_limit = row_y + 18

    if next_code_y is not None:
        lower_limit = min(lower_limit, next_code_y - 2)

    project_words = [
        w for w in words
        if row_y - 1.5 <= w["y0"] <= lower_limit
    ]

    project_words.sort(key=lambda w: (w["y0"], w["x0"]))

    # --------------------------------------------------------
    # Approval date
    # --------------------------------------------------------

    approval_date = None

    for w in project_words:
        if 220 <= w["x0"] < 265 and DATE_RE.match(w["text"]):
            approval_date = w["text"]
            break

    # --------------------------------------------------------
    # Original / Revised Cost
    # --------------------------------------------------------

    costs = []

    for w in project_words:

        # Cost values are located around x=275-303.
        # Only accept the current project's own vertical band.
        if not (265 <= w["x0"] < 315):
            continue

        value = w["text"].strip()

        if value == "-":
            continue

        n = number(value)

        if n is not None:
            costs.append((w["y0"], w["x0"], n))

    costs.sort(key=lambda item: (item[0], item[1]))

    original_cost = None
    revised_cost = None

    # First value on the current row = original cost.
    # A second value below it = revised cost.
    if costs:
        original_cost = costs[0][2]

    if len(costs) >= 2:
        # Revised cost must be on a subsequent PDF line,
        # not from another project.
        if costs[1][0] > costs[0][0]:
            revised_cost = costs[1][2]

    # --------------------------------------------------------
    # Anticipated Cost
    # --------------------------------------------------------

    anticipated_cost = None

    for w in project_words:

        if 315 <= w["x0"] < 350:

            n = number(w["text"])

            if n is not None:
                anticipated_cost = n
                break

    # --------------------------------------------------------
    # Cumulative Expenditure
    # --------------------------------------------------------

    cumulative_expenditure = None

    for w in project_words:

        if 350 <= w["x0"] < 405:

            n = number(w["text"])

            if n is not None:
                cumulative_expenditure = n
                break

    # --------------------------------------------------------
    # Original / Revised Date of Commissioning
    # --------------------------------------------------------

    docs = []

    for w in project_words:

        if 405 <= w["x0"] < 445 and DATE_RE.match(w["text"]):
            docs.append((w["y0"], w["x0"], w["text"]))

    docs.sort()

    original_doc = docs[0][2] if len(docs) >= 1 else None
    revised_doc = docs[1][2] if len(docs) >= 2 else None

    # --------------------------------------------------------
    # Anticipated Date of Commissioning
    # --------------------------------------------------------

    anticipated_doc = None

    for w in project_words:

        if 445 <= w["x0"] < 480 and DATE_RE.match(w["text"]):
            anticipated_doc = w["text"]
            break

    # --------------------------------------------------------
    # Delay
    # --------------------------------------------------------

    delays = []

    for w in project_words:

        if 495 <= w["x0"] < 525:

            m = DELAY_RE.match(w["text"])

            if m:
                delays.append(
                    (
                        w["y0"],
                        w["x0"],
                        int(m.group(1)),
                        m.group(2),
                    )
                )

    delays.sort()

    original_delay_months = None
    revised_delay_months = None

    for _, _, value, kind in delays:

        if kind == "O" and original_delay_months is None:
            original_delay_months = value

        elif kind == "R" and revised_delay_months is None:
            revised_delay_months = value

    # Plain revised-delay values such as 0 can appear
    # without the (R) suffix.
    if revised_delay_months is None:

        for w in project_words:

            if 505 <= w["x0"] < 525:

                n = number(w["text"])

                if n is not None:
                    revised_delay_months = int(n)
                    break

    # --------------------------------------------------------
    # Milestones
    # --------------------------------------------------------

    milestones_achieved = None
    milestones_total = None

    for w in project_words:

        if 545 <= w["x0"] < 580:

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


def parse_identity(
    words,
    anchor,
    previous_anchor=None,
    next_anchor=None
):

    code_index = anchor["code_index"]
    code_y = anchor["code_y"]

    code_word = words[code_index]

    # --------------------------------------------------------
    # Find project-name text.
    #
    # We search backward from the code within the project
    # column. Numeric metadata columns are excluded.
    # --------------------------------------------------------

    name_words = []

    previous_code_y = None

    # Use the previous code as a vertical boundary only when
    # the previous project is on the same PDF page.
    if (
        previous_anchor is not None
        and previous_anchor["page"] == anchor["page"]
    ):

        previous_code_y = (
            previous_anchor["code_y"]
        )

    for word in words:

        x = word["x0"]
        y = word["y0"]
        text = word["text"].strip()

        if not (
            45 <= x < 220
        ):
            continue

        if y >= code_y:
            continue

        if previous_code_y is not None:

            if y <= previous_code_y:
                continue

        else:

            # For the first project on a page, prevent table
            # headers from being treated as project-name text.
            if y < 145:
                continue

        # Exclude page/table headings.
        if text in {
            "Total",
            "Projects",
            "Project",
            "SI.No",
            "CIVIL",
            "AVIATION",
        }:

            continue

        # Exclude standalone numbers.
        if re.fullmatch(
            r"\d+",
            text
        ):

            continue

        name_words.append(word)

    # --------------------------------------------------------
    # Also include project-column words on the same code row
    # before the code itself.
    # --------------------------------------------------------

    code_line_words = []

    for word in words:

        if abs(
            word["y0"] - code_y
        ) > 1.5:

            continue

        if not (
            45 <= word["x0"] < 220
        ):

            continue

        if word["index"] >= code_index:

            continue

        text = word["text"].strip()

        if text in {
            "Total",
            "Projects",
        }:

            continue

        code_line_words.append(word)

    name_words.extend(
        code_line_words
    )

    # --------------------------------------------------------
    # Sort and build text.
    # --------------------------------------------------------

    name_words.sort(
        key=lambda w: (
            w["y0"],
            w["x0"]
        )
    )

    name_parts = []

    for word in name_words:

        value = word["text"].strip()

        if not value:
            continue

        name_parts.append(value)

    project_name = clean_text(
        " ".join(name_parts)
    )

    # --------------------------------------------------------
    # Remove obvious non-name prefixes.
    # --------------------------------------------------------

    project_name = re.sub(
        r"^\d+\s+",
        "",
        project_name
    )

    project_name = re.sub(
        r"\s+-\s*$",
        "",
        project_name
    )

    # --------------------------------------------------------
    # Agency and state.
    #
    # Code word examples:
    #
    # [N02000010]NPCIL,GUJARAT
    # [020100044]BHAVNI,TAMIL
    # --------------------------------------------------------

    agency = None
    state_parts = []

    code_text = code_word["text"]

    match = re.search(
        r"\[[A-Za-z0-9]+\]([^,]+),(.+)",
        code_text
    )

    if match:

        agency = clean_text(
            match.group(1)
        )

        state_parts.append(
            clean_text(
                match.group(2)
            )
        )

    # --------------------------------------------------------
    # State continuation on same row.
    # Example:
    #
    # [N04000073]AAI,A
    # &
    # N
    # ISLANDS
    # --------------------------------------------------------

    for word in words:

        if abs(
            word["y0"] - code_y
        ) > 1.5:

            continue

        if word["index"] <= code_index:

            continue

        x = word["x0"]

        if not (
            45 <= x < 220
        ):

            continue

        value = word["text"].strip()

        if value == ",":
            continue

        if value in {
            "Central",
            "Sector",
            "Projects",
            "Total",
        }:

            break

        state_parts.append(value)

    state = clean_text(
        " ".join(
            part
            for part in state_parts
            if part
        )
    )

    # --------------------------------------------------------
    # Remove contract / classification suffixes.
    # --------------------------------------------------------

    state = re.sub(
        r"\s+(PPP\s*\(BOT\)|EPC)$",
        "",
        state,
        flags=re.I
    )

    return {
        "serial": anchor["serial"],
        "project_code":
            anchor["project_code"],

        "project_name":
            project_name or None,

        "agency": agency,

        "state":
            state or None,

        "page": anchor["page"],
    }


# ============================================================
# EXTRACT ONE PROJECT
# ============================================================

def extract_project(
    page_data,
    anchor,
    previous_anchor,
    next_anchor
):

    words = page_data["words"]

    identity = parse_identity(
        words,
        anchor,
        previous_anchor,
        next_anchor
    )

    row_y = find_numeric_row(
        words,
        anchor["code_y"],
        (
            next_anchor["code_y"]
            if next_anchor is not None
            and next_anchor["page"]
                == anchor["page"]
            else None
        )
    )

    next_code_y = (
        next_anchor["code_y"]
        if next_anchor is not None
        and next_anchor["page"] == anchor["page"]
        else None
    )

    numeric = parse_numeric_fields(
        words,
        row_y,
        next_code_y
    )

    record = {
        **identity,
        **numeric,
    }

    return record


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print("2021-22 APRIL HISTORICAL EXTRACTION")
    print("=" * 100)

    pages = load_pages()

    anchors = find_code_anchors(
        pages
    )

    print(
        f"Expected code anchors : "
        f"{EXPECTED_PROJECTS}"
    )

    print(
        f"Detected code anchors : "
        f"{len(anchors)}"
    )

    unique_codes = len(
        set(
            a["project_code"]
            for a in anchors
        )
    )

    print(
        f"Unique codes          : "
        f"{unique_codes}"
    )

    if len(anchors) != EXPECTED_PROJECTS:

        raise RuntimeError(
            "Code-anchor count does not "
            "match expected project count."
        )

    if unique_codes != EXPECTED_PROJECTS:

        raise RuntimeError(
            "Project codes are not unique."
        )

    pages_lookup = {
        p["page"]: p
        for p in pages
    }

    page_groups = anchors_by_page(
        anchors
    )

    records = []

    # --------------------------------------------------------
    # Process each page independently.
    # --------------------------------------------------------

    for page_no, page_anchors in (
        page_groups.items()
    ):

        page_data = pages_lookup[
            page_no
        ]

        for i, anchor in enumerate(
            page_anchors
        ):

            previous_anchor = None

            if i > 0:

                previous_anchor = (
                    page_anchors[i - 1]
                )

            else:

                # Previous project may be on
                # previous PDF page.
                global_index = (
                    anchors.index(anchor)
                )

                if global_index > 0:

                    previous_anchor = (
                        anchors[
                            global_index - 1
                        ]
                    )

            next_anchor = None

            if i + 1 < len(
                page_anchors
            ):

                next_anchor = (
                    page_anchors[i + 1]
                )

            else:

                global_index = (
                    anchors.index(anchor)
                )

                if (
                    global_index + 1
                    < len(anchors)
                ):

                    next_anchor = (
                        anchors[
                            global_index + 1
                        ]
                    )

            record = extract_project(
                page_data,
                anchor,
                previous_anchor,
                next_anchor
            )

            records.append(record)

    # --------------------------------------------------------
    # Final ordering.
    # --------------------------------------------------------

    records.sort(
        key=lambda r: r["serial"]
    )

    # --------------------------------------------------------
    # Validation.
    # --------------------------------------------------------

    codes = [
        r["project_code"]
        for r in records
    ]

    serials = [
        r["serial"]
        for r in records
    ]

    duplicate_codes = (
        len(codes)
        - len(set(codes))
    )

    duplicate_serials = (
        len(serials)
        - len(set(serials))
    )

    missing_names = [
        r
        for r in records
        if not r["project_name"]
    ]

    missing_serials = [
        i
        for i in range(
            1,
            EXPECTED_PROJECTS + 1
        )
        if i not in set(serials)
    ]

    print()
    print("=" * 100)
    print(
        f"Extracted records     : "
        f"{len(records)}"
    )

    print(
        f"Unique codes          : "
        f"{len(set(codes))}"
    )

    print(
        f"Missing names         : "
        f"{len(missing_names)}"
    )

    print(
        f"Serial range          : "
        f"{min(serials)} - {max(serials)}"
    )

    print(
        f"Duplicate serials     : "
        f"{duplicate_serials}"
    )

    print(
        f"Missing serials       : "
        f"{len(missing_serials)}"
    )

    if missing_serials:

        print()
        print("MISSING SERIALS")
        print(missing_serials)

    if missing_names:

        print()
        print("MISSING NAMES")

        for record in missing_names[:50]:

            print(
                f"{record['serial']} | "
                f"{record['project_code']} | "
                f"page {record['page']}"
            )

    # --------------------------------------------------------
    # Critical validation records.
    # --------------------------------------------------------

    validation_codes = {
        "N02000010",
        "N02000027",
        "020100044",
        "N02000028",
        "N04000073",
        "N24000720",
        "N24001298",
        "N24000677",
        "N30000047",
        "N30000048",
        "N30000049",
        "N28000103",
        "N40000003",
    }

    print()
    print("KEY VALIDATION RECORDS")

    for record in records:

        if record["project_code"] in validation_codes:

            print(
                f"{record['serial']} | "
                f"{record['project_code']} | "
                f"{record['project_name']} | "
                f"{record['agency']} | "
                f"{record['state']} | "
                f"OrigCost={record['original_cost']} | "
                f"RevisedCost={record['revised_cost']} | "
                f"AntCost={record['anticipated_cost']} | "
                f"Exp={record['cumulative_expenditure']}"
            )

    # --------------------------------------------------------
    # First 5.
    # --------------------------------------------------------

    print()
    print("FIRST 5")

    for record in records[:5]:

        print(
            f"{record['serial']} | "
            f"{record['project_code']} | "
            f"{record['project_name']} | "
            f"{record['agency']} | "
            f"{record['state']}"
        )

    # --------------------------------------------------------
    # Last 5.
    # --------------------------------------------------------

    print()
    print("LAST 5")

    for record in records[-5:]:

        print(
            f"{record['serial']} | "
            f"{record['project_code']} | "
            f"{record['project_name']} | "
            f"{record['agency']} | "
            f"{record['state']}"
        )

    # --------------------------------------------------------
    # Save.
    # --------------------------------------------------------

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            records,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print(
        f"Saved: {OUTPUT}"
    )


if __name__ == "__main__":

    main()
