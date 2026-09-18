from pathlib import Path
import json
import re
from collections import Counter

import pymupdf


PDF = Path("raw/2020-21/monthly/FR_APril_2020.pdf")
OUTPUT = Path("processed/extracted/historical_2020_april.json")

START_PAGE = 68
END_PAGE = 157
EXPECTED_PROJECTS = 1682

CODE_RE = re.compile(r"\[([A-Za-z0-9]+)\]")
DATE_RE = re.compile(r"^\d{2}/\d{4}$")
NUMBER_RE = re.compile(r"^-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)$")
DELAY_RE = re.compile(r"^-?\d+\([OR]\)$")


def clean(value):
    if value is None:
        return None

    value = re.sub(r"\s+", " ", value).strip()

    if value in {"", "-"}:
        return None

    return value


def parse_number(value):
    value = clean(value)

    if value is None:
        return None

    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def is_integer_token(text):
    return bool(re.fullmatch(r"\d{1,4}", text))


def find_code_indices(words):
    return [
        i for i, word in enumerate(words)
        if CODE_RE.search(word[4])
    ]


def find_serial_before_code(words, code_index):
    code_y = words[code_index][1]

    candidates = []

    for i, word in enumerate(words):
        x0, y0, x1, y1, text, *_ = word

        if x0 >= 40:
            continue

        if y0 > code_y + 1:
            continue

        if not is_integer_token(text):
            continue

        serial = int(text)

        if 1 <= serial <= EXPECTED_PROJECTS:
            candidates.append((y0, serial))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0])

    serial_y, serial = candidates[-1]

    return serial, serial_y


def parse_agency_state(words, code_index):
    """
    Reconstruct agency and state from the code area.

    State can wrap across multiple PDF words/lines.
    """

    code_word = words[code_index]

    text = code_word[4]

    match = CODE_RE.search(text)

    if not match:
        return None, None

    tail = text[match.end():]

    if "," not in tail:
        return clean(tail), None

    agency, state_start = tail.split(",", 1)

    agency = clean(agency)

    state_parts = []

    if state_start.strip():
        state_parts.append(
            state_start.strip()
        )

    code_y = code_word[1]

    for word in words[code_index + 1:]:

        x0, y0, x1, y1, token, *_ = word

        if x0 >= 220:
            continue

        if y0 < code_y - 1:
            continue

        if y0 > code_y + 30:
            break

        token = token.strip()

        if token == ",":
            break

        if token.lower() in {
            "central",
            "sector",
            "projects",
            "ppp",
            "(bot)",
            "epc",
        }:
            break

        state_parts.append(token)

    state = clean(
        " ".join(state_parts)
    )

    if state:
        state = state.rstrip(" ,")

    return agency, state


def remove_state_suffix(project_name, state):
    """
    Remove state text that leaked into the project name.

    The state field is independently reconstructed from the
    project-code area, so it is safe to remove a matching
    suffix from project_name.

    Examples:

        "... - NADU" + "TAMIL NADU"
            -> "..."

        "... - BENGAL" + "WEST BENGAL"
            -> "..."

        "... - & N ISLANDS" + "A & N ISLANDS"
            -> "..."

        "... - STATE" + "MULTI STATE"
            -> "..."
    """

    if not project_name or not state:
        return project_name

    name = project_name.strip()

    state = re.sub(
        r"\s+",
        " ",
        state
    ).strip()

    # Remove the full state if present.
    patterns = [
        re.escape(state),
    ]

    # Handle common PDF wrapping where the first word(s)
    # of the state appear at the end of project_name.
    state_words = state.split()

    if len(state_words) > 1:

        for n in range(
            len(state_words) - 1,
            0,
            -1
        ):
            suffix = " ".join(
                state_words[-n:]
            )

            patterns.append(
                re.escape(suffix)
            )

    for pattern in patterns:

        new_name = re.sub(
            rf"\s*[-,]?\s*{pattern}\s*,?\s*$",
            "",
            name,
            flags=re.IGNORECASE
        )

        if new_name != name:

            name = new_name.strip()

            break

    # Remove a trailing hyphen/comma left behind.
    name = re.sub(
        r"\s*[-,]\s*$",
        "",
        name
    ).strip()

    return name


