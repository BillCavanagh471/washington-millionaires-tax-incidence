"""
Build Fair Start legislative-district allocation v0.1.

Geographic methodology
----------------------
Allocate an illustrative statewide Fair Start pool among Washington's
49 legislative districts in proportion to the 2024 ACS 5-Year estimated
population of children under age 5 living in households.

ACS source:
    B09001_003E = under age 3
    B09001_004E = age 3 and 4

The ACS distribution is used only as a relative geographic proxy for
potential Fair Start beneficiaries. It is NOT an estimate of program
eligibility, childcare utilization, or future program enrollment.

Scenario treatment
------------------
FY2029:
    5% * $2.698B = $134.9M

FY2030:
    5% * $3.732B = $186.6M

These are illustrative same-FY-equivalent amounts for geographic
comparison. They do NOT represent the literal statutory cash-transfer
timing, which is based on prior-fiscal-year Millionaires Tax receipts.
"""

from pathlib import Path
import csv


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

INPUT_FILE = Path(
    "data/raw/census/acs2024_wa_ld_fair_start.csv"
)

OUTPUT_DIR = Path("data/processed/model")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = (
    OUTPUT_DIR / "fair_start_ld_allocation_v0_1.csv"
)


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

EXPECTED_LD_COUNT = 49
EXPECTED_STATEWIDE_UNDER5 = 432_371

FAIR_START_FY2029 = 134_900_000
FAIR_START_FY2030 = 186_600_000


def find_column(fieldnames, candidates):
    """
    Return the first matching candidate column.

    Matching is case-insensitive so the builder tolerates modest naming
    differences in the acquisition output.
    """

    lookup = {
        name.lower(): name
        for name in fieldnames
    }

    for candidate in candidates:
        match = lookup.get(candidate.lower())
        if match:
            return match

    return None


def load_source():
    with INPUT_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        reader = csv.DictReader(handle)

        fieldnames = reader.fieldnames or []

        ld_col = find_column(
            fieldnames,
            [
                "legislative_district",
                "district",
                "ld",
            ],
        )

        under3_col = find_column(
            fieldnames,
            [
                "under_3",
                "under3",
                "children_under_3",
                "B09001_003E",
            ],
        )

        age3_4_col = find_column(
            fieldnames,
            [
                "age_3_4",
                "age3_4",
                "age_3_and_4",
                "children_age_3_4",
                "B09001_004E",
            ],
        )

        under5_col = find_column(
            fieldnames,
            [
                "children_under_5",
                "under_5",
                "under5",
                "under5_population",
            ],
        )

        if ld_col is None:
            raise ValueError(
                "Could not identify legislative-district column. "
                f"Available columns: {fieldnames}"
            )

        if under5_col is None and (
            under3_col is None or age3_4_col is None
        ):
            raise ValueError(
                "Could not identify either an under-5 total column "
                "or both under-3 and age-3/4 columns. "
                f"Available columns: {fieldnames}"
            )

        rows = []

        for source_row in reader:
            district = int(float(source_row[ld_col]))

            if under5_col is not None:
                under5 = int(
                    round(float(source_row[under5_col]))
                )

                under3 = (
                    int(round(float(source_row[under3_col])))
                    if under3_col is not None
                    else None
                )

                age3_4 = (
                    int(round(float(source_row[age3_4_col])))
                    if age3_4_col is not None
                    else None
                )

            else:
                under3 = int(
                    round(float(source_row[under3_col]))
                )

                age3_4 = int(
                    round(float(source_row[age3_4_col]))
                )

                under5 = under3 + age3_4

            rows.append(
                {
                    "legislative_district": district,
                    "children_under_3": under3,
                    "children_age_3_4": age3_4,
                    "children_under_5": under5,
                }
            )

    return rows


def build_allocation(rows):
    statewide_under5 = sum(
        row["children_under_5"]
        for row in rows
    )

    for row in rows:
        share = (
            row["children_under_5"]
            / statewide_under5
        )

        row["under5_share"] = share

        row["fair_start_fy2029_134_9m"] = (
            FAIR_START_FY2029 * share
        )

        row["fair_start_fy2030_186_6m"] = (
            FAIR_START_FY2030 * share
        )

        row["equal_fair_start_fy2029"] = (
            FAIR_START_FY2029 / EXPECTED_LD_COUNT
        )

        row["equal_fair_start_fy2030"] = (
            FAIR_START_FY2030 / EXPECTED_LD_COUNT
        )

        row["fy2029_difference_from_equal"] = (
            row["fair_start_fy2029_134_9m"]
            - row["equal_fair_start_fy2029"]
        )

        row["fy2030_difference_from_equal"] = (
            row["fair_start_fy2030_186_6m"]
            - row["equal_fair_start_fy2030"]
        )

    return statewide_under5


