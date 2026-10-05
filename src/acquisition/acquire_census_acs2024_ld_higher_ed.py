from pathlib import Path
import csv
import json
import os
import urllib.parse
import urllib.request


YEAR = 2024
STATE_FIPS = "53"
GROUP = "B14004"

BASE_URL = f"https://api.census.gov/data/{YEAR}/acs/acs5"

OUTPUT_DIR = Path("data/raw/census")

RAW_OUTPUT = (
    OUTPUT_DIR
    / "acs2024_wa_ld_higher_ed_raw.json"
)

CSV_OUTPUT = (
    OUTPUT_DIR
    / "acs2024_wa_ld_higher_ed.csv"
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
    # Retrieve official table metadata.
    # ------------------------------------------------------------

    metadata_url = census_url(
        f"groups/{GROUP}.json"
    )

    metadata = get_json(
        metadata_url
    )

    variables = metadata["variables"]

    print(
        f"Table: {GROUP}"
    )

    # Census group metadata sometimes puts the descriptive
    # table title in "description" rather than "name".
    concept = (
        metadata.get("description")
        or metadata.get("name")
        or "UNKNOWN"
    )

    print(
        f"Concept: {concept}"
    )

    # ------------------------------------------------------------
    # Inventory estimate variables.
    # ------------------------------------------------------------

    estimate_variables = []

    for variable, info in variables.items():

        if not variable.startswith(
            GROUP + "_"
        ):
            continue

        if not variable.endswith("E"):
            continue

        if variable.endswith("EA"):
            continue

        label = info.get(
            "label",
            "",
        )

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
        key=lambda x:
            x["variable"]
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
    # Identify PUBLIC and PRIVATE college / graduate-school
    # enrollment leaf variables.
    #
    # B14004 contains sex -> enrollment type -> age.
    # We want the age-level cells underneath the public/private
    # branches, not their parent totals.
    # ------------------------------------------------------------

    public_candidates = []
    private_candidates = []

    for item in estimate_variables:

        label_lower = (
            item["label"].lower()
        )

        if (
            "enrolled in public college "
            "or graduate school"
            in label_lower
        ):
            public_candidates.append(
                item
            )

        if (
            "enrolled in private college "
            "or graduate school"
            in label_lower
        ):
            private_candidates.append(
                item
            )

    if not public_candidates:
        raise RuntimeError(
            "No public college enrollment "
            "variables identified."
        )

    if not private_candidates:
        raise RuntimeError(
            "No private college enrollment "
            "variables identified."
        )

    # ------------------------------------------------------------
    # Select deepest hierarchy level.
    #
    # This should retain the age-specific cells for male/female
    # while excluding the public/private parent subtotal.
    # ------------------------------------------------------------

    public_max_depth = max(
        item["label"].count("!!")
        for item in public_candidates
    )

    private_max_depth = max(
        item["label"].count("!!")
        for item in private_candidates
    )

    public_selected = [
        item
        for item in public_candidates
        if item["label"].count("!!")
        == public_max_depth
    ]

    private_selected = [
        item
        for item in private_candidates
        if item["label"].count("!!")
        == private_max_depth
    ]

    print()
    print(
        "SELECTED PUBLIC COLLEGE / "
        "GRADUATE SCHOOL VARIABLES"
    )
    print("-" * 80)

    for item in public_selected:
        print(
            f"{item['variable']}: "
            f"{item['label']}"
        )

    print()
    print(
        f"Selected public variables: "
        f"{len(public_selected)}"
    )

    print()
    print(
        "SELECTED PRIVATE COLLEGE / "
        "GRADUATE SCHOOL VARIABLES"
    )
    print("-" * 80)

    for item in private_selected:
        print(
            f"{item['variable']}: "
            f"{item['label']}"
        )

    print()
    print(
        f"Selected private variables: "
        f"{len(private_selected)}"
    )

    # B14004 should give:
    #
    # male:
    #   15-17
    #   18-24
    #   25-34
    #   35+
    #
    # female:
    #   15-17
    #   18-24
    #   25-34
    #   35+
    #
    # = 8 public and 8 private leaf cells.

    if len(public_selected) != 8:
        raise RuntimeError(
            "Expected exactly 8 public "
            f"leaf variables; found "
            f"{len(public_selected)}."
        )

    if len(private_selected) != 8:
        raise RuntimeError(
            "Expected exactly 8 private "
            f"leaf variables; found "
            f"{len(private_selected)}."
        )

    public_names = [
        item["variable"]
        for item in public_selected
    ]

    private_names = [
        item["variable"]
        for item in private_selected
    ]

    selected_names = (
        public_names
        + private_names
    )

    # ------------------------------------------------------------
    # Retrieve all 49 WA upper-chamber legislative districts.
    # ------------------------------------------------------------

    get_fields = [
        "NAME",
        *selected_names,
    ]

    params = {
        "get":
            ",".join(get_fields),

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

    data = get_json(
        data_url
    )

    header = data[0]
    records = data[1:]

    print()
    print(
        f"Rows returned: "
        f"{len(records)}"
    )

    if len(records) != 49:
        raise RuntimeError(
            "Expected 49 Washington "
            "legislative districts; "
            f"Census returned "
            f"{len(records)}."
        )

    # ------------------------------------------------------------
    # Build district-level estimates.
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

        component_values = {}

        for variable in selected_names:

            raw_value = source.get(
                variable
            )

            if raw_value in (
                None,
                "",
                "null",
            ):
                value = 0
            else:
                value = int(
                    raw_value
                )

            if value < 0:
                raise RuntimeError(
                    "Unexpected negative "
                    f"Census value for "
                    f"LD {ld}, "
                    f"{variable}: "
                    f"{value}"
                )

            component_values[
                variable
            ] = value

        public_estimate = sum(
            component_values[v]
            for v in public_names
        )

        private_estimate = sum(
            component_values[v]
            for v in private_names
        )

        total_estimate = (
            public_estimate
            + private_estimate
        )

        rows.append(
            {
                "legislative_district":
                    ld,

                "census_name":
                    source["NAME"],

                "public_higher_ed_enrollment_estimate":
                    public_estimate,

                "private_higher_ed_enrollment_estimate":
                    private_estimate,

                "total_higher_ed_enrollment_estimate":
                    total_estimate,

                **component_values,
            }
        )

    rows.sort(
        key=lambda x:
            x["legislative_district"]
    )

    if [
        row["legislative_district"]
        for row in rows
    ] != list(range(1, 50)):

        raise RuntimeError(
            "Legislative districts are "
            "not exactly 1 through 49."
        )

    # ------------------------------------------------------------
    # Statewide controls.
    # ------------------------------------------------------------

    statewide_public = sum(
        row[
            "public_higher_ed_enrollment_estimate"
        ]
        for row in rows
    )

    statewide_private = sum(
        row[
            "private_higher_ed_enrollment_estimate"
        ]
        for row in rows
    )

    statewide_total = sum(
        row[
            "total_higher_ed_enrollment_estimate"
        ]
        for row in rows
    )

    if statewide_public <= 0:
        raise RuntimeError(
            "Statewide public higher-ed "
            "estimate is not positive."
        )

    if statewide_total <= 0:
        raise RuntimeError(
            "Statewide total higher-ed "
            "estimate is not positive."
        )

    for row in rows:

        row[
            "public_higher_ed_ld_share"
        ] = (
            row[
                "public_higher_ed_enrollment_estimate"
            ]
            / statewide_public
        )

        row[
            "total_higher_ed_ld_share"
        ] = (
            row[
                "total_higher_ed_enrollment_estimate"
            ]
            / statewide_total
        )

    public_share_sum = sum(
        row[
            "public_higher_ed_ld_share"
        ]
        for row in rows
    )

    total_share_sum = sum(
        row[
            "total_higher_ed_ld_share"
        ]
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

        "metadata_url":
            metadata_url,

        "data_url":
            data_url,

        "public_selected_variables":
            public_selected,

        "private_selected_variables":
            private_selected,

        "metadata":
            metadata,

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
    # Save processed CSV.
    # ------------------------------------------------------------

    fieldnames = [
        "legislative_district",
        "census_name",

        "public_higher_ed_enrollment_estimate",
        "private_higher_ed_enrollment_estimate",
        "total_higher_ed_enrollment_estimate",

        "public_higher_ed_ld_share",
        "total_higher_ed_ld_share",

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
        writer.writerows(
            rows
        )

    # ------------------------------------------------------------
    # Report.
    # ------------------------------------------------------------

    print()
    print("STATEWIDE CONTROLS")
    print("-" * 80)

    print(
        f"Public college / graduate "
        f"enrollment : "
        f"{statewide_public:,}"
    )

    print(
        f"Private college / graduate "
        f"enrollment: "
        f"{statewide_private:,}"
    )

    print(
        f"Total college / graduate "
        f"enrollment  : "
        f"{statewide_total:,}"
    )

    print(
        f"Public share of enrollment  : "
        f"{statewide_public / statewide_total:.2%}"
    )

    print(
        f"Public LD share sum         : "
        f"{public_share_sum:.12f}"
    )

    print(
        f"Total LD share sum          : "
        f"{total_share_sum:.12f}"
    )

    # ------------------------------------------------------------
    # Rankings using PUBLIC enrollment.
    # ------------------------------------------------------------

    ranked_public = sorted(
        rows,
        key=lambda x:
            x[
                "public_higher_ed_enrollment_estimate"
            ],
        reverse=True,
    )

    print()
    print(
        "TOP 10 LDs -- PUBLIC "
        "COLLEGE / GRADUATE ENROLLMENT"
    )
    print("-" * 80)

    for row in ranked_public[:10]:

        print(
            f"LD "
            f"{row['legislative_district']:>2}: "
            f"{row['public_higher_ed_enrollment_estimate']:>7,}  "
            f"{row['public_higher_ed_ld_share']:>6.2%}"
        )

    print()
    print(
        "BOTTOM 10 LDs -- PUBLIC "
        "COLLEGE / GRADUATE ENROLLMENT"
    )
    print("-" * 80)

    for row in ranked_public[-10:]:

        print(
            f"LD "
            f"{row['legislative_district']:>2}: "
            f"{row['public_higher_ed_enrollment_estimate']:>7,}  "
            f"{row['public_higher_ed_ld_share']:>6.2%}"
        )

    # ------------------------------------------------------------
    # Compare public-vs-total geography.
    # ------------------------------------------------------------

    comparison = []

    for row in rows:

        difference = (
            row[
                "public_higher_ed_ld_share"
            ]
            - row[
                "total_higher_ed_ld_share"
            ]
        )

        comparison.append(
            (
                abs(difference),
                difference,
                row,
            )
        )

    comparison.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    print()
    print(
        "LARGEST PUBLIC-vs-TOTAL "
        "GEOGRAPHIC SHARE DIFFERENCES"
    )
    print("-" * 80)

    for _, difference, row in comparison[:10]:

        print(
            f"LD "
            f"{row['legislative_district']:>2}: "
            f"public="
            f"{row['public_higher_ed_ld_share']:>6.2%}  "
            f"all="
            f"{row['total_higher_ed_ld_share']:>6.2%}  "
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