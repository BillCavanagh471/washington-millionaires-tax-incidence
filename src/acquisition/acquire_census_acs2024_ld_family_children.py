import csv
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


YEAR = 2024
STATE_FIPS = "53"
DATASET = "acs/acs5"
GROUP = "B17010"

OUTPUT_DIR = Path("data/raw/census")
OUTPUT_CSV = OUTPUT_DIR / "acs2024_wa_ld_family_children.csv"
OUTPUT_JSON = OUTPUT_DIR / "acs2024_wa_ld_family_children_raw.json"


def get_group_metadata(api_key):
    url = (
        f"https://api.census.gov/data/{YEAR}/{DATASET}"
        f"/groups/{GROUP}.json?key={api_key}"
    )

    with urlopen(url) as response:
        return json.load(response)


def main():
    api_key = os.environ.get("CENSUS_API_KEY")

    if not api_key:
        raise RuntimeError(
            "CENSUS_API_KEY environment variable is not set."
        )

    print("Retrieving Census table metadata...")

    metadata = get_group_metadata(api_key)

    # Select estimate variables only.
    variables = sorted(
        variable
        for variable in metadata["variables"]
        if variable.startswith(f"{GROUP}_")
        and variable.endswith("E")
        and variable[len(GROUP) + 1:-1].isdigit()
    )

    print(f"Estimate variables found: {len(variables)}")

    params = {
        "get": "NAME," + ",".join(variables),
        "for": "state legislative district (upper chamber):*",
        "in": f"state:{STATE_FIPS}",
        "key": api_key,
    }

    url = (
        f"https://api.census.gov/data/{YEAR}/{DATASET}?"
        + urlencode(params)
    )

    print("Requesting Census ACS family/children data...")
    print(f"Dataset : {YEAR} ACS 5-Year")
    print(f"Table   : {GROUP}")
    print("Geography: Washington legislative districts")

    with urlopen(url) as response:
        data = json.load(response)

    header = data[0]
    records = data[1:]

    print(f"Rows returned: {len(records)}")

    if len(records) != 49:
        raise RuntimeError(
            f"Expected 49 districts; received {len(records)}."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": metadata,
                "data": data,
            },
            f,
            indent=2,
        )

    district_field = (
        "state legislative district (upper chamber)"
    )

    district_idx = header.index(district_field)
    name_idx = header.index("NAME")

    clean_rows = []

    for row in records:
        record = {
            "legislative_district": int(row[district_idx]),
            "census_name": row[name_idx],
        }

        for variable in variables:
            record[variable] = int(
                row[header.index(variable)]
            )

        clean_rows.append(record)

    clean_rows.sort(
        key=lambda x: x["legislative_district"]
    )

    fields = [
        "legislative_district",
        "census_name",
        *variables,
    ]

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(clean_rows)

    print()
    print("Acquisition complete.")
    print(f"Raw JSON : {OUTPUT_JSON}")
    print(f"Clean CSV: {OUTPUT_CSV}")

    total_variable = f"{GROUP}_001E"

    if total_variable in variables:
        statewide_total = sum(
            r[total_variable]
            for r in clean_rows
        )

        print(
            f"Statewide ACS families represented: "
            f"{statewide_total:,}"
        )


if __name__ == "__main__":
    main()