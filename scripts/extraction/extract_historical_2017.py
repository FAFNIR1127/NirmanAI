from pathlib import Path
import json
import re
import sys

import pymupdf


PDF = Path("raw/2017-18/monthly/FR_APril_2017.pdf")
OUTPUT = Path("processed/extracted/historical_2017_april.json")

START_PAGE = 57
END_PAGE = 119
EXPECTED_PROJECTS = 1247

CODE_RE = re.compile(r"\[([A-Za-z0-9]+)\]")
SERIAL_RE = re.compile(r"^\d{1,4}$")
DATE_RE = re.compile(r"^\d{2}/\d{4}$")
NUMBER_RE = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
DELAY_RE = re.compile(r"^(-?\d+)\(([OR])\)$")
MILESTONE_RE = re.compile(r"^\d+/\d+$")


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def is_date(text):
    return bool(DATE_RE.fullmatch(text))


def is_number(text):
    return bool(NUMBER_RE.fullmatch(text))


def to_number(text):
    if text == "-":
        return None
    return float(text.replace(",", ""))


def is_delay(text):
    return bool(DELAY_RE.fullmatch(text))

def parse_delay(text):
    if text == "-":
        return None

    match = DELAY_RE.fullmatch(text)

    if not match:
        return None

    return {
        "months": int(match.group(1)),
        "basis": (
            "original"
            if match.group(2) == "O"
            else "revised"
        ),
    }


def parse_milestone(text):
    if not MILESTONE_RE.fullmatch(text):
        return None

    achieved, total = text.split("/")

    return {
        "achieved": int(achieved),
        "total": int(total),
    }


def get_words(page):
    result = []

    for item in page.get_text("words"):
        x0, y0, x1, y1, text, block, line, word = item

        text = clean(text)

        if text:
            result.append({
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "text": text,
            })

    return result


def find_code_anchors(words):
    anchors = []

    for word in words:

        matches = CODE_RE.findall(word["text"])

        for code in matches:

            anchors.append({
                "code": code,
                "x": word["x0"],
                "y": word["y0"],
                "word": word,
            })

    return anchors


def collect_project_words(words, anchor, next_anchor):
    """
    Collect all words belonging to one project.

    A project starts at its [PROJECT_CODE] anchor and ends
    immediately before the next project-code anchor.

    This avoids relying on PDF text-line structure.
    """

    current_y = anchor["y"]

    if next_anchor:
        next_y = next_anchor["y"]

        # Different page.
        if next_anchor["page"] != anchor["page"]:
            next_y = 10_000
    else:
        next_y = 10_000

    selected = []

    for word in words:

        y = word["y0"]

        if y < current_y - 12:
            continue

        if y >= next_y - 2:
            continue

        selected.append(word)

    return selected


def parse_identity(project_words, code):
    """
    Parse project identity from historical Table-28.

    The serial number and project name may span several physical
    lines before the [PROJECT_CODE] line. The agency/state appear
    on the project-code line.
    """

    left_words = [
        w for w in project_words
        if w["x0"] < 220
    ]

    left_words.sort(key=lambda w: (w["y0"], w["x0"]))

    # ---------------------------------------------------------
    # Locate current project-code word.
    # ---------------------------------------------------------

    code_index = None

    for i, w in enumerate(left_words):
        if re.search(
            rf"\[{re.escape(code)}\]",
            w["text"]
        ):
            code_index = i
            break

    if code_index is None:
        return None, None, None, None

    code_word = left_words[code_index]
    code_y = code_word["y0"]

    # ---------------------------------------------------------
    # Find the serial number by searching upward from the code.
    #
    # Serial is a standalone integer at the far-left of the
    # project column.
    # ---------------------------------------------------------

    serial_no = None
    serial_index = None

    for i in range(code_index - 1, -1, -1):

        w = left_words[i]

        # Stop if we encounter another project-code anchor.
        if CODE_RE.search(w["text"]):
            break

        if (
            w["x0"] < 45
            and SERIAL_RE.fullmatch(w["text"])
        ):
            serial_no = int(w["text"])
            serial_index = i
            break

    # ---------------------------------------------------------
    # Project name:
    # Everything between the serial and the code.
    # ---------------------------------------------------------

    if serial_index is not None:
        name_words = left_words[
            serial_index + 1 : code_index
        ]
    else:
        name_words = left_words[
            max(0, code_index - 20) : code_index
        ]

    project_name = clean(
        " ".join(w["text"] for w in name_words)
    )

    project_name = project_name.rstrip(" -")

    # ---------------------------------------------------------
    # Agency and state.
    #
    # Code line may be:
    #
    # [N28000089]CPWD,TAMIL NADU ,
    #
    # so collect all words on the same physical line.
    # ---------------------------------------------------------

    code_line_words = [
        w for w in left_words
        if abs(w["y0"] - code_y) < 2.0
    ]

    code_line_words.sort(
        key=lambda w: w["x0"]
    )

    code_line_text = clean(
        " ".join(w["text"] for w in code_line_words)
    )

    code_match = re.search(
        rf"\[{re.escape(code)}\]",
        code_line_text
    )

    agency = None
    state = None

    if code_match:

        after_code = code_line_text[
            code_match.end():
        ].strip(" ,")

        if "," in after_code:

            agency, state = after_code.split(
                ",",
                1
            )

            agency = clean(agency)
            state = clean(state)

        elif after_code:

            agency = clean(after_code)

    if agency:
        agency = agency.strip(" ,")

    if state:
        state = state.strip(" ,")

    return serial_no, project_name, agency, state

