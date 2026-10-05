import csv
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


YEAR = 2024
DATASET = "acs/acs5"
STATE_FIPS = "53"  # Washington
VARIABLE = "B19013_001E"

OUTPUT_DIR = Path("data/raw/census")
OUTPUT_CSV = OUTPUT_DIR / "acs2024_wa_ld_median_household_income.csv"
OUTPUT_JSON = OUTPUT_DIR / "acs2024_wa_ld_median_household_income_raw.json"


def main():
    api_key = os.environ.get("CENSUS_API_KEY")

    if not api_key:
        raise RuntimeError(
            "CENSUS_API_KEY environment variable is not set."
        )

    params = {
        "get": f"NAME,{VARIABLE}",
        "for": "state legislative district (upper chamber):*",
        "in": f"state:{STATE_FIPS}",
        "key": api_key,
    }

    url = (
        f"https://api.census.gov/data/{YEAR}/{DATASET}?"
        + urlencode(params)
    )

    print("Requesting Census ACS data...")
    print(f"Dataset: {YEAR} ACS 5-Year")
    print(f"Variable: {VARIABLE}")
    print("Geography: Washington legislative districts")

    with urlopen(url) as response:
        data = json.load(response)

    header = data[0]
    records = data[1:]

    print(f"Rows returned: {len(records)}")

    if len(records) != 49:
        raise RuntimeError(
            f"Expected 49 Washington legislative districts; "
            f"received {len(records)}."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Preserve the original API response.
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Create a clean analytical CSV.
    name_idx = header.index("NAME")
    income_idx = header.index(VARIABLE)
    district_idx = header.index(
        "state legislative district (upper chamber)"
    )

    clean_rows = []

    for row in records:
        clean_rows.append(
            {
                "legislative_district": int(row[district_idx]),
                "median_household_income": int(row[income_idx]),
                "census_name": row[name_idx],
                "acs_year": YEAR,
                "acs_dataset": "ACS 5-Year",
                "acs_table": "B19013",
                "acs_variable": VARIABLE,
            }
        )

    clean_rows.sort(key=lambda x: x["legislative_district"])

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "legislative_district",
                "median_household_income",
                "census_name",
                "acs_year",
                "acs_dataset",
                "acs_table",
                "acs_variable",
            ],
        )
        writer.writeheader()
        writer.writerows(clean_rows)

    print()
    print("Acquisition complete.")
    print(f"Raw JSON : {OUTPUT_JSON}")
    print(f"Clean CSV: {OUTPUT_CSV}")
    print()
    print(
        "Median household income range: "
        f"${min(r['median_household_income'] for r in clean_rows):,} "
        "to "
        f"${max(r['median_household_income'] for r in clean_rows):,}"
    )


if __name__ == "__main__":
    main()