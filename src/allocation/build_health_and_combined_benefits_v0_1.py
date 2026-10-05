from pathlib import Path
import csv


MEDICAID_INPUT = Path(
    "data/raw/census/acs2024_wa_ld_medicaid.csv"
)

EXISTING_INPUT = Path(
    "data/processed/model/illustrative_benefit_components_v0_1.csv"
)

OUTPUT_DIR = Path("data/processed/model")

HEALTH_OUTPUT = (
    OUTPUT_DIR / "health_ld_allocation_v0_1.csv"
)

COMBINED_OUTPUT = (
    OUTPUT_DIR / "illustrative_benefit_components_v0_2.csv"
)


EXPECTED_LDS = 49
MEDICAID_CONTROL = 1_573_853

HEALTH_LOW_POOL = 500_000_000
HEALTH_CENTRAL_POOL = 750_000_000
HEALTH_HIGH_POOL = 1_000_000_000

WFTC_CENTRAL_POOL = 250_000_000
K12_CENTRAL_POOL = 1_000_000_000

COMBINED_CENTRAL_POOL = (
    WFTC_CENTRAL_POOL
    + K12_CENTRAL_POOL
    + HEALTH_CENTRAL_POOL
)


def money(value):
    return round(value, 2)


def load_csv(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Input not found: {path}"
        )

    with path.open(
        newline="",
        encoding="utf-8",
    ) as f:

        reader = csv.DictReader(f)
        rows = list(reader)

    return rows


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    medicaid_rows = load_csv(
        MEDICAID_INPUT
    )

    existing_rows = load_csv(
        EXISTING_INPUT
    )

    # ------------------------------------------------------------
    # Validate row counts.
    # ------------------------------------------------------------

    if len(medicaid_rows) != EXPECTED_LDS:
        raise RuntimeError(
            f"Expected {EXPECTED_LDS} Medicaid rows; "
            f"found {len(medicaid_rows)}."
        )

    if len(existing_rows) != EXPECTED_LDS:
        raise RuntimeError(
            f"Expected {EXPECTED_LDS} existing model rows; "
            f"found {len(existing_rows)}."
        )

    # ------------------------------------------------------------
    # Index Medicaid geography.
    # ------------------------------------------------------------

    medicaid_by_ld = {}

    for row in medicaid_rows:

        ld = int(
            row["legislative_district"]
        )

        estimate = int(
            row[
                "medicaid_means_tested_public_coverage_estimate"
            ]
        )

        share = float(
            row["medicaid_ld_share"]
        )

        if ld in medicaid_by_ld:
            raise RuntimeError(
                f"Duplicate Medicaid LD {ld}."
            )

        medicaid_by_ld[ld] = {
            "estimate": estimate,
            "share": share,
        }

    # ------------------------------------------------------------
    # Index existing WFTC + K-12 model.
    # ------------------------------------------------------------

    existing_by_ld = {}

    for row in existing_rows:

        ld = int(
            row["legislative_district"]
        )

        if ld in existing_by_ld:
            raise RuntimeError(
                f"Duplicate existing-model LD {ld}."
            )

        existing_by_ld[ld] = row

    expected_lds = set(
        range(1, 50)
    )

    if set(medicaid_by_ld) != expected_lds:
        raise RuntimeError(
            "Medicaid districts are not exactly 1-49."
        )

    if set(existing_by_ld) != expected_lds:
        raise RuntimeError(
            "Existing-model districts are not exactly 1-49."
        )

    # ------------------------------------------------------------
    # Validate statewide Medicaid control.
    # ------------------------------------------------------------

    observed_medicaid_control = sum(
        item["estimate"]
        for item in medicaid_by_ld.values()
    )

    if observed_medicaid_control != MEDICAID_CONTROL:
        raise RuntimeError(
            "Medicaid statewide control mismatch. "
            f"Expected {MEDICAID_CONTROL:,}; "
            f"found {observed_medicaid_control:,}."
        )

    # ------------------------------------------------------------
    # Build health allocation.
    # ------------------------------------------------------------

    equal_health_low = (
        HEALTH_LOW_POOL / EXPECTED_LDS
    )

    equal_health_central = (
        HEALTH_CENTRAL_POOL / EXPECTED_LDS
    )

    equal_health_high = (
        HEALTH_HIGH_POOL / EXPECTED_LDS
    )

    health_rows = []

    for ld in range(1, 50):

        item = medicaid_by_ld[ld]

        share = item["share"]

        low = (
            HEALTH_LOW_POOL * share
        )

        central = (
            HEALTH_CENTRAL_POOL * share
        )

        high = (
            HEALTH_HIGH_POOL * share
        )

        health_rows.append(
            {
                "legislative_district": ld,

                "medicaid_acs_estimate":
                    item["estimate"],

                "medicaid_share":
                    share,

                "health_low_500m":
                    money(low),

                "health_central_750m":
                    money(central),

                "health_high_1b":
                    money(high),

                "equal_health_low_500m":
                    money(equal_health_low),

                "equal_health_central_750m":
                    money(equal_health_central),

                "equal_health_high_1b":
                    money(equal_health_high),

                "health_central_difference_from_equal":
                    money(
                        central
                        - equal_health_central
                    ),

                "health_central_ratio_to_equal":
                    (
                        central
                        / equal_health_central
                    ),
            }
        )

    # ------------------------------------------------------------
    # Write standalone health model.
    # ------------------------------------------------------------

    with HEALTH_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(
                health_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            health_rows
        )

    # ------------------------------------------------------------
    # Build three-component central model.
    # ------------------------------------------------------------

    health_by_ld = {
        row["legislative_district"]: row
        for row in health_rows
    }

    equal_combined = (
        COMBINED_CENTRAL_POOL
        / EXPECTED_LDS
    )

    combined_rows = []

    for ld in range(1, 50):

        old = existing_by_ld[ld]
        health = health_by_ld[ld]

        wftc = float(
            old["wftc_central_250m"]
        )

        k12 = float(
            old["k12_central_1b"]
        )

        health_central = float(
            health[
                "health_central_750m"
            ]
        )

        combined = (
            wftc
            + k12
            + health_central
        )

        combined_share = (
            combined
            / COMBINED_CENTRAL_POOL
        )

        difference = (
            combined
            - equal_combined
        )

        combined_rows.append(
            {
                "legislative_district":
                    ld,

                "wftc_estimated_approvals_v02":
                    old[
                        "wftc_estimated_approvals_v02"
                    ],

                "wftc_central_250m":
                    money(wftc),

                "k12_public_enrollment":
                    old[
                        "k12_public_enrollment"
                    ],

                "k12_central_1b":
                    money(k12),

                "medicaid_acs_estimate":
                    health[
                        "medicaid_acs_estimate"
                    ],

                "health_central_750m":
                    money(
                        health_central
                    ),

                "combined_wftc_k12_health":
                    money(combined),

                "combined_share":
                    combined_share,

                "equal_combined_2b":
                    money(
                        equal_combined
                    ),

                "difference_from_equal":
                    money(
                        difference
                    ),

                "ratio_to_equal":
                    (
                        combined
                        / equal_combined
                    ),
            }
        )

    # ------------------------------------------------------------
    # Write combined model.
    # ------------------------------------------------------------

    with COMBINED_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(
                combined_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            combined_rows
        )

    # ------------------------------------------------------------
    # Validation.
    # ------------------------------------------------------------

    medicaid_share_sum = sum(
        row["medicaid_share"]
        for row in health_rows
    )

    health_low_total = sum(
        row["health_low_500m"]
        for row in health_rows
    )

    health_central_total = sum(
        row["health_central_750m"]
        for row in health_rows
    )

    health_high_total = sum(
        row["health_high_1b"]
        for row in health_rows
    )

    wftc_total = sum(
        row["wftc_central_250m"]
        for row in combined_rows
    )

    k12_total = sum(
        row["k12_central_1b"]
        for row in combined_rows
    )

    combined_health_total = sum(
        row["health_central_750m"]
        for row in combined_rows
    )

    combined_total = sum(
        row["combined_wftc_k12_health"]
        for row in combined_rows
    )

    combined_share_sum = sum(
        row["combined_share"]
        for row in combined_rows
    )

    difference_total = sum(
        row["difference_from_equal"]
        for row in combined_rows
    )

    print(
        "HEALTH + THREE-COMPONENT "
        "ILLUSTRATIVE BENEFIT MODEL v0.1"
    )
    print("=" * 80)

    print()
    print("HEALTH MODEL")
    print("-" * 80)

    print(
        "Geography : 2024 ACS 5-Year C27007 "
        "Medicaid/means-tested public coverage"
    )

    print(
        "Use       : relative geographic "
        "allocation weights only"
    )

    print(
        "Low pool  : $500,000,000"
    )

    print(
        "Central   : $750,000,000"
    )

    print(
        "High pool : $1,000,000,000"
    )

    print()
    print("HEALTH CONTROLS")
    print("-" * 80)

    print(
        f"Legislative districts       : "
        f"{len(health_rows)}"
    )

    print(
        f"ACS Medicaid control        : "
        f"{observed_medicaid_control:,}"
    )

    print(
        f"Medicaid share sum          : "
        f"{medicaid_share_sum:.12f}"
    )

    print(
        f"Low allocation total        : "
        f"${health_low_total:,.2f}"
    )

    print(
        f"Central allocation total    : "
        f"${health_central_total:,.2f}"
    )

    print(
        f"High allocation total       : "
        f"${health_high_total:,.2f}"
    )

    print()
    print(
        "THREE-COMPONENT CENTRAL MODEL"
    )
    print("-" * 80)

    print(
        f"WFTC                       : "
        f"${wftc_total:,.2f}"
    )

    print(
        f"K-12                       : "
        f"${k12_total:,.2f}"
    )

    print(
        f"Health                     : "
        f"${combined_health_total:,.2f}"
    )

    print(
        f"Combined                   : "
        f"${combined_total:,.2f}"
    )

    print(
        f"Combined share sum         : "
        f"{combined_share_sum:.12f}"
    )

    print(
        f"Difference-from-equal sum  : "
        f"${difference_total:,.2f}"
    )

    print()
    print(
        "LARGEST ABOVE EQUAL SHARE"
    )
    print("-" * 80)

    for row in sorted(
        combined_rows,
        key=lambda x:
            x["difference_from_equal"],
        reverse=True,
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"WFTC=${row['wftc_central_250m']:>11,.2f}  "
            f"K12=${row['k12_central_1b']:>12,.2f}  "
            f"Health=${row['health_central_750m']:>12,.2f}  "
            f"Total=${row['combined_wftc_k12_health']:>12,.2f}  "
            f"vs equal=${row['difference_from_equal']:>+12,.2f}"
        )

    print()
    print(
        "LARGEST BELOW EQUAL SHARE"
    )
    print("-" * 80)

    for row in sorted(
        combined_rows,
        key=lambda x:
            x["difference_from_equal"],
    )[:10]:

        print(
            f"LD {row['legislative_district']:>2}: "
            f"WFTC=${row['wftc_central_250m']:>11,.2f}  "
            f"K12=${row['k12_central_1b']:>12,.2f}  "
            f"Health=${row['health_central_750m']:>12,.2f}  "
            f"Total=${row['combined_wftc_k12_health']:>12,.2f}  "
            f"vs equal=${row['difference_from_equal']:>+12,.2f}"
        )

    print()
    print("OUTPUT")
    print("-" * 80)

    print(HEALTH_OUTPUT)
    print(COMBINED_OUTPUT)


if __name__ == "__main__":
    main()