def parse_columns(project_words):
    """
    Extract right-hand table values using physical x positions.
    """

    approval = []
    cost_original_revised = []
    anticipated_cost = []
    expenditure = []
    commissioning = []
    delays = []
    milestones = []

    for word in project_words:

        x = word["x0"]
        text = word["text"]

        # Ignore project identity.
        if x < 220:
            continue

        # Approval column.
        if 220 <= x < 265:

            if is_date(text):
                approval.append(word)

        # Original/Revised cost column.
        elif 265 <= x < 317:

            if is_number(text) or text == "-":
                cost_original_revised.append(word)

        # Anticipated cost.
        elif 317 <= x < 353:

            if is_number(text) or text == "-":
                anticipated_cost.append(word)

        # Cumulative expenditure.
        elif 353 <= x < 407:

            if is_number(text) or text == "-":
                expenditure.append(word)

        # Commissioning dates.
        elif 407 <= x < 488:

            if is_date(text) or text == "-":
                commissioning.append(word)

        # Delay.
        elif 488 <= x < 543:

            if is_delay(text) or text == "-":
                delays.append(word)

        # Milestones.
        elif x >= 543:

            if MILESTONE_RE.fullmatch(text):
                milestones.append(word)

    # Sort physically.
    for collection in (
        approval,
        cost_original_revised,
        anticipated_cost,
        expenditure,
        commissioning,
        delays,
        milestones,
    ):
        collection.sort(
            key=lambda w: (w["y0"], w["x0"])
        )

    return {
        "approval": approval,
        "cost_original_revised": cost_original_revised,
        "anticipated_cost": anticipated_cost,
        "expenditure": expenditure,
        "commissioning": commissioning,
        "delays": delays,
        "milestones": milestones,
    }


def parse_project(project_words, code):
    serial_no, project_name, agency, state = parse_identity(
        project_words,
        code,
    )

    columns = parse_columns(project_words)

    approval_words = columns["approval"]

    approval_date = (
        approval_words[0]["text"]
        if approval_words
        else None
    )

    # ---------------------------------------------------------
    # Original / Revised Cost
    #
    # These are vertically stacked in the same x-column.
    # ---------------------------------------------------------

    cost_values = columns["cost_original_revised"]

    original_cost = None
    revised_cost = None

    if len(cost_values) >= 1:
        original_cost = to_number(
            cost_values[0]["text"]
        )

    if len(cost_values) >= 2:
        revised_cost = to_number(
            cost_values[1]["text"]
        )

    # If only one value exists, it represents the original
    # cost and there is no revised value.
    if len(cost_values) == 1:
        revised_cost = None

    # ---------------------------------------------------------
    # Anticipated cost
    # ---------------------------------------------------------

    anticipated_values = columns["anticipated_cost"]

    anticipated_cost = (
        to_number(anticipated_values[0]["text"])
        if anticipated_values
        else None
    )

    # ---------------------------------------------------------
    # Expenditure
    # ---------------------------------------------------------

    expenditure_values = columns["expenditure"]

    cumulative_expenditure = (
        to_number(expenditure_values[0]["text"])
        if expenditure_values
        else None
    )

    # ---------------------------------------------------------
    # Commissioning dates
    # ---------------------------------------------------------

    date_values = [
        w["text"]
        for w in columns["commissioning"]
    ]

    original_commissioning = (
        date_values[0]
        if len(date_values) >= 1
        and date_values[0] != "-"
        else None
    )

    revised_commissioning = (
        date_values[1]
        if len(date_values) >= 2
        and date_values[1] != "-"
        else None
    )

    anticipated_commissioning = (
        date_values[2]
        if len(date_values) >= 3
        and date_values[2] != "-"
        else None
    )

    # ---------------------------------------------------------
    # Delays
    # ---------------------------------------------------------

    delay_values = columns["delays"]

    original_delay = None
    revised_delay = None

    if len(delay_values) >= 1:
        original_delay = parse_delay(
            delay_values[0]["text"]
        )

    if len(delay_values) >= 2:
        revised_delay = parse_delay(
            delay_values[1]["text"]
        )

    # ---------------------------------------------------------
    # Milestones
    # ---------------------------------------------------------

    milestone_values = columns["milestones"]

    milestones = None

    if milestone_values:
        milestones = parse_milestone(
            milestone_values[0]["text"]
        )

    return {
        "serial_no": serial_no,
        "project_code": code,
        "project_name": project_name,
        "implementing_agency": agency,
        "state": state,

        "approval_date": approval_date,

        "original_cost_crore": original_cost,
        "revised_cost_crore": revised_cost,
        "anticipated_cost_crore": anticipated_cost,
        "cumulative_expenditure_crore": cumulative_expenditure,

        "original_commissioning_date":
            original_commissioning,

        "revised_commissioning_date":
            revised_commissioning,

        "anticipated_commissioning_date":
            anticipated_commissioning,

        "original_delay_months":
            original_delay["months"]
            if original_delay
            else None,

        "revised_delay_months":
            revised_delay["months"]
            if revised_delay
            else None,

        "milestones_achieved":
            milestones["achieved"]
            if milestones
            else None,

        "milestones_total":
            milestones["total"]
            if milestones
            else None,
    }


