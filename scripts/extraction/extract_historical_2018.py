from pathlib import Path
import pymupdf
import re
import json

PDF = Path("raw/2018-19/monthly/FR_APr_2018.pdf")
OUTPUT = Path("processed/extracted/historical_2018_april.json")

START_PAGE = 73
END_PAGE = 142
EXPECTED_PROJECTS = 1332

CODE_RE = re.compile(r"\[([A-Za-z0-9]+)\]")
SERIAL_RE = re.compile(r"^\d{1,4}$")
DATE_RE = re.compile(r"^\d{2}/\d{4}$")
NUMBER_RE = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
DELAY_RE = re.compile(r"^-?\d+\([OR]\)$")
MILESTONE_RE = re.compile(r"^\d+/\d+$")

STOP_MARKERS = [
    "Central Sector Projects",
    "Central Sector",
    "PPP (BOT)",
    "PPP (ANNUITY)",
    "EPC",
    "ITEM RATE",
]


def clean(s):
    if not s:
        return None

    s = re.sub(r"\s+", " ", s)
    s = s.strip(" ,-;")

    return s or None


def is_serial(w):
    return (
        w[0] < 40
        and SERIAL_RE.fullmatch(
            w[4].strip()
        ) is not None
    )


def group_lines(words, tol=2.5):

    lines = []

    for w in sorted(
        words,
        key=lambda z: (z[1], z[0])
    ):

        y = w[1]
        found = None

        for line in lines:

            if abs(
                line["y"] - y
            ) <= tol:

                found = line
                break

        if found is None:

            found = {
                "y": y,
                "words": []
            }

            lines.append(found)

        found["words"].append(w)

    for line in lines:

        line["words"].sort(
            key=lambda z: z[0]
        )

    return lines


def line_text(line):

    return " ".join(
        w[4]
        for w in line["words"]
    )


def find_records(lines):

    records = []

    for i, line in enumerate(lines):

        serial_words = [
            w
            for w in line["words"]
            if is_serial(w)
        ]

        if not serial_words:
            continue

        serial_word = serial_words[0]
        serial = int(
            serial_word[4]
        )

        code_index = None
        code = None

        for j in range(
            i,
            min(i + 12, len(lines))
        ):

            m = CODE_RE.search(
                line_text(lines[j])
            )

            if m:

                code_index = j
                code = m.group(1)
                break

            if j > i:

                if any(
                    is_serial(w)
                    for w in lines[j]["words"]
                ):
                    break

        if code is None:
            continue

        records.append({
            "serial": serial,
            "code": code,
            "start": i,
            "code_line": code_index,
        })

    return records


def parse_name(
    lines,
    start,
    code_index
):

    parts = []

    for i in range(
        start,
        code_index + 1
    ):

        line = lines[i]

        for w in line["words"]:

            value = w[4]

            # Stop at project code.
            if "[" in value:

                before = value.split(
                    "[",
                    1
                )[0].strip()

                if before:
                    parts.append(before)

                break

            # Ignore actual serial.
            if (
                i == start
                and is_serial(w)
            ):
                continue

            # Project name column only.
            if w[0] < 220:
                parts.append(value)

    name = clean(
        " ".join(parts)
    )

    if not name:
        return None

    # Remove administrative suffixes.
    for marker in STOP_MARKERS:

        if marker in name:
            name = name.split(
                marker,
                1
            )[0]

    name = clean(name)

    if not name:
        return None

    # Remove accidental trailing state fragments.
    tokens = name.split()

    while tokens:

        last = tokens[-1].upper().strip(",-")

        if last in {
            "NADU",
            "PRADESH",
            "BENGAL",
            "ISLANDS",
            "STATE",
        }:

            tokens.pop()

        else:
            break

    return clean(
        " ".join(tokens)
    )