def find_project_name(
    words,
    serial_y,
    code_index,
    state
):
    """
    Extract project name from the project column and then
    remove any state suffix that leaked into the name.
    """

    code_y = words[code_index][1]

    result = []

    for i, word in enumerate(words):

        if i == code_index:
            continue

        x0, y0, x1, y1, text, *_ = word

        if x0 < 40 or x0 >= 220:
            continue

        if y0 < serial_y - 2:
            continue

        if y0 > code_y + 2:
            continue

        if CODE_RE.search(text):
            continue

        result.append(word)

    result.sort(
        key=lambda w: (
            round(w[1], 1),
            w[0]
        )
    )

    name = " ".join(
        w[4]
        for w in result
    )

    name = clean(name)

    if name:
        name = name.rstrip(" -,")

    name = remove_state_suffix(
        name,
        state
    )

    return name


def words_in_row(
    words,
    serial_y,
    next_serial_y
):
    result = []

    for word in words:

        y0 = word[1]

        if y0 < serial_y - 2:
            continue

        if (
            next_serial_y is not None
            and y0 >= next_serial_y - 1
        ):
            continue

        result.append(word)

    return result


def column_values(
    row_words,
    xmin,
    xmax
):
    values = []

    for word in row_words:

        x0, y0, x1, y1, text, *_ = word

        if xmin <= x0 < xmax:
            values.append(word)

    values.sort(
        key=lambda w: (
            round(w[1], 1),
            w[0]
        )
    )

    return values


def parse_row_fields(row_words):

    result = {
        "date_of_approval": None,
        "original_cost": None,
        "revised_cost": None,
        "anticipated_cost": None,
        "cumulative_expenditure": None,
        "original_doc": None,
        "revised_doc": None,
        "anticipated_doc": None,
        "delay_original_months": None,
        "delay_revised_months": None,
        "milestones_achieved": None,
        "milestones_total": None,
    }

    # Date of approval
    approval_words = column_values(
        row_words,
        220,
        265
    )

    for word in approval_words:

        if DATE_RE.fullmatch(word[4]):

            result["date_of_approval"] = word[4]

            break

    # Original / Revised Cost
    cost_words = column_values(
        row_words,
        265,
        315
    )

    cost_values = [
        word[4]
        for word in cost_words
        if (
            word[4] == "-"
            or NUMBER_RE.fullmatch(word[4])
        )
    ]

    if len(cost_values) >= 1:
        result["original_cost"] = parse_number(
            cost_values[0]
        )

    if len(cost_values) >= 2:
        result["revised_cost"] = parse_number(
            cost_values[1]
        )

    # Anticipated Cost
    anticipated_words = column_values(
        row_words,
        315,
        360
    )

    for word in anticipated_words:

        if NUMBER_RE.fullmatch(word[4]):

            result["anticipated_cost"] = parse_number(
                word[4]
            )

            break

    # Expenditure
    expenditure_words = column_values(
        row_words,
        360,
        410
    )

    for word in expenditure_words:

        if NUMBER_RE.fullmatch(word[4]):

            result["cumulative_expenditure"] = parse_number(
                word[4]
            )

            break

    # Original / Revised DoC
    doc_words = column_values(
        row_words,
        405,
        445
    )

    doc_values = [
        word[4]
        for word in doc_words
        if (
            word[4] == "-"
            or DATE_RE.fullmatch(word[4])
        )
    ]

    if len(doc_values) >= 1:
        result["original_doc"] = clean(
            doc_values[0]
        )

    if len(doc_values) >= 2:
        result["revised_doc"] = clean(
            doc_values[1]
        )

    # Anticipated DoC
    anticipated_doc_words = column_values(
        row_words,
        445,
        490
    )

    for word in anticipated_doc_words:

        if DATE_RE.fullmatch(word[4]):

            result["anticipated_doc"] = word[4]

            break

    # Delay
    delay_words = column_values(
        row_words,
        490,
        540
    )

    delay_values = [
        word[4]
        for word in delay_words
        if DELAY_RE.fullmatch(word[4])
    ]

    if len(delay_values) >= 1:

        result["delay_original_months"] = int(
            delay_values[0].split("(")[0]
        )

    if len(delay_values) >= 2:

        result["delay_revised_months"] = int(
            delay_values[1].split("(")[0]
        )

    # Milestones
    milestone_words = column_values(
        row_words,
        540,
        590
    )

    for word in milestone_words:

        match = re.fullmatch(
            r"(\d+)\s*/\s*(\d+)",
            word[4]
        )

        if match:

            result["milestones_achieved"] = int(
                match.group(1)
            )

            result["milestones_total"] = int(
                match.group(2)
            )

            break

    return result


