from pathlib import Path
import json
import re
import pymupdf

PDF = Path("raw/2019-20/monthly/FR_APr_Report_2019.pdf")
OUTPUT = Path("processed/extracted/historical_2019_april.json")

START_PAGE = 68
END_PAGE = 144
EXPECTED_PROJECTS = 1453

CODE_RE = re.compile(r"\[([A-Za-z0-9]+)\]")
DATE_RE = re.compile(r"^\d{2}/\d{4}$")
NUMBER_RE = re.compile(r"^-?\d[\d,]*(?:\.\d+)?$")
DELAY_RE = re.compile(r"^-?\d+\([OR]\)$")


def clean(value):
    value = re.sub(r"\s+", " ", value or "").strip()

    if value in {"", "-"}:
        return None

    if value == ".00":
        return 0.0

    return value


def number(value):
    value = clean(value)

    if value is None:
        return None

    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def parse_identity(words, code_index):
    code_word = words[code_index]
    code_y = code_word[1]

    # Serial numbers are in the left-most column.
    candidates = []

    for i, w in enumerate(words):
        x0, y0, x1, y1, text, *_ = w

        if x0 >= 40:
            continue

        if not re.fullmatch(r"\d{1,4}", text):
            continue

        serial = int(text)

        if not 1 <= serial <= EXPECTED_PROJECTS:
            continue

        # Serial must be above or on the code row.
        if y0 <= code_y + 5:
            candidates.append(
                (abs(code_y - y0), serial, i)
            )

    if not candidates:
        return None, None, None

    candidates.sort(key=lambda x: x[0])

    _, serial, serial_index = candidates[0]

    serial_y = words[serial_index][1]

    # Collect project words between serial and code.
    project_words = []

    for i, w in enumerate(words):

        if i == code_index:
            break

        x0, y0, x1, y1, text, *_ = w

        if x0 < 40:
            continue

        if y0 < serial_y - 2:
            continue

        if y0 > code_y + 2:
            continue

        project_words.append(w)

    project_words.sort(
        key=lambda w: (round(w[1], 1), w[0])
    )

    project_name = clean(
        " ".join(w[4] for w in project_words)
    )

    if project_name:
        project_name = project_name.rstrip(" -")

    return serial, project_name, serial_index


def parse_agency_state(words, code_index):
    """
    Reconstruct agency/state from the code row.

    Examples in the source PDF:

        [020100044]BHAVNI,TAMIL
        NADU,

        [N28000104]CPWD,WEST
        BENGAL,
        Central Sector Projects

        [N04000073]AAI,A
        &
        N
        ISLANDS,
    """

    code_word = words[code_index]

    code_y = code_word[1]

    raw = re.sub(
        r"^\[[A-Za-z0-9]+\]",
        "",
        code_word[4]
    )

    if "," not in raw:
        return None, None

    agency, state_start = raw.split(",", 1)

    agency = clean(agency)

    state_parts = []

    if state_start.strip():
        state_parts.append(state_start.strip())

    # Collect words immediately following the code row.
    #
    # State can wrap onto several lines. Stop when we encounter
    # the terminating comma or a known classification.
    for w in words[code_index + 1:]:

        x0, y0, x1, y1, text, *_ = w

        # Only nearby lines.
        if y0 < code_y - 1:
            continue

        if y0 > code_y + 30:
            break

        # Avoid pulling data from other columns.
        if x0 > 220:
            continue

        token = text.strip()

        if token == ",":
            break

        if token.lower() in {
            "central",
            "sector",
            "projects",
        }:
            # Classification starts here.
            break

        if token.lower() in {
            "ppp",
            "(bot)",
            "epc",
        }:
            break

        state_parts.append(token)

    state = clean(" ".join(state_parts))

    # Remove trailing punctuation.
    state = state.rstrip(" ,")

    return agency, state


def parse_numeric_fields(words_after):
    texts = [w[4] for w in words_after]

    approval_index = None

    for i, text in enumerate(texts):
        if DATE_RE.fullmatch(text):
            approval_index = i
            break

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

    if approval_index is None:
        return result

    result["date_of_approval"] = texts[approval_index]

    tail = texts[approval_index + 1:]

    numeric = [
        x for x in tail
        if NUMBER_RE.fullmatch(x)
    ]

    if len(numeric) >= 1:
        result["original_cost"] = number(numeric[0])

    if len(numeric) >= 2:
        result["revised_cost"] = number(numeric[1])

    if len(numeric) >= 3:
        result["anticipated_cost"] = number(numeric[2])

    if len(numeric) >= 4:
        result["cumulative_expenditure"] = number(numeric[3])

    dates = [
        x for x in tail
        if DATE_RE.fullmatch(x)
    ]

    if len(dates) >= 1:
        result["original_doc"] = dates[0]

    if len(dates) >= 2:
        result["revised_doc"] = dates[1]

    if len(dates) >= 3:
        result["anticipated_doc"] = dates[2]

    delays = []

    for x in tail:
        m = DELAY_RE.fullmatch(x)

        if m:
            delays.append(
                int(x.split("(")[0])
            )

    if len(delays) >= 1:
        result["delay_original_months"] = delays[0]

    if len(delays) >= 2:
        result["delay_revised_months"] = delays[1]

    milestone_matches = re.findall(
        r"(\d+)\s*/\s*(\d+)",
        " ".join(tail)
    )

    if milestone_matches:
        a, b = milestone_matches[-1]

        result["milestones_achieved"] = int(a)
        result["milestones_total"] = int(b)

    return result


def parse_page(page, page_number):
    words = page.get_text("words")

    code_indices = [
        i for i, w in enumerate(words)
        if CODE_RE.search(w[4])
    ]

    records = []

    for position, code_index in enumerate(code_indices):

        code_match = CODE_RE.search(
            words[code_index][4]
        )

        if not code_match:
            continue

        code = code_match.group(1)

        serial, project_name, _ = parse_identity(
            words,
            code_index
        )

        agency, state = parse_agency_state(
            words,
            code_index
        )

        code_y = words[code_index][1]

        if position + 1 < len(code_indices):
            next_code_y = words[
                code_indices[position + 1]
            ][1]
        else:
            next_code_y = None

        after = []

        for i, w in enumerate(words):

            if i <= code_index:
                continue

            y = w[1]

            if y <= code_y + 1:
                continue

            if (
                next_code_y is not None
                and y >= next_code_y
            ):
                continue

            after.append(w)

        parsed = parse_numeric_fields(after)

        records.append({
            "serial_no": serial,
            "project_code": code,
            "project_name": project_name,
            "agency": agency,
            "state": state,
            **parsed,
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

    print("=" * 80)
    print("2019-20 APRIL HISTORICAL EXTRACTION")
    print("=" * 80)

    print(f"Expected records     : {EXPECTED_PROJECTS}")
    print(f"Extracted records    : {len(records)}")
    print(f"Unique codes         : {len(set(codes))}")
    print(
        f"Duplicate codes      : "
        f"{len(codes) - len(set(codes))}"
    )
    print(f"Missing names        : {len(missing_names)}")

    if serials:
        print(
            f"Serial range         : "
            f"{min(serials)} - {max(serials)}"
        )

    print()
    print("KEY VALIDATION RECORDS")

    test_codes = [
        "020100044",
        "N24000453",
        "N24000561",
        "N28000104",
        "N04000073",
        "N39000001",
        "N39000002",
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
                    f'page {r["source_page"]}'
                )

    print()
    print("FIRST 5")

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
        print("MISSING NAMES")

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