def parse_agency_state(
    lines,
    code_index
):

    code_line = lines[
        code_index
    ]

    code_word = None

    for w in code_line["words"]:

        if CODE_RE.search(w[4]):

            code_word = w
            break

    if code_word is None:
        return None, None

    match = CODE_RE.search(
        code_word[4]
    )

    after = code_word[4][
        match.end():
    ]

    # ---------------------------------------------------------
    # IMPORTANT:
    # Only use text physically belonging to the
    # agency/state area.
    # Never use the complete text of the visual line,
    # because cost/date fields can share the same Y.
    # ---------------------------------------------------------

    agency = None
    state_parts = []

    if "," in after:

        agency_part, state_part = after.split(
            ",",
            1
        )

        agency = clean(
            agency_part
        )

        if state_part.strip():
            state_parts.append(
                state_part
            )

    else:

        agency = clean(after)

    # Continuation on the SAME line after the code.
    # Only x < 220 is allowed.
    for w in code_line["words"]:

        if w[0] <= code_word[2]:
            continue

        if w[0] >= 220:
            continue

        value = w[4].strip()

        if not value:
            continue

        if DATE_RE.fullmatch(value):
            continue

        if NUMBER_RE.fullmatch(value):
            continue

        if DELAY_RE.fullmatch(value):
            continue

        if MILESTONE_RE.fullmatch(value):
            continue

        state_parts.append(value)

    # ---------------------------------------------------------
    # State may continue onto the next physical line.
    # Again, ONLY x < 220.
    # ---------------------------------------------------------

    if code_index + 1 < len(lines):

        next_line = lines[
            code_index + 1
        ]

        next_words = next_line["words"]

        # Don't consume another project.
        if not any(
            is_serial(w)
            for w in next_words
        ):

            continuation = []

            for w in next_words:

                if w[0] >= 220:
                    continue

                value = w[4].strip()

                if not value:
                    continue

                if DATE_RE.fullmatch(value):
                    continue

                if NUMBER_RE.fullmatch(value):
                    continue

                if DELAY_RE.fullmatch(value):
                    continue

                if MILESTONE_RE.fullmatch(value):
                    continue

                continuation.append(value)

            if continuation:

                state_parts.extend(
                    continuation
                )

    state = clean(
        " ".join(state_parts)
    )

    if state:

        for marker in STOP_MARKERS:

            if marker in state:

                state = state.split(
                    marker,
                    1
                )[0]

        state = clean(state)

    return agency, state


def extract_fields(
    words,
    code_y,
    end_y
):

    block = [
        w
        for w in words
        if code_y - 12 <= w[1] < end_y
    ]

    # Original / Revised cost.
    costs = []

    for w in block:

        value = w[4].strip()

        if not NUMBER_RE.fullmatch(value):
            continue

        if 260 <= w[0] < 315:

            costs.append(
                (
                    w[1],
                    w[0],
                    float(
                        value.replace(
                            ",",
                            ""
                        )
                    )
                )
            )

    costs.sort()

    original_cost = (
        costs[0][2]
        if len(costs) >= 1
        else None
    )

    revised_cost = (
        costs[1][2]
        if len(costs) >= 2
        else None
    )

    # Anticipated cost.
    anticipated = []

    for w in block:

        value = w[4].strip()

        if not NUMBER_RE.fullmatch(value):
            continue

        if 315 <= w[0] < 365:

            anticipated.append(
                (
                    w[1],
                    w[0],
                    float(
                        value.replace(
                            ",",
                            ""
                        )
                    )
                )
            )

    anticipated.sort()

    anticipated_cost = (
        anticipated[0][2]
        if anticipated
        else None
    )

    # Expenditure.
    expenditure = []

    for w in block:

        value = w[4].strip()

        if not NUMBER_RE.fullmatch(value):
            continue

        if 365 <= w[0] < 410:

            expenditure.append(
                (
                    w[1],
                    w[0],
                    float(
                        value.replace(
                            ",",
                            ""
                        )
                    )
                )
            )

    expenditure.sort()

    cumulative_expenditure = (
        expenditure[0][2]
        if expenditure
        else None
    )

    # Dates.
    dates = []

    for w in block:

        value = w[4].strip()

        if DATE_RE.fullmatch(value):

            dates.append(
                (
                    w[1],
                    w[0],
                    value
                )
            )

    dates.sort()

    approval = [
        x[2]
        for x in dates
        if 215 <= x[1] < 260
    ]

    commissioning = [
        x[2]
        for x in dates
        if x[1] >= 395
    ]

    # Delays.
    delays = []

    for w in block:

        value = w[4].strip()

        if DELAY_RE.fullmatch(value):

            delays.append(
                (
                    w[1],
                    w[0],
                    value
                )
            )

    delays.sort()

    # Milestones.
    milestones = []

    for w in block:

        value = w[4].strip()

        if MILESTONE_RE.fullmatch(value):

            milestones.append(
                (
                    w[1],
                    w[0],
                    value
                )
            )

    milestones.sort()

    return {
        "original_cost": (
            original_cost
        ),

        "revised_cost": (
            revised_cost
        ),

        "anticipated_cost": (
            anticipated_cost
        ),

        "cumulative_expenditure": (
            cumulative_expenditure
        ),

        "approval_date": (
            approval[0]
            if approval
            else None
        ),

        "original_doc": (
            commissioning[0]
            if len(commissioning) > 0
            else None
        ),

        "revised_doc": (
            commissioning[1]
            if len(commissioning) > 1
            else None
        ),

        "anticipated_doc": (
            commissioning[2]
            if len(commissioning) > 2
            else None
        ),

        "original_delay": (
            delays[0][2]
            if len(delays) > 0
            else None
        ),

        "revised_delay": (
            delays[1][2]
            if len(delays) > 1
            else None
        ),

        "milestones": (
            milestones[0][2]
            if milestones
            else None
        ),
    }