def validate(rows, statewide_under5):
    assert len(rows) == EXPECTED_LD_COUNT, (
        f"Expected {EXPECTED_LD_COUNT} LDs, "
        f"found {len(rows)}."
    )

    districts = sorted(
        row["legislative_district"]
        for row in rows
    )

    assert districts == list(range(1, 50)), (
        "Legislative districts are not exactly 1-49."
    )

    assert statewide_under5 == EXPECTED_STATEWIDE_UNDER5, (
        f"Expected statewide under-5 population "
        f"{EXPECTED_STATEWIDE_UNDER5:,}, "
        f"found {statewide_under5:,}."
    )

    share_sum = sum(
        row["under5_share"]
        for row in rows
    )

    assert abs(share_sum - 1.0) < 1e-12

    fy2029_sum = sum(
        row["fair_start_fy2029_134_9m"]
        for row in rows
    )

    fy2030_sum = sum(
        row["fair_start_fy2030_186_6m"]
        for row in rows
    )

    assert abs(
        fy2029_sum - FAIR_START_FY2029
    ) < 0.01

    assert abs(
        fy2030_sum - FAIR_START_FY2030
    ) < 0.01


def write_csv(rows):
    fieldnames = [
        "legislative_district",
        "children_under_3",
        "children_age_3_4",
        "children_under_5",
        "under5_share",

        "fair_start_fy2029_134_9m",
        "fair_start_fy2030_186_6m",

        "equal_fair_start_fy2029",
        "equal_fair_start_fy2030",

        "fy2029_difference_from_equal",
        "fy2030_difference_from_equal",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def money(value):
    return f"${value:,.2f}"


def print_report(rows, statewide_under5):
    print()
    print(
        "FAIR START LEGISLATIVE-DISTRICT "
        "ALLOCATION v0.1"
    )
    print("=" * 80)

    print()
    print("GEOGRAPHIC CONTROL")
    print("-" * 80)
    print(
        f"Legislative districts          : "
        f"{len(rows)}"
    )
    print(
        f"ACS children under age 5       : "
        f"{statewide_under5:,}"
    )
    print(
        f"Geographic shares sum          : "
        f"{sum(r['under5_share'] for r in rows):.12f}"
    )

    print()
    print("FAIR START SCENARIO CONTROLS")
    print("-" * 80)
    print(
        f"FY2029 statewide pool          : "
        f"{money(FAIR_START_FY2029)}"
    )
    print(
        f"FY2030 statewide pool          : "
        f"{money(FAIR_START_FY2030)}"
    )

    print()
    print("ALLOCATION VALIDATION")
    print("-" * 80)

    fy2029_sum = sum(
        r["fair_start_fy2029_134_9m"]
        for r in rows
    )

    fy2030_sum = sum(
        r["fair_start_fy2030_186_6m"]
        for r in rows
    )

    print(
        f"FY2029 allocated total         : "
        f"{money(fy2029_sum)}"
    )
    print(
        f"FY2030 allocated total         : "
        f"{money(fy2030_sum)}"
    )

    print()
    print("LARGEST UNDER-5 GEOGRAPHIC SHARES")
    print("-" * 80)

    ranked = sorted(
        rows,
        key=lambda r: r["under5_share"],
        reverse=True,
    )

    for row in ranked[:10]:
        print(
            f"LD {row['legislative_district']:>2}: "
            f"{row['children_under_5']:>7,} children  "
            f"{row['under5_share']:>7.3%}  "
            f"FY2029={money(row['fair_start_fy2029_134_9m'])}"
        )

    print()
    print("IMPORTANT")
    print("-" * 80)
    print(
        "ACS under-5 population is used as a relative geographic "
        "allocation proxy only."
    )
    print(
        "It does not represent Fair Start eligibility, childcare "
        "utilization, or future enrollment."
    )
    print(
        "FY2029 and FY2030 Fair Start amounts use the illustrative "
        "same-FY-equivalent convention adopted for this model."
    )
    print(
        "They do not represent literal statutory cash-transfer timing."
    )

    print()
    print("OUTPUT")
    print("-" * 80)
    print(OUTPUT_FILE)


def main():
    rows = load_source()

    statewide_under5 = build_allocation(rows)

    validate(
        rows,
        statewide_under5,
    )

    rows.sort(
        key=lambda row: row["legislative_district"]
    )

    write_csv(rows)

    print_report(
        rows,
        statewide_under5,
    )


if __name__ == "__main__":
    main()