def parse_page(
    page,
    page_number
):

    words = page.get_text("words")

    code_indices = find_code_indices(
        words
    )

    serial_candidates = []

    for word in words:

        x0, y0, x1, y1, text, *_ = word

        if x0 >= 40:
            continue

        if not is_integer_token(text):
            continue

        serial = int(text)

        if 1 <= serial <= EXPECTED_PROJECTS:

            serial_candidates.append(
                (y0, serial)
            )

    serial_candidates.sort()

    records = []

    for code_index in code_indices:

        code_match = CODE_RE.search(
            words[code_index][4]
        )

        if not code_match:
            continue

        code = code_match.group(1)

        serial, serial_y = find_serial_before_code(
            words,
            code_index
        )

        if serial is None:

            print(
                f"WARNING: serial not found: "
                f"{code}, page {page_number}"
            )

            continue

        agency, state = parse_agency_state(
            words,
            code_index
        )

        project_name = find_project_name(
            words,
            serial_y,
            code_index,
            state
        )

        next_serial_y = None

        for y, candidate_serial in serial_candidates:

            if y > serial_y + 1:

                next_serial_y = y

                break

        row_words = words_in_row(
            words,
            serial_y,
            next_serial_y
        )

        fields = parse_row_fields(
            row_words
        )

        records.append({
            "serial_no": serial,
            "project_code": code,
            "project_name": project_name,
            "agency": agency,
            "state": state,
            **fields,
            "source_page": page_number,
        })

    return records


def main():

    if not PDF.exists():
        raise FileNotFoundError(PDF)

    doc = pymupdf.open(PDF)

    records = []

    for page_number in range(
        START_PAGE,
        END_PAGE + 1
    ):

        records.extend(
            parse_page(
                doc[page_number - 1],
                page_number
            )
        )

    doc.close()

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

    codes = [
        r["project_code"]
        for r in records
    ]

    serials = [
        r["serial_no"]
        for r in records
        if r["serial_no"] is not None
    ]

    missing_names = [
        r
        for r in records
        if not r["project_name"]
    ]

    duplicate_codes = [
        code
        for code, count in Counter(codes).items()
        if count > 1
    ]

    duplicate_serials = [
        serial
        for serial, count in Counter(serials).items()
        if count > 1
    ]

    missing_serials = sorted(
        set(range(1, EXPECTED_PROJECTS + 1))
        - set(serials)
    )

    print("=" * 80)
    print("2020-21 APRIL HISTORICAL EXTRACTION")
    print("=" * 80)

    print(
        f"Expected records     : "
        f"{EXPECTED_PROJECTS}"
    )

    print(
        f"Extracted records    : "
        f"{len(records)}"
    )

    print(
        f"Unique codes         : "
        f"{len(set(codes))}"
    )

    print(
        f"Duplicate codes      : "
        f"{len(duplicate_codes)}"
    )

    print(
        f"Missing names        : "
        f"{len(missing_names)}"
    )

    if serials:

        print(
            f"Serial range         : "
            f"{min(serials)} - {max(serials)}"
        )

    print(
        f"Duplicate serials    : "
        f"{len(duplicate_serials)}"
    )

    print(
        f"Missing serials      : "
        f"{len(missing_serials)}"
    )

    print()
    print("KEY VALIDATION RECORDS")
    print("-" * 80)

    test_codes = [
        "N02000010",
        "N02000027",
        "020100044",
        "N04000073",
        "N04000078",
        "N40000002",
        "N40000001",
    ]

    for code in test_codes:

        for r in records:

            if r["project_code"] == code:

                print(
                    f'{r["serial_no"]} | '
                    f'{r["project_code"]} | '
                    f'{r["project_name"]} | '
                    f'{r["agency"]} | '
                    f'{r["state"]} | '
                    f'OrigCost={r["original_cost"]} | '
                    f'RevisedCost={r["revised_cost"]} | '
                    f'AntCost={r["anticipated_cost"]} | '
                    f'Exp={r["cumulative_expenditure"]}'
                )

    print()
    print("FIRST 5")
    print("-" * 80)

    for r in records[:5]:

        print(
            f'{r["serial_no"]} | '
            f'{r["project_code"]} | '
            f'{r["project_name"]} | '
            f'{r["agency"]} | '
            f'{r["state"]}'
        )

    print()
    print("LAST 5")
    print("-" * 80)

    for r in records[-5:]:

        print(
            f'{r["serial_no"]} | '
            f'{r["project_code"]} | '
            f'{r["project_name"]} | '
            f'{r["agency"]} | '
            f'{r["state"]}'
        )

    if missing_names:

        print()
        print("MISSING PROJECT NAMES")
        print("-" * 80)

        for r in missing_names[:20]:

            print(
                f'{r["serial_no"]} | '
                f'{r["project_code"]} | '
                f'page {r["source_page"]}'
            )

    print()
    print("Saved:")
    print(OUTPUT)


if __name__ == "__main__":
    main()