def extract_page(
    page,
    page_no
):

    words = page.get_text(
        "words"
    )

    lines = group_lines(
        words
    )

    starts = find_records(
        lines
    )

    records = []

    for n, item in enumerate(starts):

        start = item["start"]
        code_index = item["code_line"]

        project_name = parse_name(
            lines,
            start,
            code_index
        )

        agency, state = parse_agency_state(
            lines,
            code_index
        )

        code_y = lines[
            code_index
        ]["y"]

        if n + 1 < len(starts):

            next_start = starts[
                n + 1
            ]["start"]

            end_y = lines[
                next_start
            ]["y"]

        else:

            end_y = page.rect.height

        # Stop before totals.
        for i in range(
            code_index,
            min(
                next_start
                if n + 1 < len(starts)
                else len(lines),
                len(lines)
            )
        ):

            t = line_text(
                lines[i]
            ).lower().strip()

            if (
                t == "total"
                or t.startswith("total ")
                or "grand total" in t
            ):

                end_y = lines[i]["y"]
                break

        fields = extract_fields(
            words,
            code_y,
            end_y
        )

        records.append({
            "serial_no": item["serial"],
            "project_code": item["code"],
            "project_name": project_name,
            "agency": agency,
            "state": state,
            **fields,
            "source_page": page_no,
        })

    return records


def main():

    if not PDF.exists():
        raise FileNotFoundError(
            PDF
        )

    pdf = pymupdf.open(
        PDF
    )

    all_records = []

    for page_no in range(
        START_PAGE,
        END_PAGE + 1
    ):

        all_records.extend(
            extract_page(
                pdf[page_no - 1],
                page_no
            )
        )

    pdf.close()

    # Deduplicate by project code.
    unique = {}

    for r in all_records:

        code = r[
            "project_code"
        ]

        if code not in unique:
            unique[code] = r

    all_records = list(
        unique.values()
    )

    all_records.sort(
        key=lambda r: (
            r["source_page"],
            r["serial_no"]
        )
    )

    unique_codes = {
        r["project_code"]
        for r in all_records
    }

    missing_names = [
        r
        for r in all_records
        if not r.get("project_name")
    ]

    print("=" * 90)
    print(
        "2018-19 APRIL HISTORICAL EXTRACTION"
    )
    print("=" * 90)

    print(
        f"Expected records : {EXPECTED_PROJECTS}"
    )

    print(
        f"Extracted records: {len(all_records)}"
    )

    print(
        f"Unique codes     : {len(unique_codes)}"
    )

    print(
        f"Missing names    : {len(missing_names)}"
    )

    serials = [
        r["serial_no"]
        for r in all_records
    ]

    print(
        f"Serial range     : "
        f"{min(serials)} - {max(serials)}"
    )

    print("\nKEY VALIDATION RECORDS")

    targets = [
        "020100044",
        "N04000073",
        "N24000561",
        "N28000062",
        "N28000101",
        "N28000104",
    ]

    for code in targets:

        for r in all_records:

            if r["project_code"] == code:

                print(
                    r["serial_no"],
                    "|",
                    r["project_code"],
                    "|",
                    r["project_name"],
                    "|",
                    r["agency"],
                    "|",
                    r["state"]
                )

    print("\nFIRST 5")

    for r in all_records[:5]:

        print(
            r["serial_no"],
            "|",
            r["project_code"],
            "|",
            r["project_name"],
            "|",
            r["agency"],
            "|",
            r["state"]
        )

    print("\nLAST 5")

    for r in all_records[-5:]:

        print(
            r["serial_no"],
            "|",
            r["project_code"],
            "|",
            r["project_name"],
            "|",
            r["agency"],
            "|",
            r["state"]
        )

    if missing_names:

        print("\nMISSING NAMES")

        for r in missing_names:

            print(
                r["serial_no"],
                "|",
                r["project_code"],
                "| page",
                r["source_page"]
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
            all_records,
            f,
            indent=2,
            ensure_ascii=False
        )

    print("\nSaved:")
    print(OUTPUT)

    print("=" * 90)


if __name__ == "__main__":
    main()
