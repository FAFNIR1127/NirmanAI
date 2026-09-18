from pathlib import Path
import pymupdf
import re
import json


PDF = Path("raw/2021-22/monthly/FR_APr_2021.pdf")
OUTPUT = Path("processed/extracted/historical_2021_april.json")

START_PAGE = 84
END_PAGE = 176
EXPECTED_PROJECTS = 1737

CODE_RE = re.compile(r"\[([A-Za-z0-9]+)\]")
SERIAL_RE = re.compile(r"^\d{1,4}$")
DATE_RE = re.compile(r"^\d{2}/\d{4}$")
NUMBER_RE = re.compile(r"^-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)$")
DELAY_RE = re.compile(r"^(-?\d+)\(([OR])\)$")

METADATA_WORDS = {
    "Central",
    "Sector",
    "Projects",
    "PPP",
    "(BOT)",
    "BOT",
    "EPC",
    "ITEM",
    "RATE",
}


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def parse_number(text):
    text = text.strip()

    if text in {"-", "", "—"}:
        return None

    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def load_pages(doc):

    pages = []

    for page_no in range(START_PAGE, END_PAGE + 1):

        page = doc[page_no - 1]
        words = []

        for w in page.get_text("words"):

            x0, y0, x1, y1, text, block_no, line_no, word_no = w

            words.append({
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "text": text.strip(),
                "block": block_no,
                "line": line_no,
                "word": word_no,
            })

        words.sort(key=lambda w: (w["y0"], w["x0"]))

        pages.append({
            "page": page_no,
            "words": words
        })

    return pages


def find_code_anchors(pages):

    """
    Build project anchors from the ordered project-code anchors.

    Project code is the canonical identity.

    The serial number is reconstructed from document order because
    the PDF serial-number coordinates are inconsistent across
    wrapped rows and page layouts.

    serial_y is retained for compatibility with the downstream
    parser. It is initialized from the code Y-coordinate.
    """

    anchors = []
    seen = set()

    for page_data in pages:

        page_no = page_data["page"]
        words = page_data["words"]

        for i, word in enumerate(words):

            match = CODE_RE.search(word["text"])

            if not match:
                continue

            code = match.group(1)

            if code in seen:
                continue

            seen.add(code)

            anchors.append({
                "page": page_no,
                "code": code,
                "serial": len(anchors) + 1,
                "code_index": i,
                "code_y": word["y0"],

                # Compatibility field required by downstream
                # record-boundary logic.
                "serial_y": word["y0"],
            })

    print()
    print("ANCHOR/SEQUENCE DIAGNOSTICS")
    print(f"Detected code anchors : {len(anchors)}")
    print(f"Unique project codes  : {len(set(a['code'] for a in anchors))}")

    return anchors

def get_record_words(page_words, start_y, end_y=None):

    result = []

    for word in page_words:

        if word["y0"] < start_y - 1:
            continue

        if end_y is not None and word["y0"] >= end_y - 1:
            continue

        result.append(word)

    return result

