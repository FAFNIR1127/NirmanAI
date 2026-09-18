from pathlib import Path
import pymupdf
import re
import json


# ============================================================
# CONFIGURATION
# ============================================================

PDF_PATH = Path(
    "raw/2025-26/monthly/FlashReport_August_2025.pdf"
)

OUTPUT_PATH = Path(
    "processed/extracted/august_2025_all_ongoing.json"
)

START_PAGE = 37
END_PAGE = 66


# ============================================================
# REGEX
# ============================================================

PROJECT_CODE_RE = re.compile(
    r"^\((\d{5,})\)$"
)

DATE_RE = re.compile(
    r"^\(?\d{2}/\d{4}\)?$"
)

NUMBER_RE = re.compile(
    r"^\(?\d[\d,]*(?:\.\d+)?\)?$"
)


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_line(value):
    return value.strip()


def is_missing(value):
    return value in {
        "-",
        "(-)",
        "()",
        "NA",
        "(NA)"
    }


def is_date(value):
    if is_missing(value):
        return True

    return DATE_RE.match(value) is not None


def normalize_date(value):
    if is_missing(value):
        return None

    value = value.strip()

    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]

    return value


def number_value(value):
    value = value.strip()
    value = value.replace(",", "")

    if is_missing(value):
        return None

    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]

    try:
        return float(value)
    except ValueError:
        return None


def is_numeric(value):
    return NUMBER_RE.match(value) is not None


# ============================================================
# PROJECT CODE DETECTION
# ============================================================

def is_project_code(lines, index):

    value = lines[index]

    match = PROJECT_CODE_RE.match(value)

    if not match:
        return False

    # A real project code is followed by a state.
    if index + 1 >= len(lines):
        return False

    next_line = lines[index + 1]

    # Revised cost values such as:
    # (27213)
    # 1953.52
    #
    # must NOT be mistaken for project codes.
    if is_numeric(next_line):
        return False

    # A code followed by a dash is also not a valid
    # project-code structure.
    if next_line in {"-", "(-)"}:
        return False

    return True


# ============================================================
# PROJECT IDENTITY EXTRACTION
# ============================================================

def find_previous_serial(lines, index):

    for j in range(index - 1, max(-1, index - 20), -1):

        value = lines[j]

        if value.isdigit():

            serial = int(value)

            if 1 <= serial <= 5000:
                return serial

    return None


def find_agency(lines, index):

    for j in range(index - 1, max(-1, index - 10), -1):

        value = lines[j]

        if (
            value.startswith("(")
            and value.endswith(")")
            and not PROJECT_CODE_RE.match(value)
        ):

            agency = value[1:-1].strip()

            if agency:
                return agency

    return None


def find_project_name(lines, index):

    name_parts = []

    for j in range(index - 1, max(-1, index - 15), -1):

        value = lines[j]

        # Stop at previous serial number.
        if value.isdigit():

            serial = int(value)

            if 1 <= serial <= 5000:
                break

        # Stop if another project code appears.
        if PROJECT_CODE_RE.match(value):
            break

        # Agency-like line should not be included.
        if (
            value.startswith("(")
            and value.endswith(")")
        ):
            continue

        name_parts.append(value)

    name_parts.reverse()

    return " ".join(name_parts).strip()


# ============================================================
# STATE EXTRACTION
# ============================================================

def extract_state(lines, index):

    state_parts = []

    i = index + 1

    while i < len(lines):

        value = lines[i]

        # Stop at approval date.
        if is_date(value):
            break

        # A numeric value here means something went wrong.
        if is_numeric(value):
            break

        # Ignore empty placeholders.
        if value not in {"-", "(-)", "()"}:
            state_parts.append(value)

        i += 1

    return " ".join(state_parts).strip(), i


# ============================================================
# RECORD PARSER
# ============================================================

