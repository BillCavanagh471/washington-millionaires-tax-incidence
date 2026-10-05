from pathlib import Path
import csv
import json
import os
import urllib.parse
import urllib.request


YEAR = 2024
STATE_FIPS = "53"
GROUP = "B09001"

BASE_URL = f"https://api.census.gov/data/{YEAR}/acs/acs5"

OUTPUT_DIR = Path("data/raw/census")

RAW_OUTPUT = (
    OUTPUT_DIR
    / "acs2024_wa_ld_fair_start_raw.json"
)

CSV_OUTPUT = (
    OUTPUT_DIR
    / "acs2024_wa_ld_fair_start.csv"
)

# B09001:
# 003 = Under 3 years, in households
# 004 = 3 and 4 years, in households
#
# Together these give our simple under-5 geographic proxy.

UNDER_3 = "B09001_003E"
AGE_3_4 = "B09001_004E"

SELECTED_VARIABLES = [
    UNDER_3,
    AGE_3_4,
]


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

    if not api_key:
        raise RuntimeError(
            "CENSUS_API_KEY is not set."
        )

    # ------------------------------------------------------------
    # Retrieve table metadata.
    # ------------------------------------------------------------

    metadata_url = census_url(
        f"groups/{GROUP}.json"
    )

    metadata = get_json(
        metadata_url
    )

    variables = metadata["variables"]

    print(
        "FAIR START GEOGRAPHY ACQUISITION v0.1"
    )
    print("=" * 80)

    print()
    print(f"Table: {GROUP}")
    print(
        "Concept: Population Under 18 Years by Age"
    )

    print()
    print("SELECTED VARIABLES")
    print("-" * 80)

    for variable in SELECTED_VARIABLES:

        info = variables.get(variable)

        if info is None:
            raise RuntimeError(
                f"{variable} not found in "
                f"{GROUP} metadata."
            )

        print(
            f"{variable}: "
            f"{info.get('label', '')}"
        )

    # ------------------------------------------------------------
    # Retrieve WA upper-chamber legislative districts.
    # ------------------------------------------------------------

    params = {
        "get":
            "NAME,"
            + ",".join(
                SELECTED_VARIABLES
            ),

        "for":
            "state legislative district "
            "(upper chamber):*",

        "in":
            f"state:{STATE_FIPS}",

        "key":
            api_key,
    }

    data_url = census_url(
        params=params
    )

    data = get_json(
        data_url
    )

    header = data[0]
    records = data[1:]

    print()
    print(
        f"Rows returned: {len(records)}"
    )

    if len(records) != 49:
        raise RuntimeError(
            "Expected 49 Washington "
            "legislative districts; "
            f"received {len(records)}."
        )

    # ------------------------------------------------------------
    # Build district records.
    # ------------------------------------------------------------

    rows = []

    for record in records:

        source = dict(
            zip(
                header,
                record,
            )
        )

        ld = int(
            source[
                "state legislative district "
                "(upper chamber)"
            ]
        )

        under_3 = int(
            source[UNDER_3]
        )

        age_3_4 = int(
            source[AGE_3_4]
        )

        if under_3 < 0 or age_3_4 < 0:
            raise RuntimeError(
                f"Unexpected negative Census "
                f"value in LD {ld}."
            )

        under_5 = (
            under_3
            + age_3_4
        )

        rows.append(
            {
                "legislative_district":
                    ld,

                "census_name":
                    source["NAME"],

                "children_under_3":
                    under_3,

                "children_age_3_4":
                    age_3_4,

                "children_under_5":
                    under_5,
            }
        )

    rows.sort(
        key=lambda x:
            x["legislative_district"]
    )

    expected_lds = list(
        range(1, 50)
    )

    observed_lds = [
        row["legislative_district"]
        for row in rows
    ]

    if observed_lds != expected_lds:
        raise RuntimeError(
            "Legislative districts are "
            "not exactly 1 through 49."
        )

    # ------------------------------------------------------------
    # Statewide controls.
    # ------------------------------------------------------------

    statewide_under_3 = sum(
        row["children_under_3"]
        for row in rows
    )

    statewide_age_3_4 = sum(
        row["children_age_3_4"]
        for row in rows
    )

    statewide_under_5 = sum(
        row["children_under_5"]
        for row in rows
    )

    if statewide_under_5 <= 0:
        raise RuntimeError(
            "Statewide under-5 population "
            "is not positive."
        )

    for row in rows:

        row["under_5_ld_share"] = (
            row["children_under_5"]
            / statewide_under_5
        )

    share_sum = sum(
        row["under_5_ld_share"]
        for row in rows
    )

    # ------------------------------------------------------------
    # Preserve raw acquisition evidence.
    # ------------------------------------------------------------

    raw_package = {
        "year": YEAR,

        "dataset":
            "ACS 5-Year Estimates "
            "Detailed Tables",

        "group":
            GROUP,

        "state_fips":
            STATE_FIPS,

        "geography":
            "Washington State Legislative "
            "District (Upper Chamber)",

        "method":
            (
                "Fair Start baseline geographic "
                "proxy = B09001_003E "
                "(under 3 years in households) "
                "+ B09001_004E "
                "(3 and 4 years in households)."
            ),

        "metadata_url":
            metadata_url,

        "data_url":
            data_url,

        "selected_variables":
            {
                variable:
                    variables[variable]
                for variable
                in SELECTED_VARIABLES
            },

        "api_response":
            data,
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
    # Write processed CSV.
    # ------------------------------------------------------------

    fieldnames = [
        "legislative_district",
        "census_name",
        "children_under_3",
        "children_age_3_4",
        "children_under_5",
        "under_5_ld_share",
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
    print("STATEWIDE CONTROLS")
    print("-" * 80)

    print(
        f"Children under 3           : "
        f"{statewide_under_3:,}"
    )

    print(
        f"Children age 3-4           : "
        f"{statewide_age_3_4:,}"
    )

    print(
        f"Children under 5           : "
        f"{statewide_under_5:,}"
    )

    print(
        f"LD share sum               : "
        f"{share_sum:.12f}"
    )

    ranked = sorted(
        rows,
        key=lambda x:
            x["children_under_5"],
        reverse=True,
    )

    print()
    print(
        "TOP 10 LDs -- CHILDREN UNDER 5"
    )
    print("-" * 80)

    for row in ranked[:10]:

        print(
            f"LD "
            f"{row['legislative_district']:>2}: "
            f"{row['children_under_5']:>7,}  "
            f"{row['under_5_ld_share']:>6.2%}"
        )

    print()
    print(
        "BOTTOM 10 LDs -- CHILDREN UNDER 5"
    )
    print("-" * 80)

    for row in ranked[-10:]:

        print(
            f"LD "
            f"{row['legislative_district']:>2}: "
            f"{row['children_under_5']:>7,}  "
            f"{row['under_5_ld_share']:>6.2%}"
        )

    print()
    print(
        "DEVIATION FROM EQUAL 1/49 SHARE"
    )
    print("-" * 80)

    equal_share = 1 / 49

    deviations = sorted(
        rows,
        key=lambda x:
            abs(
                x["under_5_ld_share"]
                - equal_share
            ),
        reverse=True,
    )

    for row in deviations[:10]:

        difference = (
            row["under_5_ld_share"]
            - equal_share
        )

        print(
            f"LD "
            f"{row['legislative_district']:>2}: "
            f"share="
            f"{row['under_5_ld_share']:>6.2%}  "
            f"equal="
            f"{equal_share:>6.2%}  "
            f"diff="
            f"{difference:+.2%}"
        )

    print()
    print("OUTPUT")
    print("-" * 80)

    print(RAW_OUTPUT)
    print(CSV_OUTPUT)


if __name__ == "__main__":
    main()