def parse_identity(
    page_words,
    anchor,
    previous_anchor=None,
    next_anchor=None
):

    serial = anchor["serial"]
    code = anchor["code"]

    code_index = anchor["code_index"]
    code_y = anchor["code_y"]

    # --------------------------------------------------------
    # Find the code word.
    # --------------------------------------------------------

    code_word = page_words[code_index]

    # --------------------------------------------------------
    # Project-name words are located in the project column
    # (approximately x=45 to x<220).
    #
    # They can occur on multiple lines ABOVE the code.
    # Therefore we scan backwards from the code.
    # --------------------------------------------------------

    name_words = []

    # Previous code gives us a hard upper boundary.
    previous_code_y = None

    if previous_anchor is not None:
        previous_code_y = previous_anchor["code_y"]

    for word in page_words:

        x = word["x0"]
        y = word["y0"]
        value = word["text"].strip()

        # Only project column.
        if not (45 <= x < 220):
            continue

        # Only words before current code.
        if y > code_y + 0.5:
            continue

        # Do not cross the previous project.
        if previous_code_y is not None and y <= previous_code_y:
            continue

        # Ignore obvious metadata.
        if value in {
            "Total",
            "Projects",
            "Central",
            "Sector",
            "COMMERCE",
            "CONSTRUCTION",
        }:
            continue

        # Ignore standalone serial numbers.
        if SERIAL_RE.fullmatch(value):
            continue

        name_words.append(word)

    # --------------------------------------------------------
    # Sort naturally by PDF position.
    # --------------------------------------------------------

    name_words.sort(key=lambda w: (w["y0"], w["x0"]))

    # --------------------------------------------------------
    # Build text.
    # --------------------------------------------------------

    raw_name = " ".join(w["text"].strip() for w in name_words)

    # Remove the code and everything following it.
    code_pos = raw_name.find(f"[{code}]")

    if code_pos >= 0:
        raw_name = raw_name[:code_pos]

    # Remove trailing separator.
    raw_name = re.sub(r"\s*-\s*$", "", raw_name)

    # Remove repeated whitespace.
    raw_name = re.sub(r"\s+", " ", raw_name).strip()

    # --------------------------------------------------------
    # Agency + state are on the same line as the code.
    # --------------------------------------------------------

    agency = None
    state = None

    code_text = code_word["text"]

    # Example:
    # [N02000010]NPCIL,GUJARAT
    # [020100044]BHAVNI,TAMIL
    m = re.search(
        r"\[[A-Za-z0-9]+\]([^,]+),(.+)",
        code_text
    )

    if m:

        agency = m.group(1).strip()
        state = m.group(2).strip()

    # --------------------------------------------------------
    # State can continue onto following words.
    # Example:
    # [N04000073]AAI,A
    # &
    # N
    # ISLANDS
    # --------------------------------------------------------

    if agency is not None:

        continuation = []

        for word in page_words:

            y = word["y0"]
            x = word["x0"]
            value = word["text"].strip()

            if y < code_y - 0.5:
                continue

            if y > code_y + 20:
                continue

            if x < 45 or x >= 220:
                continue

            if word is code_word:
                continue

            if value == ",":
                continue

            if SERIAL_RE.fullmatch(value):
                continue

            # Metadata starts at x >= 220.
            continuation.append((x, value))

        continuation.sort()

        state_parts = [state]

        for _, value in continuation:

            if value in {
                "Central",
                "Sector",
                "Projects",
                "Total",
            }:
                break

            state_parts.append(value)

        state = " ".join(
            part for part in state_parts
            if part
        )

        state = re.sub(r"\s+", " ", state).strip()

    return {
        "serial": serial,
        "project_code": code,
        "project_name": raw_name if raw_name else None,
        "agency": agency,
        "state": state,
        "page": anchor["page"],
    }

