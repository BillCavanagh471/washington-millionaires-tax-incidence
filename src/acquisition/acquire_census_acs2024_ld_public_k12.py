from pathlib import Path
import csv
import json
import os
import urllib.parse
import urllib.request


YEAR = 2024
STATE_FIPS = "53"

BASE_URL = f"https://api.census.gov/data/{YEAR}/acs/acs5"
GROUP = "B14002"

RAW_DIR = Path("data/raw/census")
RAW_JSON = RAW_DIR / "acs2024_wa_ld_public_k12_raw.json"
OUTPUT_CSV = RAW_DIR / "acs2024_wa_ld_public_k12.csv"


def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def main():

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("CENSUS_API_KEY")

    if not api_key:
        raise RuntimeError(
            "CENSUS_API_KEY is not set in this PowerShell session."
        )

    # ------------------------------------------------------------
    # Retrieve official B14002 metadata.
    # ------------------------------------------------------------

    metadata_url = f"{BASE_URL}/groups/{GROUP}.json"
    metadata = get_json(metadata_url)

    variables = metadata["variables"]

    # We deliberately identify variables from their Census labels
    # rather than hard-coding assumptions about column numbers.
    #
    # Desired universe:
    #   Male/Female
    #   Enrolled in PUBLIC school
    #   Kindergarten through grade 12
    #
    # Exclude:
    #   nursery/preschool
    #   private school
    #   college
    #   graduate/professional school

    desired_levels = (
        "kindergarten",
        "grade 1 to grade 4",
        "grade 5 to grade 8",
        "grade 9 to grade 12",
    )

    selected = []

    for variable, info in variables.items():

        if not variable.endswith("E"):
            continue

        label = info.get("label", "")
        label_lower = label.lower()

        if "public school" not in label_lower:
            continue

        if not any(
            level in label_lower
            for level in desired_levels
        ):
            continue

        selected.append(
            (
                variable,
                label,
            )
        )

    selected.sort()

    print("2024 ACS 5-YEAR PUBLIC K-12 ENROLLMENT")
    print("=" * 80)
    print(f"Table: {GROUP}")
    print()
    print("SELECTED VARIABLES")
    print("-" * 80)

    for variable, label in selected:
        print(f"{variable}: {label}")

    print()
    print(f"Selected estimate variables: {len(selected)}")

    # We expect:
    #   4 school levels x 2 sexes = 8 variables.

    if len(selected) != 8:
        raise RuntimeError(
            "Expected exactly 8 public K-12 estimate variables "
            f"from B14002; found {len(selected)}. "
            "Inspect Census metadata before continuing."
        )

    variable_names = [
        variable
        for variable, _ in selected
    ]

    # ------------------------------------------------------------
    # Retrieve all Washington upper-chamber legislative districts.
    #
    # Washington legislative districts elect one senator and two
    # representatives from the same district boundaries, so the
    # Census upper-chamber geography gives us the 49 LD geography.
    # ------------------------------------------------------------

    params = {
        "get": ",".join(
            ["NAME"] + variable_names
        ),
        "for": "state legislative district (upper chamber):*",
        "in": f"state:{STATE_FIPS}",
        "key": api_key,
    }

    query_url = (
        BASE_URL
        + "?"
        + urllib.parse.urlencode(
            params,
            safe=",:*()",
        )
    )

    data = get_json(query_url)

    header = data[0]
    rows = data[1:]

    print()
    print(f"Rows returned: {len(rows)}")

    if len(rows) != 49:
        raise RuntimeError(
            f"Expected 49 Washington legislative districts; "
            f"received {len(rows)}."
        )

    # Preserve raw metadata + response for provenance.

    raw_package = {
        "year": YEAR,
        "dataset": "acs/acs5",
        "table": GROUP,
        "state_fips": STATE_FIPS,
        "selected_variables": [
            {
                "variable": variable,
                "label": label,
            }
            for variable, label in selected
        ],
        "metadata_url": metadata_url,
        "response_header": header,
        "response_rows": rows,
    }

    RAW_JSON.write_text(
        json.dumps(
            raw_package,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------------
    # Convert to clean LD-level output.
    # ------------------------------------------------------------

    index = {
        name: position
        for position, name in enumerate(header)
    }

    output_rows = []

    for row in rows:

        ld_code = row[
            index[
                "state legislative district "
                "(upper chamber)"
            ]
        ]

        components = {}

        public_k12 = 0

        for variable, label in selected:

            value = row[index[variable]]

            if value in (None, "", "null"):
                numeric = 0
            else:
                numeric = int(value)

            components[variable] = numeric
            public_k12 += numeric

        output_rows.append(
            {
                "legislative_district": int(ld_code),
                "census_name": row[index["NAME"]],
                "public_k12_enrollment_estimate": public_k12,
                **components,
            }
        )

    output_rows.sort(
        key=lambda x: x["legislative_district"]
    )

    statewide = sum(
        row["public_k12_enrollment_estimate"]
        for row in output_rows
    )

    for row in output_rows:

        row["public_k12_share"] = (
            row["public_k12_enrollment_estimate"]
            / statewide
            if statewide
            else 0
        )

    fieldnames = list(output_rows[0].keys())

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(output_rows)

    print()
    print("RESULT")
    print("-" * 80)
    print(
        f"Statewide ACS public K-12 enrollment estimate: "
        f"{statewide:,}"
    )
    print(
        f"LD shares sum: "
        f"{sum(r['public_k12_share'] for r in output_rows):.12f}"
    )

    print()
    print("TOP 10 LEGISLATIVE DISTRICTS")
    print("-" * 80)

    for row in sorted(
        output_rows,
        key=lambda x: x["public_k12_enrollment_estimate"],
        reverse=True,
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"{row['public_k12_enrollment_estimate']:>7,} "
            f"({row['public_k12_share']:.2%})"
        )

    print()
    print("OUTPUTS")
    print("-" * 80)
    print(RAW_JSON)
    print(OUTPUT_CSV)


if __name__ == "__main__":
    main()