def parse_record(lines, code_index):

    code = PROJECT_CODE_RE.match(
        lines[code_index]
    ).group(1)

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    serial_no = find_previous_serial(
        lines,
        code_index
    )

    implementing_agency = find_agency(
        lines,
        code_index
    )

    project_name = find_project_name(
        lines,
        code_index
    )

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    state, index = extract_state(
        lines,
        code_index
    )

    if not state:
        raise ValueError("NO_STATE")

    # --------------------------------------------------------
    # Approval date
    # --------------------------------------------------------

    if index >= len(lines):
        raise ValueError("NO_APPROVAL_DATE")

    approval_date = normalize_date(
        lines[index]
    )

    index += 1

    # --------------------------------------------------------
    # Revised approval date
    # --------------------------------------------------------

    if index >= len(lines):
        raise ValueError(
            "NO_REVISED_APPROVAL_DATE"
        )

    revised_approval_date = normalize_date(
        lines[index]
    )

    index += 1

    # --------------------------------------------------------
    # Original Date of Completion
    # --------------------------------------------------------

    if index >= len(lines):
        raise ValueError(
            "NO_ORIGINAL_DOC"
        )

    original_doc = normalize_date(
        lines[index]
    )

    index += 1

    # --------------------------------------------------------
    # Revised Date of Completion
    # --------------------------------------------------------

    if index >= len(lines):
        raise ValueError(
            "NO_REVISED_DOC"
        )

    revised_doc = normalize_date(
        lines[index]
    )

    index += 1

    # --------------------------------------------------------
    # Original cost
    # --------------------------------------------------------

    if index >= len(lines):
        raise ValueError(
            "NO_ORIGINAL_COST"
        )

    original_cost = number_value(
        lines[index]
    )

    if original_cost is None:
        raise ValueError(
            "INVALID_ORIGINAL_COST"
        )

    index += 1

    # --------------------------------------------------------
    # Revised cost
    # --------------------------------------------------------

    if index >= len(lines):
        raise ValueError(
            "NO_REVISED_COST"
        )

    revised_cost = number_value(
        lines[index]
    )

    if revised_cost is None:
        raise ValueError(
            "INVALID_REVISED_COST"
        )

    index += 1

    # --------------------------------------------------------
    # Cumulative expenditure
    # --------------------------------------------------------

    if index >= len(lines):
        raise ValueError(
            "NO_EXPENDITURE"
        )

    expenditure = number_value(
        lines[index]
    )

    if expenditure is None:
        raise ValueError(
            "INVALID_EXPENDITURE"
        )

    index += 1

    # --------------------------------------------------------
    # Physical progress
    # --------------------------------------------------------

    if index >= len(lines):
        raise ValueError(
            "NO_PHYSICAL_PROGRESS"
        )

    physical_progress = number_value(
        lines[index]
    )

    if physical_progress is None:
        raise ValueError(
            "INVALID_PHYSICAL_PROGRESS"
        )

    if not 0 <= physical_progress <= 100:
        raise ValueError(
            "INVALID_PHYSICAL_PROGRESS"
        )

    # --------------------------------------------------------
    # Final record
    # --------------------------------------------------------

    return {
        "serial_no": serial_no,
        "project_code": code,
        "project_name": project_name,
        "implementing_agency": implementing_agency,
        "legacy_ocms_code": None,
        "pmgid": None,
        "state": state,
        "approval_date": approval_date,
        "revised_approval_date": revised_approval_date,
        "original_doc": original_doc,
        "revised_doc": revised_doc,
        "original_cost_crore": original_cost,
        "revised_cost_crore": revised_cost,
        "cumulative_expenditure_crore": expenditure,
        "physical_progress_pct": physical_progress,
    }


# ============================================================
# MAIN EXTRACTION
# ============================================================

def main():

    print("=" * 70)
    print("AUGUST 2025 PAIMANA EXTRACTION")
    print("=" * 70)

    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"PDF not found: {PDF_PATH}"
        )

    doc = pymupdf.open(PDF_PATH)

    candidates = []
    rejected = []

    # --------------------------------------------------------
    # Process pages
    # --------------------------------------------------------

    for page_number in range(
        START_PAGE,
        END_PAGE + 1
    ):

        page = doc[page_number - 1]

        lines = [
            normalize_line(x)
            for x in page
            .get_text("text")
            .splitlines()
            if normalize_line(x)
        ]

        # ----------------------------------------------------
        # Detect project codes
        # ----------------------------------------------------

        for i in range(len(lines)):

            if not is_project_code(lines, i):
                continue

            code = PROJECT_CODE_RE.match(
                lines[i]
            ).group(1)

            candidates.append(
                {
                    "page": page_number,
                    "code": code,
                    "index": i
                }
            )

    # --------------------------------------------------------
    # Parse candidates
    # --------------------------------------------------------

    valid_records = []

    for candidate in candidates:

        page_number = candidate["page"]
        code = candidate["code"]

        lines = [
            normalize_line(x)
            for x in doc[page_number - 1]
            .get_text("text")
            .splitlines()
            if normalize_line(x)
        ]

        try:

            record = parse_record(
                lines,
                candidate["index"]
            )

            record["source_page"] = page_number

            valid_records.append(record)

        except ValueError as e:

            rejected.append(
                {
                    "page": page_number,
                    "project_code": code,
                    "reason": str(e)
                }
            )

    doc.close()

    # --------------------------------------------------------
    # Save output
    # --------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            valid_records,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    print(
        f"Candidate records : {len(candidates)}"
    )

    print(
        f"Valid records     : {len(valid_records)}"
    )

    print(
        f"Rejected records  : {len(rejected)}"
    )

    print()

    if rejected:

        print("Rejected records:")

        for item in rejected:

            print(
                f"Page {item['page']} | "
                f"Code {item['project_code']} | "
                f"{item['reason']}"
            )

    print()

    print("Output:")
    print(OUTPUT_PATH)

    # --------------------------------------------------------
    # Preview
    # --------------------------------------------------------

    if valid_records:

        print()
        print("First record:")

        print(
            json.dumps(
                valid_records[0],
                indent=2,
                ensure_ascii=False
            )
        )

        print()
        print("Last record:")

        print(
            json.dumps(
                valid_records[-1],
                indent=2,
                ensure_ascii=False
            )
        )


if __name__ == "__main__":
    main()