def parse_numeric_fields(page_words, anchor, next_anchor=None):

    serial_y = anchor["serial_y"]

    if next_anchor is not None:
        end_y = next_anchor["serial_y"] - 1
    else:
        end_y = None

    words = get_record_words(
        page_words,
        serial_y,
        end_y
    )

    # --------------------------------------------------------
    # APPROVAL DATE
    # --------------------------------------------------------

    approval_candidates = [
        w for w in words
        if 220 <= w["x0"] < 265
        and DATE_RE.match(w["text"])
    ]

    approval_candidates.sort(
        key=lambda w: (w["y0"], w["x0"])
    )

    date_approval = (
        approval_candidates[0]["text"]
        if approval_candidates
        else None
    )

    # --------------------------------------------------------
    # ORIGINAL / REVISED COST
    # --------------------------------------------------------

    cost_candidates = [
        w for w in words
        if 265 <= w["x0"] < 315
        and (
            NUMBER_RE.match(w["text"])
            or w["text"] in {"-", "—"}
        )
    ]

    cost_candidates.sort(
        key=lambda w: (w["y0"], w["x0"])
    )

    cost_values = [
        parse_number(w["text"])
        for w in cost_candidates
    ]

    original_cost = (
        cost_values[0]
        if len(cost_values) >= 1
        else None
    )

    revised_cost = (
        cost_values[1]
        if len(cost_values) >= 2
        else None
    )

    # --------------------------------------------------------
    # ANTICIPATED COST
    # --------------------------------------------------------

    anticipated_candidates = [
        w for w in words
        if 315 <= w["x0"] < 350
        and (
            NUMBER_RE.match(w["text"])
            or w["text"] in {"-", "—"}
        )
    ]

    anticipated_candidates.sort(
        key=lambda w: (w["y0"], w["x0"])
    )

    anticipated_cost = None

    for w in anticipated_candidates:

        value = parse_number(w["text"])

        if value is not None:

            anticipated_cost = value
            break

    # --------------------------------------------------------
    # CUMULATIVE EXPENDITURE
    # --------------------------------------------------------

    expenditure_candidates = [
        w for w in words
        if 350 <= w["x0"] < 405
        and (
            NUMBER_RE.match(w["text"])
            or w["text"] in {"-", "—"}
        )
    ]

    expenditure_candidates.sort(
        key=lambda w: (w["y0"], w["x0"])
    )

    expenditure = None

    for w in expenditure_candidates:

        value = parse_number(w["text"])

        if value is not None:

            expenditure = value
            break

    # --------------------------------------------------------
    # DATE OF COMMISSIONING
    # --------------------------------------------------------

    doc_candidates = [
        w for w in words
        if 405 <= w["x0"] < 490
        and DATE_RE.match(w["text"])
    ]

    doc_candidates.sort(
        key=lambda w: (w["y0"], w["x0"])
    )

    commissioning_dates = [
        w["text"]
        for w in doc_candidates
    ]

    original_doc = (
        commissioning_dates[0]
        if len(commissioning_dates) >= 1
        else None
    )

    revised_doc = (
        commissioning_dates[1]
        if len(commissioning_dates) >= 2
        else None
    )

    anticipated_doc = (
        commissioning_dates[2]
        if len(commissioning_dates) >= 3
        else None
    )

    # --------------------------------------------------------
    # DELAY
    # --------------------------------------------------------

    delay_candidates = [
        w for w in words
        if 490 <= w["x0"] < 540
        and (
            DELAY_RE.match(w["text"])
            or NUMBER_RE.match(w["text"])
            or w["text"] in {"-", "—"}
        )
    ]

    delay_candidates.sort(
        key=lambda w: (w["y0"], w["x0"])
    )

    delays = []

    for w in delay_candidates:

        text = w["text"].strip()

        match = DELAY_RE.match(text)

        if match:

            delays.append({
                "months": int(match.group(1)),
                "schedule": match.group(2),
            })

        elif NUMBER_RE.match(text):

            delays.append({
                "months": parse_number(text),
                "schedule": None,
            })

    original_delay = (
        delays[0]
        if len(delays) >= 1
        else None
    )

    revised_delay = (
        delays[1]
        if len(delays) >= 2
        else None
    )

    # --------------------------------------------------------
    # MILESTONES
    # --------------------------------------------------------

    milestone_candidates = [
        w for w in words
        if 540 <= w["x0"] < 590
        and re.match(
            r"^\d+/\d+$",
            w["text"]
        )
    ]

    milestone_candidates.sort(
        key=lambda w: (w["y0"], w["x0"])
    )

    milestones = (
        milestone_candidates[0]["text"]
        if milestone_candidates
        else None
    )

    return {
        "date_of_approval": date_approval,
        "original_cost": original_cost,
        "revised_cost": revised_cost,
        "anticipated_cost": anticipated_cost,
        "cumulative_expenditure": expenditure,
        "original_doc": original_doc,
        "revised_doc": revised_doc,
        "anticipated_doc": anticipated_doc,
        "original_delay": original_delay,
        "revised_delay": revised_delay,
        "milestones": milestones,
    }