def extract():

    if not PDF.exists():
        print(f"ERROR: {PDF} not found")
        sys.exit(1)

    doc = pymupdf.open(PDF)

    all_projects = []

    # ---------------------------------------------------------
    # Process each page independently.
    # ---------------------------------------------------------

    for page_number in range(
        START_PAGE,
        END_PAGE + 1,
    ):

        page = doc[page_number - 1]

        words = get_words(page)

        anchors = find_code_anchors(words)

        # Sort anchors vertically.
        anchors.sort(
            key=lambda a: (a["y"], a["x"])
        )

        for index, anchor in enumerate(anchors):

            next_anchor = (
                anchors[index + 1]
                if index + 1 < len(anchors)
                else None
            )

            # If next anchor exists on the same page, use it.
            # Otherwise the project extends to page bottom.
            project_words = []

            for word in words:

                if word["y0"] < anchor["y"] - 20:
                    continue

                if next_anchor:
                    if (
                        word["y0"]
                        >= next_anchor["y"] - 2
                    ):
                        continue

                project_words.append(word)

            project_words.sort(
                key=lambda w: (w["y0"], w["x0"])
            )

            record = parse_project(
                project_words,
                anchor["code"],
            )

            record["source_file"] = str(PDF)
            record["source_page"] = page_number

            all_projects.append(record)

    doc.close()

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    codes = [
        r["project_code"]
        for r in all_projects
    ]

    serials = [
        r["serial_no"]
        for r in all_projects
        if r["serial_no"] is not None
    ]

    duplicate_codes = {
        code
        for code in codes
        if codes.count(code) > 1
    }

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = {
        "source_file": str(PDF),
        "report_month": "2017-04",
        "table": "Table-28",
        "table_pages": {
            "start": START_PAGE,
            "end": END_PAGE,
        },

        "expected_project_count":
            EXPECTED_PROJECTS,

        "actual_project_count":
            len(all_projects),

        "unique_project_codes":
            len(set(codes)),

        "duplicate_project_codes":
            sorted(duplicate_codes),

        "min_serial":
            min(serials)
            if serials
            else None,

        "max_serial":
            max(serials)
            if serials
            else None,

        "records": all_projects,
    }

    with OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # ---------------------------------------------------------
    # Report
    # ---------------------------------------------------------

    print("=" * 100)
    print("HISTORICAL TABLE-28 EXTRACTION")
    print("=" * 100)

    print(f"Source:               {PDF}")
    print(
        f"Table pages:          "
        f"{START_PAGE}-{END_PAGE}"
    )

    print(
        f"Expected projects:    "
        f"{EXPECTED_PROJECTS}"
    )

    print(
        f"Extracted projects:   "
        f"{len(all_projects)}"
    )

    print(
        f"Unique project codes: "
        f"{len(set(codes))}"
    )

    print(
        f"Duplicate codes:      "
        f"{len(duplicate_codes)}"
    )

    print(
        f"Serial range:         "
        f"{min(serials) if serials else None}"
        f"-"
        f"{max(serials) if serials else None}"
    )

    print(f"Output:               {OUTPUT}")

    print()

    if (
        len(all_projects) == EXPECTED_PROJECTS
        and len(set(codes)) == EXPECTED_PROJECTS
        and not duplicate_codes
    ):
        print("STATUS: PASS")
    else:
        print("STATUS: REVIEW")


if __name__ == "__main__":
    extract()
