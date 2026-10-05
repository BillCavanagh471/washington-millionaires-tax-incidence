from pathlib import Path
import csv
import json
import os
import urllib.parse
import urllib.request


YEAR = 2024
STATE_FIPS = "53"
GROUP = "C27007"

BASE_URL = f"https://api.census.gov/data/{YEAR}/acs/acs5"

OUTPUT_DIR = Path("data/raw/census")

RAW_OUTPUT = (
    OUTPUT_DIR
    / "acs2024_wa_ld_medicaid_raw.json"
)

CSV_OUTPUT = (
    OUTPUT_DIR
    / "acs2024_wa_ld_medicaid.csv"
)


def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def census_url(path="", params=None):
    url = BASE_URL

    if path:
        url += "/" + path.lstrip("/")

    if params:
        url += "?" + urllib.parse.urlencode(
            params,
            safe=",:*",
        )

    return url


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    api_key = os.environ.get(
        "CENSUS_API_KEY"
    )

    # ------------------------------------------------------------
    # Retrieve table metadata.
    # ------------------------------------------------------------

    metadata_url = census_url(
        f"groups/{GROUP}.json"
    )

    metadata = get_json(metadata_url)

    variables = metadata["variables"]

    print(
        f"Table: {GROUP}"
    )

    print(
        f"Concept: "
        f"{metadata.get('name', 'UNKNOWN')}"
    )

    # ------------------------------------------------------------
    # Inspect all estimate variables.
    #
    # We deliberately identify Medicaid coverage dynamically from
    # Census metadata rather than hard-coding variable numbers.
    # ------------------------------------------------------------

    estimate_variables = []

    for variable, info in variables.items():

        if not variable.endswith("E"):
            continue

        if variable.endswith("EA"):
            continue

        label = info.get("label", "")

        estimate_variables.append(
            {
                "variable": variable,
                "label": label,
                "concept": info.get(
                    "concept",
                    "",
                ),
            }
        )

    estimate_variables.sort(
        key=lambda x: x["variable"]
    )

    print()
    print("ESTIMATE VARIABLES")
    print("-" * 80)

    for item in estimate_variables:
        print(
            f"{item['variable']}: "
            f"{item['label']}"
        )

    # ------------------------------------------------------------
    # Select Medicaid-covered population variables.
    #
    # C27007 is structured by sex and age, with coverage-status
    # branches. We want the leaf estimates for persons WITH
    # Medicaid/means-tested public coverage, not subtotals.
    #
    # We first identify candidate variables from their labels and
    # then remove any parent/subtotal categories.
    # ------------------------------------------------------------

    candidates = []

    for item in estimate_variables:

        label_lower = item["label"].lower()

        if (
            "with medicaid/means-tested public coverage"
            in label_lower
        ):
            candidates.append(item)

    if not candidates:
        raise RuntimeError(
            "No Medicaid coverage variables identified "
            "from Census metadata."
        )

    print()
    print("MEDICAID CANDIDATE VARIABLES")
    print("-" * 80)

    for item in candidates:
        print(
            f"{item['variable']}: "
            f"{item['label']}"
        )

    # ------------------------------------------------------------
    # Select leaf age/sex categories.
    #
    # A leaf category will normally contain multiple hierarchy
    # separators (!!), while broad totals contain fewer.
    #
    # We select the deepest Medicaid-positive categories so that
    # each person is represented once rather than summing both
    # parent and child categories.
    # ------------------------------------------------------------

    depths = [
        item["label"].count("!!")
        for item in candidates
    ]

    max_depth = max(depths)

    selected = [
        item
        for item in candidates
        if item["label"].count("!!")
        == max_depth
    ]

    print()
    print("SELECTED MEDICAID LEAF VARIABLES")
    print("-" * 80)

    for item in selected:
        print(
            f"{item['variable']}: "
            f"{item['label']}"
        )

    print()
    print(
        f"Selected variables: "
        f"{len(selected)}"
    )

    if len(selected) < 2:
        raise RuntimeError(
            "Unexpected Medicaid variable structure. "
            "Stopping rather than silently producing "
            "an unreliable estimate."
        )

    selected_names = [
        item["variable"]
        for item in selected
    ]

    # ------------------------------------------------------------
    # Retrieve all Washington upper-chamber legislative districts.
    # ------------------------------------------------------------

    get_fields = [
        "NAME",
        *selected_names,
    ]

    params = {
        "get": ",".join(get_fields),
        "for":
            "state legislative district "
            "(upper chamber):*",
        "in":
            f"state:{STATE_FIPS}",
    }

    if api_key:
        params["key"] = api_key

    data_url = census_url(
        params=params
    )

    data = get_json(data_url)

    header = data[0]
    records = data[1:]

    print()
    print(
        f"Rows returned: {len(records)}"
    )

    if len(records) != 49:
        raise RuntimeError(
            f"Expected 49 Washington legislative "
            f"districts; Census returned "
            f"{len(records)}."
        )

    # ------------------------------------------------------------
    # Build district-level Medicaid estimates.
    # ------------------------------------------------------------

    rows = []

    for record in records:

        row = dict(
            zip(header, record)
        )

        ld = int(
            row[
                "state legislative district "
                "(upper chamber)"
            ]
        )

        medicaid_estimate = 0

        component_values = {}

        for variable in selected_names:

            raw_value = row.get(variable)

            if raw_value in (
                None,
                "",
                "null",
            ):
                value = 0
            else:
                value = int(raw_value)

            # Census missing-value sentinel protection.
            if value < 0:
                raise RuntimeError(
                    f"Unexpected negative Census "
                    f"value for LD {ld}, "
                    f"{variable}: {value}"
                )

            component_values[
                variable
            ] = value

            medicaid_estimate += value

        rows.append(
            {
                "legislative_district":
                    ld,

                "census_name":
                    row["NAME"],

                "medicaid_means_tested_public_coverage_estimate":
                    medicaid_estimate,

                **component_values,
            }
        )

    rows.sort(
        key=lambda x:
            x["legislative_district"]
    )

    actual_lds = [
        row["legislative_district"]
        for row in rows
    ]

    if actual_lds != list(range(1, 50)):
        raise RuntimeError(
            "Legislative districts are not "
            "exactly 1 through 49."
        )

    statewide_medicaid = sum(
        row[
            "medicaid_means_tested_public_coverage_estimate"
        ]
        for row in rows
    )

    if statewide_medicaid <= 0:
        raise RuntimeError(
            "Statewide Medicaid estimate is "
            "not positive."
        )

    for row in rows:

        row["medicaid_ld_share"] = (
            row[
                "medicaid_means_tested_public_coverage_estimate"
            ]
            / statewide_medicaid
        )

    share_sum = sum(
        row["medicaid_ld_share"]
        for row in rows
    )

    # ------------------------------------------------------------
    # Save raw acquisition evidence.
    # ------------------------------------------------------------

    raw_package = {
        "year": YEAR,
        "dataset":
            "ACS 5-Year Estimates Detailed Tables",
        "group": GROUP,
        "state_fips": STATE_FIPS,
        "geography":
            "Washington State Legislative District "
            "(Upper Chamber)",
        "metadata_url": metadata_url,
        "data_url": data_url,
        "selected_variables": selected,
        "metadata": metadata,
        "api_response": data,
    }

    with RAW_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            raw_package,
            f,
            indent=2,
        )

    # ------------------------------------------------------------
    # Save processed acquisition CSV.
    # ------------------------------------------------------------

    fieldnames = [
        "legislative_district",
        "census_name",
        "medicaid_means_tested_public_coverage_estimate",
        "medicaid_ld_share",
        *selected_names,
    ]

    with CSV_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    # ------------------------------------------------------------
    # Report.
    # ------------------------------------------------------------

    print()
    print("STATEWIDE CONTROL")
    print("-" * 80)

    print(
        "ACS Medicaid/means-tested public "
        f"coverage estimate : "
        f"{statewide_medicaid:,}"
    )

    print(
        f"LD share sum       : "
        f"{share_sum:.12f}"
    )

    print()
    print("TOP 10 LEGISLATIVE DISTRICTS")
    print("-" * 80)

    ranked = sorted(
        rows,
        key=lambda x:
            x[
                "medicaid_means_tested_public_coverage_estimate"
            ],
        reverse=True,
    )

    for row in ranked[:10]:

        print(
            f"LD "
            f"{row['legislative_district']:>2}: "
            f"{row['medicaid_means_tested_public_coverage_estimate']:>8,}  "
            f"{row['medicaid_ld_share']:>6.2%}"
        )

    print()
    print("BOTTOM 10 LEGISLATIVE DISTRICTS")
    print("-" * 80)

    for row in ranked[-10:]:

        print(
            f"LD "
            f"{row['legislative_district']:>2}: "
            f"{row['medicaid_means_tested_public_coverage_estimate']:>8,}  "
            f"{row['medicaid_ld_share']:>6.2%}"
        )

    print()
    print("OUTPUT")
    print("-" * 80)

    print(RAW_OUTPUT)
    print(CSV_OUTPUT)


if __name__ == "__main__":
    main()