def main():

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    doc = pymupdf.open(PDF)

    pages = load_pages(doc)

    anchors = find_code_anchors(pages)

    print("=" * 80)
    print("2021-22 APRIL HISTORICAL EXTRACTION")
    print("=" * 80)

    print(
        f"Expected code anchors : "
        f"{EXPECTED_PROJECTS}"
    )

    print(
        f"Detected code anchors : "
        f"{len(anchors)}"
    )

    codes = [
        a["code"]
        for a in anchors
    ]

    print(
        f"Unique codes          : "
        f"{len(set(codes))}"
    )

    duplicate_codes = sorted(
        code for code in set(codes)
        if codes.count(code) > 1
    )

    print(
        f"Duplicate codes       : "
        f"{len(duplicate_codes)}"
    )

    page_anchor_map = {}

    for anchor in anchors:

        page_anchor_map.setdefault(
            anchor["page"],
            []
        ).append(anchor)

    records = []

    for page_data in pages:

        page_no = page_data["page"]
        page_words = page_data["words"]

        page_anchors = page_anchor_map.get(
            page_no,
            []
        )

        page_anchors.sort(
            key=lambda a: a["serial_y"]
        )

        for idx, anchor in enumerate(
            page_anchors
        ):

            next_anchor = (
                page_anchors[idx + 1]
                if idx + 1 < len(page_anchors)
                else None
            )

            identity = parse_identity(
                page_words,
                anchor,
                next_anchor
            )

            numeric = parse_numeric_fields(
                page_words,
                anchor,
                next_anchor
            )

            record = {
                **identity,
                **numeric,
                "report_year": "2021-22",
                "report_month": "April",
                "source_page": page_no,
            }

            records.append(record)

    doc.close()

    serials = [
        r["serial"]
        for r in records
    ]

    codes = [
        r["project_code"]
        for r in records
    ]

    missing_names = [
        r for r in records
        if not r["project_name"]
    ]

    duplicate_serials = sorted(
        s for s in set(serials)
        if serials.count(s) > 1
    )

    missing_serials = sorted(
        set(range(
            1,
            EXPECTED_PROJECTS + 1
        )) - set(serials)
    )

    print()
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

    if serials:

        print(
            f"Serial range          : "
            f"{min(serials)} - {max(serials)}"
        )

    else:

        print("Serial range          : NONE")

    print(
        f"Duplicate serials     : "
        f"{len(duplicate_serials)}"
    )

    print(
        f"Missing serials       : "
        f"{len(missing_serials)}"
    )

    if missing_serials:

        print()
        print("MISSING SERIALS")

        print(
            missing_serials[:100]
        )

    if missing_names:

        print()
        print("MISSING NAMES")

        for r in missing_names[:50]:

            print(
                f"{r['serial']} | "
                f"{r['project_code']} | "
                f"page {r['source_page']}"
            )

    lookup_codes = {
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
        "N40000003",
    }

    print()
    print("KEY VALIDATION RECORDS")

    for r in records:

        if r["project_code"] in lookup_codes:

            print(
                f"{r['serial']} | "
                f"{r['project_code']} | "
                f"{r['project_name']} | "
                f"{r['agency']} | "
                f"{r['state']} | "
                f"OrigCost={r['original_cost']} | "
                f"RevisedCost={r['revised_cost']} | "
                f"AntCost={r['anticipated_cost']} | "
                f"Exp={r['cumulative_expenditure']}"
            )

    print()
    print("FIRST 5")

    for r in records[:5]:

        print(
            f"{r['serial']} | "
            f"{r['project_code']} | "
            f"{r['project_name']} | "
            f"{r['agency']} | "
            f"{r['state']}"
        )

    print()
    print("LAST 5")

    for r in records[-5:]:

        print(
            f"{r['serial']} | "
            f"{r['project_code']} | "
            f"{r['project_name']} | "
            f"{r['agency']} | "
            f"{r['state']}"
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

    print()
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
