from pathlib import Path
import json
import re
import pymupdf


# ============================================================
# CONFIGURATION
# ============================================================

PDF = Path("raw/2024-25/monthly/April_Part-II_List_of_tables.pdf")

OUTPUT = Path(
    "processed/extracted/historical_2024_april.json"
)

START_PAGE = 462
END_PAGE = 572


# ============================================================
# REGEX
# ============================================================

DATE_RE = re.compile(
    r"^\(?\[?(\d{1,2}/\d{4})\]?\)?$"
)

NUMBER_RE = re.compile(
    r"^[(\[]?-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)[)\]]?$"
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
    v = str(value).replace(",", "").replace("[", "").replace("]", "").replace("(", "").replace(")", "").strip()
    if not NUMBER_RE.match(v):
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ============================================================
# PARSE ANNEXURE XVIII
# ============================================================

def extract_2024_projects():
    if not PDF.exists():
        raise FileNotFoundError(f"PDF not found: {PDF}")

    doc = pymupdf.open(PDF)

    # Load historical code lookup
    hist_files = [
        Path("processed/extracted/historical_2017_april.json"),
        Path("processed/extracted/historical_2018_april.json"),
        Path("processed/extracted/historical_2019_april.json"),
        Path("processed/extracted/historical_2020_april.json"),
        Path("processed/extracted/historical_2021_april.json"),
        Path("processed/extracted/historical_2022_april.json"),
        Path("processed/extracted/historical_2023_april.json"),
    ]

    name_to_code = {}
    for hf in hist_files:
        if hf.exists():
            with hf.open("r", encoding="utf-8") as f:
                data = json.load(f)
                for r in data:
                    if r.get("project_name") and r.get("project_code"):
                        key = re.sub(r"[^A-Za-z0-9]", "", r["project_name"].upper())
                        name_to_code[key] = r["project_code"]

    records = []
    current_state = None
    current_sector = None
    serial_counter = 0

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

        # Identify serial tokens (x0 < 45, integer)
        serials = [w for w in words if w["x0"] < 45 and w["text"].isdigit() and w["y0"] > 200]

        for i, s_word in enumerate(serials):
            serial_counter += 1
            s_y = s_word["y0"]
            next_s_y = serials[i + 1]["y0"] if i + 1 < len(serials) else 800.0

            # Find state / sector headers before s_y on page
            for w in words:
                if 45 <= w["x0"] < 210 and w["y0"] < s_y and (i == 0 or w["y0"] > serials[i-1]["y0"]):
                    text_str = w["text"]
                    if text_str.isupper() and len(text_str) > 3 and text_str not in {"PROJECT", "SI.NO", "TABLE", "ANNEXURE", "DETAILS"}:
                        if text_str in {"ANDAMAN AND NICOBAR ISLANDS", "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM", "BIHAR", "CHHATTISGARH", "DELHI", "GOA", "GUJARAT", "HARYANA", "HIMACHAL PRADESH", "JAMMU AND KASHMIR", "JHARKHAND", "KARNATAKA", "KERALA", "LADAKH", "MADHYA PRADESH", "MAHARASHTRA", "MANIPUR", "MEGHALAYA", "MIZORAM", "NAGALAND", "ODISHA", "PUDUCHERRY", "PUNJAB", "RAJASTHAN", "SIKKIM", "TAMIL NADU", "TELANGANA", "TRIPURA", "UTTAR PRADESH", "UTTARAKHAND", "WEST BENGAL", "MULTI STATE"}:
                            current_state = text_str

            # Collect project words
            proj_words = [w for w in words if s_y - 2 <= w["y0"] < next_s_y - 2]

            name_w = [w["text"] for w in proj_words if 45 <= w["x0"] < 210 and w["text"] not in {"SI.No", "Project"}]
            name_text = clean_text(" ".join(name_w))

            # Match code from history
            clean_key = re.sub(r"[^A-Za-z0-9]", "", name_text.upper()) if name_text else ""
            code = name_to_code.get(clean_key)
            if not code:
                # Try prefix match
                for hk, hc in name_to_code.items():
                    if clean_key and (clean_key.startswith(hk[:30]) or hk.startswith(clean_key[:30])):
                        code = hc
                        break

            # Approval date (x0 ~ 210-250)
            approval_date = None
            for w in proj_words:
                if 200 <= w["x0"] < 260:
                    m = DATE_RE.match(w["text"])
                    if m:
                        approval_date = m.group(1)
                        break

            # Cost column (x0 ~ 380-450)
            costs = []
            for w in proj_words:
                if 380 <= w["x0"] < 470:
                    val = w["text"].strip()
                    n = number(val)
                    if n is not None:
                        costs.append((w["y0"], w["x0"], n))

            costs.sort()
            original_cost = costs[0][2] if len(costs) >= 1 else None
            revised_cost = costs[1][2] if len(costs) >= 2 else None
            anticipated_cost = costs[2][2] if len(costs) >= 3 else (revised_cost if revised_cost else original_cost)

            # Cumulative Expenditure (x0 ~ 470-560)
            cumulative_expenditure = None
            for w in proj_words:
                if 470 <= w["x0"] < 560:
                    n = number(w["text"])
                    if n is not None:
                        cumulative_expenditure = n
                        break

            # Date of commissioning (x0 ~ 260-380)
            docs = []
            for w in proj_words:
                if 260 <= w["x0"] < 380:
                    m = DATE_RE.match(w["text"])
                    if m:
                        docs.append((w["y0"], w["x0"], m.group(1)))

            docs.sort()
            original_doc = docs[0][2] if len(docs) >= 1 else None
            revised_doc = docs[1][2] if len(docs) >= 2 else None
            anticipated_doc = docs[2][2] if len(docs) >= 3 else None

            record = {
                "serial": serial_counter,
                "project_code": code,
                "project_name": name_text if name_text else None,
                "agency": None,
                "state": current_state,
                "page": page_no,
                "approval_date": approval_date,
                "original_cost": original_cost,
                "revised_cost": revised_cost,
                "anticipated_cost": anticipated_cost,
                "cumulative_expenditure": cumulative_expenditure,
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
    print("2024-25 APRIL HISTORICAL EXTRACTION")
    print("=" * 100)

    records = extract_2024_projects()
    codes = [r["project_code"] for r in records if r["project_code"]]
    missing_names = [r for r in records if r["project_name"] is None]
    missing_codes = [r for r in records if r["project_code"] is None]

    print(f"\nExtracted records     : {len(records)}")
    print(f"Matched project codes : {len(codes)}")
    print(f"Missing codes         : {len(missing_codes)}")
    print(f"Missing names         : {len(missing_names)}")

    print("\nKEY VALIDATION RECORDS")
    for r in records[:10]:
        print(
            f"{r['serial']} | {r['project_code']} | {r['project_name']} | "
            f"{r['state']} | OrigCost={r['original_cost']} | "
            f"RevisedCost={r['revised_cost']} | AntCost={r['anticipated_cost']} | "
            f"Exp={r['cumulative_expenditure']}"
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"\nSaved: {OUTPUT}")


if __name__ == "__main__":
    main()
